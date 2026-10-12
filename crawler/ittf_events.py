#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛事日历数据生成
================
拉取 ITTF/WTT 官方赛事清单，按中文映射模块分级、命名、判定状态（已结束/进行中/即将开始），
输出 data/events.json，供「赛事日历（全年重要赛事）」页面与「每日赛程」页面使用。

用法
----
  python ittf_events.py                 # 抓取并写入 ../data/events.json
  python ittf_events.py --out out.json
"""

import os
import sys
import re
import json
import argparse
import datetime
import time

import requests
from requests.adapters import HTTPAdapter

# 复用中文映射与协会映射
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from name_maps import classify_event, event_cn, CITY_CN, host_info
try:
    from ittf_ranking import COUNTRY_MAP
except Exception:
    COUNTRY_MAP = {}

EVENT_LIST_API = (
    "https://wtt-website-api-prod-3-frontdoor-bddnb2haduafdze9.a01.azurefd.net"
    "/api/cms/GetAllEventsOnlyWithEventName"
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


def fetch_event_list(session, retries=6):
    for i in range(retries):
        try:
            resp = session.get(EVENT_LIST_API, timeout=40)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
            else:
                raise
    raise RuntimeError("赛事清单接口获取失败")


def parse_dates(event):
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
    for fld, setter in (("startDateTime", "s"), ("endDateTime", "e")):
        v = event.get(fld)
        if v:
            try:
                d = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).date()
                if setter == "s" and start is None:
                    start = d
                if setter == "e" and end is None:
                    end = d
            except Exception:
                pass
    return start, end


def year_of(start, end, name):
    for d in (start, end):
        if d:
            return d.year
    m = re.search(r"(19|20)\d{2}", name or "")
    return int(m.group(0)) if m else None


def strip_sponsor(name):
    n = re.sub(r"Presented by.*$", "", name or "", flags=re.I).strip()
    n = re.sub(r"\s*\([^)]*\)", "", n).strip()
    return n


def main():
    parser = argparse.ArgumentParser(description="生成赛事日历数据")
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "events.json")
    parser.add_argument("--out", default=default_out)
    parser.add_argument("--since", default="2024-01-01", help="仅保留此日期之后的赛事（含）")
    args = parser.parse_args()

    since = datetime.date.fromisoformat(args.since)
    today = datetime.date.today()
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=5))
    session.headers.update(HEADERS)

    print("[1/3] 获取赛事清单 ...")
    raw = fetch_event_list(session)
    print("      共 {} 个赛事".format(len(raw)))

    # 从 matches.json 获取每个赛事的项目(disciplines)与场次计数（若有）
    matches_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "matches.json")
    disc_map = {}
    cnt_map = {}
    if os.path.exists(matches_path):
        try:
            md = json.load(open(matches_path, encoding="utf-8"))
            for e in md.get("events", []):
                disc_map[str(e.get("event_id"))] = []
                cnt_map[str(e.get("event_id"))] = e.get("matches_count", 0)
            for m in md.get("matches", []):
                eid = str(m.get("event_id"))
                if eid not in disc_map:
                    disc_map[eid] = []
                    cnt_map[eid] = 0
                sub = m.get("sub_event")
                if sub and sub not in disc_map[eid]:
                    disc_map[eid].append(sub)
        except Exception:
            pass

    print("[2/3] 解析、分级、中文命名 ...")
    events = []
    for e in raw:
        start, end = parse_dates(e)
        yr = year_of(start, end, e.get("eventName"))
        if start is None and end is None:
            continue
        if end < since and (yr is None or yr < since.year):
            continue
        name_raw = e.get("eventName") or ""
        name_en = strip_sponsor(name_raw)
        key, tier_cn, level, is_important = classify_event(name_raw)
        name_cn = event_cn(name_raw)
        cc = e.get("countryCode") or ""
        # 东道主城市 / 国家 / 旗帜代码：优先从英文名推导（接口未提供）
        host, country_cn2, country_code = host_info(name_raw)
        country_cn, _ = COUNTRY_MAP.get(cc, (country_cn2 or e.get("countryName") or cc, ""))
        eid = str(e.get("eventId"))
        if start <= today <= end:
            status = "ongoing"
        elif end < today:
            status = "past"
        else:
            status = "upcoming"
        events.append({
            "event_id": eid,
            "name": name_en,
            "name_cn": name_cn,
            "name_raw": name_raw,
            "tier_key": key,
            "tier_cn": tier_cn,
            "level": level,
            "is_important": is_important,
            "start_date": start.isoformat() if start else "",
            "end_date": end.isoformat() if end else "",
            "year": yr,
            "city": host,
            "country_code": country_code or cc,
            "country_cn": country_cn or e.get("countryName") or "",
            "venue": e.get("venueName") or "",
            "logo": e.get("logo") or "",
            "background": e.get("backgroundImage") or "",
            "disciplines": disc_map.get(eid, []),
            "matches_count": cnt_map.get(eid, 0),
            "status": status,
        })

    # 按开始日期倒序
    events.sort(key=lambda x: (x["start_date"] or "0000-00-00"), reverse=True)
    print("      输出 {} 个赛事".format(len(events)))

    print("[3/3] 写入 {} ...".format(args.out))
    payload = {
        "meta": {
            "title": "乒乓球赛事日历",
            "source": "ITTF / WTT 官方赛事清单接口（GetAllEventsOnlyWithEventName）",
            "generated_at": today.isoformat(),
            "today": today.isoformat(),
            "note": "赛事分级与中文名由本地映射生成（接口未提供分级字段）；状态以生成日为准。",
        },
        "events": events,
    }
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("完成：{} 个赛事 -> {}".format(len(events), out_path))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("生成失败：{}".format(e), file=sys.stderr)
        sys.exit(1)
