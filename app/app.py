"""
乒乓球资讯站点 · 后端服务
--------------------------------
提供以下页面（路由）：
  /               世界排名（首页）
  /rankings       世界排名
  /matches        对战记录
  /events         赛事安排（建设中）

数据来源：
  data/rankings.json  ITTF 官方世界排名（crawler/ittf_ranking.py 产出）
  data/matches.json   ITTF/WTT 各赛事对阵记录（crawler/ittf_matches.py 产出）
"""

import os
import sys
import json

from flask import Flask, render_template, send_file, abort, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 允许从 crawler/ 目录导入 COUNTRY_MAP（与排名爬虫共用协会映射）
CRAWLER_DIR = os.path.join(BASE_DIR, "..", "crawler")
if CRAWLER_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(CRAWLER_DIR))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
RANKINGS_FILE = os.path.join(DATA_DIR, "rankings.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


# 协会代码 -> (中文名, 旗帜 iso2)，用于前端旗帜与中文协会名展示
try:
    from ittf_ranking import COUNTRY_MAP  # crawler/ittf_ranking.py
except Exception:
    COUNTRY_MAP = {}

ORG_MAP = {
    code: {"cn": cn, "iso2": iso2}
    for code, (cn, iso2) in COUNTRY_MAP.items()
}


@app.route("/")
@app.route("/rankings")
def rankings():
    data = load_json(RANKINGS_FILE, {"meta": {}, "categories": {}})
    return render_template("world_ranking.html", data=data, active="rankings")


@app.route("/matches")
def matches():
    meta = load_json(MATCHES_FILE, {"meta": {}}).get("meta", {})
    return render_template(
        "matches.html",
        meta=meta,
        org_map=ORG_MAP,
        active="matches",
    )


@app.route("/api/matches")
def api_matches():
    """以流式方式返回对阵记录 JSON，避免大文件占用内存。"""
    if not os.path.exists(MATCHES_FILE):
        abort(404)
    return send_file(
        os.path.abspath(MATCHES_FILE),
        mimetype="application/json",
        as_attachment=False,
        conditional=True,
    )


# ---------------------------------------------------------------------------
# 赛事日历 / 每日赛程
# ---------------------------------------------------------------------------
_MATCHES_CACHE = None


def get_all_matches():
    global _MATCHES_CACHE
    if _MATCHES_CACHE is None:
        _MATCHES_CACHE = load_json(MATCHES_FILE, {"matches": [], "events": []})
    return _MATCHES_CACHE


def build_schedule(matches):
    """把对阵列表按比赛日(YYYY-MM-DD)分组并排序。"""
    days = {}
    for m in matches:
        d = (m.get("date") or "")[:10]
        if not d:
            d = "未排期"
        days.setdefault(d, []).append(m)
    out = []
    for d in sorted(days.keys()):
        ms = sorted(days[d], key=lambda x: (x.get("date") or ""))
        out.append({"date": d, "matches": ms})
    return out


@app.route("/api/events")
def api_events():
    if not os.path.exists(EVENTS_FILE):
        abort(404)
    return send_file(
        os.path.abspath(EVENTS_FILE),
        mimetype="application/json",
        as_attachment=False,
        conditional=True,
    )


@app.route("/events")
def events():
    meta = load_json(EVENTS_FILE, {}).get("meta", {})
    return render_template("events.html", meta=meta, org_map=ORG_MAP, active="events")


@app.route("/schedule")
def schedule():
    meta = load_json(EVENTS_FILE, {}).get("meta", {})
    return render_template("schedule.html", meta=meta, org_map=ORG_MAP, active="schedule")


_SCHEDULE_CACHE = {}


@app.route("/api/schedule")
def api_schedule():
    """返回某赛事的每日赛程；优先用本地 matches.json，缺则实时抓取官方接口。"""
    event_id = request.args.get("event_id", "").strip()
    if not event_id:
        return jsonify({"error": "缺少 event_id"}), 400

    if event_id in _SCHEDULE_CACHE:
        return jsonify(_SCHEDULE_CACHE[event_id])

    # 1) 先查本地已抓取的 matches.json
    data = get_all_matches()
    ms = [m for m in data.get("matches", []) if str(m.get("event_id")) == event_id]

    source = "local"
    if not ms:
        # 2) 实时抓取官方 GetOfficialResult（针对未爬取到的赛事，如未来赛事）
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "ittf_matches", os.path.join(CRAWLER_DIR, "ittf_matches.py"))
            im = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(im)
            session = im.get_session()
            raws = im.fetch_event_matches(session, event_id)
            ms = []
            for r in raws:
                nm = im.normalize_match(r, "")
                if nm:
                    ms.append(nm)
            source = "live"
        except Exception as e:
            ms = []
            source = "error:" + repr(e)[:120]

    # 赛事元信息
    ev_meta = next((e for e in data.get("events", [])
                    if str(e.get("event_id")) == event_id), None)
    if ev_meta is None:
        # 从 events.json 找
        evj = load_json(EVENTS_FILE, {"events": []})
        ev_meta = next((e for e in evj.get("events", [])
                        if str(e.get("event_id")) == event_id), {})

    payload = {
        "event_id": event_id,
        "event_name": ev_meta.get("name") or ev_meta.get("event_name") or "",
        "event_name_cn": ev_meta.get("name_cn") or "",
        "start_date": ev_meta.get("start_date") or "",
        "end_date": ev_meta.get("end_date") or "",
        "city": ev_meta.get("city") or "",
        "country_cn": ev_meta.get("country_cn") or "",
        "tier_cn": ev_meta.get("tier_cn") or "",
        "disciplines": ev_meta.get("disciplines") or [],
        "source": source,
        "days": build_schedule(ms),
        "matches_count": len(ms),
    }
    _SCHEDULE_CACHE[event_id] = payload
    return jsonify(payload)


if __name__ == "__main__":
    # host=0.0.0.0 便于在局域网/容器中访问；port 可自定义
    app.run(host="0.0.0.0", port=5000, debug=True)
