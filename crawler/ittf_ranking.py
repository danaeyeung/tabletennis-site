#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITTF / WTT 世界排名爬虫
========================
把国际乒联（ITTF）官方世界排名抓取到 data/rankings.json，供前端页面使用。

数据来源说明
------------
  ittf.com 主站有 Cloudflare 反爬，直接用 requests 抓会被 403 拦掉。
  但排名数据本身由 ITTF / WTT 后端（worldtabletennis.com 的 Azure frontdoor）
  以 JSON 形式公开发布，本脚本抓取该接口：
      https://wtt-web-frontdoor-...azurefd.net/ranking/SEN_SINGLES.json
  该文件包含全部成年组单打（男单 MS / 女单 WS）的当前排名。

输出字段（与 data/rankings.json 保持一致）
  rank / name_cn / name_en / code / assoc_cn / iso2 / points / move

用法
----
  python ittf_ranking.py                # 抓取并写入 ../data/rankings.json
  python ittf_ranking.py --out out.json # 指定输出路径
"""

import os
import sys
import json
import argparse
import datetime

import requests

# 排名数据接口（注意：子域名里的哈希可能随官方调整而变动，若抓取失败请更新此 URL）
FRONTDOOR_URL = (
    "https://wtt-web-frontdoor-withoutcache-cqakg0andqf5hchn.a01.azurefd.net"
    "/ranking/SEN_SINGLES.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.worldtabletennis.com",
    "Origin": "https://www.worldtabletennis.com",
    "Accept": "application/json, text/plain, */*",
}

# 每个性别保留多少名（ITTF 单文件含前 100 名，设为 100 即完整榜单）
TOP_N = 100

# 协会代码 -> (中文名, 旗帜代码 iso2)。中国港澳台按规范显示为“中国XX”，不单独使用地区旗帜。
COUNTRY_MAP = {
    # 协会代码 -> (中文名, 旗帜代码 iso2)。旗帜代码用于 flag-icons 的 SVG 文件名。
    # 中国港澳台按规范显示为“中国XX”，不单独使用地区旗帜（iso2 留空）。
    "CHN": ("中国", "cn"),
    "JPN": ("日本", "jp"),
    "KOR": ("韩国", "kr"),
    "GER": ("德国", "de"),
    "FRA": ("法国", "fr"),
    "SWE": ("瑞典", "se"),
    "BRA": ("巴西", "br"),
    "TPE": ("中国台北", ""),
    "SLO": ("斯洛文尼亚", "si"),
    "DEN": ("丹麦", "dk"),
    "RUS": ("俄罗斯", "ru"),
    "MAC": ("中国澳门", ""),
    "PUR": ("波多黎各", "pr"),
    "ENG": ("英格兰", "gb-eng"),
    "GBR": ("英国", "gb"),
    "ESP": ("西班牙", "es"),
    "POR": ("葡萄牙", "pt"),
    "CRO": ("克罗地亚", "hr"),
    "EGY": ("埃及", "eg"),
    "IND": ("印度", "in"),
    "USA": ("美国", "us"),
    "HKG": ("中国香港", ""),
    "AUT": ("奥地利", "at"),
    "ITA": ("意大利", "it"),
    "UKR": ("乌克兰", "ua"),
    "POL": ("波兰", "pl"),
    "ROU": ("罗马尼亚", "ro"),
    "CAN": ("加拿大", "ca"),
    "AUS": ("澳大利亚", "au"),
    "NZL": ("新西兰", "nz"),
    "SGP": ("新加坡", "sg"),
    "THA": ("泰国", "th"),
    "VIE": ("越南", "vn"),
    "IRI": ("伊朗", "ir"),
    "KAZ": ("哈萨克斯坦", "kz"),
    "CZE": ("捷克", "cz"),
    "NED": ("荷兰", "nl"),
    "BEL": ("比利时", "be"),
    "TUR": ("土耳其", "tr"),
    "MEX": ("墨西哥", "mx"),
    "ARG": ("阿根廷", "ar"),
    "CHI": ("智利", "cl"),
    "TUN": ("突尼斯", "tn"),
    "NGR": ("尼日利亚", "ng"),
    "CMR": ("喀麦隆", "cm"),
    "LUX": ("卢森堡", "lu"),
    "SVK": ("斯洛伐克", "sk"),
    "ALG": ("阿尔及利亚", "dz"),
    "HUN": ("匈牙利", "hu"),
    "MON": ("蒙古", "mn"),
    "MDA": ("摩尔多瓦", "md"),
    "WAL": ("威尔士", "gb-wls"),
}

# 中文名映射（按稳定的 IttfId 键控）。仅收录有把握的；其余回退为英文原名。
NAME_CN_MAP = {
    # 中国男单
    "121558": "王楚钦",
    "137237": "林诗栋",
    "203067": "温瑞博",
    "119533": "周启豪",
    "135050": "陈垣宇",
    "135888": "向鹏",
    "119588": "梁靖崑",
    "137238": "黄友政",
    "221452": "李天阳",
    "204288": "陈俊菘",
    # 中国台北男单
    "121582": "林昀儒",
    "200044": "郭冠宏",
    "122727": "冯翊新",
    "135924": "张佑安",
    # 中国女单
    "131163": "孙颖莎",
    "121411": "王曼昱",
    "135049": "蒯曼",
    "124110": "王艺迪",
    "121403": "陈幸同",
    "117332": "朱雨玲",
    "132132": "陈熠",
    "123120": "石洵瑶",
    "144628": "覃予萱",
    "119730": "何卓佳",
    "200907": "纵歌曼",
    "135922": "杨屹韵",
    # 中国台北 / 中国澳门女单
    "110797": "郑怡静",
    "145033": "彭郁涵",
    "136987": "叶伊恬",
    "124162": "李昱谆",
    "124165": "简彤娟",
}


def fetch_raw():
    """抓取原始 JSON 并返回 Result 列表。"""
    resp = requests.get(FRONTDOOR_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("Result")
    if not isinstance(result, list):
        raise ValueError("接口返回结构异常：未找到 Result 列表")
    return data, result


def title_case(name):
    """把 ITTF 的 'WANG Chuqin' / 'Sora MATSUSHIMA' 转成 'Wang Chuqin' / 'Sora Matsushima'。"""
    return " ".join(w[:1].upper() + w[1:].lower() for w in name.split() if w)


def to_chinese_name(entry):
    return NAME_CN_MAP.get(str(entry.get("IttfId", "")), "")


def build_category(result, subevent, top_n):
    rows = [r for r in result if r.get("SubEventCode") == subevent]
    rows.sort(key=lambda r: int(r.get("CurrentRank") or 0))

    players = []
    for r in rows[:top_n]:
        cur = int(r.get("CurrentRank") or 0)
        prev = int(r.get("PreviousRank") or cur)
        move = prev - cur if prev != cur else 0
        try:
            points = int(r.get("RankingPointsYTD") or 0)
        except (TypeError, ValueError):
            points = 0

        code = r.get("AssociationCountryCode") or r.get("CountryCode") or ""
        assoc_cn, iso2 = COUNTRY_MAP.get(code, (code, ""))

        name_en = title_case(r.get("PlayerName", ""))
        name_cn = to_chinese_name(r)

        players.append({
            "rank": cur,
            "name_cn": name_cn,
            "name_en": name_en,
            "code": code,
            "assoc_cn": assoc_cn,
            "iso2": iso2,
            "points": points,
            "move": move,
        })
    return players


def build_payload(data, result, top_n):
    meta = data.get("Result") and {}
    # 取一条样本推断周次 / 发布日期（所有条目一致）
    sample = next((r for r in result if r.get("SubEventCode") == "MS"), None) or (result[0] if result else {})
    week = sample.get("RankingWeek", "")
    year = sample.get("RankingYear", "")
    month = sample.get("RankingMonth", "")
    updated = ""
    try:
        # PublishDate 形如 10/05/2026 00:00:00（月/日/年）
        updated = datetime.datetime.strptime(
            sample.get("PublishDate", ""), "%m/%d/%Y %H:%M:%S"
        ).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        updated = ""

    return {
        "meta": {
            "title": "乒乓球世界排名",
            "updated": updated or datetime.date.today().strftime("%Y-%m-%d"),
            "week": int(week) if str(week).isdigit() else "",
            "source": "ITTF（国际乒联）第 {} 周世界排名".format(week),
            "note": "数据抓取自 ITTF/WTT 官方排名接口，积分为过去 12 个月八站最高积分之和。",
        },
        "categories": {
            "men": {
                "key": "men",
                "label": "男子单打",
                "label_en": "Men's Singles",
                "players": build_category(result, "MS", top_n),
            },
            "women": {
                "key": "women",
                "label": "女子单打",
                "label_en": "Women's Singles",
                "players": build_category(result, "WS", top_n),
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="抓取 ITTF/WTT 世界排名")
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "rankings.json")
    parser.add_argument("--out", default=default_out, help="输出 JSON 路径")
    parser.add_argument("--top", type=int, default=TOP_N, help="每个性别保留的名次数量")
    args = parser.parse_args()

    print("[1/3] 抓取排名数据 ...")
    data, result = fetch_raw()
    print("      共获取到 {} 条记录".format(len(result)))

    print("[2/3] 解析并转换为页面格式 ...")
    payload = build_payload(data, result, args.top)
    men_n = len(payload["categories"]["men"]["players"])
    women_n = len(payload["categories"]["women"]["players"])
    print("      男单 {} 名，女单 {} 名".format(men_n, women_n))

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("[3/3] 已写入 {}".format(out_path))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("抓取失败：{}".format(e), file=sys.stderr)
        sys.exit(1)
