# -*- coding: utf-8 -*-
"""
test_mbti_engine.py — 성향 엔진(mbti_engine.py) 재현성·정합 테스트

mebric-flow-tdd 결로: 이 테스트가 구현보다 먼저 작성됐다(빨강). 검증 대상:
  1. 재현성 — 같은 입력 2회 호출 → 완전히 동일한 카드(결정론 보증, 설계서 §2.3)
  2. 16유형 전수 인지기능 스택 — 설계서 §3.2-A 규약대로 유일 스택 결정
  3. 두 입력 경로 수렴 — 유형 직접(a) vs 문항(b)이 같은 4글자면 스택·태그 동일(설계서 §2.2)
  4. 문항 채점 산식 — 부호 판정·clarity·동점 뒷글자 고정(설계서 §3.4)
  5. 미제공 강등 — 무효/미입력 → provided:false(설계서 §6.2, mbti_util 계승)
  6. 스키마 계약 — 카드 필드·meta.note 4중 라벨(설계서 §3.1)
  7. 표현 전환 계약 — traitTags에 유형코드·축코드 문자열 미포함(가드 5 정합)

표준 라이브러리(unittest)만 사용. 외부 IO·난수·시간 없음.
실행:  python test_mbti_engine.py     (또는 python -m unittest test_mbti_engine)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mbti_engine  # noqa: E402


# 16유형 전수 인지기능 스택 기대값 — 융 유형론 확립 규약(설계서 §3.2-A).
# (dominant, auxiliary, tertiary, inferior) 기능 코드.
EXPECTED_STACKS = {
    "ISTJ": ("Si", "Te", "Fi", "Ne"),
    "ISFJ": ("Si", "Fe", "Ti", "Ne"),
    "INFJ": ("Ni", "Fe", "Ti", "Se"),
    "INTJ": ("Ni", "Te", "Fi", "Se"),
    "ISTP": ("Ti", "Se", "Ni", "Fe"),
    "ISFP": ("Fi", "Se", "Ni", "Te"),
    "INFP": ("Fi", "Ne", "Si", "Te"),
    "INTP": ("Ti", "Ne", "Si", "Fe"),
    "ESTP": ("Se", "Ti", "Fe", "Ni"),
    "ESFP": ("Se", "Fi", "Te", "Ni"),
    "ENFP": ("Ne", "Fi", "Te", "Si"),
    "ENTP": ("Ne", "Ti", "Fe", "Si"),
    "ESTJ": ("Te", "Si", "Ne", "Fi"),
    "ESFJ": ("Fe", "Si", "Ne", "Ti"),
    "ENFJ": ("Fe", "Ni", "Se", "Ti"),
    "ENTJ": ("Te", "Ni", "Se", "Fi"),
}

ALL_TYPES = list(EXPECTED_STACKS.keys())


def _stack_tuple(card):
    cs = card["cognitiveStack"]
    return (cs["dominant"]["function"], cs["auxiliary"]["function"],
            cs["tertiary"]["function"], cs["inferior"]["function"])


class TestReproducibility(unittest.TestCase):
    """1. 재현성 — 같은 입력 → 항상 같은 카드."""

    def test_type_path_same_input_same_card(self):
        inp = {"mode": "type", "type": "INTJ"}
        c1 = mbti_engine.build_mbti_card(inp)
        c2 = mbti_engine.build_mbti_card(inp)
        self.assertEqual(c1, c2)

    def test_quiz_path_same_input_same_card(self):
        inp = {"mode": "quiz", "answers": {
            "EI": [-1, -1, +1], "SN": [+1, +1, +1],
            "TF": [+1, -1, +1], "JP": [+1, +1, -1]}}
        c1 = mbti_engine.build_mbti_card(inp)
        c2 = mbti_engine.build_mbti_card(inp)
        self.assertEqual(c1, c2)

    def test_all_16_types_reproducible(self):
        for t in ALL_TYPES:
            inp = {"mode": "type", "type": t}
            self.assertEqual(mbti_engine.build_mbti_card(inp),
                             mbti_engine.build_mbti_card(inp),
                             f"{t} 재현성 위반")


class TestCognitiveStack(unittest.TestCase):
    """2. 16유형 전수 인지기능 스택 — 설계서 §3.2-A 규약."""

    def test_all_16_stacks_match_design(self):
        for t in ALL_TYPES:
            card = mbti_engine.build_mbti_card({"mode": "type", "type": t})
            self.assertEqual(_stack_tuple(card), EXPECTED_STACKS[t],
                             f"{t} 스택 불일치: {_stack_tuple(card)} != {EXPECTED_STACKS[t]}")

    def test_intj_example_matches_spec(self):
        # 설계서 §3.1 예시: INTJ → Ni·Te·Fi·Se
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        self.assertEqual(_stack_tuple(card), ("Ni", "Te", "Fi", "Se"))

    def test_stack_has_korean_labels(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        self.assertEqual(card["cognitiveStack"]["dominant"]["label"], "내향 직관")
        self.assertEqual(card["cognitiveStack"]["inferior"]["label"], "외향 감각")


class TestPathConvergence(unittest.TestCase):
    """3. 두 입력 경로 수렴 — 4글자 확정 시점부터 스택·태그 동일(설계서 §2.2)."""

    def test_quiz_and_type_converge_on_stack_and_tags(self):
        # 문항이 ISTJ로 확정되는 입력 (설계서 §6.3 예시)
        quiz = {"mode": "quiz", "answers": {
            "EI": [-1, -1, +1], "SN": [+1, +1, +1],
            "TF": [+1, -1, +1], "JP": [+1, +1, -1]}}
        card_q = mbti_engine.build_mbti_card(quiz)
        card_t = mbti_engine.build_mbti_card({"mode": "type", "type": "ISTJ"})
        self.assertEqual(card_q["type"], "ISTJ")
        # 수렴: 스택·태그·axes 동일
        self.assertEqual(_stack_tuple(card_q), _stack_tuple(card_t))
        self.assertEqual(card_q["traitTags"], card_t["traitTags"])
        self.assertEqual(card_q["axes"], card_t["axes"])

    def test_only_clarity_and_confidence_differ(self):
        # 두 경로의 차이는 preferenceClarity(a=null, b=산출)·confidence.level뿐
        quiz = {"mode": "quiz", "answers": {
            "EI": [-1, -1, +1], "SN": [+1, +1, +1],
            "TF": [+1, -1, +1], "JP": [+1, +1, -1]}}
        card_q = mbti_engine.build_mbti_card(quiz)
        card_t = mbti_engine.build_mbti_card({"mode": "type", "type": "ISTJ"})
        self.assertIsNone(card_t["preferenceClarity"])
        self.assertIsNotNone(card_q["preferenceClarity"])
        self.assertEqual(card_t["confidence"]["level"], "self_declared")
        self.assertEqual(card_q["confidence"]["level"], "quiz_derived")


class TestQuizScoring(unittest.TestCase):
    """4. 문항 채점 산식 — 부호·clarity·동점 뒷글자 고정(설계서 §3.4·§6.3)."""

    def test_spec_example_istj(self):
        # 설계서 §6.3 검산: EI 합 -1→I / SN 합 +3→S / TF 합 +1→T / JP 합 +1→J
        inp = {"mode": "quiz", "answers": {
            "EI": [-1, -1, +1], "SN": [+1, +1, +1],
            "TF": [+1, -1, +1], "JP": [+1, +1, -1]}}
        card = mbti_engine.build_mbti_card(inp)
        self.assertEqual(card["type"], "ISTJ")
        pc = card["preferenceClarity"]
        self.assertAlmostEqual(pc["EI"], 1 / 3, places=4)
        self.assertAlmostEqual(pc["SN"], 1.0, places=4)
        self.assertAlmostEqual(pc["TF"], 1 / 3, places=4)
        self.assertAlmostEqual(pc["JP"], 1 / 3, places=4)
        # confidence.score = 4축 clarity 평균 ≈ 0.50
        self.assertAlmostEqual(card["confidence"]["score"], (1/3 + 1.0 + 1/3 + 1/3) / 4, places=4)

    def test_tie_resolves_to_second_letter(self):
        # 동점(합 0)이면 규칙상 뒷글자로 고정(I/N/F/P) — 재현 보장(설계서 §3.4)
        inp = {"mode": "quiz", "answers": {
            "EI": [+1, -1], "SN": [+1, -1],
            "TF": [+1, -1], "JP": [+1, -1]}}
        card = mbti_engine.build_mbti_card(inp)
        self.assertEqual(card["type"], "INFP")  # 전부 동점 → 뒷글자

    def test_clarity_zero_on_tie(self):
        inp = {"mode": "quiz", "answers": {
            "EI": [+1, -1], "SN": [+1, +1],
            "TF": [-1, -1], "JP": [+1, -1]}}
        card = mbti_engine.build_mbti_card(inp)
        self.assertAlmostEqual(card["preferenceClarity"]["EI"], 0.0, places=4)
        self.assertAlmostEqual(card["preferenceClarity"]["JP"], 0.0, places=4)


class TestNotProvided(unittest.TestCase):
    """5. 미제공 강등 — 무효/미입력 → provided:false(설계서 §6.2)."""

    def test_empty_input(self):
        card = mbti_engine.build_mbti_card({})
        self.assertFalse(card["meta"]["provided"])

    def test_invalid_type(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "XXXX"})
        self.assertFalse(card["meta"]["provided"])

    def test_none_input(self):
        card = mbti_engine.build_mbti_card(None)
        self.assertFalse(card["meta"]["provided"])

    def test_quiz_missing_axis(self):
        # 축 하나가 빠지면 강등(문항 경로 무효)
        card = mbti_engine.build_mbti_card({"mode": "quiz", "answers": {"EI": [1]}})
        self.assertFalse(card["meta"]["provided"])

    def test_not_provided_card_has_no_stack(self):
        card = mbti_engine.build_mbti_card({})
        self.assertIsNone(card.get("cognitiveStack"))
        self.assertIsNone(card.get("type"))


class TestSchemaContract(unittest.TestCase):
    """6. 스키마 계약 — 카드 필드·meta.note 4중 라벨(설계서 §3.1)."""

    def test_card_top_level_fields(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        for f in ("brand", "engine", "meta", "type", "axes",
                  "preferenceClarity", "cognitiveStack", "traitTags",
                  "dominantAxes", "confidence"):
            self.assertIn(f, card, f"필드 누락: {f}")
        self.assertEqual(card["brand"], "samsin")
        self.assertEqual(card["engine"], "mbti_engine")

    def test_meta_note_quadruple_label(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        note = card["meta"]["note"]
        # 4중 라벨: 자기보고 / 이론 기반 / 사주 사실 아님 / 임상검사 아님
        self.assertIn("self-reported", note)
        self.assertIn("theory-based", note)
        self.assertIn("NOT a saju fact", note)
        self.assertIn("NOT a clinical test", note)

    def test_trait_tags_four_keys(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        for k in ("decision", "communication", "energy", "execution"):
            self.assertIn(k, card["traitTags"])

    def test_trait_tags_match_spec_labels(self):
        # 설계서 §3.3 규칙: INTJ = T·I·I·J → 따져/혼자정리/안으로/계획
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        tt = card["traitTags"]
        self.assertEqual(tt["decision"], "따져 납득하는 결")
        self.assertEqual(tt["communication"], "혼자 정리해 꺼내는 결")
        self.assertEqual(tt["energy"], "안으로 채우는 결")
        self.assertEqual(tt["execution"], "계획해 두는 결")


class TestExpressionSwitchContract(unittest.TestCase):
    """7. 표현 전환 계약 — traitTags 문자열에 유형코드·축코드 미포함(가드 5)."""

    FORBIDDEN = ALL_TYPES + ["MBTI", "EI", "SN", "TF", "JP",
                             "외향형", "내향형"]

    def test_trait_tags_have_no_type_or_axis_codes(self):
        # traitTags는 2층이 그대로 서술에 써도 노출 0이어야 함(설계서 §3.3).
        for t in ALL_TYPES:
            card = mbti_engine.build_mbti_card({"mode": "type", "type": t})
            for tag_value in card["traitTags"].values():
                for forbidden in self.FORBIDDEN:
                    self.assertNotIn(forbidden, tag_value,
                                     f"{t} traitTags에 금지어 노출: {forbidden}")


class TestDominantAxes(unittest.TestCase):
    """dominantAxes — (a) 규칙표 우선순위 / (b) clarity 상위(설계서 §3.2)."""

    def test_quiz_dominant_axes_is_clarity_top(self):
        # SN만 뚜렷(clarity 1.0)한 §6.3 예시 → dominantAxes에 SN
        inp = {"mode": "quiz", "answers": {
            "EI": [-1, -1, +1], "SN": [+1, +1, +1],
            "TF": [+1, -1, +1], "JP": [+1, +1, -1]}}
        card = mbti_engine.build_mbti_card(inp)
        self.assertIn("SN", card["dominantAxes"])

    def test_type_dominant_axes_present(self):
        card = mbti_engine.build_mbti_card({"mode": "type", "type": "INTJ"})
        self.assertTrue(len(card["dominantAxes"]) >= 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
