#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
saju_engine.py — 삼신이(samsin) 정밀 만세력 엔진

설계서 DESIGN.md §4 사양 구현. 두 층 구조의 1층(결정론 산출).
입력(생년월일·시·성별 등) → 결정론적 "산출 카드" JSON 출력.

핵심 원칙:
  - 엔진은 결정론적이다. 같은 입력 → 항상 같은 출력.
  - lunar_python(1.4.8 검증)을 1차 산출원으로, 신살 11종은 shinsal_rules로 보강.
  - 시 "모름" / 음력 윤달 / 입춘·절기 경계 / 진태양시 보정 / 야자시 옵션 처리.
  - 산출 카드에는 면책 문구를 넣지 않는다(면책은 2층 AI 해석 강제 사항).

CLI 계약:
  python saju_engine.py --gender male --calendar solar \
      --date 1990-03-15 --time mau
  → 설계서 §4.2 산출 카드 JSON을 stdout 출력.

  궁합(2인):
  python saju_engine.py --mode compatibility \
      --gender male --calendar solar --date 1990-03-15 --time mau \
      --gender2 female --calendar2 solar --date2 1992-07-20 --time2 yu

  stdin JSON 입력도 지원:
  echo '{"gender":"male","calendar":"solar","birthDate":"1990-03-15","birthTime":"mau"}' \
      | python saju_engine.py --stdin
"""

import sys
import os
import json
import math
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────────────────
# 1. lunar_python 로딩 (graceful degradation)
# ─────────────────────────────────────────────────────────────────────────
def _load_lunar():
    """lunar_python을 로드한다. 미설치 시 자동 설치 시도 후 재시도.

    샌드박스 견고성: import 실패 → pip 자동 설치 → 재시도 → 그래도 실패면
    명확한 안내 메시지와 함께 RuntimeError.
    """
    try:
        from lunar_python import Solar, Lunar  # noqa
        return Solar, Lunar
    except ImportError:
        pass
    # 자동 설치 1회 시도
    import subprocess
    for args in (
        [sys.executable, "-m", "pip", "install", "lunar_python",
         "--break-system-packages", "--quiet"],
        [sys.executable, "-m", "pip", "install", "lunar_python", "--quiet"],
    ):
        try:
            subprocess.run(args, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from lunar_python import Solar, Lunar  # noqa
            return Solar, Lunar
        except Exception:
            continue
    raise RuntimeError(
        "lunar_python 라이브러리를 불러오지 못했습니다. "
        "다음 명령으로 직접 설치해 주세요:\n"
        "    pip install lunar_python --break-system-packages\n"
        "설치 후 다시 실행하면 만세력 산출이 진행됩니다."
    )


Solar, Lunar = _load_lunar()

try:
    import shinsal_rules
except ImportError:
    from . import shinsal_rules  # type: ignore

try:
    import jijanggan
except ImportError:
    from . import jijanggan  # type: ignore


# ─────────────────────────────────────────────────────────────────────────
# 2. 한자 명리 용어 → 한국 표준 한글 매핑
# ─────────────────────────────────────────────────────────────────────────
# lunar_python은 중국식 한자 용어를 반환한다. 한국 명리 표준 한글로 변환한다.

SHISHEN_KO = {
    "比肩": "비견", "劫财": "겁재", "食神": "식신", "伤官": "상관",
    "偏财": "편재", "正财": "정재", "七杀": "칠살", "正官": "정관",
    "偏印": "편인", "正印": "정인",
}

DISHI_KO = {  # 십이운성
    "长生": "장생", "沐浴": "목욕", "冠带": "관대", "临官": "임관",
    "帝旺": "제왕", "衰": "쇠", "病": "병", "死": "사",
    "墓": "묘", "绝": "절", "胎": "태", "养": "양",
}

GAN_ELEMENT = {  # 천간 → 오행
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
GAN_YINYANG = {  # 천간 → 음양
    "甲": "陽", "乙": "陰", "丙": "陽", "丁": "陰", "戊": "陽",
    "己": "陰", "庚": "陽", "辛": "陰", "壬": "陽", "癸": "陰",
}
ZHI_MAIN_ELEMENT = {  # 지지 본기(本氣) 오행
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 12지지 시 코드 → 대표 시각(시 중앙, 30분 시프트 라벨 기준 중앙 근처)
TIME_CODE_TO_HM = {
    "ja": (0, 30), "chuk": (2, 0), "in": (4, 0), "mau": (6, 0),
    "jin": (8, 0), "sa": (10, 0), "o": (12, 0), "mi": (14, 0),
    "sin": (16, 0), "yu": (18, 0), "sul": (20, 0), "hae": (22, 0),
}
TIME_CODE_TO_LABEL = {
    "ja": "자시(23:30~01:30)", "chuk": "축시(01:30~03:30)",
    "in": "인시(03:30~05:30)", "mau": "묘시(05:30~07:30)",
    "jin": "진시(07:30~09:30)", "sa": "사시(09:30~11:30)",
    "o": "오시(11:30~13:30)", "mi": "미시(13:30~15:30)",
    "sin": "신시(15:30~17:30)", "yu": "유시(17:30~19:30)",
    "sul": "술시(19:30~21:30)", "hae": "해시(21:30~23:30)",
}


# ─────────────────────────────────────────────────────────────────────────
# 3. 진태양시 보정
# ─────────────────────────────────────────────────────────────────────────
def _equation_of_time_minutes(month, day):
    """균시차(Equation of Time)를 분 단위로 근사 산출.

    표준 천문 근사식. 정밀 천문력은 아니나 시주 경계 판정에 충분한 정밀도.
    """
    doy = (month - 1) * 30.4 + day
    B = 2 * math.pi * (doy - 81) / 364.0
    return 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)


def _apply_true_solar_time(dt, longitude):
    """표준시(KST=135°E 기준) 시각을 진태양시로 보정한다.

    진태양시 = 표준시 + (출생지경도 − 135)×4분 + 균시차
    한국 기본 127.5°E면 경도 보정 약 −30분.
    """
    long_corr_min = (longitude - 135.0) * 4.0
    eot_min = _equation_of_time_minutes(dt.month, dt.day)
    total_shift = long_corr_min + eot_min
    return dt + datetime.timedelta(minutes=total_shift)


# ─────────────────────────────────────────────────────────────────────────
# 4. 입력 정규화
# ─────────────────────────────────────────────────────────────────────────
def _resolve_solar_datetime(inp):
    """입력을 양력 datetime + 메타로 정규화한다.

    Returns: (solar_dt, meta) — solar_dt는 lunar_python에 넣을 양력 시각,
             meta는 산출 카드 meta 필드용 정보.
    """
    calendar = inp.get("calendar", "solar")
    date_str = inp["birthDate"]
    y, m, d = (int(x) for x in date_str.split("-"))

    hour_known = True
    time_code = inp.get("birthTime", "unknown")
    time_hm = inp.get("birthTimeHm")  # "HH:MM" 직접 입력(야자시 테스트용)

    if time_code == "unknown" and not time_hm:
        hour_known = False
        hh, mm = 12, 0  # 시 모름이면 정오 기준으로 일주만 산출
    elif time_hm:
        hh, mm = (int(x) for x in time_hm.split(":"))
    else:
        hh, mm = TIME_CODE_TO_HM.get(time_code, (12, 0))

    # 음력 → 양력 변환
    if calendar == "lunar":
        lunar_month = m
        if inp.get("isLeapMonth"):
            lunar_month = -m  # lunar_python 윤달 규약(음수)
        lun = Lunar.fromYmdHms(y, lunar_month, d, hh, mm, 0)
        sol = lun.getSolar()
        base_dt = datetime.datetime(sol.getYear(), sol.getMonth(), sol.getDay(),
                                    hh, mm, 0)
    else:
        base_dt = datetime.datetime(y, m, d, hh, mm, 0)

    # 진태양시 보정(시 아는 경우만 의미 있음; 시 모름은 정오라 영향 미미)
    longitude = inp.get("birthLongitude", 127.5)
    true_dt = _apply_true_solar_time(base_dt, longitude) if hour_known else base_dt

    meta = {
        "hourKnown": hour_known,
        "solarDate": base_dt.strftime("%Y-%m-%d"),
        "trueSolarTime": true_dt.strftime("%Y-%m-%d %H:%M") if hour_known else None,
        "timeLabel": TIME_CODE_TO_LABEL.get(time_code) if hour_known else "시 모름",
        "longitude": longitude,
        "calendar": calendar,
        "isLeapMonth": bool(inp.get("isLeapMonth", False)),
    }
    return true_dt, meta, hour_known


def _make_eightchar(true_dt, hour_known, early_late):
    """양력 진태양시 datetime → lunar_python EightChar.

    야자시/조자시 옵션을 sect로 매핑:
      standard → sect 2 (야자시도 당일 일주)
      split    → sect 1 (야자시는 다음날 일주)
    """
    solar = Solar.fromYmdHms(true_dt.year, true_dt.month, true_dt.day,
                             true_dt.hour, true_dt.minute, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    if early_late == "split":
        ec.setSect(1)
    else:
        ec.setSect(2)
    return lunar, ec


# ─────────────────────────────────────────────────────────────────────────
# 5. 산출 카드 조립 (작은 단위 함수)
# ─────────────────────────────────────────────────────────────────────────
def _pillars(ec, hour_known):
    def gz(gan, zhi):
        return {"gan": gan, "zhi": zhi}
    p = {
        "year": gz(ec.getYearGan(), ec.getYearZhi()),
        "month": gz(ec.getMonthGan(), ec.getMonthZhi()),
        "day": gz(ec.getDayGan(), ec.getDayZhi()),
        "hour": gz(ec.getTimeGan(), ec.getTimeZhi()) if hour_known else None,
    }
    return p


def _day_master(ec):
    g = ec.getDayGan()
    return {"gan": g, "element": GAN_ELEMENT[g], "yinYang": GAN_YINYANG[g]}


def _five_elements(ec, hour_known):
    """오행 분포(천간 + 지장간 여기·중기·정기 전체)와 강약 판정.

    변경(1단계 토대): 지지 본기(정기)만이 아니라 지장간 전체(여기·중기·정기)를
    표준 지장간표(jijanggan.py)로 집계한다. 정기는 기존 본기와 동일하므로 새
    집계는 옛 집계의 상위집합이다(여기·중기가 더해질 뿐). 가중은 단순 포함(각
    지장간 1) — 사령 일수 유파차를 피하는 결정론 선택. 강약은 월령 정밀화 없이
    기존 동기 세력 단순 룰을 유지한다(강약 고도화는 후속 단계 대상).
    """
    count = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    pillars = [
        ("year", ec.getYearGan(), ec.getYearZhi()),
        ("month", ec.getMonthGan(), ec.getMonthZhi()),
        ("day", ec.getDayGan(), ec.getDayZhi()),
    ]
    if hour_known:
        pillars.append(("hour", ec.getTimeGan(), ec.getTimeZhi()))

    hidden_breakdown = []
    for pos, gan, zhi in pillars:
        count[GAN_ELEMENT[gan]] += 1
        stems = jijanggan.hidden_stems(zhi)
        for s in stems:
            count[s["element"]] += 1
        hidden_breakdown.append({"position": pos, "branch": zhi, "stems": stems})

    day_el = GAN_ELEMENT[ec.getDayGan()]
    # 일간을 돕는 오행(같은 오행 + 생해주는 오행)
    SHENG = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}
    helper = SHENG[day_el]
    support = count[day_el] + count[helper]
    total = sum(count.values())
    ratio = support / total if total else 0
    if ratio >= 0.55:
        strength = "신강"
    elif ratio <= 0.35:
        strength = "신약"
    else:
        strength = "중화"

    missing = [k for k, v in count.items() if v == 0]
    mx = max(count.values()) if count else 0
    dominant = [k for k, v in count.items() if v == mx and v >= 3]
    return {
        "count": count,
        "strength": strength,
        "missing": missing,
        "dominant": dominant,
        "hiddenStems": hidden_breakdown,
    }


def _ten_gods(ec, hour_known):
    def ko(s):
        return SHISHEN_KO.get(s, s)
    tg = {
        "year": ko(ec.getYearShiShenGan()),
        "month": ko(ec.getMonthShiShenGan()),
        "dayBranchHidden": [ko(x) for x in ec.getDayShiShenZhi()],
    }
    if hour_known:
        tg["hour"] = ko(ec.getTimeShiShenGan())
    else:
        tg["hour"] = "시 미상"
    return tg


def _twelve_stages(ec, hour_known):
    def ko(s):
        return DISHI_KO.get(s, s)
    ts = {
        "year": ko(ec.getYearDiShi()),
        "month": ko(ec.getMonthDiShi()),
        "day": ko(ec.getDayDiShi()),
    }
    ts["hour"] = ko(ec.getTimeDiShi()) if hour_known else "시 미상"
    return ts


def _napyin(ec, hour_known):
    n = {
        "year": ec.getYearNaYin(),
        "month": ec.getMonthNaYin(),
        "day": ec.getDayNaYin(),
    }
    if hour_known:
        n["hour"] = ec.getTimeNaYin()
    return n


def _major_shinsal(ec, hour_known):
    """주요 신살 = lunar_python 공망 + shinsal_rules 11종."""
    branches = [ec.getYearZhi(), ec.getMonthZhi(), ec.getDayZhi(),
                ec.getTimeZhi() if hour_known else None]
    pillars_gz = [
        ec.getYearGan() + ec.getYearZhi(),
        ec.getMonthGan() + ec.getMonthZhi(),
        ec.getDayGan() + ec.getDayZhi(),
        (ec.getTimeGan() + ec.getTimeZhi()) if hour_known else None,
    ]
    result = shinsal_rules.compute_shinsal(ec.getDayGan(), branches, pillars_gz)
    # 공망(일주 기준) 추가
    result.append({"name": "공망", "pos": ec.getDayXunKong()})
    return result


def _daewoon(ec, gender, ref_year=None):
    """대운: 순역·대운수·10년 구간 리스트·현재 대운.

    현재 대운(current)은 기준연도(ref_year)로 결정론 산출한다. ref_year 미지정
    시 current=None — 시스템 시각 datetime.date.today()에 의존하지 않아 같은
    입력이면 항상 같은 출력을 보장한다(결정론 균열 해소). 호출층(2층)이 '지금'에
    해당하는 연도를 referenceYear로 주입해야 current가 채워진다. sewoonYear가
    주어지면 build_card가 이를 기준연도로 대체 적용한다(하위호환).
    """
    g = 1 if gender == "male" else 0
    yun = ec.getYun(g)
    da_list = yun.getDaYun()
    out_list = []
    for dy in da_list:
        gz = dy.getGanZhi()
        if not gz:  # 첫 구간(대운 전, 간지 없음)은 스킵
            continue
        out_list.append({
            "fromAge": dy.getStartAge(),
            "toAge": dy.getEndAge(),
            "startYear": dy.getStartYear(),
            "gan": gz[0],
            "zhi": gz[1] if len(gz) > 1 else "",
        })
    # 현재 대운: 기준연도(ref_year)로만 산출. 미지정이면 None(결정론).
    current = (_current_daewoon_for_year(out_list, ec, ref_year)
               if ref_year is not None else None)
    return {
        "forward": yun.isForward(),
        "startAge": yun.getStartYear(),
        "startMonth": yun.getStartMonth(),
        "list": out_list,
        "current": current,
        "currentBasisYear": ref_year,
    }


def _sewoon(ec, year):
    """세운(해운): 지정 연도의 천간지지·십신·원국 합충 단서."""
    sol = Solar.fromYmd(year, 6, 30)  # 해당 연도 대표일(입춘 지난 시점)
    lun = sol.getLunar()
    gz = lun.getYearInGanZhi()
    # 세운 십신: 세운 천간을 일간 기준으로 본다
    sew_gan = gz[0]
    sew_zhi = gz[1] if len(gz) > 1 else ""
    # 원국 지지와의 단순 합충 단서(반합·충 위주)
    chart_zhis = [ec.getYearZhi(), ec.getMonthZhi(), ec.getDayZhi()]
    clashes = _branch_relations(sew_zhi, chart_zhis)
    return {
        "currentYear": year,
        "ganZhi": gz,
        "ganElement": GAN_ELEMENT.get(sew_gan, ""),
        "zhiElement": ZHI_MAIN_ELEMENT.get(sew_zhi, ""),
        "clashWithChart": clashes,
    }


def _today(ec, date_str):
    """오늘의 일진(천간지지)과 원국 합충 단서."""
    y, m, d = (int(x) for x in date_str.split("-"))
    lun = Solar.fromYmd(y, m, d).getLunar()
    gz = lun.getDayInGanZhi()
    today_zhi = gz[1] if len(gz) > 1 else ""
    chart_zhis = [ec.getYearZhi(), ec.getMonthZhi(), ec.getDayZhi()]
    return {
        "date": date_str,
        "ganZhi": gz,
        "ganElement": GAN_ELEMENT.get(gz[0], ""),
        "clash": _branch_relations(today_zhi, chart_zhis),
    }


# 지지 관계(삼합 반합·육합·충) 단서 산출
_LIUHE = {  # 육합
    frozenset(["子", "丑"]), frozenset(["寅", "亥"]), frozenset(["卯", "戌"]),
    frozenset(["辰", "酉"]), frozenset(["巳", "申"]), frozenset(["午", "未"]),
}
_CHONG = {  # 충
    frozenset(["子", "午"]), frozenset(["丑", "未"]), frozenset(["寅", "申"]),
    frozenset(["卯", "酉"]), frozenset(["辰", "戌"]), frozenset(["巳", "亥"]),
}
# 삼합 반합(두 글자 결합) — 그룹별 인접 반합
_BANHAP = {
    frozenset(["申", "子"]): "水", frozenset(["子", "辰"]): "水",
    frozenset(["寅", "午"]): "火", frozenset(["午", "戌"]): "火",
    frozenset(["巳", "酉"]): "金", frozenset(["酉", "丑"]): "金",
    frozenset(["亥", "卯"]): "木", frozenset(["卯", "未"]): "木",
}


def _branch_relations(zhi, chart_zhis):
    out = []
    for cz in chart_zhis:
        if not cz or cz == zhi:
            continue
        pair = frozenset([zhi, cz])
        if pair in _CHONG:
            out.append(f"{zhi}{cz} 충")
        elif pair in _LIUHE:
            out.append(f"{zhi}{cz} 육합")
        elif pair in _BANHAP:
            out.append(f"{zhi}{cz} {_BANHAP[pair]} 반합")
    return out


def _yongshin(ec, five_el):
    """용신·조후 후보(억부/조후) 단순 룰 산출.

    설계서 MVP 수준: 신약이면 일간 돕는 오행, 조후는 월지 한난조습 기준.
    """
    day_el = GAN_ELEMENT[ec.getDayGan()]
    SHENG = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}
    KE = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}
    strength = five_el["strength"]
    candidates = []
    if strength == "신약":
        candidates.append({
            "type": "억부", "element": SHENG[day_el],
            "reason": f"신약한 일간({day_el})을 생조하는 {SHENG[day_el]} 보강",
        })
        candidates.append({
            "type": "억부", "element": day_el,
            "reason": f"일간과 같은 {day_el}로 세력 보강",
        })
    elif strength == "신강":
        candidates.append({
            "type": "억부", "element": KE[day_el],
            "reason": f"신강한 일간({day_el})을 제어하는 {KE[day_el]}로 균형",
        })
    else:
        candidates.append({
            "type": "조후", "element": "통관",
            "reason": "중화 사주 — 부족한 오행을 채워 흐름을 잇는다",
        })
    # 조후: 월지로 계절 한난 판정
    month_zhi = ec.getMonthZhi()
    WINTER = {"亥", "子", "丑"}
    SUMMER = {"巳", "午", "未"}
    if month_zhi in WINTER:
        candidates.append({"type": "조후", "element": "火",
                           "reason": "겨울철 한기 — 火로 조후"})
    elif month_zhi in SUMMER:
        candidates.append({"type": "조후", "element": "水",
                           "reason": "여름철 조열 — 水로 조후"})
    elif month_zhi in {"寅", "卯", "辰"}:
        candidates.append({"type": "조후", "element": "火",
                           "reason": "이른 봄 한기 — 火로 온기 보강"})
    johu_desc = f"{month_zhi}월 출생 — 계절 기운으로 한난조습 판정"
    return {"johu": johu_desc, "candidates": candidates}


def _tojeong(ec, year):
    """토정비결 괘 산출(태세수 기반 144괘 — 상·중·하괘 + 월별).

    전통 토정비결 작괘법(상수/중수/하수)을 나이·생월·생일 기반으로 산출.
    공인 토정비결 책마다 미세 차이가 있어 MVP는 표준 산식 1종을 결정론 구현.
    """
    birth_year = ec.getLunar().getSolar().getYear()
    age = year - birth_year + 1  # 세는나이
    lun = ec.getLunar()
    birth_lunar_month = abs(lun.getMonth())
    birth_lunar_day = lun.getDay()

    # 태세수: 나이 + 해당년 태세(간지)수. 간단 결정론 산식.
    tae_se = ((age + year) % 8) + 1            # 상괘(1~8)
    wol_gun = ((birth_lunar_month + 6) % 6) + 1  # 중괘(1~6)
    il_jin = ((birth_lunar_day + 3) % 3) + 1     # 하괘(1~3)
    monthly = []
    for mo in range(1, 13):
        gwae = ((tae_se + wol_gun + il_jin + mo) % 6) + 1
        monthly.append({"month": mo, "gwae": str(gwae)})
    return {
        "year": year,
        "sangGwae": str(tae_se),
        "jungGwae": str(wol_gun),
        "haGwae": str(il_jin),
        "gwaeNumber": f"{tae_se}{wol_gun}{il_jin}",
        "monthly": monthly,
    }


# ─────────────────────────────────────────────────────────────────────────
# 6. 산출 카드 빌더 (공개 API)
# ─────────────────────────────────────────────────────────────────────────
def build_card(inp):
    """입력 dict → 산출 카드 dict (설계서 §4.2)."""
    true_dt, meta, hour_known = _resolve_solar_datetime(inp)
    early_late = inp.get("earlyLateZiShi", "standard")
    ref_year = inp.get("referenceYear")
    lunar, ec = _make_eightchar(true_dt, hour_known, early_late)

    five_el = _five_elements(ec, hour_known)
    card = {
        "brand": "samsin",
        "meta": meta,
        "input": {
            "gender": inp.get("gender"),
            "calendar": inp.get("calendar", "solar"),
            "birthDate": inp["birthDate"],
            "birthTime": inp.get("birthTime", "unknown"),
        },
        "pillars": _pillars(ec, hour_known),
        "dayMaster": _day_master(ec),
        "fiveElements": five_el,
        "tenGods": _ten_gods(ec, hour_known),
        "twelveStages": _twelve_stages(ec, hour_known),
        "napEum": _napyin(ec, hour_known),
        "taeWon": ec.getTaiYuan(),
        "mingGong": ec.getMingGong(),
        "shenGong": ec.getShenGong(),
        "majorShinsal": _major_shinsal(ec, hour_known),
        "daewoon": _daewoon(ec, inp.get("gender", "male"), ref_year),
        "yongshin": _yongshin(ec, five_el),
    }

    # 세운(기본 올해 또는 지정 연도)
    sew_year = inp.get("sewoonYear")
    if sew_year:
        card["sewoon"] = _sewoon(ec, int(sew_year))
        # referenceYear 미지정 시에만 sewoonYear를 현재대운 기준연도로 대체(하위호환)
        if ref_year is None:
            card["daewoon"]["current"] = _current_daewoon_for_year(
                card["daewoon"]["list"], ec, int(sew_year))
            card["daewoon"]["currentBasisYear"] = int(sew_year)

    # 오늘의운세(요청 시)
    today_date = inp.get("todayDate")
    if today_date:
        card["today"] = _today(ec, today_date)

    # 토정비결(요청 시)
    tojeong_year = inp.get("tojeongYear")
    if tojeong_year:
        card["tojeong"] = _tojeong(ec, int(tojeong_year))

    return card


def _current_daewoon_for_year(da_list, ec, year):
    birth_year = ec.getLunar().getSolar().getYear()
    age = year - birth_year + 1
    for d in da_list:
        if d["fromAge"] <= age <= d["toAge"]:
            return d
    return None


def build_compatibility(inp_a, inp_b):
    """궁합 2인 산출 — 두 사람 카드 + compatibility 분석."""
    card_a = build_card(inp_a)
    card_b = build_card(inp_b)

    gan_a = card_a["dayMaster"]["gan"]
    gan_b = card_b["dayMaster"]["gan"]
    zhi_a = card_a["pillars"]["day"]["zhi"]
    zhi_b = card_b["pillars"]["day"]["zhi"]

    # 일간 합/충
    GAN_HAP = {  # 천간합
        frozenset(["甲", "己"]), frozenset(["乙", "庚"]), frozenset(["丙", "辛"]),
        frozenset(["丁", "壬"]), frozenset(["戊", "癸"]),
    }
    gan_rel = "보통"
    if frozenset([gan_a, gan_b]) in GAN_HAP:
        gan_rel = "천간합(끌림)"

    # 일지 합충
    pair = frozenset([zhi_a, zhi_b])
    if pair in _CHONG:
        zhi_rel = "일지 충(긴장)"
    elif pair in _LIUHE:
        zhi_rel = "일지 육합(화합)"
    elif pair in _BANHAP:
        zhi_rel = f"일지 {_BANHAP[pair]} 반합(결속)"
    else:
        zhi_rel = "일지 무관계"

    # 오행 상호보완: 서로 부족한 오행을 채워주는가
    miss_a = set(card_a["fiveElements"]["missing"])
    miss_b = set(card_b["fiveElements"]["missing"])
    have_a = {k for k, v in card_a["fiveElements"]["count"].items() if v > 0}
    have_b = {k for k, v in card_b["fiveElements"]["count"].items() if v > 0}
    a_fills_b = miss_b & have_a
    b_fills_a = miss_a & have_b

    return {
        "personA": card_a,
        "personB": card_b,
        "compatibility": {
            "dayGanRelation": gan_rel,
            "dayZhiRelation": zhi_rel,
            "aFillsBElements": sorted(a_fills_b),
            "bFillsAElements": sorted(b_fills_a),
            "complementScore": len(a_fills_b) + len(b_fills_a),
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# 7. CLI
# ─────────────────────────────────────────────────────────────────────────
def _parse_args(argv):
    p = argparse.ArgumentParser(description="삼신이 만세력 엔진")
    p.add_argument("--mode", default="single",
                   choices=["single", "compatibility"])
    p.add_argument("--stdin", action="store_true", help="stdin JSON 입력")
    # 1인
    p.add_argument("--gender", choices=["male", "female"])
    p.add_argument("--calendar", default="solar", choices=["solar", "lunar"])
    p.add_argument("--leap", action="store_true", help="음력 윤달")
    p.add_argument("--date", help="YYYY-MM-DD")
    p.add_argument("--time", default="unknown", help="12지지 시 코드 또는 unknown")
    p.add_argument("--time-hm", help="HH:MM 직접(선택)")
    p.add_argument("--longitude", type=float, default=127.5)
    p.add_argument("--zishi", default="standard", choices=["standard", "split"])
    p.add_argument("--sewoon-year", type=int)
    p.add_argument("--reference-year", type=int,
                   help="대운 현재구간 기준연도(미지정 시 current=null — 결정론)")
    p.add_argument("--today-date")
    p.add_argument("--tojeong-year", type=int)
    # 2인(궁합)
    p.add_argument("--gender2", choices=["male", "female"])
    p.add_argument("--calendar2", default="solar", choices=["solar", "lunar"])
    p.add_argument("--leap2", action="store_true")
    p.add_argument("--date2")
    p.add_argument("--time2", default="unknown")
    return p.parse_args(argv)


def _args_to_input(args, suffix=""):
    g = getattr(args, "gender" + suffix)
    cal = getattr(args, "calendar" + suffix)
    leap = getattr(args, "leap" + suffix)
    date = getattr(args, "date" + suffix)
    time = getattr(args, "time" + suffix)
    inp = {
        "gender": g, "calendar": cal, "isLeapMonth": leap,
        "birthDate": date, "birthTime": time,
    }
    if not suffix:
        inp["birthLongitude"] = args.longitude
        inp["earlyLateZiShi"] = args.zishi
        if args.time_hm:
            inp["birthTimeHm"] = args.time_hm
        if args.sewoon_year:
            inp["sewoonYear"] = args.sewoon_year
        if args.reference_year:
            inp["referenceYear"] = args.reference_year
        if args.today_date:
            inp["todayDate"] = args.today_date
        if args.tojeong_year:
            inp["tojeongYear"] = args.tojeong_year
    return inp


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    args = _parse_args(argv)

    if args.stdin:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if payload.get("mode") == "compatibility":
            out = build_compatibility(payload["personA"], payload["personB"])
        else:
            out = build_card(payload)
    elif args.mode == "compatibility":
        out = build_compatibility(
            _args_to_input(args, ""), _args_to_input(args, "2"))
    else:
        if not args.date or not args.gender:
            print(json.dumps({
                "error": "필수 입력 누락",
                "need": "--gender, --date(YYYY-MM-DD) 필요. "
                        "--time은 12지지 코드(ja~hae) 또는 unknown.",
            }, ensure_ascii=False))
            return 2
        out = build_card(_args_to_input(args, ""))

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
