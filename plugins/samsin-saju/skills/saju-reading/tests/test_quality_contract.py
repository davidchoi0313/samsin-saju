# -*- coding: utf-8 -*-
"""고객용 한국어 결과물 품질 계약 검증기 테스트.

실행:
    python3 -m unittest discover -s tests -p 'test_*.py'

표준 라이브러리만 사용한다. 실제 프롬프트 트리를 한 번 검증하고, 임시 복사본을
일부러 훼손해 핵심 회귀가 정확한 코드로 잡히는지도 확인한다.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import quality_contract  # noqa: E402


def finding_codes(findings):
    return {finding.code for finding in findings}


class PromptContractTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo_root = Path(self.tempdir.name) / "repo"
        self.plugin_root = self.repo_root / "plugins" / "samsin-saju"
        self.root = self.plugin_root / "skills" / "saju-reading"
        shutil.copytree(SKILL_ROOT, self.root)

        source_plugin_root = SKILL_ROOT.parents[1]
        source_repo_root = SKILL_ROOT.parents[3]
        for relative in (
            Path(".claude-plugin/plugin.json"),
            Path(".codex-plugin/plugin.json"),
        ):
            destination = self.plugin_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_plugin_root / relative, destination)

        marketplace_relative = Path(".agents/plugins/marketplace.json")
        marketplace_destination = self.repo_root / marketplace_relative
        marketplace_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_repo_root / marketplace_relative, marketplace_destination)

    def validate(self):
        return quality_contract.validate_prompt_contract(self.root)

    def rewrite(self, relative_path, transform):
        path = self.root / relative_path
        self.rewrite_path(path, transform)

    def rewrite_path(self, path, transform):
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        self.assertNotEqual(updated, original, "테스트 훼손 변환이 실제 파일을 바꾸지 못했습니다.")
        path.write_text(updated, encoding="utf-8")


class TestLivePromptContract(unittest.TestCase):
    def test_repository_prompt_contract_passes(self):
        findings = quality_contract.validate_prompt_contract(SKILL_ROOT)
        self.assertEqual([], findings, "\n" + "\n".join(item.render() for item in findings))

    def test_cli_passes_for_repository_tree(self):
        self.assertEqual(0, quality_contract.main(["--root", str(SKILL_ROOT)]))


class TestPromptRegressionDetection(PromptContractTestCase):
    def test_missing_menu_is_blocked(self):
        (self.root / "menus" / "08-yeonae.md").unlink()
        self.assertIn("MENU_FILE_MISSING", finding_codes(self.validate()))

    def test_missing_action_library_is_blocked(self):
        (self.root / "reference" / "action-library.md").unlink()
        self.assertIn("ACTION_LIBRARY_FILE_MISSING", finding_codes(self.validate()))

    def test_common_disclaimer_drift_is_blocked(self):
        self.rewrite(
            "menus/13-geongang.md",
            lambda text: text.replace(quality_contract.COMMON_DISCLAIMER, "짧은 참고 문구", 1),
        )
        self.assertIn("MENU_COMMON_DISCLAIMER", finding_codes(self.validate()))

    def test_action_choice_count_removal_is_blocked(self):
        self.rewrite(
            "menus/01-pyeongsaeng.md",
            lambda text: text.replace(
                text[text.index("## 실행 설계") : text.index("## 권장 밀도")],
                "## 실행 설계\n\n마음가짐을 잘 정리한다.\n\n",
                1,
            ),
        )
        self.assertIn("MENU_ACTION_CARD_CONTRACT", finding_codes(self.validate()))

    def test_easy_korean_contract_removal_is_blocked(self):
        self.rewrite(
            "reference/output-contract.md",
            lambda text: text.replace("친근하고 또렷한 현대식 반말", "대본 같은 고어", 1),
        )
        self.assertIn("OUTPUT_CONTRACT_RESPECT", finding_codes(self.validate()))

    def test_brand_source_change_requires_all_prompts_to_follow(self):
        self.rewrite(
            "reference/brand.md",
            lambda text: text.replace("| `BRAND_KO` | 삼신이 |", "| `BRAND_KO` | 새브랜드 |", 1),
        )
        codes = finding_codes(self.validate())
        self.assertIn("SKILL_BRAND_MISMATCH", codes)

    def test_hiring_structured_questions_removal_is_blocked(self):
        self.rewrite(
            "menus/15-injae-chaeyong.md",
            lambda text: text.replace("질문 3개", "질문 몇 개"),
        )
        self.assertIn("MENU_HIRING_ACTION", finding_codes(self.validate()))

    def test_special_medical_disclaimer_drift_is_blocked(self):
        self.rewrite(
            "menus/13-geongang.md",
            lambda text: text.replace(quality_contract.MEDICAL_DISCLAIMER, "건강은 참고만 하세요.", 1),
        )
        self.assertIn("MENU_MEDICAL_DISCLAIMER", finding_codes(self.validate()))

    def test_special_disclaimer_after_common_disclaimer_is_blocked(self):
        self.rewrite(
            "menus/13-geongang.md",
            lambda text: text.replace(
                f"> {quality_contract.MEDICAL_DISCLAIMER}\n\n"
                f"> {quality_contract.COMMON_DISCLAIMER}",
                f"> {quality_contract.COMMON_DISCLAIMER}\n\n"
                f"> {quality_contract.MEDICAL_DISCLAIMER}",
                1,
            ),
        )
        self.assertIn("MENU_DISCLAIMER_ORDER", finding_codes(self.validate()))

    def test_optional_input_form_copy_is_guarded(self):
        self.rewrite(
            "reference/input-form.html",
            lambda text: text.replace("적지 않아도 괜찮아", "반드시 적어줘", 1),
        )
        self.assertIn("INPUT_FORM_OPTIONAL_NAME", finding_codes(self.validate()))

    def test_personality_code_privacy_contract_is_guarded(self):
        self.rewrite(
            "reference/mbti-layer.md",
            lambda text: text.replace(
                "검사명, 네 글자 유형 코드, 축 코드, 내부 객체명을 노출하지 않는다",
                "네 글자 유형 코드를 그대로 보여준다",
                1,
            ),
        )
        self.assertIn("MBTI_CUSTOMER_LANGUAGE", finding_codes(self.validate()))

    def test_openai_and_claude_manifest_versions_must_match(self):
        self.rewrite_path(
            self.plugin_root / ".codex-plugin" / "plugin.json",
            lambda text: text.replace('"version": "0.6.0"', '"version": "0.6.1"', 1),
        )
        self.assertIn("HOST_MANIFEST_VERSION", finding_codes(self.validate()))

    def test_openai_manifest_skills_path_must_exist(self):
        self.rewrite_path(
            self.plugin_root / ".codex-plugin" / "plugin.json",
            lambda text: text.replace('"skills": "./skills/"', '"skills": "./missing/"', 1),
        )
        self.assertIn("CODEX_SKILLS_PATH", finding_codes(self.validate()))

    def test_openai_interface_requires_all_three_values(self):
        self.rewrite(
            "agents/openai.yaml",
            lambda text: text.replace("  default_prompt:", "  removed_prompt:", 1),
        )
        self.assertIn("OPENAI_INTERFACE_FIELDS", finding_codes(self.validate()))

    def test_openai_marketplace_source_must_resolve(self):
        self.rewrite_path(
            self.repo_root / ".agents" / "plugins" / "marketplace.json",
            lambda text: text.replace(
                '"path": "./plugins/samsin-saju"',
                '"path": "./plugins/missing"',
                1,
            ),
        )
        self.assertIn("OPENAI_MARKETPLACE_SOURCE", finding_codes(self.validate()))

    def test_claude_helpers_have_direct_execution_fallback(self):
        self.rewrite(
            "SKILL.md",
            lambda text: text.replace(
                "ChatGPT·Codex처럼 조력자가 없는 환경에서는 같은 순서를 직접 수행한다.",
                "조력자가 없으면 실행하지 않는다.",
                1,
            ),
        )
        self.assertIn("SKILL_CLAUDE_FALLBACK", finding_codes(self.validate()))

    def test_skill_must_load_action_library(self):
        self.rewrite(
            "SKILL.md",
            lambda text: text.replace("`reference/action-library.md`", "행동 참고 자료"),
        )
        self.assertIn("SKILL_ACTION_LIBRARY_REFERENCE", finding_codes(self.validate()))

    def test_action_library_keeps_use_caution_and_check_types(self):
        self.rewrite(
            "reference/action-library.md",
            lambda text: text.replace("확인 지표", "느낌", 1),
        )
        self.assertIn("ACTION_LIBRARY_ACTION_TYPES", finding_codes(self.validate()))

    def test_personality_only_changes_execution_method(self):
        self.rewrite(
            "reference/mbti-layer.md",
            lambda text: text.replace(
                "근거나 행동 주제를 바꾸지 않고, 실행 방법",
                "행동 주제와 결론을 바꾸고",
                1,
            ),
        )
        self.assertIn("MBTI_EXECUTION_METHOD", finding_codes(self.validate()))


class TestCustomerOutputContract(unittest.TestCase):
    def test_actionable_friendly_reading_passes(self):
        output = f"""어서 와, 아가. 기준: 양력 1990년 3월 15일 · 태어난 시 오전 5:30~7:30 · 남성

한눈에 먼저 보면, 맡은 일을 차분히 마무리할 때 강점이 잘 보여. 다만 혼자 다 책임지려 하면 쉽게 지칠 수 있겠구나.

### 오늘 10분
오늘 저녁 9시에 내일 할 일 세 개를 10분 동안 적어보렴. 메모 세 줄이 남으면 완료야.

### 이번 주 실험
다음 회의 전 상대가 원하는 결과를 한 번 되물어봐. 질문과 답을 한 줄씩 기록하면 완료야.

### 7일 뒤 확인
기록을 보고 피로가 줄었으면 유지하고, 변화가 없으면 방법을 수정하고, 부담이 커졌으면 중단해.

### 이번에는 하지 않을 것
이번 주에는 새 일을 두 개 넘게 동시에 시작하지 말아.

{quality_contract.COMMON_DISCLAIMER}"""
        findings = quality_contract.validate_customer_output(output, 1)
        self.assertEqual([], findings, "\n" + "\n".join(item.render() for item in findings))

    def test_requested_modern_honorific_reading_passes(self):
        output = f"""기준: 양력 1990년 3월 15일 · 태어난 시 오전 5:30~7:30 · 남성

한눈에 먼저 보면, 맡은 일을 차분히 마무리하는 강점이 있어요. 혼자 다 책임지면 쉽게 지칠 수 있어요.

### 오늘 10분
오늘 저녁 9시에 내일 할 일 세 개를 10분 동안 적어보세요. 메모 세 줄이 남으면 완료예요.

### 이번 주 실험
다음 회의 전 상대가 원하는 결과를 한 번 질문하세요. 질문과 답을 한 줄씩 기록하면 완료예요.

### 7일 뒤 확인
기록을 보고 피로가 줄었으면 유지하고, 변화가 없으면 수정하고, 부담이 커졌으면 중단하세요.

### 이번에는 하지 않을 것
이번 주에는 새 일을 두 개 넘게 동시에 시작하지 마세요.

{quality_contract.COMMON_DISCLAIMER}"""
        findings = quality_contract.validate_customer_output(output, 1)
        self.assertEqual([], findings, "\n" + "\n".join(item.render() for item in findings))

    def test_optional_personality_only_adjusts_execution_method(self):
        output = f"""기준: 양력 1990년 3월 15일 · 태어난 시 오전 5:30~7:30 · 남성 · 직업운

한눈에 먼저 보면, 복잡한 업무를 정리해 작은 결과물로 만드는 실험이 좋아. 스스로 알려준 성향은 사주 근거가 아니라 같은 행동을 편하게 실행하는 방법에만 반영했어. 글로 먼저 정리하는 방식이 편하다면 아래 순서를 써보자.

### 하면 좋은 행동 — 오늘 10분
오늘 저녁 8시에 반복되는 업무 문제 하나를 고르고 `문제·영향·작은 개선안`을 한 줄씩 적어보렴. 메모 세 줄이 남으면 완료야.

### 조심할 행동 — 이번 주 실험
이번 주에는 개선 과제를 두 개 넘게 벌이지 말아. 다음 회의 전 한 과제만 골라 30분 초안을 만들고 한 사람에게 보여줘. 초안과 답 한 줄이 남으면 완료야.

### 7일 뒤 검토
7일 뒤 결과물이 실제로 쓰였는지와 부담이 줄었는지를 각각 확인해보렴. 둘 다 좋아졌으면 유지하고, 하나만 좋아졌으면 시간이나 범위를 수정하고, 둘 다 아니면 중단하면 된단다.

{quality_contract.PERSONALITY_DISCLAIMER}

{quality_contract.COMMON_DISCLAIMER}"""
        self.assertNotRegex(output, r"\bMBTI\b|\b[EI][SN][TF][JP]\b")
        for marker in ("하면 좋은 행동", "조심할 행동", "7일 뒤 검토"):
            self.assertIn(marker, output)
        findings = quality_contract.validate_customer_output(output, 7)
        self.assertEqual([], findings, "\n" + "\n".join(item.render() for item in findings))

    def test_abstract_and_fatalistic_output_is_blocked(self):
        output = f"""삶의 균형을 찾으세요. 반드시 성공한다.

{quality_contract.COMMON_DISCLAIMER}"""
        codes = finding_codes(quality_contract.validate_customer_output(output, 1))
        self.assertTrue(
            {
                "OUTPUT_ACTION_CARDS",
                "OUTPUT_ABSTRACT_ACTION",
                "OUTPUT_COMPLETION_CRITERION",
                "OUTPUT_FEEDBACK_LOOP",
                "OUTPUT_FATALISTIC_CLAIM",
            }.issubset(codes),
            codes,
        )

    def test_awkward_korean_internal_fields_and_type_code_are_blocked(self):
        output = f"""dayMaster를 보면 INTJ 결이에요. 결정을 하룻밤 재우세요.

오늘 10분 동안 메모해보세요. 이번 주 실험 뒤 7일 뒤 유지·수정·중단을 정하세요. 메모가 남으면 완료예요.

{quality_contract.COMMON_DISCLAIMER}"""
        codes = finding_codes(quality_contract.validate_customer_output(output, 1))
        self.assertIn("OUTPUT_AWKWARD_KOREAN", codes)
        self.assertIn("OUTPUT_RAW_FIELD_LEAK", codes)
        self.assertIn("OUTPUT_PERSONALITY_CODE_LEAK", codes)

    def test_untranslated_hanja_is_blocked_but_parenthetical_hanja_is_allowed(self):
        bad = f"""일주는 丙午라 불기운이 도드라져요.
오늘 10분 기록하고 이번 주 실험 뒤 7일 뒤 유지·수정·중단을 정하세요. 기록이 남으면 완료예요.
{quality_contract.COMMON_DISCLAIMER}"""
        self.assertIn(
            "OUTPUT_HANJA_EXPOSURE",
            finding_codes(quality_contract.validate_customer_output(bad, 1)),
        )

        allowed = f"""본바탕은 병오(丙午)라 불기운이 도드라져요.
오늘 10분 기록하고 이번 주 실험 뒤 7일 뒤 유지·수정·중단을 정하세요. 기록이 남으면 완료예요.
{quality_contract.COMMON_DISCLAIMER}"""
        self.assertNotIn(
            "OUTPUT_HANJA_EXPOSURE",
            finding_codes(quality_contract.validate_customer_output(allowed, 1)),
        )

    def test_health_reading_needs_medical_disclaimer(self):
        output = f"""쉴 시간을 정해두면 생활 리듬을 확인하기 쉬워요.
오늘 10분 움직이고 이번 주 실험 뒤 7일 뒤 유지·수정·중단을 정하세요. 기록이 남으면 완료예요.
{quality_contract.COMMON_DISCLAIMER}"""
        self.assertIn(
            "OUTPUT_MEDICAL_DISCLAIMER",
            finding_codes(quality_contract.validate_customer_output(output, 13)),
        )

    def test_menu_disclaimer_must_precede_common_disclaimer(self):
        output = f"""기준을 확인해. 오늘 생활 리듬을 살펴보자.
오늘 10분 기록해보렴. 이번 주 실험을 한 번 하고 기록이 남으면 완료야. 7일 뒤 유지·수정·중단을 정하면 된단다.
{quality_contract.COMMON_DISCLAIMER}
{quality_contract.MEDICAL_DISCLAIMER}"""
        self.assertIn(
            "OUTPUT_DISCLAIMER_ORDER",
            finding_codes(quality_contract.validate_customer_output(output, 13)),
        )

    def test_hiring_verdict_is_blocked_even_with_required_disclaimer(self):
        output = f"""이 지원자는 채용 부적합이니 뽑지 마세요.
직무 관련 구조화 질문과 행동 증거를 확인하세요.
{quality_contract.COMMON_DISCLAIMER}
{quality_contract.HIRING_DISCLAIMER}"""
        codes = finding_codes(quality_contract.validate_customer_output(output, 15))
        self.assertIn("OUTPUT_HIRING_VERDICT", codes)

    def test_infantilizing_address_and_filler_are_blocked(self):
        output = f"""아가, 오구오구 잘 왔단다. 오늘도 아가라고 부를게.
오늘 10분 기록하고 이번 주 실험 뒤 7일 뒤 유지·수정·중단을 정하렴. 기록이 남으면 완료란다.
{quality_contract.COMMON_DISCLAIMER}"""
        codes = finding_codes(quality_contract.validate_customer_output(output, 1))
        self.assertIn("OUTPUT_DISRESPECTFUL_VOICE", codes)
        self.assertIn("OUTPUT_ADDRESS_OVERUSE", codes)

    def test_signature_old_endings_are_limited_to_four(self):
        output = f"""어서 와, 아가. 하나씩 보자.
오늘 10분 적어보렴. 이번 주에도 해보렴. 7일 뒤에는 확인하렴. 유지·수정·중단을 고르렴. 어렵다면 다시 해보렴. 기록이 남으면 완료란다.
{quality_contract.COMMON_DISCLAIMER}"""
        self.assertIn(
            "OUTPUT_SIGNATURE_TONE_COUNT",
            finding_codes(quality_contract.validate_customer_output(output, 1)),
        )

    def test_excessively_archaic_ending_is_blocked(self):
        output = f"""어서 와. 하나씩 보자.
오늘 10분 적어보렴. 이번 주에도 한 번 기록해. 7일 뒤 유지·수정·중단을 확인하거라. 기록이 세 줄 남으면 완료란다.
{quality_contract.COMMON_DISCLAIMER}"""
        self.assertIn(
            "OUTPUT_ARCHAIC_VOICE",
            finding_codes(quality_contract.validate_customer_output(output, 1)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
