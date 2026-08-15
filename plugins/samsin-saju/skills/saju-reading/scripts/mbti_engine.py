#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbti_engine.py — 삼신이(samsin) 결정론 성향 엔진

설계서 docs/personality-engine-design.md 구현. 만세력 엔진(saju_engine.py)과 나란히 놓이는
두 번째 결정론 모듈. 만세력이 `생년월일시·성별 → (규칙) → 사주 카드`를 LLM 개입
0으로 고정하듯, 성향 엔진은 `유형/문항 입력 → (규칙) → 성향 카드`를 LLM 개입 0으로
고정한다.

★불변 원칙 (사주 로직과 완전 분리 · mbti_util.py 무접점 원칙 계승):
  - 엔진은 결정론적이다. 같은 입력 → 항상 같은 카드.
  - 모든 도출은 룩업 또는 산술(자유 생성·추론 없음). LLM·난수·시간·외부 IO 금지.
  - saju_engine.py를 import하지 않는다(무접점). 사주 로직과 물리 분리.
  - 산출 카드에는 면책 문구를 넣지 않는다(면책은 2층 AI 해석 강제 사항).
  - 표준 라이브러리만 사용.

★결정론 = 재현성 ≠ 과학적 타당성 (설계서 §4.1 안전 척추):
  성향 엔진의 결정론은 융(C.G. Jung) 심리유형론 기반 '이론 매핑'이라, 같은 입력을
  항상 같게 변환할 뿐 사람을 과학적으로 규정한다고 주장하지 않는다. 이 라벨은
  meta.note(_NOTE)에 4중으로 못 박는다.

CLI 계약 (saju_engine.py와 대칭):
  python mbti_engine.py --mode type --type INTJ
  echo '{"mode":"quiz","answers":{"EI":[-1,-1,1],"SN":[1,1,1],"TF":[1,-1,1],"JP":[1,1,-1]}}' \
      | python mbti_engine.py --stdin
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 파싱·유효성 유틸은 현행 mbti_util.py를 흡수·계승(설계서 §6.1·§8.3).
try:
    import mbti_util
except ImportError:
    from . import mbti_util  # type: ignore


# ─────────────────────────────────────────────────────────────────────────
# 0. 성격 라벨 상수 (⚑ 법무 확정 대기 — placeholder)
# ─────────────────────────────────────────────────────────────────────────
# ⚑ 법무 확정 대기(placeholder): "성격검사/과학적 진단 아님" 고지 문구는 법무
# 검토 항목(설계서 §4.3 R1·기획안 §7.2)이다. 최종 문구·법령 근거는 법무 팀장이
# 확정하며, 아래는 임의 확정이 아니라 설계서 §3.1·§3.2 meta.note 4중 라벨을 그대로
# 옮긴 자리표시자다. 확정 전까지 이 상수 1곳만 손보면 전체가 일괄 정합된다.
_NOTE = (
    "self-reported / theory-based mapping. NOT a saju fact. "
    "NOT a clinical test. tone/advice personalization only."
)

_AXIS_KEYS = ("EI", "SN", "TF", "JP")
# 각 축의 (앞글자=+, 뒷글자=−). 동점(0)은 규칙상 뒷글자로 고정(설계서 §3.4).
_AXIS_LETTERS = {"EI": ("E", "I"), "SN": ("S", "N"),
                 "TF": ("T", "F"), "JP": ("J", "P")}

# 인지기능 → 한국어 라벨(설계서 §3.1). i=내향, e=외향.
_FUNCTION_LABEL = {
    "Ni": "내향 직관", "Ne": "외향 직관",
    "Si": "내향 감각", "Se": "외향 감각",
    "Ti": "내향 사고", "Te": "외향 사고",
    "Fi": "내향 감정", "Fe": "외향 감정",
}


# ─────────────────────────────────────────────────────────────────────────
# 1. 인지기능 스택 결정론 도출 (설계서 §3.2-A 규약)
# ─────────────────────────────────────────────────────────────────────────
# 융 유형론의 확립된 스택 규칙을 산식으로 못 박는다(16유형 각각 유일 스택 결정).
# 규칙(설계서 §3.2-A):
#   1. 4번째 글자(J/P)가 '외부로 내보이는 기능'이 판단(T/F)이냐 인식(S/N)이냐를 정한다.
#      - J → 판단기능(T/F)을 외향으로 내보인다.
#      - P → 인식기능(S/N)을 외향으로 내보인다.
#   2. 주기능의 방향(i/e)은 1번째 글자(E/I)를 따른다.
#      - E이면 '외부로 내보이는 기능'이 곧 주기능(외향 주기능).
#      - I이면 '외부로 내보이는 기능'은 부기능이고, 주기능은 반대 범주의 내향.
#   3. 3차 = 부기능의 반대극(같은 범주 반대 방향은 아님 — 아래 대칭쌍 규약),
#      열등 = 주기능의 반대극(범주·방향 모두 반대).
#
# 결정론 유도(반례 없이 16유형 전수 산출):
#   - judging  = 'T' 또는 'F' 중 그 사람의 실제 글자(TF축).
#   - perceiving = 'S' 또는 'N' 중 그 사람의 실제 글자(SN축).
#   - J형: 외부로 내보이는(=외향) 기능은 judging → (judging)e. 내부(내향)는 perceiving → (perceiving)i.
#   - P형: 외부로 내보이는(=외향) 기능은 perceiving → (perceiving)e. 내부는 judging → (judging)i.
#   - E형: 주기능 = 외향 기능,  부기능 = 내향 기능.
#   - I형: 주기능 = 내향 기능,  부기능 = 외향 기능.
#   - 3차 = 부기능과 같은 방향 반대, 열등 = 주기능과 같은 방향 반대(대칭쌍).
#     기능 반대극쌍: N↔S, T↔F. 방향 반대: i↔e.
_OPPOSITE_FUNC = {"N": "S", "S": "N", "T": "F", "F": "T"}
_OPPOSITE_DIR = {"i": "e", "e": "i"}


def _cognitive_stack(type4):
    """4글자 유형 → 인지기능 스택 4단(주·부·3차·열등). 결정론 룩업/산식.

    반환: {"dominant":{function,label}, "auxiliary":..., "tertiary":..., "inferior":...}
    """
    ei, sn, tf, jp = type4[0], type4[1], type4[2], type4[3]
    judging = tf       # 'T' or 'F'
    perceiving = sn    # 'S' or 'N'

    # J/P → 외부로 내보이는(외향) 기능이 판단이냐 인식이냐를 정한다.
    if jp == "J":
        extraverted_func = judging      # judging을 외향으로
        introverted_func = perceiving   # perceiving은 내향
    else:  # 'P'
        extraverted_func = perceiving   # perceiving을 외향으로
        introverted_func = judging      # judging은 내향

    # E/I → 주·부기능 방향 결정.
    if ei == "E":
        dominant = extraverted_func + "e"
        auxiliary = introverted_func + "i"
    else:  # 'I'
        dominant = introverted_func + "i"
        auxiliary = extraverted_func + "e"

    # 3차 = 부기능의 반대극(기능 반대·방향 반대), 열등 = 주기능의 반대극.
    def opposite(func_dir):
        f, d = func_dir[0], func_dir[1]
        return _OPPOSITE_FUNC[f] + _OPPOSITE_DIR[d]

    tertiary = opposite(auxiliary)
    inferior = opposite(dominant)

    def node(fd):
        return {"function": fd, "label": _FUNCTION_LABEL[fd]}

    return {
        "dominant": node(dominant),
        "auxiliary": node(auxiliary),
        "tertiary": node(tertiary),
        "inferior": node(inferior),
    }


# ─────────────────────────────────────────────────────────────────────────
# 2. 파생 성향 태그 결정론 도출 (설계서 §3.3)
# ─────────────────────────────────────────────────────────────────────────
# 각 태그는 단일 축을 룩업한다(축 조합 아님 — 결정론·투명성). 라벨은 mbti-layer
# §1.3 번역 사전('성향결' 언어)과 정합하는 고정 문자열. 유형코드·축코드는 태그
# 문자열에 들어가지 않는다(가드 5 정합).
_TRAIT_TABLE = {
    "decision": {  # TF축
        "T": "따져 납득하는 결", "F": "마음·관계를 먼저 보는 결"},
    "communication": {  # EI축
        "E": "사람들과 나누며 꺼내는 결", "I": "혼자 정리해 꺼내는 결"},
    "energy": {  # EI축
        "E": "사람 사이서 채우는 결", "I": "안으로 채우는 결"},
    "execution": {  # JP축
        "J": "계획해 두는 결", "P": "마음 가는 대로 가는 결"},
}


def _trait_tags(axes):
    """4축 분해(axes dict) → 파생 성향 태그 4결. 단일 축 룩업."""
    return {
        "decision": _TRAIT_TABLE["decision"][axes["TF"]],
        "communication": _TRAIT_TABLE["communication"][axes["EI"]],
        "energy": _TRAIT_TABLE["energy"][axes["EI"]],
        "execution": _TRAIT_TABLE["execution"][axes["JP"]],
    }


# ─────────────────────────────────────────────────────────────────────────
# 3. 문항 채점·선호 명확도 산식 (경로 b · 설계서 §3.4)
# ─────────────────────────────────────────────────────────────────────────
def _score_axis(responses):
    """축 문항 응답 리스트 → (선호 글자, clarity, 축점수).

    - 축 점수 = 방향값(±1) 합산 ∈ [−N, +N].
    - 선호 방향 = 부호. 양수면 앞글자, 음수면 뒷글자. 0(동점)이면 뒷글자 고정.
    - clarity = |축점수| / N ∈ [0,1].
    호출부에서 축 키(EI/SN/TF/JP)에 맞춰 글자를 매핑한다.
    """
    n = len(responses)
    total = sum(responses)
    clarity = abs(total) / n if n else 0.0
    return total, clarity


def _parse_quiz(answers):
    """문항 응답 dict → (type4, axes, preferenceClarity) 또는 무효 시 None.

    4축 모두 존재하고 각 축이 비지 않은 정수 리스트여야 유효(설계서 §3.4).
    """
    if not isinstance(answers, dict):
        return None
    axes = {}
    clarity = {}
    for key in _AXIS_KEYS:
        resp = answers.get(key)
        if not isinstance(resp, (list, tuple)) or len(resp) == 0:
            return None
        try:
            resp_int = [int(x) for x in resp]
        except (TypeError, ValueError):
            return None
        total, clr = _score_axis(resp_int)
        front, back = _AXIS_LETTERS[key]
        # 양수면 앞글자, 음수/0이면 뒷글자(동점 뒷글자 고정 — 재현 보장).
        axes[key] = front if total > 0 else back
        clarity[key] = round(clr, 10)  # 부동소수 재현성 안정화
    type4 = "".join(axes[k] for k in _AXIS_KEYS)
    return type4, axes, clarity


# ─────────────────────────────────────────────────────────────────────────
# 4. dominantAxes·confidence 산출 (설계서 §3.2)
# ─────────────────────────────────────────────────────────────────────────
# 경로(a) 유형 직접: 규칙표 우선순위. clarity 정보가 없으므로 고정 우선순위로
# 가장 성향 서술에 도드라지는 2축을 짚는다(SN=인지 방향, EI=에너지 방향 우선).
_AXES_PRIORITY = ("SN", "EI", "TF", "JP")


def _dominant_axes_from_priority():
    return list(_AXES_PRIORITY[:2])


def _dominant_axes_from_clarity(clarity):
    # clarity 상위 2축(동률이면 _AXES_PRIORITY 순서로 안정 정렬 — 재현 보장).
    ordered = sorted(
        _AXIS_KEYS,
        key=lambda k: (-clarity[k], _AXES_PRIORITY.index(k)))
    return ordered[:2]


# ─────────────────────────────────────────────────────────────────────────
# 5. 미제공 카드 (강등 — 예외 없음, mbti_util 계승)
# ─────────────────────────────────────────────────────────────────────────
def _not_provided(input_mode=None):
    """미제공/무효 입력의 표준 성향 카드(provided:false — 사주 단독 폴백 신호)."""
    return {
        "brand": "samsin",
        "engine": "mbti_engine",
        "meta": {
            "inputMode": input_mode,
            "provided": False,
            "note": _NOTE,
        },
        "type": None,
        "axes": None,
        "preferenceClarity": None,
        "cognitiveStack": None,
        "traitTags": None,
        "dominantAxes": None,
        "confidence": {"level": "not_provided", "score": None},
    }


# ─────────────────────────────────────────────────────────────────────────
# 6. 성향 카드 빌더 (공개 API)
# ─────────────────────────────────────────────────────────────────────────
def build_mbti_card(inp):
    """입력 dict → 성향 카드 dict. 같은 입력 → 항상 같은 카드(LLM 개입 0).

    inp["mode"] == "type" : inp["type"](4글자) 기반 경로(a)
    inp["mode"] == "quiz" : inp["answers"](축별 응답) 기반 경로(b)
    무효/미입력 → provided:false 카드(강등 — 예외 없음, 설계서 §6.2).
    """
    if not isinstance(inp, dict):
        return _not_provided(None)

    mode = inp.get("mode")

    if mode == "quiz":
        parsed = _parse_quiz(inp.get("answers"))
        if parsed is None:
            return _not_provided("quiz")
        type4, axes, clarity = parsed
        confidence_level = "quiz_derived"
        confidence_score = round(sum(clarity.values()) / 4.0, 10)
        preference_clarity = clarity
        dominant_axes = _dominant_axes_from_clarity(clarity)
    elif mode == "type":
        type4 = mbti_util.parse_mbti_type(inp.get("type"))
        if type4 is None:
            return _not_provided("type")
        axes = {k: ch for k, ch in zip(_AXIS_KEYS, type4)}
        confidence_level = "self_declared"
        confidence_score = None
        preference_clarity = None  # 직접 입력은 강도 정보 없음
        dominant_axes = _dominant_axes_from_priority()
    else:
        return _not_provided(mode)

    # 수렴 지점: 4글자 확정 후 스택·태그 도출은 두 경로 공통 규칙(분기 없음).
    return {
        "brand": "samsin",
        "engine": "mbti_engine",
        "meta": {
            "inputMode": mode,
            "provided": True,
            "note": _NOTE,
        },
        "type": type4,
        "axes": axes,
        "preferenceClarity": preference_clarity,
        "cognitiveStack": _cognitive_stack(type4),
        "traitTags": _trait_tags(axes),
        "dominantAxes": dominant_axes,
        "confidence": {"level": confidence_level, "score": confidence_score},
    }


# ─────────────────────────────────────────────────────────────────────────
# 7. CLI (saju_engine.py와 대칭)
# ─────────────────────────────────────────────────────────────────────────
def _parse_args(argv):
    p = argparse.ArgumentParser(description="삼신이 성향 엔진")
    p.add_argument("--mode", default="type", choices=["type", "quiz"])
    p.add_argument("--type", help="4글자 유형(예: INTJ) — mode type")
    p.add_argument("--stdin", action="store_true",
                   help="stdin JSON 입력({mode, type|answers})")
    return p.parse_args(argv)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    args = _parse_args(argv)

    if args.stdin:
        payload = json.loads(sys.stdin.read())
        out = build_mbti_card(payload)
    elif args.mode == "type":
        if not args.type:
            print(json.dumps({
                "error": "필수 입력 누락",
                "need": "--type <4글자 유형> 필요(mode type). "
                        "또는 --stdin으로 {mode:quiz, answers:{...}} 전달.",
            }, ensure_ascii=False))
            return 2
        out = build_mbti_card({"mode": "type", "type": args.type})
    else:  # quiz는 stdin JSON으로만(문항 배열 CLI 전달은 비실용)
        print(json.dumps({
            "error": "quiz 모드는 --stdin JSON으로 전달하세요",
            "example": '{"mode":"quiz","answers":{"EI":[-1,-1,1],'
                       '"SN":[1,1,1],"TF":[1,-1,1],"JP":[1,1,-1]}}',
        }, ensure_ascii=False))
        return 2

    print(json.dumps({"mbti_card": out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
