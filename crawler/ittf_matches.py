#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITTF / WTT 赛事对阵记录爬虫
==========================
爬取国际乒联（ITTF）/ 世界乒乓球职业大联盟（WTT）官方比赛结果接口，
抓取「2024 年 8 月之后」各赛事的对阵记录（双方选手、协会、每局比分、
总比分、胜者、轮次、日期、场馆等），并写入 data/matches.json 供前端展示。

数据来源（均由前端 SPA 调用的公开后端接口反推得到）：
  1) 赛事列表：
     https://wtt-website-api-prod-3-frontdoor-bddnb2haduafdze9.a01.azurefd.net/api/cms/GetAllEventsOnlyWithEventName
  2) 单站官方对阵结果（含比赛卡片）：
     https://wtt-website-api-vm-frontdoor-hhaec5epbhdyfugz.a01.azurefd.net/liveeventsapi/api/cms/GetOfficialResult?EventId={id}&include_match_card=true

输出字段（data/matches.json）
  meta   : 抓取元信息（来源、时间范围、统计）
  events : 赛事列表（仅元信息 + 场次计数）
  matches: 扁平化的对阵记录，每条含所属赛事、选手、比分、胜负、轮次、日期等

用法
----
  python ittf_matches.py                      # 抓取 2024-08-01 至今天的全部赛事
  python ittf_matches.py --since 2025-01-01   # 指定起始日期
  python ittf_matches.py --until 2025-12-31   # 指定结束日期
  python ittf_matches.py --exclude "Youth|Feeder"   # 排除某些赛事（正则，按赛事名）
  python ittf_matches.py --include "Smash|Champions" # 只保留匹配赛事（正则）
  python ittf_matches.py --workers 10          # 并发数
  python ittf_matches.py --out ../data/matches.json
"""

import os
import sys
import re
import json
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
import urllib3

urllib3.disable_warnings()

# ---- 接口地址（注意：这些 frontdoor 域名哈希可能随官方调整而变动，若抓取失败请更新）----
EVENT_LIST_API = (
    "https://wtt-website-api-prod-3-frontdoor-bddnb2haduafdze9.a01.azurefd.net/api"
    "/cms/GetAllEventsOnlyWithEventName"
)
RESULT_API = (
    "https://wtt-website-api-vm-frontdoor-hhaec5epbhdyfugz.a01.azurefd.net"
    "/liveeventsapi/api/cms/GetOfficialResult"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.worldtabletennis.com/",
    "Origin": "https://www.worldtabletennis.com",
    "Accept": "application/json, text/plain, */*",
}

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# 复用排名爬虫里的中文名映射（按 IttfId 键控），没有则回退英文原名
try:
    from ittf_ranking import NAME_CN_MAP  # 同目录
except Exception:  # 兜底：为空也不影响英文展示
    NAME_CN_MAP = {}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    return s


# ---------------------------------------------------------------------------
# 赛事列表
# ---------------------------------------------------------------------------
def fetch_event_list(session):
    """返回原始赛事列表（dict 列表）。"""
    resp = session.get(EVENT_LIST_API, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError("赛事列表接口返回结构异常")
    return data


def parse_event_dates(event):
    """
    从赛事名（'...(DD Mon YYYY - DD Mon YYYY)'）或 startDateTime 推断起止日期。
    返回 (start: date|None, end: date|None)。
    """
    name = event.get("eventName") or ""
    start = end = None
    m = re.search(
        r"\((\d{1,2}) ([A-Z][a-z]{2}) (\d{4}) - (\d{1,2}) ([A-Z][a-z]{2}) (\d{4})\)",
        name,
    )
    if m:
        try:
            start = datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
            end = datetime.date(int(m.group(6)), MONTHS[m.group(5)], int(m.group(4)))
        except Exception:
            start = end = None
    sdt = event.get("startDateTime")
    if sdt:
        try:
            d = datetime.datetime.fromisoformat(sdt.replace("Z", "+00:00")).date()
            if start is None:
                start = d
            if end is None:
                end = d
        except Exception:
            pass
    edt = event.get("endDateTime")
    if edt and end is None:
        try:
            end = datetime.datetime.fromisoformat(edt.replace("Z", "+00:00")).date()
        except Exception:
            pass
    return start, end


def filter_events(events, since, until, include_re, exclude_re):
    out = []
    for e in events:
        start, end = parse_event_dates(e)
        if start is None and end is None:
            continue
        # 赛事与 [since, until] 区间有重叠即保留
        ev_end = end or start
        ev_start = start or end
        if ev_end < since or ev_start > until:
            continue
        name = e.get("eventName") or ""
        if exclude_re and exclude_re.search(name):
            continue
        if include_re and not include_re.search(name):
            continue
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# 单站对阵结果
# ---------------------------------------------------------------------------
def fetch_event_matches(session, event_id):
    """返回某赛事全部官方对阵（含 match_card），失败返回空列表。"""
    try:
        resp = session.get(
            RESULT_API,
            params={"EventId": event_id, "include_match_card": "true"},
            timeout=40,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def title_case_name(raw):
    """把 ITTF 的 'CALDERANO Hugo' 转成 'Hugo Calderano'。"""
    if not raw:
        return ""
    parts = raw.strip().split()
    if not parts:
        return ""
    # 格式稳定为「姓(全大写) 名」，重排为「名 姓」并做标题化
    surname = parts[0].title()
    given = " ".join(parts[1:]).title()
    return (given + " " + surname).strip() if given else surname


def parse_scores(scores_str):
    """'7,9,11,8,9,0,0' -> [7,9,11,8,9,0,0]，忽略空白与空段。"""
    if not scores_str:
        return []
    out = []
    for s in scores_str.split(","):
        s = s.strip()
        if s.isdigit():
            out.append(int(s))
    return out


def parse_overall(overall_str):
    """'1-4' -> (1, 4)；异常返回 (0,0)。"""
    if not overall_str:
        return 0, 0
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)\s*", overall_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def parse_round(desc):
    """'Men's Singles - Final - Match 1' -> 'Final'。"""
    if not desc:
        return ""
    segs = [s.strip() for s in desc.split("-")]
    # 形如 [子项, 轮次, Match N] 或 [子项, 轮次]
    if len(segs) >= 2:
        candidate = segs[1]
        if candidate.lower().startswith("match"):
            return segs[0] if len(segs) > 2 else ""
        return candidate
    return ""


def normalize_match(raw, event_name):
    """把一条原始对阵（含 match_card）规整为统一结构。"""
    mc = raw.get("match_card") or {}
    competitiors = mc.get("competitiors") or []
    if len(competitiors) < 2:
        return None

    def comp_info(c):
        players = c.get("players") or []
        if players:
            # 单打 1 人；双打 2 人
            names = [p.get("playerName", "") for p in players]
            ids = [str(p.get("playerId", "")) for p in players]
            orgs = [p.get("playerOrgCode", "") for p in players]
            name_en = " / ".join(title_case_name(n) for n in names if n)
            org = next((o for o in orgs if o), "")
            # 中文名：取首位选手（单打即本人）
            cn = NAME_CN_MAP.get(ids[0], "") if ids else ""
            return {
                "id": ids[0] if ids else str(c.get("competitiorId", "")),
                "name_en": name_en,
                "name_cn": cn,
                "org": org or c.get("competitiorOrg", ""),
            }
        # 兜底：直接取 competitior 字段
        cid = str(c.get("competitiorId", ""))
        return {
            "id": cid,
            "name_en": title_case_name(c.get("competitiorName", "")),
            "name_cn": NAME_CN_MAP.get(cid, ""),
            "org": c.get("competitiorOrg", ""),
        }

    a = comp_info(competitiors[0])  # H
    b = comp_info(competitiors[1])  # A
    scores_a = parse_scores(competitiors[0].get("scores"))
    scores_b = parse_scores(competitiors[1].get("scores"))
    games_a, games_b = parse_overall(mc.get("overallScores") or raw.get("overallScores"))

    # 判定胜者：总局数多者胜
    if games_a > games_b:
        winner_side = "a"
        winner = a
    elif games_b > games_a:
        winner_side = "b"
        winner = b
    else:
        winner_side = ""
        winner = None

    # 日期
    date_str = ""
    mdt = mc.get("matchDateTime") or {}
    sl = mdt.get("startDateLocal") or raw.get("startDateLocal") or ""
    # 形如 09/13/2026 19:30:00 或 2026-09-13T19:30:00
    m1 = re.match(r"(\d{2})/(\d{2})/(\d{4})[ T](\d{2}):(\d{2})", sl)
    m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", sl)
    if m1:
        date_str = f"{m1.group(3)}-{m1.group(1)}-{m1.group(2)} {m1.group(4)}:{m1.group(5)}"
    elif m2:
        date_str = f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)} {m2.group(4)}:{m2.group(5)}"

    return {
        "match_id": raw.get("id"),
        "event_id": raw.get("eventId") or (mc.get("eventId")),
        "event_name": event_name,
        "sub_event": mc.get("subEventName") or raw.get("subEventType") or "",
        "round": parse_round(mc.get("subEventDescription") or raw.get("subEventDescription")),
        "stage_desc": mc.get("subEventDescription") or "",
        "date": date_str,
        "venue": mc.get("venueName") or "",
        "table": mc.get("tableName") or "",
        "duration": mdt.get("duration") or "",
        "best_of": (mc.get("matchConfig") or {}).get("bestOfXGames"),
        "player_a": a,
        "player_b": b,
        "scores_a": scores_a,
        "scores_b": scores_b,
        "games_a": games_a,
        "games_b": games_b,
        "winner_side": winner_side,
        "winner_name": (winner.get("name_cn") or winner.get("name_en")) if winner else "",
        "status": mc.get("resultStatus") or raw.get("fullResults") or "",
    }


# ---------------------------------------------------------------------------
# 进度与写出
# ---------------------------------------------------------------------------
class Progress:
    """轻量进度条：TTY 下显示单行刷新条；非 TTY（后台/管道）写入日志文件。"""

    def __init__(self, total, log_path):
        self.total = total
        self.done = 0
        self.matches = 0
        self.log_path = log_path
        self.tty = sys.stderr.isatty()
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    def update(self, n_matches, label=""):
        self.done += 1
        self.matches += n_matches
        pct = (self.done / self.total * 100) if self.total else 100.0
        line = "[{}/{}] {:5.1f}%  matches={}  {}".format(
            self.done, self.total, pct, self.matches, (label or "")[:40])
        if self.tty:
            sys.stderr.write("\r" + line.ljust(90))
            sys.stderr.flush()
        else:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    f.flush()
            except Exception:
                pass

    def finish(self):
        if self.tty:
            sys.stderr.write("\n")


def save_payload(payload, path):
    """原子写出：先写 .tmp 再 rename，避免中途损坏；同时用于增量落盘。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="抓取 ITTF/WTT 赛事对阵记录")
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "matches.json")
    parser.add_argument("--out", default=default_out, help="输出 JSON 路径")
    parser.add_argument("--since", default="2024-08-01", help="起始日期 YYYY-MM-DD（含）")
    parser.add_argument("--until", default=datetime.date.today().strftime("%Y-%m-%d"), help="结束日期 YYYY-MM-DD（含）")
    parser.add_argument("--workers", type=int, default=8, help="并发抓取赛事数")
    parser.add_argument("--include", default="", help="只保留赛事名匹配此正则的赛事（空=全部）")
    parser.add_argument("--exclude", default="", help="排除赛事名匹配此正则的赛事（空=不排除）")
    parser.add_argument("--max-events", type=int, default=0, help="最多抓取赛事数（0=不限制）")
    args = parser.parse_args()

    since = datetime.date.fromisoformat(args.since)
    until = datetime.date.fromisoformat(args.until)
    include_re = re.compile(args.include, re.I) if args.include else None
    exclude_re = re.compile(args.exclude, re.I) if args.exclude else None

    session = get_session()

    print("[1/4] 获取赛事列表 ...")
    events = fetch_event_list(session)
    print("      共获取到 {} 个赛事".format(len(events)))

    print("[2/4] 过滤 2024-08 之后的赛事 ...")
    target = filter_events(events, since, until, include_re, exclude_re)
    if args.max_events:
        target = target[: args.max_events]
    print("      命中 {} 个赛事".format(len(target)))

    print("[3/4] 并发抓取各赛事对阵结果 ...")
    all_matches = []
    event_meta = []
    total = len(target)
    out_path = os.path.abspath(args.out)
    prog = Progress(total, os.path.join(os.path.dirname(out_path), "crawl_progress.log"))

    def worker(ev):
        eid = ev.get("eventId")
        raws = fetch_event_matches(session, eid)
        norm = []
        for r in raws:
            nm = normalize_match(r, ev.get("eventName", ""))
            if nm:
                norm.append(nm)
        return ev, norm

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = {ex.submit(worker, ev): ev for ev in target}
        for fut in as_completed(futures):
            ev, norm = fut.result()
            start, end = parse_event_dates(ev)
            event_meta.append({
                "event_id": ev.get("eventId"),
                "event_name": ev.get("eventName", ""),
                "city": ev.get("city") or "",
                "country": ev.get("countryCode") or "",
                "start_date": start.isoformat() if start else "",
                "end_date": end.isoformat() if end else "",
                "matches_count": len(norm),
            })
            all_matches.extend(norm)
            prog.update(len(norm), ev.get("eventName", ""))
            # 每 20 个赛事增量落盘到临时文件，防止中断丢全部数据
            if prog.done % 20 == 0:
                save_payload({
                    "meta": {
                        "title": "乒乓球赛事对阵记录（抓取中…）",
                        "source": "ITTF / WTT 官方比赛结果接口（GetOfficialResult）",
                        "generated_at": datetime.date.today().isoformat(),
                        "since": args.since, "until": args.until,
                        "events_count": len(event_meta),
                        "matches_count": len(all_matches),
                        "partial": True,
                    },
                    "events": event_meta, "matches": all_matches,
                }, out_path + ".tmp")

    prog.finish()
    # 赛事按结束日期倒序，便于前端展示近期赛事在前
    event_meta.sort(key=lambda e: (e["end_date"] or "0000-00-00"), reverse=True)

    print("[4/4] 写入 {} ...".format(out_path))
    payload = {
        "meta": {
            "title": "乒乓球赛事对阵记录",
            "source": "ITTF / WTT 官方比赛结果接口（GetOfficialResult）",
            "generated_at": datetime.date.today().isoformat(),
            "since": args.since,
            "until": args.until,
            "events_count": len(event_meta),
            "matches_count": len(all_matches),
            "note": "数据抓取自 ITTF/WTT 官方公开接口，覆盖 2024-08 之后各赛事的单打/双打/混双对阵。",
        },
        "events": event_meta,
        "matches": all_matches,
    }
    save_payload(payload, out_path)
    print("完成：{} 个赛事，{} 场对阵，写入 {}".format(
        len(event_meta), len(all_matches), out_path))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("抓取失败：{}".format(e), file=sys.stderr)
        sys.exit(1)
