# -*- coding: utf-8 -*-
"""
mbti_util.py — MBTI 자기보고 레이어 파싱·검증 유틸 (엔진 무접점)

계약: reference/mbti-layer.md §2 스키마.

★불변 원칙 (사주 로직과 완전 분리):
- MBTI는 만세력 엔진(saju_engine.py) 밖의 '자기보고 입력 레이어'다.
- 이 파일은 순수 문자열 파싱·검증만 한다. 사주 로직·엔진·달력 라이브러리를
  import하지 않는다(무접점). 결정론 엔진은 이 파일과 아무 관계가 없다.
- MBTI는 톤·조언 개인화 힌트로만 쓰이며, 사주 사실 근거가 아니다.
  source는 항상 "self_report"로 고정해 그 성격을 스키마 레벨에서 못박는다.

표준 라이브러리만 사용.
"""

# 16유형의 자리별 허용 글자 (E/I·S/N·T/F·J/P)
_AXIS_ALLOWED = (("E", "I"), ("S", "N"), ("T", "F"), ("J", "P"))
_AXIS_KEYS = ("EI", "SN", "TF", "JP")

_NOTE = "self-reported. NOT a saju fact. tone/advice personalization only."


def _not_provided():
    """미제공/무효 입력의 표준 프로파일(강등 — 예외를 던지지 않음)."""
    return {
        "provided": False,
        "type": None,
        "axes": None,
        "axis_strength": None,
        "source": "self_report",
        "note": _NOTE,
    }


def parse_mbti_type(raw):
    """입력 문자열을 4글자 대문자 유형으로 정규화하거나, 무효면 None 반환.

    - None·빈 문자열·공백만·"모름" 등 → None (강등)
    - 대소문자·앞뒤 공백은 정규화
    - 길이 4 + 자리별 허용 글자를 모두 만족해야 유효
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip().upper()
    if len(s) != 4:
        return None
    for ch, allowed in zip(s, _AXIS_ALLOWED):
        if ch not in allowed:
            return None
    return s


def build_mbti_profile(raw):
    """자기보고 입력(raw)을 계약(§2) 스키마의 mbti_profile 객체로 만든다.

    유효한 16유형이면 provided:true, 아니면 provided:false(강등).
    강등 시에도 예외 없이 안전한 기본 객체를 반환한다(호출부 오염 방지).
    """
    t = parse_mbti_type(raw)
    if t is None:
        return _not_provided()
    axes = {key: ch for key, ch in zip(_AXIS_KEYS, t)}
    return {
        "provided": True,
        "type": t,
        "axes": axes,
        "axis_strength": None,  # v2 후보. MVP는 4축 코드만.
        "source": "self_report",  # 고정 — 엔진 산출 아님을 못박음.
        "note": _NOTE,
    }


if __name__ == "__main__":
    import json
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps({"mbti_profile": build_mbti_profile(arg)},
                     ensure_ascii=False, indent=2))
