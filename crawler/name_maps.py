#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文映射模块（赛事 / 选手 / 城市）
================================
为「赛事日历」与「对战记录」页面提供中文名映射：
  - 赛事分级：大满贯 / 冠军赛 / 总决赛 / 球星挑战赛 / 挑战赛 / 支线赛 / 青少年 / 世锦赛 / 世界杯 / 奥运 / 亚洲
  - 赛事中文名：基于赛事英文名 + 东道主城市中文名 组合（尽力而为，英文原名始终保留）
  - 城市中文名：常见主办城市 / 国家
  - 选手中文名：知名外国选手（含华裔外援、中国台北/香港/韩国名将）的常用中文译名

说明：接口未提供分级字段（event_Tier_name 全为 null），故分级完全依据赛事英文名关键词；
选手仅覆盖「叫得出名字」的知名选手（"如果有"），大量青少年赛事陌生选手保留英文原名。
"""

import re

# ---------------------------------------------------------------------------
# 城市 / 国家 中文名（用于赛事东道主展示）
# ---------------------------------------------------------------------------
CITY_CN = {
    # 国家
    "china": "中国", "japan": "日本", "korea": "韩国", "germany": "德国",
    "france": "法国", "sweden": "瑞典", "brazil": "巴西", "portugal": "葡萄牙",
    "romania": "罗马尼亚", "austria": "奥地利", "slovenia": "斯洛文尼亚",
    "england": "英格兰", "spain": "西班牙", "puerto rico": "波多黎各",
    "nigeria": "尼日利亚", "india": "印度", "egypt": "埃及", "thailand": "泰国",
    "australia": "澳大利亚", "new zealand": "新西兰", "luxembourg": "卢森堡",
    "croatia": "克罗地亚", "denmark": "丹麦", "russia": "俄罗斯",
    "united states": "美国", "canada": "加拿大", "iran": "伊朗", "kazakhstan": "哈萨克斯坦",
    "czech republic": "捷克", "netherlands": "荷兰", "belgium": "比利时",
    "turkey": "土耳其", "mexico": "墨西哥", "argentina": "阿根廷", "chile": "智利",
    "tunisia": "突尼斯", "ukraine": "乌克兰", "poland": "波兰", "hungary": "匈牙利",
    # 城市
    "beijing": "北京", "shijingshan": "北京", "shijingshan culture": "北京",
    "chongqing": "重庆", "chengdu": "成都", "taiyuan": "太原", "wuxi": "无锡",
    "haining": "海宁", "macao": "中国澳门", "hong kong": "中国香港",
    "singapore": "新加坡", "frankfurt": "法兰克福", "dusseldorf": "杜塞尔多夫",
    "darmstadt": "达姆施塔特", "muscat": "马斯喀特", "istanbul": "伊斯坦布尔",
    "doha": "多哈", "ljubljana": "卢布尔雅那", "tunis": "突尼斯", "bangkok": "曼谷",
    "incheon": "仁川", "zagreb": "萨格勒布", "lagos": "拉各斯", "ottawa": "渥太华",
    "ballarat": "巴拉瑞特", "podgorica": "波德戈里察", "gaborone": "哈博罗内",
    "almaty": "阿拉木图", "panagyurishte": "帕纳久里什泰", "cairo": "开罗",
    "surabaya": "泗水", "budapest": "布达佩斯", "skopje": "斯科普里",
    "tashkent": "塔什干", "manama": "麦纳麦", "sarajevo": "萨拉热窝",
    "herzliya": "赫兹利亚", "villach": "菲拉赫", "lima": "利马", "santiago": "圣地亚哥",
    "tucuman": "图库曼", "mendoza": "门多萨", "fez": "非斯", "agadir": "阿加迪尔",
    "tunja": "通哈", "havana": "哈瓦那", "tallinn": "塔林", "varna": "瓦尔纳",
    "smederevo": "斯梅代雷沃", "novi sad": "诺维萨德", "kuala lumpur": "吉隆坡",
    "kazan": "喀山", "samara": "萨马拉", "ekaterinburg": "叶卡捷琳堡", "spa": "斯帕",
    "senec": "塞内茨", "pattaya": "芭堤雅", "taipei": "中国台北", "kaohsiung": "中国台北",
    "hamilton": "哈密尔顿", "lynghy": "灵比", "armenia": "亚美尼亚",
    "rosario": "罗萨里奥", "cuenca": "昆卡", "ambato": "安巴托",
    "sweden": "瑞典", "europe": "欧洲", "gangneung": "江陵", "astana": "阿斯塔纳",
    "yokohama": "横滨", "montpellier": "蒙彼利埃", "spain": "西班牙", "italy": "意大利",
    "asia": "亚洲", "london": "伦敦", "paris": "巴黎", "dubai": "迪拜",
    "new york": "纽约", "san francisco": "圣弗朗西斯科",
    "buenos aires": "布宜诺斯艾利斯", "rio de janeiro": "里约热内卢",
    "metz": "梅斯", "havirov": "哈维若夫", "varazdin": "瓦拉日丁",
    "vientiane": "万象", "chennai": "金奈", "lignano": "利尼亚诺",
    "platja d aro": "普拉特哈达罗", "wladyslawowo": "弗沃茨瓦沃", "lille": "里尔",
    "gdansk": "格但斯克", "olomouc": "奥洛穆茨", "sandefjord": "桑讷菲尤尔",
    "vila real": "维拉雷阿尔", "vadodara": "瓦多达拉", "mississauga": "密西沙加",
    "humacao": "乌马考", "hennebont": "埃内邦", "foz do iguaçu": "伊瓜苏",
    "zrenjanin": "兹雷尼亚宁", "rionegro": "里奥内格罗", "benghazi": "班加西",
    "algiers": "阿尔及尔", "corpus christi": "科珀斯克里斯蒂", "saudi": "沙特",
    "asunción": "亚松森", "caracas": "加拉加斯", "helsingborg": "赫尔辛堡",
    "puerto princesa": "公主港", "beirut": "贝鲁特", "tbilisi": "第比利斯",
    "batumi": "巴统", "spokane": "斯波坎", "fremont": "弗里蒙特",
    "westchester": "韦斯特切斯特", "cagliari": "卡利亚里", "darwin": "达尔文",
    "halmstad": "哈尔姆斯塔德", "perth": "珀斯", "parma": "帕尔马",
    "manchester": "曼彻斯特", "são josé": "圣若泽", "são josé dos campos": "圣若泽杜斯坎普斯",
    "vila nova de gaia": "加亚新镇", "sulaymaniyah": "苏莱曼尼亚",
    "ottawa": "渥太华", "ballarat": "巴拉瑞特", "podgorica": "波德戈里察",
    "gaborone": "哈博罗内", "almaty": "阿拉木图", "panagyurishte": "帕纳久里什泰",
    "surabaya": "泗水", "skopje": "斯科普里", "manama": "麦纳麦",
    "sarajevo": "萨拉热窝", "herzliya": "赫兹利亚", "villach": "菲拉赫",
    "tucuman": "图库曼", "mendoza": "门多萨", "fez": "非斯", "agadir": "阿加迪尔",
    "tunja": "通哈", "havana": "哈瓦那", "tallinn": "塔林", "varna": "瓦尔纳",
    "smederevo": "斯梅代雷沃", "novi sad": "诺维萨德", "kuala lumpur": "吉隆坡",
    "kazan": "喀山", "samara": "萨马拉", "ekaterinburg": "叶卡捷琳堡", "spa": "斯帕",
    "senec": "塞内茨", "pattaya": "芭堤雅", "armenia": "亚美尼亚",
    "rosario": "罗萨里奥", "cuenca": "昆卡", "ambato": "安巴托",
    "otocec": "奥托塞克", "prishtina": "普里什蒂纳", "cappadocia": "卡帕多奇亚",
}

# ---------------------------------------------------------------------------
# 赛事分级
# ---------------------------------------------------------------------------
# 级别（数值越小越重要）；is_important 用于「重要赛事」筛选
TIER_LEVEL = {
    "smash": 1, "finals": 1, "champions": 1, "world_champ": 1,
    "world_cup": 1, "olympic": 1, "asian": 2, "star": 2,
    "contender": 3, "feeder": 4, "youth": 4, "other": 5,
}


def classify_event(name):
    """返回 (tier_key, tier_cn, level, is_important) 基于英文名关键词。"""
    n = name or ""
    low = n.lower()
    is_youth = "youth" in low

    if "world championship" in low or "championships" in low:
        key, cn = "world_champ", "世界锦标赛"
    elif "olympic" in low:
        key, cn = "olympic", "奥林匹克运动会"
    elif "mixed team world cup" in low:
        key, cn = "world_cup", "混合团体世界杯"
    elif "world cup" in low:
        key, cn = "world_cup", "世界杯"
    elif "asian championship" in low:
        key, cn = "asian", "亚洲锦标赛"
    elif "asian cup" in low:
        key, cn = "asian", "亚洲杯"
    elif "asian" in low:
        key, cn = "asian", "亚洲赛事"
    elif "smash" in low:
        key, cn = "smash", "大满贯"
    elif "finals" in low:
        key, cn = "finals", "总决赛"
    elif "champions" in low:          # WTT Champions（注意区别于 Championships）
        key, cn = "champions", "冠军赛"
    elif "star contender" in low:
        key, cn = "star", "球星挑战赛"
    elif "contender" in low:
        key, cn = "contender", "挑战赛"
    elif "feeder" in low:
        key, cn = "feeder", "支线赛"
    elif is_youth:
        key, cn = "youth", "青少年赛"
    else:
        key, cn = "other", "其他赛事"

    # 青少年系列：把"青少年"前置到类型名
    if is_youth and key in ("smash", "star", "contender", "feeder"):
        cn = "青少年" + cn

    level = TIER_LEVEL.get(key, 5)
    is_important = level <= 2 or key in ("world_champ", "olympic", "world_cup", "asian")
    return key, cn, level, is_important


def _strip_sponsor(name):
    n = re.sub(r"Presented by.*$", "", name, flags=re.I).strip()
    n = re.sub(r"\s*\([^)]*\)$", "", n).strip()
    return n


def _extract_host(base):
    """从 'WTT Champions Frankfurt 2026' 这类字符串里抠出东道主（Frankfurt）。"""
    n = base
    n = re.sub(r"^WTT\s+", "", n, flags=re.I)
    n = re.sub(r"^ITTF\s+", "", n, flags=re.I)
    n = re.sub(r"\b(World Youth Championships|World Championships?|Olympic Games?|"
               r"Olympics|Mixed Team World Cup|World Cup|Asian Championships?|"
               r"Asian Cup|Asian|Smash|Finals|Champions|Star Contender|Contender|"
               r"Feeder|Youth)\b", " ", n, flags=re.I)
    n = re.sub(r"\b(19|20)\d{2}\b", " ", n)             # 年份
    n = re.sub(r"[^\w\s-]", " ", n)                      # 去除 & ' ( ) 等标点
    # 多词城市 / 国家短语替换（如 hong kong、new zealand、puerto rico）
    for k, v in CITY_CN.items():
        if " " in k:
            n = re.sub(r"\b" + re.escape(k) + r"\b", " " + v + " ", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    if not n:
        return ""
    # 逐词匹配中文城市 / 国家（命中则替换为中文）
    tokens = re.split(r"[\s\-]+", n)
    mapped = [CITY_CN[t.lower()] for t in tokens if t.lower() in CITY_CN]
    if mapped:
        # 取最后一个命中的（最具体，如「欧洲·瑞典」取「瑞典」）
        return mapped[-1]
    return n


def event_cn(name):
    """赛事中文名（尽力而为）。英文名始终另存，不覆盖。"""
    if not name:
        return ""
    base = _strip_sponsor(name)
    key, tier_cn, _lv, _imp = classify_event(name)
    host = _extract_host(base)
    if host:
        if re.match(r"^[一-鿿·]+$", host):
            return host + tier_cn          # 东道主已是中文
        return tier_cn + "·" + host        # 东道主为英文
    return tier_cn


# ---------------------------------------------------------------------------
# 知名外国选手中文名（按 "given surname" 小写键）
# ---------------------------------------------------------------------------
PLAYER_CN_MAP = {
    # 巴西
    "hugo calderano": "雨果·卡尔德拉诺",
    "bruna takahashi": "布鲁娜·高桥",
    # 日本
    "tomokazu harimoto": "张本智和", "miwa harimoto": "张本美和",
    "miu hirano": "平野美宇", "mima ito": "伊藤美诚",
    "hina hayata": "早田希娜", "satsuki odo": "大藤沙月",
    "sakura yokoi": "横井咲樱", "miyuu kihara": "木原美悠",
    "sora matsushima": "松岛聪", "hiroto shinozuka": "篠塚大登",
    "shunsuke togami": "户上隼辅", "yukiya uda": "宇田幸矢",
    "maharu yoshimura": "吉村真晴", "kazuhiro yoshimura": "吉村和弘",
    "ryoichi yoshiyama": "吉山僚一", "ukyo kobayashi": "小林有星",
    "shunta harasawa": "原泽陆", "soma ono": "及川隼",
    # 德国（含华裔）
    "dang qiu": "邱党", "patrick franziska": "帕特里克·弗朗西斯卡",
    "dimitrij ovtcharov": "迪米特里·奥恰洛夫", "timo boll": "蒂姆·波尔",
    "benedikt duda": "贝内迪克特·杜达", "ying han": "韩莹",
    "shan xiaona": "单晓娜", "xiaona shan": "单晓娜",
    # 法国（含华裔）
    "felix lebrun": "费利克斯·勒布伦", "alexis lebrun": "艾利克斯·勒布伦",
    "simon gauzy": "西蒙·高茨", "jia nan yuan": "袁嘉楠",
    "prithika pavade": "普里蒂卡·帕瓦德",
    # 瑞典
    "truls moregard": "特鲁斯·莫雷加德", "anton kallberg": "安东·卡尔伯格",
    "mattias falck": "马蒂亚斯·法尔克", "kristian karlsson": "克里斯蒂安·卡尔松",
    "jon persson": "乔恩·佩尔松",
    # 斯洛文尼亚
    "darko jorgic": "达科·约奇克",
    # 韩国
    "woojin jang": "张禹珍", "jang woojin": "张禹珍",
    "jonghoon lim": "林钟勋", "lim jonghoon": "林钟勋",
    "jaehyun an": "安宰贤", "an jaehyun": "安宰贤",
    "yubin shin": "申裕斌", "shin yubin": "申裕斌",
    "hyowon suh": "徐孝元", "jihee jeon": "田志希",
    "hyojoo choi": "崔孝珠", "sangsu lee": "李尚洙",
    # 中国台北
    "yun-ju lin": "林昀儒", "lin yun-ju": "林昀儒",
    "cheng i-ching": "郑怡静", "chih-yuan chuang": "庄智渊",
    "cheng-jui kao": "高承睿", "kao cheng-jui": "高承睿",
    "szu-yu chen": "陈思羽", "chen szu-yu": "陈思羽",
    "feng yihsin": "冯翊新", "kuo chen-hao": "郭冠宏",
    "chang yu-an": "张佑安",
    # 中国香港
    "chun ting wong": "黄镇廷", "ho kwan kit": "何钧杰",
    "lee ho ching": "李皓晴", "zhu chengzhu": "朱成竹",
    "chengzhu zhu": "朱成竹", "doo hye kyung": "杜凯琹",
    "hye kyung doo": "杜凯琹", "minnie soo": "苏慧音",
    # 西班牙
    "alvaro robles": "阿尔瓦罗·罗布莱斯",
    # 葡萄牙
    "marcos freitas": "马科斯·弗雷塔斯", "joao geraldo": "若昂·热拉尔多",
    "tiago apolonia": "蒂亚戈·阿波洛尼亚",
    # 埃及
    "omar assar": "奥马尔·阿萨尔", "hana goda": "哈娜·高达",
    # 尼日利亚
    "quadri aruna": "夸德里·阿鲁纳",
    # 印度
    "manika batra": "玛尼卡·巴特拉", "sreeja akula": "斯丽贾·阿库拉",
    "harmeet desai": "哈米特·德赛", "sharath kamal": "沙拉斯·卡迈勒",
    # 波多黎各
    "adriana diaz": "阿德里安娜·迪亚兹",
    # 罗马尼亚
    "bernadette szocs": "伯纳黛特·斯佐科斯",
    "elizabeta samara": "伊丽莎贝塔·萨马拉",
    # 奥地利
    "sofia polcanova": "索菲亚·波尔卡诺娃",
    # 英格兰
    "liam pitchford": "利亚姆·皮奇福德",
    # 卢森堡（含华裔）
    "ni xialian": "倪夏莲", "xiaolian ni": "倪夏莲",
    # 美国（含华裔）
    "lily zhang": "张安", "zhang lily": "张安",
    # 克罗地亚
    "andrej gacina": "安德烈·加奇纳",
}


def player_cn(name_en, existing_cn=""):
    """返回选手中文名：优先已有映射，否则查表，否则空（保留英文）。"""
    if existing_cn:
        return existing_cn
    if not name_en:
        return ""
    key = re.sub(r"\s+", " ", name_en.strip().lower())
    return PLAYER_CN_MAP.get(key, "")


# ---------------------------------------------------------------------------
# 东道主 -> 国家 / 国旗（用于赛事卡片展示东道主与旗帜）
# ---------------------------------------------------------------------------
try:
    from ittf_ranking import COUNTRY_MAP as _COUNTRY_MAP
except Exception:
    _COUNTRY_MAP = {}

# 国家中文名 -> iso2（来自排名协会表）
_COUNTRY_CN_TO_ISO2 = {cn: iso2 for _c, (cn, iso2) in _COUNTRY_MAP.items() if iso2}
_ISO2_TO_CN = {iso2: cn for _c, (cn, iso2) in _COUNTRY_MAP.items() if iso2}

# 补充排名表未覆盖的东道主国家
ISO2_TO_CN_EXTRA = {
    "qa": "卡塔尔", "tr": "土耳其", "th": "泰国", "om": "阿曼", "me": "黑山",
    "mk": "北马其顿", "uz": "乌兹别克斯坦", "kz": "哈萨克斯坦", "tn": "突尼斯",
    "si": "斯洛文尼亚", "hr": "克罗地亚", "at": "奥地利", "sk": "斯洛伐克",
    "pl": "波兰", "eg": "埃及", "be": "比利时", "pe": "秘鲁", "au": "澳大利亚",
    "bw": "博茨瓦纳", "rs": "塞尔维亚", "bh": "巴林", "it": "意大利",
    "gb-eng": "英格兰", "se": "瑞典", "mx": "墨西哥", "in": "印度", "cl": "智利",
    "dz": "阿尔及利亚", "ec": "厄瓜多尔", "cz": "捷克", "jo": "约旦", "ba": "波黑",
    "iq": "伊拉克", "lu": "卢森堡", "mn": "蒙古", "ca": "加拿大", "sa": "沙特阿拉伯",
    "ge": "格鲁吉亚", "py": "巴拉圭", "ve": "委内瑞拉", "ar": "阿根廷", "ae": "阿联酋",
    "ph": "菲律宾", "lb": "黎巴嫩", "no": "挪威", "pt": "葡萄牙", "es": "西班牙",
    "ly": "利比亚", "la": "老挝", "co": "哥伦比亚", "br": "巴西", "us": "美国",
    "de": "德国", "fr": "法国", "jp": "日本", "kr": "韩国", "hk": "中国香港",
    "mo": "中国澳门", "tw": "中国台北", "ng": "尼日利亚", "ro": "罗马尼亚",
    "nl": "荷兰", "hu": "匈牙利", "dk": "丹麦", "ua": "乌克兰", "ir": "伊朗",
}
for _k, _v in ISO2_TO_CN_EXTRA.items():
    _ISO2_TO_CN.setdefault(_k, _v)


def _iso2_to_cn(code):
    return _ISO2_TO_CN.get(code, "")


# 东道主 -> 国旗 iso2：覆盖 data/events.json 中实际出现的 130 个主办地
# （中文城市 / 国家级中文名 / 英文城市小写均可命中；国家级中文名优先走国家表反查）
HOST_ISO2 = {
    # 中文城市
    "多哈": "qa", "突尼斯": "tn", "曼谷": "th", "新加坡": "sg", "阿拉木图": "kz",
    "帕纳久里什泰": "bg", "中国香港": "hk", "伊斯坦布尔": "tr", "马斯喀特": "om",
    "波德戈里察": "me", "中国澳门": "mo", "拉各斯": "ng", "斯科普里": "mk",
    "塔什干": "uz", "萨格勒布": "hr", "卢布尔雅那": "si", "重庆": "cn", "太原": "cn",
    "塞内茨": "sk", "林茨": "at", "江陵": "kr", "柏林": "de", "阿斯塔纳": "kz",
    "格但斯克": "pl", "开罗": "eg", "斯帕": "be", "横滨": "jp", "仁川": "kr",
    "利马": "pe", "巴拉瑞特": "au", "哈博罗内": "bw", "诺维萨德": "rs", "麦纳麦": "bh",
    "帕尔马": "it", "伦敦": "gb-eng", "珀斯": "au", "福冈": "jp", "哈尔姆斯塔德": "se",
    "巴黎": "fr", "门多萨": "ar", "里约热内卢": "br", "坎昆": "mx", "果阿": "in",
    "安塔利亚": "tr", "圣地亚哥": "cl", "阿尔及尔": "dz", "蒙彼利埃": "fr",
    "杜塞尔多夫": "de", "法兰克福": "de", "昆卡": "ec", "奥洛穆茨": "cz", "安曼": "jo",
    "萨拉热窝": "ba", "苏莱曼尼亚": "iq", "卢森堡": "lu", "弗沃茨瓦沃": "pl",
    "维拉雷尔": "pt", "瓦多达拉": "in", "乌兰巴托": "mn", "密西沙加": "ca", "达曼": "sa",
    "巴统": "ge", "曼彻斯特": "gb-eng", "休斯顿": "us", "第比利斯": "ge",
    "兹雷尼亚宁": "rs", "伊瓜苏": "br", "纽约": "us", "卡利亚里": "it", "达尔文": "au",
    "贝鲁特": "lb", "成都": "cn", "蒙塞里亚": "co", "斯波坎": "us", "弗里蒙特": "us",
    "韦斯特切斯特": "us", "科珀斯克里斯蒂": "us", "里奥内格罗": "co", "伊斯梅利亚": "eg",
    "圣弗朗西斯科": "us", "圣若泽": "br", "公主港": "ph", "加拉加斯": "ve",
    "亚松森": "py", "赫尔辛堡": "se", "梅斯": "fr", "卡帕多奇亚": "tr",
    "布宜诺斯艾利斯": "ar", "düsseldorf": "de", "san francisco": "us",
    # 英文（未被中文表覆盖的城市）
    "otocec": "si", "havirov": "cz", "varazdin": "hr", "vientiane": "la",
    "buenos aires": "ar", "metz": "fr", "cappadocia": "tr", "vila nova de gaia": "pt",
    "chennai": "in", "lignano": "it", "platja d aro": "es", "wladyslawowo": "pl",
    "lille": "fr", "gdansk": "pl", "olomouc": "cz", "sandefjord": "no",
    "vila real": "pt", "vadodara": "in", "são josé": "br", "mississauga": "ca",
    "humacao": "pr", "dammam": "sa", "batumi": "ge", "manchester": "gb-eng",
    "houston": "us", "tbilisi": "ge", "são josé dos campos": "br", "hennebont": "fr",
    "parma": "it", "london": "gb-eng", "perth": "au", "fremont": "us", "spokane": "us",
    "foz do iguaçu": "br", "new york": "us", "zrenjanin": "rs", "fukuoka": "jp",
    "rionegro": "co", "ismailia": "eg", "cagliari": "it", "darwin": "au",
    "halmstad": "se", "paris": "fr", "benghazi": "ly", "westchester": "us",
    "rio de janeiro": "br", "cancun": "mx", "goa": "in", "antalya": "tr",
    "corpus christi": "us", "saudi": "sa", "asunción": "py", "caracas": "ve",
    "helsingborg": "se", "dubai": "ae", "puerto princesa": "ph", "beirut": "lb",
    "algiers": "dz",
}

# 中文东道主 -> iso2（由 CITY_CN 反推：英文键或中文键命中均可）
HOST_CN_TO_ISO2 = {}
for _eng, _cn in CITY_CN.items():
    _c = HOST_ISO2.get(_eng) or HOST_ISO2.get(_cn)
    if _c:
        HOST_CN_TO_ISO2[_cn] = _c


def host_info(name_en):
    """从赛事英文名推导 (host_display, country_cn, country_code)。

    host_display：东道主显示名（中文优先，否则英文原名）。
    country_cn / country_code：用于旗帜与国名展示；无法确定时为空。
    """
    if not name_en:
        return ("", "", "")
    base = _strip_sponsor(name_en)
    # 多词城市 / 国家短语替换（如 hong kong、new zealand、puerto rico）
    for k, v in CITY_CN.items():
        if " " in k:
            base = re.sub(r"\b" + re.escape(k) + r"\b", " " + v + " ", base, flags=re.I)
    # 保留中文与带音调的拉丁字母（如 ó/ñ/ü），仅剔除标点
    text = re.sub(r"[^\w\s\-]", " ", base)
    tokens = [t for t in re.split(r"[\s\-]+", text.strip()) if t]
    _cn_vals = set(CITY_CN.values())
    cns = []
    for t in tokens:
        tl = t.lower()
        if tl in CITY_CN:
            cns.append(CITY_CN[tl])          # 英文命中 -> 中文
        elif t in _cn_vals:
            cns.append(t)                     # 已是中文
    host_cn = cns[-1] if cns else ""

    # 英文残留（剔除已中文化 token、年份、级别词后的地点词）
    eng = " ".join(t for t in tokens if t.lower() not in CITY_CN and t not in _cn_vals)
    eng_clean = re.sub(r"\s+(ii|iii|iv|v)\b", "", eng, flags=re.I).strip()

    # 显示名：中文优先，否则英文（首字母大写）
    display = host_cn if host_cn else (eng_clean.title() if eng_clean else "")

    # 国家代码：国家级中文名优先走国家表反查；其次中文东道主表；最后英文残留
    code = ""
    if host_cn in _COUNTRY_CN_TO_ISO2:
        code = _COUNTRY_CN_TO_ISO2[host_cn]
    if not code and host_cn in HOST_CN_TO_ISO2:
        code = HOST_CN_TO_ISO2[host_cn]
    if not code:
        for cand in (eng.lower(), eng_clean.lower()):
            if cand and cand in HOST_ISO2:
                code = HOST_ISO2[cand]
                break
    if not code:
        for t in tokens:
            if t.lower() in HOST_ISO2:
                code = HOST_ISO2[t.lower()]
                break

    country_cn = _iso2_to_cn(code)
    return (display, country_cn, code)


if __name__ == "__main__":
    import json
    tests = ["China Smash 2026 Presented by Beijing ... (01 Oct 2026 - 11 Oct 2026)",
             "WTT Champions Frankfurt 2026 (03 Nov 2026 - 08 Nov 2026)",
             "WTT Finals Hong Kong 2026 (09 Dec 2026 - 13 Dec 2026)",
             "WTT Star Contender Muscat 2026 (16 Nov 2026 - 21 Nov 2026)",
             "WTT Youth Contender Ballarat 2026 (14 Nov 2026 - 17 Nov 2026)",
             "ITTF Mixed Team World Cup Chengdu 2026 (29 Nov 2026 - 06 Dec 2026)",
             "WTT Feeder Ottawa 2026 (...)"]
    for t in tests:
        k, cn, lv, imp = classify_event(t)
        print(f"{event_cn(t):30s} | {cn} | imp={imp} | {t[:40]}")
    print("player:", player_cn("Tomokazu Harimoto"), player_cn("Felix Lebrun"),
          player_cn("Hugo Calderano"), player_cn("Yun-Ju Lin"))
