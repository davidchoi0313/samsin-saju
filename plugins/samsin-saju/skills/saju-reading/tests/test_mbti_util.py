# -*- coding: utf-8 -*-
"""
test_mbti_util.py — MBTI 자기보고 레이어 유틸 테스트 (TDD 빨강 우선)

계약: reference/mbti-layer.md §2 스키마 정합.
MBTI는 엔진 밖 자기보고 레이어이며, 이 유틸은 순수 파싱·검증만 한다.
사주 로직(saju_engine.py)과 무접점 — import조차 하지 않는다.

실행:  python3 test_mbti_util.py
표준 라이브러리 unittest만 사용(외부 러너 불요).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import mbti_util  # noqa: E402


class TestValidType(unittest.TestCase):
    """유효한 16유형은 provided:true로 파싱된다."""

    def test_intj_upper(self):
        p = mbti_util.build_mbti_profile("INTJ")
        self.assertTrue(p["provided"])
        self.assertEqual(p["type"], "INTJ")
        self.assertEqual(p["axes"], {"EI": "I", "SN": "N", "TF": "T", "JP": "J"})
        self.assertEqual(p["source"], "self_report")
        self.assertIsNone(p["axis_strength"])

    def test_lowercase_normalized(self):
        """소문자 입력도 대문자로 정규화된다."""
        p = mbti_util.build_mbti_profile("enfp")
        self.assertTrue(p["provided"])
        self.assertEqual(p["type"], "ENFP")
        self.assertEqual(p["axes"], {"EI": "E", "SN": "N", "TF": "F", "JP": "P"})

    def test_whitespace_stripped(self):
        p = mbti_util.build_mbti_profile("  estp  ")
        self.assertTrue(p["provided"])
        self.assertEqual(p["type"], "ESTP")

    def test_all_16_types_valid(self):
        """16유형 전부 provided:true."""
        types = [a + b + c + d
                 for a in "EI" for b in "SN" for c in "TF" for d in "JP"]
        self.assertEqual(len(types), 16)
        for t in types:
            self.assertTrue(mbti_util.build_mbti_profile(t)["provided"], t)


class TestInvalidType(unittest.TestCase):
    """무효 입력은 provided:false로 강등(강등만, 예외 없음)."""

    def test_none(self):
        p = mbti_util.build_mbti_profile(None)
        self.assertFalse(p["provided"])
        self.assertIsNone(p["type"])

    def test_empty(self):
        self.assertFalse(mbti_util.build_mbti_profile("")["provided"])

    def test_unknown_string(self):
        """모름/미상 류는 강등."""
        for s in ["모름", "몰라", "unknown", "?"]:
            self.assertFalse(mbti_util.build_mbti_profile(s)["provided"], s)

    def test_wrong_length(self):
        self.assertFalse(mbti_util.build_mbti_profile("INT")["provided"])
        self.assertFalse(mbti_util.build_mbti_profile("INTJX")["provided"])

    def test_wrong_axis_letters(self):
        """자리별 허용 글자가 아니면 강등 (예: 첫 자리 X)."""
        self.assertFalse(mbti_util.build_mbti_profile("XNTJ")["provided"])
        self.assertFalse(mbti_util.build_mbti_profile("IETJ")["provided"])  # 2번째 자리 E 불가


class TestSchemaContract(unittest.TestCase):
    """reference/mbti-layer.md §2 스키마 필드 계약."""

    def test_field_keys_present(self):
        p = mbti_util.build_mbti_profile("ISFJ")
        for k in ["provided", "type", "axes", "axis_strength", "source", "note"]:
            self.assertIn(k, p, k)

    def test_source_always_self_report(self):
        """source는 항상 self_report 고정 (엔진 산출 아님을 못박음)."""
        self.assertEqual(mbti_util.build_mbti_profile("INTJ")["source"], "self_report")
        self.assertEqual(mbti_util.build_mbti_profile("모름")["source"], "self_report")

    def test_note_marks_not_saju_fact(self):
        """note에 '사주 사실 아님' 취지 표기."""
        note = mbti_util.build_mbti_profile("INTJ")["note"].lower()
        self.assertIn("not a saju fact", note)

    def test_no_engine_import(self):
        """엔진 무접점 — mbti_util은 saju_engine·달력 라이브러리를 import하지 않는다.

        docstring 설명 언급이 아니라 실제 import 구문 줄만 검사한다.
        """
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "mbti_util.py")
        with open(src_path, encoding="utf-8") as f:
            lines = f.readlines()
        imports = []
        for ln in lines:
            s = ln.strip()
            if s.startswith("import ") or s.startswith("from "):
                imports.append(s)
        joined = "\n".join(imports)
        self.assertNotIn("saju_engine", joined)
        self.assertNotIn("lunar", joined)
        self.assertNotIn("jijanggan", joined)
        self.assertNotIn("shinsal", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
