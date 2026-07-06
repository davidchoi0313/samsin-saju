# -*- coding: utf-8 -*-
"""
shinsal_rules.py — 주요 신살(神煞) 11종 조견표 상수·룰셋

설계서 DESIGN.md §4.4 보강 대상:
  도화 · 역마 · 화개 · 천을귀인 · 백호 · 괴강 · 원진 · 문창 · 양인 · 홍염 · 귀문관살

lunar_python이 제공하지 않는 주요 신살을 전통 명리 조견표(일간/년지/일지 기준
삼합·대조표)로 결정론적으로 산출한다. 모든 룰은 순수 데이터(상수 테이블)와
순수 함수로만 구성한다 — 외부 의존·랜덤·시각 의존 없음.

근거 기준:
  - 도화/역마/화개: 년지(또는 일지)의 삼합국 기준 십이신살 대조
  - 천을귀인: 일간 기준 귀인 지지
  - 백호: 갑진·을미·병술·정축·무진·임술·계축 (60갑자 7주)
  - 괴강: 경진·경술·임진·임술·무술(·무진) 일주/주
  - 양인: 일간 기준 양인 지지
  - 문창: 일간 기준 문창 지지
  - 홍염: 일간 기준 홍염 지지
  - 원진: 지지 짝(자미·축오·인유·묘신·진해·사술)
  - 귀문관살: 지지 짝(자유·축오·인미·묘신·진해·사술)

용어는 한국 명리 표준 한글로 산출한다.
"""

# ── 십이지지 ──────────────────────────────────────────────────────────────
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# ── 삼합국(三合局) 기준 도화·역마·화개 ────────────────────────────────────
# 삼합 그룹: 申子辰(水) / 寅午戌(火) / 巳酉丑(金) / 亥卯未(木)
# 각 그룹의 기준지(년지 또는 일지)에 대해 도화/역마/화개 지지가 고정된다.
#   도화(桃花): 子午卯酉 중 해당 — 申子辰→酉, 寅午戌→卯, 巳酉丑→午, 亥卯未→子
#   역마(驛馬): 寅申巳亥 중 해당 — 申子辰→寅, 寅午戌→申, 巳酉丑→亥, 亥卯未→巳
#   화개(華蓋): 辰戌丑未 중 해당 — 申子辰→辰, 寅午戌→戌, 巳酉丑→丑, 亥卯未→未
SAMHAP_GROUPS = {
    "水": ["申", "子", "辰"],
    "火": ["寅", "午", "戌"],
    "金": ["巳", "酉", "丑"],
    "木": ["亥", "卯", "未"],
}
# 기준지 → 삼합국
_ZHI_TO_GROUP = {}
for _g, _members in SAMHAP_GROUPS.items():
    for _z in _members:
        _ZHI_TO_GROUP[_z] = _g

DOHWA_BY_GROUP = {"水": "酉", "火": "卯", "金": "午", "木": "子"}
YEOKMA_BY_GROUP = {"水": "寅", "火": "申", "金": "亥", "木": "巳"}
HWAGAE_BY_GROUP = {"水": "辰", "火": "戌", "金": "丑", "木": "未"}

# ── 천을귀인(天乙貴人): 일간 기준 ─────────────────────────────────────────
# 甲戊庚→丑未, 乙己→子申, 丙丁→亥酉, 壬癸→巳卯, 辛→午寅 (전통 조견표)
CHEONEUL_BY_GAN = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["巳", "卯"], "癸": ["巳", "卯"],
    "辛": ["午", "寅"],
}

# ── 양인(羊刃): 일간 기준. 보통 양간(陽干)에만 성립 ───────────────────────
# 甲→卯, 丙→午, 戊→午, 庚→酉, 壬→子 (양간 양인)
# 음간 양인(을→진, 정/기→미, 신→술, 계→축)은 학파에 따라 다루나 본 엔진은
# 표준 양간 양인 + 음간은 별도 표기 없이 보수적으로 제외(과다 표기 방지).
YANGIN_BY_GAN = {
    "甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子",
}

# ── 문창(文昌): 일간 기준 ─────────────────────────────────────────────────
# 甲→巳, 乙→午, 丙→申, 丁→酉, 戊→申, 己→酉, 庚→亥, 辛→子, 壬→寅, 癸→卯
MUNCHANG_BY_GAN = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}

# ── 홍염(紅艶): 일간 기준 ─────────────────────────────────────────────────
# 甲→午, 乙→午, 丙→寅, 丁→未, 戊→辰, 己→辰, 庚→戌, 辛→酉, 壬→子, 癸→申
HONGYEOM_BY_GAN = {
    "甲": "午", "乙": "午", "丙": "寅", "丁": "未", "戊": "辰",
    "己": "辰", "庚": "戌", "辛": "酉", "壬": "子", "癸": "申",
}

# ── 백호(白虎大殺): 간지(干支) 조합. 주(柱) 단위로 본다 ────────────────────
# 甲辰 乙未 丙戌 丁丑 戊辰 壬戌 癸丑
BAEKHO_PILLARS = {"甲辰", "乙未", "丙戌", "丁丑", "戊辰", "壬戌", "癸丑"}

# ── 괴강(魁罡): 간지 조합. 주 단위 ────────────────────────────────────────
# 庚辰 庚戌 壬辰 壬戌 戊戌 (戊辰을 포함하는 학파도 있으나 보수적으로 5종)
GWAEGANG_PILLARS = {"庚辰", "庚戌", "壬辰", "壬戌", "戊戌"}

# ── 원진(怨嗔): 지지 짝 ───────────────────────────────────────────────────
# 子未 丑午 寅酉 卯申 辰亥 巳戌
WONJIN_PAIRS = {
    frozenset(["子", "未"]), frozenset(["丑", "午"]), frozenset(["寅", "酉"]),
    frozenset(["卯", "申"]), frozenset(["辰", "亥"]), frozenset(["巳", "戌"]),
}

# ── 귀문관살(鬼門關殺): 지지 짝 ───────────────────────────────────────────
# 子酉 丑午 寅未 卯申 辰亥 巳戌
GWIMUN_PAIRS = {
    frozenset(["子", "酉"]), frozenset(["丑", "午"]), frozenset(["寅", "未"]),
    frozenset(["卯", "申"]), frozenset(["辰", "亥"]), frozenset(["巳", "戌"]),
}

# 주(柱) 위치 라벨
POS_LABELS = ["년지", "월지", "일지", "시지"]


def _zhi_pos_label(idx):
    return POS_LABELS[idx]


def _find_zhi_positions(branches, target_zhi):
    """branches 리스트에서 target_zhi가 있는 위치 라벨들을 반환."""
    out = []
    for i, z in enumerate(branches):
        if z is None:
            continue
        if z == target_zhi:
            out.append(_zhi_pos_label(i))
    return out


def compute_shinsal(day_gan, branches, pillars_gz):
    """주요 신살 11종을 산출한다.

    Args:
        day_gan: 일간 문자 (예: "己")
        branches: [년지, 월지, 일지, 시지] 한자 리스트. 시 모름이면 시지=None.
        pillars_gz: ["庚午","己卯","己卯","丁卯"] 형태. 시 모름이면 마지막=None.

    Returns:
        list[dict]: [{"name": 한글신살명, "pos": 위치라벨 또는 None}, ...]
        같은 신살이 여러 위치에 있으면 위치별로 항목을 나눈다.
        해당 신살이 없으면 {"name": ..., "pos": None}로 표기(메뉴가 부재도 소비).
    """
    results = []

    # 기준지: 년지 우선(전통), 보조로 일지. 도화/역마/화개는 년지·일지 양쪽 기준 표기.
    year_zhi = branches[0]
    day_zhi = branches[2]

    def _samhap_shinsal(base_zhi, table, name):
        if base_zhi is None:
            return
        group = _ZHI_TO_GROUP.get(base_zhi)
        if group is None:
            return
        target = table[group]
        positions = _find_zhi_positions(branches, target)
        for p in positions:
            results.append({"name": name, "pos": p})

    # 도화·역마·화개 — 년지 기준 + 일지 기준 (둘 다 전통적으로 본다)
    for base in (year_zhi, day_zhi):
        _samhap_shinsal(base, DOHWA_BY_GROUP, "도화")
        _samhap_shinsal(base, YEOKMA_BY_GROUP, "역마")
        _samhap_shinsal(base, HWAGAE_BY_GROUP, "화개")

    # 천을귀인 — 일간 기준
    for z in CHEONEUL_BY_GAN.get(day_gan, []):
        for p in _find_zhi_positions(branches, z):
            results.append({"name": "천을귀인", "pos": p})

    # 양인 — 일간 기준
    yangin_zhi = YANGIN_BY_GAN.get(day_gan)
    if yangin_zhi:
        for p in _find_zhi_positions(branches, yangin_zhi):
            results.append({"name": "양인", "pos": p})

    # 문창 — 일간 기준
    munchang_zhi = MUNCHANG_BY_GAN.get(day_gan)
    if munchang_zhi:
        for p in _find_zhi_positions(branches, munchang_zhi):
            results.append({"name": "문창", "pos": p})

    # 홍염 — 일간 기준
    hongyeom_zhi = HONGYEOM_BY_GAN.get(day_gan)
    if hongyeom_zhi:
        for p in _find_zhi_positions(branches, hongyeom_zhi):
            results.append({"name": "홍염", "pos": p})

    # 백호 — 주(干支) 단위
    for i, gz in enumerate(pillars_gz):
        if gz and gz in BAEKHO_PILLARS:
            results.append({"name": "백호", "pos": POS_LABELS[i].replace("지", "주")})

    # 괴강 — 주(干支) 단위
    for i, gz in enumerate(pillars_gz):
        if gz and gz in GWAEGANG_PILLARS:
            results.append({"name": "괴강", "pos": POS_LABELS[i].replace("지", "주")})

    # 원진 — 지지 짝(원국 내 두 지지가 짝을 이루면 성립)
    present = [(i, z) for i, z in enumerate(branches) if z is not None]
    for a in range(len(present)):
        for b in range(a + 1, len(present)):
            ia, za = present[a]
            ib, zb = present[b]
            pair = frozenset([za, zb])
            if za != zb and pair in WONJIN_PAIRS:
                results.append({
                    "name": "원진",
                    "pos": f"{POS_LABELS[ia]}-{POS_LABELS[ib]}",
                })
            if za != zb and pair in GWIMUN_PAIRS:
                results.append({
                    "name": "귀문관살",
                    "pos": f"{POS_LABELS[ia]}-{POS_LABELS[ib]}",
                })

    # 산출되지 않은 신살도 "부재" 항목으로 명시(메뉴가 부재 여부를 소비)
    all_names = [
        "도화", "역마", "화개", "천을귀인", "백호", "괴강",
        "원진", "문창", "양인", "홍염", "귀문관살",
    ]
    found_names = {r["name"] for r in results}
    for name in all_names:
        if name not in found_names:
            results.append({"name": name, "pos": None})

    return results
