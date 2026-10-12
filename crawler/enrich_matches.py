#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给 matches.json 补充中文名
=========================
用 name_maps 为 matches.json 中的「选手」与「赛事」补上中文名：
  - 选手：player_a/b 的 name_cn（优先保留已有映射，否则查表）
  - 赛事：每条对阵的 event_name_cn；以及 events[] 里的 name_cn

纯本地转换，不访问网络；幂等（重复运行安全）。

用法
----
  python enrich_matches.py                  # 处理 ../data/matches.json
  python enrich_matches.py --out out.json   # 指定输出
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from name_maps import player_cn, event_cn

NON_CN = set()  # 调试用：记录未命中且高频的英文名（可选）


def enrich(matches_path):
    if not os.path.exists(matches_path):
        print("文件不存在：", matches_path)
        return
    data = json.load(open(matches_path, encoding="utf-8"))
    n_player = 0
    n_event = 0

    for m in data.get("matches", []):
        for side in ("player_a", "player_b"):
            p = m.get(side) or {}
            en = p.get("name_en", "")
            new_cn = player_cn(en, p.get("name_cn", ""))
            if new_cn and not p.get("name_cn"):
                p["name_cn"] = new_cn
                n_player += 1
        # 赛事中文名
        ev = m.get("event_name", "")
        if ev and not m.get("event_name_cn"):
            m["event_name_cn"] = event_cn(ev)
            if m.get("event_name_cn"):
                n_event += 1
        # 用补全后的中文名重算胜者显示名
        if m.get("winner_side") in ("a", "b"):
            wp = m.get("player_" + m["winner_side"]) or {}
            m["winner_name"] = wp.get("name_cn") or wp.get("name_en") or m.get("winner_name", "")

    # events[] 也补中文名
    for e in data.get("events", []):
        en = e.get("event_name", "")
        if en and not e.get("name_cn"):
            e["name_cn"] = event_cn(en)
            if e.get("name_cn"):
                n_event += 1

    out_path = matches_path
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("完成：补充选手中文名 {} 处，赛事中文名 {} 处 -> {}".format(
        n_player, n_event, out_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="给 matches.json 补中文名")
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "matches.json")
    parser.add_argument("--out", default=default, help="matches.json 路径")
    args = parser.parse_args()
    enrich(os.path.abspath(args.out))
