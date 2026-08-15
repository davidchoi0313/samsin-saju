# -*- coding: utf-8 -*-
"""삼신이 프롬프트와 고객 노출 풀이의 품질 계약 검증기.

이 모듈은 LLM이나 만세력 엔진을 호출하지 않는다. 표준 라이브러리만으로
SKILL.md, reference/brand.md, menus/*.md 사이의 정적 계약을 검사하고, 필요하면
이미 생성된 고객용 풀이 한 건도 검사한다. 프롬프트 문구를 고칠 때 아래처럼
실행하면 구조·안전·실천성 회귀를 즉시 찾을 수 있다.

    python3 scripts/quality_contract.py
    python3 scripts/quality_contract.py --output reading.txt --menu 13

종료 코드는 통과 시 0, 위반 발견 시 1이다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


COMMON_DISCLAIMER = (
    "본 풀이는 전통 명리학·무속에 기반한 오락·참고용이며, "
    "의학·법률·재정적 조언이 아닙니다. 중요한 결정은 본인의 판단과 "
    "전문가의 조언에 따르시기 바랍니다."
)

MEDICAL_DISCLAIMER = (
    "본 내용은 의료 진단이 아닙니다. 증상이 있거나 건강이 우려되면 반드시 "
    "의료 전문가와 상담하세요."
)

PERCENT_DISCLAIMER = (
    "표기된 수치는 명리학적 참고 수치이며 실제 결과를 보장하지 않습니다."
)

SENSITIVE_READING_WARNING = "심리적으로 예민하신 분은 신중히 열람해 주세요."

BUSINESS_DISCLAIMER = (
    "본 풀이는 동업·협업을 가볍게 비춰보는 참고 자료이며, 투자·동업·계약 "
    "결정의 근거가 아닙니다. 사업 결정은 사업성·재무·법률 검토 등 객관적 "
    "자료와 전문가 조언에 따라 판단하셔야 합니다. 최종 판단과 책임은 "
    "본인에게 있습니다."
)

HIRING_DISCLAIMER = (
    "본 풀이는 채용을 돕는 재미·참고 자료이며, 채용 결정·합격 판정·인재 "
    "선별 도구가 아닙니다. 채용은 직무 관련 자격·역량·검증된 평가 기준에 "
    "따라 판단하셔야 하며, 생년월일(나이)·성별·출신 등을 이유로 한 차별은 "
    "법으로 금지됩니다. 최종 판단과 책임은 사용자와 채용 담당자에게 있습니다."
)

PERSONALITY_DISCLAIMER = (
    "본 풀이에 곁들인 성향 이야기는 사용자가 스스로 밝힌 자기이해 참고값입니다. "
    "사주 해석의 근거나 과학적 진단이 아니며, 조언을 편하게 전하기 위한 "
    "참고로만 사용했습니다."
)

MENU_FILES = {
    1: "01-pyeongsaeng.md",
    2: "02-olhae.md",
    3: "03-gunghap.md",
    4: "04-gwishin.md",
    5: "05-jeonsaeng.md",
    6: "06-yongshin.md",
    7: "07-jigeop.md",
    8: "08-yeonae.md",
    9: "09-tojeong.md",
    10: "10-shinsal.md",
    11: "11-daewoon.md",
    12: "12-oneul.md",
    13: "13-geongang.md",
    14: "14-saeop-gunghap.md",
    15: "15-injae-chaeyong.md",
}

LEGACY_MENU_MARKERS = (
    "네 글자 처방",
    "└ 근거",
    "5~7개 선택지",
    '명령("~하세요") 금지',
)

DISRESPECTFUL_TERMS = (
    "오구오구",
    "기특해라",
    "사내아이",
    "계집아이",
    "동무",
    "의원 찾아가렴",
)

# 설계 문서(SKILL/output-contract/action-library)의 어휘가 고객 문장에 그대로
# 새어 나오면 풀이가 보고서 문체가 된다. 사람 말로 바꾸는 대응표는
# reference/voice-and-exemplar.md §1에 있다.
INTERNAL_JARGON_TERMS = (
    "실행 장치",
    "완료 기준",
    "산출 카드",
    "성향 카드",
    "계산 관찰",
    "행동 후보",
    "관찰 지표",
)


@dataclass(frozen=True)
class Violation:
    """한 개 품질 계약 위반."""

    code: str
    path: str
    message: str
    line: int | None = None

    def render(self) -> str:
        location = self.path
        if self.line is not None:
            location += f":{self.line}"
        return f"[{self.code}] {location} — {self.message}"


def _sorted_findings(findings: Iterable[Violation]) -> list[Violation]:
    """line=None과 정수 라인이 섞여도 안정적으로 정렬한다."""

    return sorted(
        set(findings),
        key=lambda item: (
            item.path,
            item.line if item.line is not None else -1,
            item.code,
            item.message,
        ),
    )


def _line_of(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text.count("\n", 0, index) + 1


def _add_missing(
    findings: list[Violation],
    *,
    text: str,
    needle: str,
    code: str,
    path: str,
    message: str,
) -> None:
    if needle not in text:
        findings.append(Violation(code, path, message))


def _add_missing_pattern(
    findings: list[Violation],
    *,
    text: str,
    pattern: str,
    code: str,
    path: str,
    message: str,
) -> re.Match[str] | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        findings.append(Violation(code, path, message))
    return match


def _read(path: Path, findings: list[Violation], relative: str) -> str | None:
    if not path.is_file():
        findings.append(Violation("FILE_MISSING", relative, "필수 계약 파일이 없습니다."))
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        findings.append(
            Violation("FILE_READ_ERROR", relative, f"UTF-8 파일을 읽지 못했습니다: {exc}")
        )
        return None


def _parse_json_contract(
    text: str,
    *,
    path: str,
    findings: list[Violation],
) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(
            Violation(
                "HOST_MANIFEST_JSON",
                path,
                f"플러그인 메타데이터가 올바른 JSON이 아닙니다: {exc.msg}",
                exc.lineno,
            )
        )
        return None
    if not isinstance(value, dict):
        findings.append(
            Violation("HOST_MANIFEST_JSON", path, "플러그인 메타데이터 최상위 값은 객체여야 합니다.")
        )
        return None
    return value


def _openai_interface_values(text: str) -> dict[str, str]:
    """현재 openai.yaml의 단순 interface 매핑을 외부 YAML 의존성 없이 읽는다."""

    values: dict[str, str] = {}
    in_interface = False
    for line in text.splitlines():
        if re.match(r"^interface:\s*$", line):
            in_interface = True
            continue
        if not in_interface:
            continue
        if line and not line.startswith((" ", "\t")):
            break
        match = re.match(
            r"^\s{2}(display_name|short_description|default_prompt):\s*(.*?)\s*$",
            line,
        )
        if not match:
            continue
        key, raw_value = match.groups()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _parse_brand_table(text: str, path: str, findings: list[Violation]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\|\s*`(BRAND_[A-Z]+)`\s*\|\s*(.*?)\s*\|", line)
        if not match:
            continue
        key, value = match.groups()
        if key in values:
            findings.append(
                Violation("BRAND_DUPLICATE_KEY", path, f"브랜드 키 {key}가 중복됐습니다.", line_number)
            )
        values[key] = value

    required_nonempty = (
        "BRAND_KO",
        "BRAND_SLUG",
        "BRAND_TAGLINE",
        "BRAND_GREETING",
        "BRAND_SIGNOFF",
    )
    for key in required_nonempty:
        if not values.get(key, "").strip() or values.get(key, "").strip() == "(비움)":
            findings.append(
                Violation("BRAND_REQUIRED_VALUE", path, f"{key}의 비어 있지 않은 기준값이 필요합니다.")
            )
    if "BRAND_HANJA" not in values:
        findings.append(
            Violation("BRAND_REQUIRED_KEY", path, "BRAND_HANJA 키가 필요합니다(값은 비워도 됨).")
        )

    customer_voice = " ".join(
        values.get(key, "") for key in ("BRAND_GREETING", "BRAND_SIGNOFF")
    )
    for term in DISRESPECTFUL_TERMS:
        if term in customer_voice:
            findings.append(
                Violation(
                    "BRAND_DISRESPECTFUL_VOICE",
                    path,
                    f"브랜드 인사·서명에 금지된 고객 표현이 있습니다: {term}",
                )
            )
    if customer_voice.count("아가") > 1:
        findings.append(
            Violation(
                "BRAND_ADDRESS_OVERUSE",
                path,
                "브랜드 인사·서명 전체에서 '아가'는 최대 한 번만 쓸 수 있습니다.",
            )
        )
    if not re.search(r"(?:해|봐|할게|보자|좋아|괜찮아)(?:[.!?…]|$)", customer_voice):
        findings.append(
            Violation(
                "BRAND_MODERN_VOICE",
                path,
                "브랜드 인사·서명에는 자연스러운 현대식 반말 문장이 필요합니다.",
            )
        )
    return values


def _validate_output_contract(text: str, path: str) -> list[Violation]:
    """중앙 고객 출력 계약 자체가 실행 가능성과 존중형 말투를 보존하는지 검사."""

    findings: list[Violation] = []
    required_sections = {
        "OUTPUT_CONTRACT_OUTCOME": "## 1. 고객이 받아야 하는 결과",
        "OUTPUT_CONTRACT_NO_INTERROGATION": "## 2. 추가 질문 없이 완결되는 풀이",
        "OUTPUT_CONTRACT_RESPECTFUL_TONE": "## 3. 기본 말투 — 현대어에 은은한 할머니 결",
        "OUTPUT_CONTRACT_STRUCTURE": "## 4. 모든 풀이의 출력 순서",
        "OUTPUT_CONTRACT_LENGTH": "## 5. 메뉴별 길이와 예외",
        "OUTPUT_CONTRACT_UNCERTAINTY": "## 6. 근거와 불확실성",
        "OUTPUT_CONTRACT_SAFETY": "## 7. 중대한 결정 안전선",
        "OUTPUT_CONTRACT_QA": "## 8. 출력 직전 품질 점검",
        "OUTPUT_CONTRACT_DISCLAIMER": "## 9. 고정 면책 문구",
    }
    for code, heading in required_sections.items():
        _add_missing(
            findings,
            text=text,
            needle=heading,
            code=code,
            path=path,
            message=f"중앙 출력 계약 섹션이 없습니다: {heading}",
        )

    grouped_contracts = {
        "OUTPUT_CONTRACT_RESPECT": (
            "친근하고 또렷한 현대식 반말",
            "`아가`는 캐릭터 인사",
            "할머니식 어미는 한 풀이에 2~4회",
            "고객을 가르치거나 낮춰 보는 표현",
        ),
        "OUTPUT_CONTRACT_NO_EXTRA_QUESTIONS": (
            "현재 고민이나 목표를 따로 말하지 않아도",
            "결과의 깊이·구체성·실행성이 낮아지면 안 된다",
        ),
        "OUTPUT_CONTRACT_ACTION_CARD": (
            "오늘 10분",
            "이번 주 실험",
            "확인 질문",
            "시점",
            "행동",
            "크기",
            "완료 기준",
            "유지·수정·중단",
        ),
        "OUTPUT_CONTRACT_ACTION_TYPES": (
            "더 해볼 행동",
            "조심하거나 줄일 행동",
            "실제 효과를 확인할 행동",
        ),
        "OUTPUT_CONTRACT_GROUNDING": (
            "카드에 실제로 있는 구조",
            "내부 코드나 한자를 보여주지 않는다",
            "카드 값에서 직접 나오지 않는",
        ),
        "OUTPUT_CONTRACT_SAFETY_DETAILS": (
            "오행을 질병·장기 이상·체질 진단으로 연결하지 않는다",
            "매수·매도·투자·대출·퇴사·계약 여부를 정하지 않는다",
            "만남·결혼·이별·불륜을 예언하지 않는다",
            "사주·성향으로 합불, 순위, 점수, 적합도를 만들지 않는다",
        ),
    }
    for code, snippets in grouped_contracts.items():
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            findings.append(
                Violation(code, path, "필수 문구가 빠졌습니다: " + ", ".join(missing))
            )

    for term in DISRESPECTFUL_TERMS[:5]:
        if f"`{term}`" not in text:
            findings.append(
                Violation(
                    "OUTPUT_CONTRACT_BANNED_TERM",
                    path,
                    f"고객 비하·유아화 방지 목록에 '{term}'이 없습니다.",
                )
            )

    _add_missing(
        findings,
        text=text,
        needle=COMMON_DISCLAIMER,
        code="OUTPUT_CONTRACT_COMMON_DISCLAIMER",
        path=path,
        message="공통 면책 원문이 정확히 보존돼야 합니다.",
    )
    if COMMON_DISCLAIMER in text and text[text.rfind(COMMON_DISCLAIMER) + len(COMMON_DISCLAIMER) :].strip():
        findings.append(
            Violation(
                "OUTPUT_CONTRACT_DISCLAIMER_ORDER",
                path,
                "공통 면책 원문은 중앙 출력 계약의 마지막 고객 문구여야 합니다.",
            )
        )
    return findings


def _validate_mbti_layer(text: str, path: str) -> list[Violation]:
    """선택 성향 정보가 계산·낙인·채용 판단으로 새지 않는지 검사한다."""

    findings: list[Violation] = []
    grouped_contracts = {
        "MBTI_OPTIONAL_INPUT": (
            "자발적으로 제공했을 때만",
            "성향을 받지 않았으면 추정하거나 다시 묻지 않는다",
            "성향 관련 문장과 면책도 모두 생략",
        ),
        "MBTI_SEPARATE_FROM_SAJU": (
            "사주 계산과 완전히 분리",
            "성향 때문에 사주 카드의 값이나 해석을 바꾸지 않는다",
            "사주 엔진에는 이 객체를 넘기지 않는다",
        ),
        "MBTI_CUSTOMER_LANGUAGE": (
            "검사명, 네 글자 유형 코드, 축 코드, 내부 객체명을 노출하지 않는다",
            "한두 개만 생활어로 바꿔",
            "선택 가능한 표현",
        ),
        "MBTI_EXECUTION_METHOD": (
            "근거나 행동 주제를 바꾸지 않고, 실행 방법",
            "사주 카드가 `무엇을 관찰하고 시험할지`",
            "성향은 그 실험을 글·대화·계획·선택지 중 어떤 형태로",
            "`action-library.md`의 안전선과 완료 기준",
        ),
        "MBTI_HIRING_GUARD": (
            "채용 참고(M15)에는 성향 정보를 사용하지 않는다",
            "15: 사용하지 않는다",
        ),
        "MBTI_DISCLAIMER_ORDER": (
            PERSONALITY_DISCLAIMER,
            "공통 면책 앞에",
            "공통 면책은 `output-contract.md`의 원문을 그대로 이어 붙인다",
        ),
    }
    for code, snippets in grouped_contracts.items():
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            findings.append(
                Violation(code, path, "필수 문구가 빠졌습니다: " + ", ".join(missing))
            )
    return findings


def _validate_input_form(text: str, path: str) -> list[Violation]:
    """실제 입력 UI가 짧고 친절하며 선택 정보를 강제하지 않는지 검사한다."""

    findings: list[Violation] = []
    grouped_contracts = {
        "INPUT_FORM_REQUIRED_FIELDS": (
            'data-field="gender"',
            'data-field="calendar"',
            'id="birthDate"',
        ),
        "INPUT_FORM_UNKNOWN_TIME": (
            'data-value="unknown">시 모름',
            "정확히 모르면 ‘시 모름’",
        ),
        "INPUT_FORM_OPTIONAL_NAME": (
            "적지 않아도 괜찮아",
            'aria-label="이름 (선택)"',
        ),
        "INPUT_FORM_OPTIONAL_PERSONALITY": (
            "모르면 건너뛰어도 돼",
            "입력하지 않아도 사주 풀이는 똑같이 진행돼",
            "성향: 모름(안 넣음)",
        ),
        "INPUT_FORM_HELPFUL_ERROR": (
            "정보가 빠졌구나",
            "이 항목만 채우면 바로 시작할게",
        ),
    }
    for code, snippets in grouped_contracts.items():
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            findings.append(
                Violation(code, path, "필수 문구가 빠졌습니다: " + ", ".join(missing))
            )

    if re.search(r"(?:현재 )?(?:고민|목표).{0,20}(?:필수|반드시)", text):
        findings.append(
            Violation(
                "INPUT_FORM_EXTRA_INTERROGATION",
                path,
                "현재 고민·목표를 기본 풀이의 필수 입력으로 요구하면 안 됩니다.",
            )
        )

    for term in DISRESPECTFUL_TERMS:
        if term in text:
            findings.append(
                Violation(
                    "INPUT_FORM_DISRESPECTFUL_VOICE",
                    path,
                    f"입력 안내에 고객을 유아화하거나 낡게 들리는 표현이 있습니다: {term}",
                    _line_of(text, term),
                )
            )
    return findings


def _validate_action_library(text: str, path: str) -> list[Violation]:
    """사주 신호가 선택 가능한 생활 실험으로 이어지는 공통 기준을 검사한다."""

    findings: list[Violation] = []
    required_sections = {
        "ACTION_LIBRARY_PIPELINE_SECTION": "## 1. 행동을 만드는 순서",
        "ACTION_LIBRARY_SELECTION_SECTION": "## 2. 행동 선택 규칙",
        "ACTION_LIBRARY_ELEMENTS_SECTION": "## 3. 오행을 행동으로 번역하는 범위",
        "ACTION_LIBRARY_TEN_GODS_SECTION": "## 4. 십신을 일과 생활 습관으로 번역하는 범위",
        "ACTION_LIBRARY_PERSONALITY_SECTION": "## 7. 선택 성향과 결합하는 방법",
        "ACTION_LIBRARY_CHOICE_SECTION": "## 8. 고객 선택권",
    }
    for code, heading in required_sections.items():
        _add_missing(
            findings,
            text=text,
            needle=heading,
            code=code,
            path=path,
            message=f"행동 번역 기준 섹션이 없습니다: {heading}",
        )

    grouped_contracts = {
        "ACTION_LIBRARY_SIGNAL_TO_REVIEW": (
            "**사주 신호:**",
            "**생활 가설:**",
            "**활용 행동:**",
            "**주의 행동:**",
            "**실행 장치:**",
            "**검토:**",
            "7일 뒤 유지·수정·중단",
        ),
        "ACTION_LIBRARY_ACTION_TYPES": (
            "활용해볼 행동",
            "과할 때 조심할 행동",
            "확인 지표",
        ),
        "ACTION_LIBRARY_PERSONALITY_METHOD": (
            "무엇을 관찰하고 시험할지",
            "그 행동을 어떤 방식으로 실행할지",
            "성향으로 사주 근거를 만들지 않는다",
        ),
        "ACTION_LIBRARY_CUSTOMER_CHOICE": (
            "사주와 성향은 선택을 대신하지 않는다",
            "제안 중 하나만 골라도 충분하다",
            "맞지 않으면 실패가 아니라 데이터다",
        ),
    }
    for code, snippets in grouped_contracts.items():
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            findings.append(
                Violation(code, path, "필수 문구가 빠졌습니다: " + ", ".join(missing))
            )
    return findings


def _validate_windows_checkout_paths(repository_root: Path) -> list[Violation]:
    """ChatGPT Windows 설치기가 안전하게 체크아웃할 수 있는 경로인지 검사한다."""

    findings: list[Violation] = []
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
    invalid_characters = set('<>:"\\|?*')

    for path in repository_root.rglob("*"):
        relative = path.relative_to(repository_root)
        if any(part in {".git", "__pycache__"} for part in relative.parts):
            continue

        unsafe = False
        for component in relative.parts:
            stem = component.rstrip(" .").split(".", 1)[0].upper()
            if (
                not component.isascii()
                or component.endswith((" ", "."))
                or stem in reserved_names
                or any(ord(character) < 32 or character in invalid_characters for character in component)
            ):
                unsafe = True
                break

        if unsafe:
            findings.append(
                Violation(
                    "WINDOWS_CHECKOUT_PATH",
                    relative.as_posix(),
                    "Windows용 ChatGPT 마켓플레이스가 체크아웃할 수 있도록 파일·폴더명은 "
                    "이식 가능한 ASCII 경로를 사용해야 합니다.",
                )
            )

    return findings


def _validate_host_compatibility(skill_root: Path) -> list[Violation]:
    """Claude와 OpenAI 설치 메타데이터가 같은 스킬을 가리키는지 검사한다."""

    findings: list[Violation] = []
    if skill_root.parent.name != "skills":
        return [
            Violation(
                "HOST_SKILL_LAYOUT",
                str(skill_root),
                "스킬 루트는 플러그인의 skills/<skill-name> 구조에 있어야 합니다.",
            )
        ]

    plugin_root = skill_root.parent.parent
    if plugin_root.parent.name != "plugins":
        return [
            Violation(
                "HOST_PLUGIN_LAYOUT",
                str(plugin_root),
                "플러그인은 저장소의 plugins/<plugin-name> 구조에 있어야 합니다.",
            )
        ]
    repository_root = plugin_root.parent.parent
    findings.extend(_validate_windows_checkout_paths(repository_root))

    claude_rel = "plugin/.claude-plugin/plugin.json"
    codex_rel = "plugin/.codex-plugin/plugin.json"
    marketplace_rel = ".agents/plugins/marketplace.json"
    openai_rel = "agents/openai.yaml"

    claude_text = _read(plugin_root / ".claude-plugin" / "plugin.json", findings, claude_rel)
    codex_text = _read(plugin_root / ".codex-plugin" / "plugin.json", findings, codex_rel)
    marketplace_text = _read(
        repository_root / ".agents" / "plugins" / "marketplace.json",
        findings,
        marketplace_rel,
    )
    openai_text = _read(skill_root / "agents" / "openai.yaml", findings, openai_rel)

    claude = (
        _parse_json_contract(claude_text, path=claude_rel, findings=findings)
        if claude_text is not None
        else None
    )
    codex = (
        _parse_json_contract(codex_text, path=codex_rel, findings=findings)
        if codex_text is not None
        else None
    )
    marketplace = (
        _parse_json_contract(marketplace_text, path=marketplace_rel, findings=findings)
        if marketplace_text is not None
        else None
    )

    if claude is not None and codex is not None:
        versions = (claude.get("version"), codex.get("version"))
        valid_versions = all(
            isinstance(value, str) and re.fullmatch(r"\d+\.\d+\.\d+", value)
            for value in versions
        )
        if not valid_versions or versions[0] != versions[1]:
            findings.append(
                Violation(
                    "HOST_MANIFEST_VERSION",
                    codex_rel,
                    "Claude·OpenAI manifest 버전은 같은 유효한 SemVer여야 합니다"
                    f"(현재 {versions[0]!r}, {versions[1]!r}).",
                )
            )
        if claude.get("name") != codex.get("name"):
            findings.append(
                Violation(
                    "HOST_MANIFEST_NAME",
                    codex_rel,
                    "Claude·OpenAI manifest의 플러그인 이름이 같아야 합니다.",
                )
            )

        skills_value = codex.get("skills")
        skills_path = (
            plugin_root / skills_value if isinstance(skills_value, str) else None
        )
        if (
            skills_path is None
            or not skills_path.is_dir()
            or not (skills_path / skill_root.name / "SKILL.md").is_file()
        ):
            findings.append(
                Violation(
                    "CODEX_SKILLS_PATH",
                    codex_rel,
                    "OpenAI manifest의 skills 경로가 실제 saju-reading/SKILL.md를 가리켜야 합니다.",
                )
            )

        interface = codex.get("interface")
        if not isinstance(interface, dict):
            findings.append(
                Violation(
                    "OPENAI_PUBLIC_INTERFACE",
                    codex_rel,
                    "공개 설치 화면에 필요한 interface 객체가 있어야 합니다.",
                )
            )
        else:
            if interface.get("category") != "Entertainment":
                findings.append(
                    Violation(
                        "OPENAI_PUBLIC_CATEGORY",
                        codex_rel,
                        "공개 디렉터리 category는 Entertainment여야 합니다.",
                    )
                )
            for key in ("composerIcon", "logo"):
                value = interface.get(key)
                asset_path = plugin_root / value if isinstance(value, str) else None
                if (
                    asset_path is None
                    or not value.startswith("./assets/")
                    or asset_path.suffix.lower() != ".png"
                    or not asset_path.is_file()
                ):
                    findings.append(
                        Violation(
                            "OPENAI_PUBLIC_ASSET",
                            codex_rel,
                            f"{key}은 plugin/assets 아래의 실제 PNG를 가리켜야 합니다.",
                        )
                    )
            for key in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
                value = interface.get(key)
                if not isinstance(value, str) or not value.startswith("https://"):
                    findings.append(
                        Violation(
                            "OPENAI_PUBLIC_URL",
                            codex_rel,
                            f"{key}에는 공개 HTTPS URL이 필요합니다.",
                        )
                    )

        legal_files = {
            "PRIVACY.md": ("처리하는 정보", "보존 기간", "수신자"),
            "TERMS.md": ("서비스의 성격", "금지되는 이용", "준거법"),
            "SUPPORT.md": ("지원 페이지", "이메일", "개인정보"),
        }
        for filename, snippets in legal_files.items():
            legal_text = _read(repository_root / filename, findings, filename)
            if legal_text is not None and any(snippet not in legal_text for snippet in snippets):
                findings.append(
                    Violation(
                        "OPENAI_PUBLIC_POLICY",
                        filename,
                        "공개 배포 정책 문서의 필수 설명이 빠졌습니다.",
                    )
                )

    if openai_text is not None:
        interface_values = _openai_interface_values(openai_text)
        required = ("display_name", "short_description", "default_prompt")
        missing = [key for key in required if not interface_values.get(key)]
        if missing:
            findings.append(
                Violation(
                    "OPENAI_INTERFACE_FIELDS",
                    openai_rel,
                    "OpenAI 인터페이스 필수 값이 없습니다: " + ", ".join(missing),
                )
            )
        elif not all(
            token in interface_values["default_prompt"] for token in ("사주", "행동")
        ):
            findings.append(
                Violation(
                    "OPENAI_DEFAULT_PROMPT_SKILL",
                    openai_rel,
                    "default_prompt가 사주 풀이와 행동 제안을 자연어로 설명해야 합니다.",
                )
            )

    if marketplace is not None:
        plugins = marketplace.get("plugins")
        plugin_entry: dict[str, object] | None = None
        if isinstance(plugins, list):
            for candidate in plugins:
                if isinstance(candidate, dict) and candidate.get("name") == plugin_root.name:
                    plugin_entry = candidate
                    break
        source = plugin_entry.get("source") if plugin_entry is not None else None
        source_path_value = source.get("path") if isinstance(source, dict) else None
        source_path = (
            repository_root / source_path_value
            if isinstance(source_path_value, str)
            else None
        )
        if (
            source_path is None
            or not source_path.is_dir()
            or source_path.resolve() != plugin_root.resolve()
        ):
            findings.append(
                Violation(
                    "OPENAI_MARKETPLACE_SOURCE",
                    marketplace_rel,
                    "마켓플레이스 source.path가 실제 plugins/samsin-saju 폴더를 가리켜야 합니다.",
                )
            )
        if plugin_entry is not None and plugin_entry.get("category") != "Entertainment":
            findings.append(
                Violation(
                    "OPENAI_MARKETPLACE_CATEGORY",
                    marketplace_rel,
                    "repo marketplace category도 Entertainment로 맞춰야 합니다.",
                )
            )

    return findings


def _validate_skill(text: str, path: str, brand: dict[str, str]) -> list[Violation]:
    findings: list[Violation] = []
    required_sections = {
        "SKILL_PRIORITY": "## 1. 우선순위",
        "SKILL_ENGINE_GROUNDING": "### 2.1 엔진 산출만 사용",
        "SKILL_SINGLE_VOICE": "### 2.2 단일 화자",
        "SKILL_OUTPUT_CONTRACT": "### 2.3 출력 계약",
        "SKILL_PERSONA": "## 3. 삼신이 보이스",
        "SKILL_INPUT": "## 5. 입력 수집",
        "SKILL_ROUTING": "## 8. 메뉴 라우팅",
        "SKILL_FINAL_OUTPUT": "## 9. 최종 출력",
        "SKILL_SAFETY_GUARDRAILS": "## 10. 안전 가드",
        "SKILL_DISCLAIMER_GATE": "## 11. 면책",
        "SKILL_PREFLIGHT": "## 12. 출력 전 차단 점검",
    }
    for code, heading in required_sections.items():
        _add_missing(
            findings,
            text=text,
            needle=heading,
            code=code,
            path=path,
            message=f"핵심 계약 섹션이 없습니다: {heading}",
        )

    grouped_contracts = {
        "SKILL_ENGINE_GROUNDING": (
            "카드에 실제 있는 값만 사용한다",
            "카드에 없는 행운색·방향·시간·특정 월·질병·수익·사건·점수",
            "내부 JSON, 필드 코드",
        ),
        "SKILL_TONE_RESPECTFUL_KOREAN": (
            "따뜻하고 자연스러운 현대식 반말",
            "`아가`는 인사에서 한 번까지만",
            "전체 2~4회",
            "고객이 존댓말을 원하면",
        ),
        "SKILL_TONE_ANTI_INFANTILIZATION": (
            "`오구오구`, `기특해라`, `사내아이`, `계집아이`",
            "과도한 고어·사투리",
        ),
        "SKILL_INPUT_EFFICIENT": (
            "한 메시지에 간단히 모아",
            "추가 상담 질문 없이 완성된 풀이를 바로 제공",
            "현재 고민·목표는 필수가 아니다",
        ),
        "SKILL_ACTION_CONCRETE": (
            "오늘 10분",
            "이번 주 실험",
            "7일 뒤 확인",
            "시점·동사·크기·완료 기준",
        ),
        "SKILL_ACTION_SIGNAL_CHAIN": (
            "사주 신호 → 일상에서 나타날 수 있는 행동",
            "활용할 행동 또는 조심할 행동",
            "실행 장치 → 7일 뒤 검토",
            "성향을 자발적으로 받았으면 행동의 주제가 아니라 실행 방식만",
        ),
        "SKILL_HOST_INDEPENDENT": (
            "ChatGPT·Codex·Claude 어느 환경에서도 같은 핵심 결과",
            "현재 `SKILL.md`가 있는 폴더를 스킬 루트",
            'SAJU_SKILL_ROOT="/absolute/path/to/saju-reading"',
        ),
        "SKILL_CLAUDE_FALLBACK": (
            "선택 기능이 없으면 같은 계약을 직접 수행",
            "ChatGPT·Codex처럼 조력자가 없는 환경에서는 같은 순서를 직접 수행",
        ),
        "SKILL_SAFETY_GUARDRAILS": (
            "죽음·중병·이혼·파산·사고·저주·빙의·재앙",
            "오행을 질병·장기 상태와 연결하지 않고",
            "합불·점수·등급·순위·추천을 만들지 않는다",
        ),
    }
    for code, snippets in grouped_contracts.items():
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            findings.append(
                Violation(code, path, "필수 문구가 빠졌습니다: " + ", ".join(missing))
            )

    _add_missing(
        findings,
        text=text,
        needle=COMMON_DISCLAIMER,
        code="SKILL_COMMON_DISCLAIMER",
        path=path,
        message="공통 면책 원문이 정확히 보존돼야 합니다.",
    )
    _add_missing(
        findings,
        text=text,
        needle="reference/output-contract.md",
        code="SKILL_OUTPUT_CONTRACT_REFERENCE",
        path=path,
        message="고객 출력 단일 계약(reference/output-contract.md) 참조가 필요합니다.",
    )
    _add_missing(
        findings,
        text=text,
        needle="reference/action-library.md",
        code="SKILL_ACTION_LIBRARY_REFERENCE",
        path=path,
        message="생활 행동 번역 계약(reference/action-library.md) 참조가 필요합니다.",
    )
    _add_missing(
        findings,
        text=text,
        needle="선택한 메뉴 파일은 **하나만** 읽는다",
        code="SKILL_ONE_MENU_ONLY",
        path=path,
        message="한 번에 선택한 메뉴 하나만 읽는 컨텍스트 절약 규칙이 필요합니다.",
    )
    _add_missing(
        findings,
        text=text,
        needle="reference/brand.md",
        code="SKILL_BRAND_REFERENCE",
        path=path,
        message="브랜드 단일 소스(reference/brand.md) 참조가 필요합니다.",
    )

    brand_name = brand.get("BRAND_KO")
    greeting = brand.get("BRAND_GREETING")
    if brand_name and brand_name not in text:
        findings.append(
            Violation("SKILL_BRAND_MISMATCH", path, f"기준 브랜드명 '{brand_name}'이 SKILL에 없습니다.")
        )
    if greeting and greeting not in text:
        findings.append(
            Violation("SKILL_GREETING_MISMATCH", path, "BRAND_GREETING 기준값이 SKILL과 다릅니다.")
        )

    return findings


def _declared_length_range(text: str) -> tuple[int, int] | None:
    match = re.search(r"\*{0,2}([0-9][0-9,]*)~([0-9][0-9,]*)자", text)
    if not match:
        return None
    return (
        int(match.group(1).replace(",", "")),
        int(match.group(2).replace(",", "")),
    )


def _validate_menu(
    menu_id: int,
    text: str,
    path: str,
) -> list[Violation]:
    findings: list[Violation] = []

    required_heading_patterns = {
        "MENU_PURPOSE_SECTION": r"^## 목적(?:과 [^\n]+)?\s*$",
        "MENU_INPUT_SECTION": r"^## 입력(?:과 [^\n]+)?(?:\s|$)",
        "MENU_ENGINE_FIELDS": r"^## (?:허용 필드|입력과 허용 필드)(?:\s|$)",
        "MENU_OUTPUT_SECTIONS": (
            r"^## (?:메뉴 본문|출력 형식|채용 전 요청에 대한 출력)(?:\s|$)"
        ),
        "MENU_DENSITY_SECTION": r"^## (?:권장 밀도|문체와 길이)(?:\s|$)",
        "MENU_DISCLAIMER_SECTION": r"^## (?:안전과 면책|강제 면책)(?:\s|$)",
    }
    for code, pattern in required_heading_patterns.items():
        _add_missing_pattern(
            findings,
            text=text,
            pattern=pattern,
            code=code,
            path=path,
            message=f"메뉴 {menu_id:02d}의 필수 구조가 빠졌습니다: {code}",
        )

    if not re.search(rf"^# M{menu_id:02d}\.", text, flags=re.MULTILINE):
        findings.append(
            Violation("MENU_ID_MISMATCH", path, f"첫 제목의 메뉴 번호가 M{menu_id:02d}여야 합니다.")
        )

    common_contracts = {
        "MENU_ENGINE_GROUNDING": r"실제|카드에 없는|허용 필드|카드 해석",
        "MENU_EASY_LANGUAGE": r"쉬운|생활|현실|일상|바로 (?:읽|복사)|누구나|관찰 가능한|구체적",
    }
    for code, pattern in common_contracts.items():
        _add_missing_pattern(
            findings,
            text=text,
            pattern=pattern,
            code=code,
            path=path,
            message=(
                f"메뉴 {menu_id:02d}에 엔진 근거와 고객이 이해할 생활 언어 계약이 필요합니다."
            ),
        )

    for marker in LEGACY_MENU_MARKERS:
        if marker in text:
            findings.append(
                Violation(
                    "MENU_LEGACY_OUTPUT_CONTRACT",
                    path,
                    f"중앙 출력 계약과 충돌하는 구 지시를 제거해야 합니다: {marker}",
                    _line_of(text, marker),
                )
            )

    for term in DISRESPECTFUL_TERMS:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if term not in line:
                continue
            if any(guard in line for guard in ("금지", "쓰지 않는다", "사용하지 않는다", "피한다")):
                continue
            findings.append(
                Violation(
                    "MENU_DISRESPECTFUL_VOICE",
                    path,
                    f"성인 고객을 낮추거나 낡게 들리는 표현이 남아 있습니다: {term}",
                    line_number,
                )
            )
            break

    declared_range = _declared_length_range(text)
    if declared_range is None:
        findings.append(
            Violation(
                "MENU_LENGTH_GUIDE",
                path,
                "권장 밀도에 숫자 범위를 두어 장황함과 지나친 축약을 함께 막아야 합니다.",
            )
        )

    excessive_choices = re.search(r"\b(\d+)~(\d+)개\s*선택지", text)
    if excessive_choices and int(excessive_choices.group(2)) > 5:
        findings.append(
            Violation(
                "MENU_ACTION_OVERLOAD",
                path,
                "실행 선택지는 최대 5개를 넘기지 않아야 합니다.",
                _line_of(text, excessive_choices.group(0)),
            )
        )

    time_signal = re.search(
        r"오늘|이번 주|7일|30일|2주|다음 대화 전|월간|월말|종료일|10분|언제든",
        text,
    )
    observable_signal = re.search(
        r"기록|확인|완료|결과|유지|수정|중단|적기|질문|비교|행동 증거",
        text,
    )
    sized_signal = re.search(
        r"\d+\s*(?:[~–-]\s*\d+\s*)?(?:분|번|개|줄|일|주)|한 번|한 가지|1문장",
        text,
    )
    if not (time_signal and observable_signal and sized_signal):
        findings.append(
            Violation(
                "MENU_ACTION_CARD_CONTRACT",
                path,
                "실행 설계에 시점·관찰 가능한 행동·끝낼 수 있는 크기·검토 신호가 모두 필요합니다.",
            )
        )

    if menu_id == 12 and not all(marker in text for marker in ("오늘", "피할")):
        findings.append(
            Violation(
                "MENU_DAILY_ACTION",
                path,
                "오늘의운세는 '오늘 10분' 행동 1개와 피할 것 1개가 필요합니다.",
            )
        )
    if menu_id == 15 and not all(marker in text for marker in ("구조화", "질문 3개", "행동 증거")):
        findings.append(
            Violation(
                "MENU_HIRING_ACTION",
                path,
                "채용 메뉴는 동일한 직무 관련 구조화 질문 3개와 행동 증거를 제공해야 합니다.",
            )
        )

    _add_missing(
        findings,
        text=text,
        needle=COMMON_DISCLAIMER,
        code="MENU_COMMON_DISCLAIMER",
        path=path,
        message="공통 면책 원문이 정확히 보존돼야 합니다.",
    )
    if COMMON_DISCLAIMER in text:
        common_end = text.rfind(COMMON_DISCLAIMER) + len(COMMON_DISCLAIMER)
        if text[common_end:].strip():
            findings.append(
                Violation(
                    "MENU_DISCLAIMER_ORDER",
                    path,
                    "메뉴별 추가 단서를 먼저 쓰고 공통 면책을 맨 마지막에 둬야 합니다.",
                )
            )

    special_requirements: dict[int, tuple[tuple[str, str, str], ...]] = {
        4: (
            (SENSITIVE_READING_WARNING, "MENU_SENSITIVE_WARNING", "민감 열람 경고가 필요합니다."),
            ("저위험 행동", "MENU_SOFTENING_ACTION", "공포를 키우지 않는 현실 기반 저위험 행동이 필요합니다."),
        ),
        10: (
            (SENSITIVE_READING_WARNING, "MENU_SENSITIVE_WARNING", "민감 열람 경고가 필요합니다."),
            ("저위험", "MENU_SOFTENING_ACTION", "신살 해석은 현실 기반 저위험 행동으로 닫아야 합니다."),
        ),
        13: ((MEDICAL_DISCLAIMER, "MENU_MEDICAL_DISCLAIMER", "의료 비진단 단서가 필요합니다."),),
        14: (
            (BUSINESS_DISCLAIMER, "MENU_BUSINESS_DISCLAIMER", "사업 궁합 추가 면책이 필요합니다."),
            (
                "동업·투자·계약의 가부나 수익을 판정하지 않는다",
                "MENU_BUSINESS_HARD_GATE",
                "동업·투자·계약의 가부와 수익 판정 금지 규칙이 필요합니다.",
            ),
        ),
        15: (
            (HIRING_DISCLAIMER, "MENU_HIRING_DISCLAIMER", "채용 추가 면책이 필요합니다."),
            ("## 절대 금지", "MENU_HIRING_HARD_GATE", "채용 출력 직전 금지 게이트가 필요합니다."),
            (
                "직무 관련 자격·역량",
                "MENU_HIRING_JOB_FIRST",
                "직무 자격·역량 우선 원칙이 필요합니다.",
            ),
            (
                "성향 카드·검사 유형을 채용 판단에 사용",
                "MENU_HIRING_PERSONALITY_EXCLUSION",
                "성향 카드·검사 유형의 채용 판단 사용 금지가 필요합니다.",
            ),
        ),
    }
    for needle, code, message in special_requirements.get(menu_id, ()):
        _add_missing(
            findings,
            text=text,
            needle=needle,
            code=code,
            path=path,
            message=message,
        )

        if (
            needle in text
            and COMMON_DISCLAIMER in text
            and text.rfind(needle) > text.rfind(COMMON_DISCLAIMER)
        ):
            findings.append(
                Violation(
                    "MENU_DISCLAIMER_ORDER",
                    path,
                    "메뉴별 추가 단서는 공통 면책보다 앞에 있어야 합니다.",
                )
            )

    return findings


def validate_prompt_contract(root: str | Path | None = None) -> list[Violation]:
    """SKILL/brand/15개 메뉴의 정적 품질 계약을 검사한다."""

    skill_root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    findings: list[Violation] = []

    brand_rel = "reference/brand.md"
    output_contract_rel = "reference/output-contract.md"
    action_library_rel = "reference/action-library.md"
    mbti_layer_rel = "reference/mbti-layer.md"
    input_form_rel = "reference/input-form.html"
    skill_rel = "SKILL.md"
    brand_text = _read(skill_root / brand_rel, findings, brand_rel)
    output_contract_text = _read(
        skill_root / output_contract_rel, findings, output_contract_rel
    )
    action_library_text = _read(
        skill_root / action_library_rel, findings, action_library_rel
    )
    if action_library_text is None:
        findings.append(
            Violation(
                "ACTION_LIBRARY_FILE_MISSING",
                action_library_rel,
                "사주 신호를 생활 행동으로 번역하는 공통 기준 파일이 필요합니다.",
            )
        )
    mbti_layer_text = _read(skill_root / mbti_layer_rel, findings, mbti_layer_rel)
    input_form_text = _read(skill_root / input_form_rel, findings, input_form_rel)
    skill_text = _read(skill_root / skill_rel, findings, skill_rel)

    brand: dict[str, str] = {}
    if brand_text is not None:
        brand = _parse_brand_table(brand_text, brand_rel, findings)
        for needle, code, message in (
            ("단일 소스", "BRAND_SINGLE_SOURCE", "브랜드 단일 소스 선언이 필요합니다."),
            ("HARD-LOCK", "BRAND_HARD_LOCK", "브랜드 법무 HARD-LOCK이 필요합니다."),
            ("원문 복제 절대 금지", "BRAND_COPY_GUARD", "타사 문구 원문 복제 금지가 필요합니다."),
            ("단일 창구 원칙", "BRAND_SINGLE_VOICE", "사용자 노출 화자의 단일 창구 원칙이 필요합니다."),
        ):
            _add_missing(
                findings,
                text=brand_text,
                needle=needle,
                code=code,
                path=brand_rel,
                message=message,
            )

    if output_contract_text is not None:
        findings.extend(
            _validate_output_contract(output_contract_text, output_contract_rel)
        )

    if action_library_text is not None:
        findings.extend(_validate_action_library(action_library_text, action_library_rel))

    if mbti_layer_text is not None:
        findings.extend(_validate_mbti_layer(mbti_layer_text, mbti_layer_rel))

    if input_form_text is not None:
        findings.extend(_validate_input_form(input_form_text, input_form_rel))

    findings.extend(_validate_host_compatibility(skill_root))

    if skill_text is not None:
        findings.extend(_validate_skill(skill_text, skill_rel, brand))

    menu_dir = skill_root / "menus"
    if not menu_dir.is_dir():
        findings.append(Violation("MENU_DIRECTORY_MISSING", "menus", "메뉴 디렉터리가 없습니다."))
    else:
        actual_names = {path.name for path in menu_dir.glob("*.md")}
        expected_names = set(MENU_FILES.values())
        for missing in sorted(expected_names - actual_names):
            findings.append(Violation("MENU_FILE_MISSING", f"menus/{missing}", "필수 메뉴 파일이 없습니다."))
        for unexpected in sorted(actual_names - expected_names):
            findings.append(
                Violation(
                    "MENU_FILE_UNREGISTERED",
                    f"menus/{unexpected}",
                    "등록되지 않은 메뉴입니다. 계약 목록과 라우터를 함께 갱신하세요.",
                )
            )

    for menu_id, filename in MENU_FILES.items():
        relative = f"menus/{filename}"
        text = _read(skill_root / relative, findings, relative)
        if text is not None:
            findings.extend(_validate_menu(menu_id, text, relative))

    return _sorted_findings(findings)


def _strip_fixed_disclaimers(text: str) -> str:
    body = text
    for disclaimer in (
        COMMON_DISCLAIMER,
        MEDICAL_DISCLAIMER,
        PERCENT_DISCLAIMER,
        BUSINESS_DISCLAIMER,
        HIRING_DISCLAIMER,
        PERSONALITY_DISCLAIMER,
    ):
        body = body.replace(disclaimer, "")
    return body


def _hanja_outside_parentheses(text: str) -> tuple[str, int] | None:
    depth = 0
    for index, char in enumerate(text):
        if char in "(（":
            depth += 1
        elif char in ")）":
            depth = max(0, depth - 1)
        elif depth == 0 and ("\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"):
            return char, index
    return None


def _has_concrete_action(text: str) -> bool:
    measurable = re.search(r"\d+\s*(?:분|시간|번|개|줄|잔|회|일|주|개월)", text)
    korean_measure = re.search(
        r"(?:오늘|지금|아침|점심|저녁|자기 전|출근 전|퇴근 후|매일|매주|하루|한 주에)"
        r".{0,35}(?:하나|한 번|한 줄|한 잔|몇 분|잠깐)",
        text,
    )
    return bool(measurable or korean_measure)


def validate_customer_output(
    text: str,
    menu_id: int,
) -> list[Violation]:
    """생성된 고객용 풀이 한 건의 안전·실천성·한국어 톤을 검사한다.

    이는 의미 평가를 대체하지 않는 저비용 하드 게이트다. 반환값이 비어 있으면
    기계적으로 확인 가능한 최소 계약을 통과한 것이다.
    """

    path = f"output:M{menu_id:02d}" if isinstance(menu_id, int) else "output"
    findings: list[Violation] = []
    if menu_id not in MENU_FILES:
        return [Violation("OUTPUT_MENU_ID", path, "메뉴 번호는 1~15여야 합니다.")]
    if not text or not text.strip():
        return [Violation("OUTPUT_EMPTY", path, "풀이 결과가 비어 있습니다.")]

    disclaimer_index = text.find(COMMON_DISCLAIMER)
    if disclaimer_index < 0:
        findings.append(
            Violation("OUTPUT_COMMON_DISCLAIMER", path, "공통 면책 원문이 없습니다.")
        )
        body = _strip_fixed_disclaimers(text)
    else:
        body = _strip_fixed_disclaimers(text[:disclaimer_index])
        tail = text[disclaimer_index + len(COMMON_DISCLAIMER) :]
        if tail.strip():
            findings.append(
                Violation(
                    "OUTPUT_DISCLAIMER_ORDER",
                    path,
                    "메뉴별·성향 추가 단서를 먼저 쓰고 공통 면책을 맨 마지막에 둬야 합니다.",
                )
            )

    if menu_id not in (12, 15):
        action_markers = ("오늘 10분", "이번 주 실험", "7일 뒤")
        missing = [marker for marker in action_markers if marker not in body]
        if missing:
            findings.append(
                Violation(
                    "OUTPUT_ACTION_CARDS",
                    path,
                    "실행 카드가 빠졌습니다: " + ", ".join(missing),
                )
            )
        # "완료 기준"은 설계 문서 어휘라 INTERNAL_JARGON_TERMS로 막는다.
        # 대신 고객이 읽는 사람 말 형태를 허용한다.
        if not re.search(
            r"남으면 완료|하면 완료|되면 완료"
            r"|(?:하|되|졌|었)으?면\s*(?:그날은|오늘은|그 주는|이번 주는)?\s*된 거"
            r"|(?:그날은|오늘은|그 주는|이번 주는)\s*된 거"
            r"|까지 하면 충분해|하면 충분해",
            body,
        ):
            findings.append(
                Violation(
                    "OUTPUT_COMPLETION_CRITERION",
                    path,
                    "실행 카드에 고객이 끝냈는지 알 수 있는 신호가 필요합니다"
                    "(예: '메모 세 줄이 남으면 완료야', '줄이 하나 그어졌으면 오늘은 된 거야').",
                )
            )
        if not all(marker in body for marker in ("유지", "수정", "중단")):
            findings.append(
                Violation(
                    "OUTPUT_FEEDBACK_LOOP",
                    path,
                    "7일 뒤 유지·수정·중단을 고르는 검토 기준이 필요합니다.",
                )
            )
        action_type_patterns = {
            "활용": r"하면 좋은 행동|활용할 행동|더 해볼 행동|오늘 10분",
            "주의": r"조심할 행동|줄일 행동|이번에는 하지 않을 것|피할 것|중단 기준",
            "확인": r"7일 뒤|확인 질문|검토 기준",
        }
        missing_types = [
            action_type
            for action_type, pattern in action_type_patterns.items()
            if not re.search(pattern, body)
        ]
        if missing_types:
            findings.append(
                Violation(
                    "OUTPUT_ACTION_TYPE_COVERAGE",
                    path,
                    "실행 카드에는 활용·주의·확인 행동이 모두 필요합니다: "
                    + ", ".join(missing_types),
                )
            )
    elif menu_id == 12 and not all(marker in body for marker in ("오늘 10분", "피할 것")):
        findings.append(
            Violation("OUTPUT_DAILY_ACTION", path, "오늘의운세에는 오늘 10분 행동과 피할 것 하나가 필요합니다.")
        )
    elif menu_id == 15 and not all(marker in body for marker in ("직무", "구조화", "행동 증거")):
        findings.append(
            Violation(
                "OUTPUT_HIRING_ACTION",
                path,
                "채용 풀이는 동일한 직무 관련 구조화 질문과 행동 증거를 제공해야 합니다.",
            )
        )

    if menu_id != 15 and not _has_concrete_action(body):
        findings.append(
            Violation(
                "OUTPUT_ABSTRACT_ACTION",
                path,
                "실천 조언에 시점·관찰 가능한 행동·시간/횟수/단위를 넣어주세요.",
            )
        )

    personality_referenced = re.search(
        r"스스로 (?:알려준|밝힌) 성향|선택 성향|성향 정보를 반영",
        body,
    )
    if personality_referenced:
        if PERSONALITY_DISCLAIMER not in text:
            findings.append(
                Violation(
                    "OUTPUT_PERSONALITY_DISCLAIMER",
                    path,
                    "선택 성향을 실제 반영했다면 성향 추가 단서를 공통 면책 앞에 붙여야 합니다.",
                )
            )
        if not re.search(r"글로 먼저|말로 먼저|단계|일정|두 가지 방법|선택지", body):
            findings.append(
                Violation(
                    "OUTPUT_PERSONALITY_EXECUTION_METHOD",
                    path,
                    "선택 성향은 행동 주제가 아니라 글·대화·계획·선택지 같은 실행 방식에만 반영해야 합니다.",
                )
            )

    modern_banmal = re.search(
        r"(?:해|돼|있어|보여|거야|할게|보자|좋아|말아)(?:[.!?…]|$)",
        body,
        flags=re.MULTILINE,
    )
    modern_polite = re.search(
        r"(?:해요|돼요|있어요|보여요|거예요|할게요|보세요|하세요)(?:[.!?…]|$)",
        body,
        flags=re.MULTILINE,
    )
    if menu_id == 15 and not modern_polite:
        findings.append(
            Violation("OUTPUT_VOICE", path, "채용 참고 결과는 전문적이고 자연스러운 존댓말로 써야 합니다.")
        )
    elif menu_id != 15 and not (modern_banmal or modern_polite):
        findings.append(
            Violation(
                "OUTPUT_VOICE",
                path,
                "자연스러운 현대 반말 또는 고객이 요청한 해요체가 확인되지 않습니다.",
            )
        )

    signature_endings = re.findall(r"(?:구나|보렴|하렴|란다)(?:[.!?…]|$)", body)
    if menu_id != 15 and modern_banmal and not 2 <= len(signature_endings) <= 4:
        findings.append(
            Violation(
                "OUTPUT_SIGNATURE_TONE_COUNT",
                path,
                f"할머니 느낌의 포인트 어미는 전체 2~4회만 써야 합니다(현재 {len(signature_endings)}회).",
            )
        )

    # 호칭으로 쓰인 '아가'만 센다. 부분문자열로 세면 돌아가·나아가·살아가 같은
    # 일상 동사가 그대로 걸린다.
    # 앞 글자가 한글이면 돌아가·나아가·살아가처럼 동사의 꼬리다.
    # 뒤쪽은 조사가 붙을 수 있어 열어둔다(아가야·아가는·아가라고).
    address_pattern = r"(?<![가-힣])아가(?!씨)"
    baby_matches = list(re.finditer(address_pattern, body))
    baby_count = len(baby_matches)
    if baby_count > 1 or (baby_count == 1 and baby_matches[0].start() > 160):
        findings.append(
            Violation(
                "OUTPUT_ADDRESS_OVERUSE",
                path,
                "'아가'는 첫 인사에서만 최대 1회 쓸 수 있습니다.",
                body.count("\n", 0, baby_matches[0].start()) + 1,
            )
        )

    awkward_terms = (
        "하룻밤 재우",
        "고 자시고",
        "동무",
        "꿍하",
        "너식(式)",
        "의원 찾아가렴",
    )
    found_awkward = next((term for term in awkward_terms if term in body), None)
    if found_awkward:
        findings.append(
            Violation(
                "OUTPUT_AWKWARD_KOREAN",
                path,
                f"요즘 독자가 바로 이해하기 어려운 표현입니다: {found_awkward}",
                _line_of(body, found_awkward),
            )
        )

    archaic = re.search(r"(?:하거라|려무나)(?:[.!?…]|$)", body)
    if archaic:
        findings.append(
            Violation(
                "OUTPUT_ARCHAIC_VOICE",
                path,
                f"과한 고어 어미는 사용하지 않습니다: {archaic.group(0)}",
                _line_of(body, archaic.group(0)),
            )
        )

    leaked_jargon = [term for term in INTERNAL_JARGON_TERMS if term in body]
    if leaked_jargon:
        findings.append(
            Violation(
                "OUTPUT_INTERNAL_JARGON",
                path,
                "설계 문서 용어가 고객 문장에 남았습니다: "
                + ", ".join(leaked_jargon)
                + ". reference/voice-and-exemplar.md §1의 사람 말로 바꿔주세요.",
                _line_of(body, leaked_jargon[0]),
            )
        )

    disrespectful = next((term for term in DISRESPECTFUL_TERMS if term in body), None)
    if disrespectful:
        findings.append(
            Violation(
                "OUTPUT_DISRESPECTFUL_VOICE",
                path,
                f"성인 고객을 유아화하거나 낡게 들리는 표현입니다: {disrespectful}",
                _line_of(body, disrespectful),
            )
        )

    metaphor_count = body.count("보따리") + body.count("실타래")
    if metaphor_count > 2:
        findings.append(
            Violation(
                "OUTPUT_CHARACTER_OVERUSE",
                path,
                f"캐릭터 비유가 {metaphor_count}회입니다(보따리·실타래 합계 최대 2회).",
            )
        )

    emoji_count = sum(1 for char in body if char in "🌙✨🧧")
    if emoji_count > 1:
        findings.append(
            Violation("OUTPUT_EMOJI_OVERUSE", path, f"시그니처 이모지가 {emoji_count}개입니다(최대 1개).")
        )

    fatalistic_patterns = (
        r"반드시.{0,20}(?:된다|한다|생긴다|망한다)",
        r"(?:큰일 난다|죽는다|파산한다|이혼한다)",
        r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일.{0,20}(?:사고|사망)",
    )
    for pattern in fatalistic_patterns:
        match = re.search(pattern, body)
        if match:
            findings.append(
                Violation(
                    "OUTPUT_FATALISTIC_CLAIM",
                    path,
                    f"운명·공포를 단정하는 표현입니다: {match.group(0)}",
                    _line_of(body, match.group(0)),
                )
            )
            break

    mbti_leak = re.search(r"\bMBTI\b|(?<![A-Z])[EI][SN][TF][JP](?![A-Z])", body, flags=re.IGNORECASE)
    if mbti_leak:
        findings.append(
            Violation(
                "OUTPUT_PERSONALITY_CODE_LEAK",
                path,
                "고객 결과에는 검사명·4글자 유형코드 대신 쉬운 '성향' 언어만 써야 합니다.",
                _line_of(body, mbti_leak.group(0)),
            )
        )

    raw_field = re.search(
        r"(?<![A-Za-z0-9_])"
        r"(?:pillars|dayMaster|fiveElements|tenGods|majorShinsal|daewoon|mbti_card)"
        r"(?![A-Za-z0-9_])",
        body,
    )
    if raw_field:
        findings.append(
            Violation(
                "OUTPUT_RAW_FIELD_LEAK",
                path,
                f"내부 엔진 필드명이 노출됐습니다: {raw_field.group(0)}",
                _line_of(body, raw_field.group(0)),
            )
        )

    hanja = _hanja_outside_parentheses(body)
    if hanja:
        char, index = hanja
        findings.append(
            Violation(
                "OUTPUT_HANJA_EXPOSURE",
                path,
                f"한자 '{char}'가 한글 풀이 없이 단독 노출됐습니다.",
                body.count("\n", 0, index) + 1,
            )
        )

    special_output_requirements: dict[int, tuple[tuple[str, str, str], ...]] = {
        3: ((PERCENT_DISCLAIMER, "OUTPUT_PERCENT_DISCLAIMER", "퍼센트 사용 시 수치 비보장 단서가 필요합니다."),),
        4: (
            (SENSITIVE_READING_WARNING, "OUTPUT_SENSITIVE_WARNING", "민감 열람 경고가 필요합니다."),
            ("기록", "OUTPUT_SOFTENING_ACTION", "무속 해석은 현실에서 확인할 저위험 행동으로 닫아야 합니다."),
        ),
        8: ((PERCENT_DISCLAIMER, "OUTPUT_PERCENT_DISCLAIMER", "퍼센트 사용 시 수치 비보장 단서가 필요합니다."),),
        10: (
            (SENSITIVE_READING_WARNING, "OUTPUT_SENSITIVE_WARNING", "민감 열람 경고가 필요합니다."),
            ("기록", "OUTPUT_SOFTENING_ACTION", "신살 해석은 현실에서 확인할 저위험 행동으로 닫아야 합니다."),
        ),
        13: ((MEDICAL_DISCLAIMER, "OUTPUT_MEDICAL_DISCLAIMER", "의료 비진단 단서가 필요합니다."),),
        14: ((BUSINESS_DISCLAIMER, "OUTPUT_BUSINESS_DISCLAIMER", "사업 궁합 추가 면책이 필요합니다."),),
        15: ((HIRING_DISCLAIMER, "OUTPUT_HIRING_DISCLAIMER", "채용 추가 면책이 필요합니다."),),
    }
    for needle, code, message in special_output_requirements.get(menu_id, ()):
        if menu_id in (3, 8) and "%" not in text:
            continue
        if needle not in text:
            findings.append(Violation(code, path, message))
        elif disclaimer_index >= 0 and text.rfind(needle) > disclaimer_index:
            findings.append(
                Violation(
                    "OUTPUT_DISCLAIMER_ORDER",
                    path,
                    "메뉴별 추가 단서는 공통 면책보다 앞에 있어야 합니다.",
                )
            )

    if (
        PERSONALITY_DISCLAIMER in text
        and disclaimer_index >= 0
        and text.rfind(PERSONALITY_DISCLAIMER) > disclaimer_index
    ):
        findings.append(
            Violation(
                "OUTPUT_DISCLAIMER_ORDER",
                path,
                "성향 추가 단서는 공통 면책보다 앞에 있어야 합니다.",
            )
        )

    if menu_id == 15:
        clean_hiring_body = _strip_fixed_disclaimers(text)
        verdict = re.search(
            r"뽑아라|뽑지 마라|거르라|채용 부적합|탈락 권장|"
            r"채용 적합도\s*\d+점|[ABC]\s*등급|합격선|커트라인",
            clean_hiring_body,
        )
        if verdict:
            findings.append(
                Violation(
                    "OUTPUT_HIRING_VERDICT",
                    path,
                    f"채용 가부·점수화 표현이 금지됩니다: {verdict.group(0)}",
                    _line_of(clean_hiring_body, verdict.group(0)),
                )
            )

    return _sorted_findings(findings)


def _render(findings: Iterable[Violation], *, as_json: bool) -> str:
    items = list(findings)
    if as_json:
        return json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2)
    return "\n".join(item.render() for item in items)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="삼신이 고객 결과물 품질 계약 검사")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="saju-reading 스킬 루트(기본: 이 스크립트의 상위 폴더)",
    )
    parser.add_argument("--output", type=Path, help="추가로 검사할 고객용 풀이 텍스트 파일")
    parser.add_argument("--menu", type=int, choices=range(1, 16), help="--output의 메뉴 번호(1~15)")
    parser.add_argument("--json", action="store_true", help="위반 결과를 JSON으로 출력")
    args = parser.parse_args(argv)

    if args.output is not None and args.menu is None:
        parser.error("--output을 쓰려면 --menu도 지정해야 합니다.")

    findings = validate_prompt_contract(args.root)
    if args.output is not None:
        try:
            output_text = args.output.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(
                Violation("OUTPUT_READ_ERROR", str(args.output), f"출력 파일을 읽지 못했습니다: {exc}")
            )
        else:
            findings.extend(validate_customer_output(output_text, args.menu))

    findings = _sorted_findings(findings)
    if findings:
        print(_render(findings, as_json=args.json))
        if not args.json:
            print(f"\n품질 계약 실패: {len(findings)}건", file=sys.stderr)
        return 1

    if args.json:
        print("[]")
    else:
        suffix = " + 고객용 풀이" if args.output is not None else ""
        print(f"품질 계약 통과: SKILL/brand/15개 메뉴{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
