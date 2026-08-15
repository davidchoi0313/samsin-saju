# samsin-saju 개선 계획서 (2026-08-16)

> 작성: Cowork 세션(전수 검증 완료 상태 기준). 실행: 로컬 Claude Code.
> 검증 근거: 테스트 106개 전체 통과, 엔진 전 모드(기본·궁합·음력 윤달·세운·오늘·토정) 실행 확인,
> OpenAI 공식 문서(developers.openai.com/plugins, learn.chatgpt.com/docs/build-skills)와 구조 대조 완료.
> 아래 순서(Phase 0 → 1 → 2 → 3)대로 진행한다. 각 Phase 끝의 "검증"을 통과해야 다음으로 넘어간다.

---

## Phase 0 — 배포 차단 해제 (최우선, 5분)

현재 GitHub HEAD(d4b63d1)에는 따옴표로 시작하는 깨진 경로
`"plugins/samsin-saju/docs/사용매뉴얼.md` 가 남아 있어 **Windows에서 marketplace 설치가
`error: invalid path` 로 실패**한다. 이를 지우는 커밋(0fdce09)은 로컬에만 있다.

- [ ] `git status -sb` 로 `ahead 1` 확인 후 `git push origin main`
- [ ] 참고: 레포 루트의 `_to_delete/` 폴더는 Cowork 검토 중 생긴 임시 파일 보관용이다. 폴더째 삭제한다 (git 미추적이므로 그냥 지우면 됨).

**검증**: `git ls-tree origin/main --name-only | findstr /B """` 결과가 비어 있어야 한다.
가능하면 새 폴더에 `git clone` 해서 Windows에서 오류 없이 체크아웃되는지 확인.

---

## Phase Q — 결과물 품질 개선 (담당자 최우선 요청, Phase 0 직후 진행)

**배경(진단)**: 결과물이 어색하고 추상적인 원인은 규칙 부족이 아니라 다음 4가지다.
① 완성된 모범 답안이 레포에 없어 모델이 매번 문체를 발명한다(최대 원인).
② action-library의 범용 템플릿("메모 3줄" 등)이 그대로 반복돼 누구에게나 같은 말이 된다.
③ "실행 장치·완료 기준·산출 카드" 같은 설계 문서 어휘가 고객 출력에 누출돼 보고서 문체가 된다.
④ 길이 상한이 낮아 개인화된 서사를 펼칠 밀도가 안 나온다(담당자: 길어도 좋음).

**전제**: `reference/voice-and-exemplar.md` 가 새로 추가되어 있다(Cowork 세션이 실제 엔진 카드
값에 근거해 집필·배치 완료). 문장 코퍼스 + 교정 전후 표 + 평생사주 모범 답안 전문 포함.

- [ ] **Q-1. SKILL.md 연결**: §2.3 출력 계약 문단에 `reference/voice-and-exemplar.md` 를
  output-contract·action-library 와 함께 필독 파일로 추가. §3 보이스 절 끝에
  "문체가 흔들리면 voice-and-exemplar.md 의 모범 답안 결을 기준으로 되돌린다" 1줄 추가.
- [ ] **Q-2. output-contract.md 개정**:
  - §5 길이표 상향: 평생사주 3,500~6,000자 / 일반 메뉴 2,500~4,500자 / 상징 메뉴 2,200~3,800자
    (오늘의 운세·채용은 유지). "하한 채우기용 반복 금지" 문구는 유지.
  - §3에 규칙 추가: "내부 용어 누출 금지 — voice-and-exemplar.md §1 표의 왼쪽 단어를
    고객 문장에 쓰지 않는다."
  - §3에 규칙 추가: "개인화 검증 — 쓴 문장을 다른 사주에 붙여도 말이 되면 다시 쓴다."
  - §4.5에 규칙 추가: "action-library 의 예시 문구를 그대로 복사하지 않는다. 명사·장면·숫자를
    그 고객의 카드 값과 상황으로 바꾼 뒤에만 쓴다."
- [ ] **Q-3. action-library.md 확장**: §3·§4 표의 각 칸을 '생활 장면 은행'으로 확장 —
  칸마다 서로 다른 생활 영역(일/돈/관계/말버릇/생활 리듬)의 장면 예시 2개 이상.
  기존 문구는 유지하되 "예시는 결만 참고, 그대로 복사 금지" 헤더를 문서 상단에 추가.
  문체는 voice-and-exemplar.md 의 결을 따른다.
- [ ] **Q-4. mbti-layer.md 확장**: 성향 반영 범위를 '실행 방식 한 줄'에서 '습관 설계 4요소
  (시간대·환경·기록 방식·확인 방식)'로 확장. 단 기존 안전선(성향을 사주 근거·점수·낙인으로
  쓰지 않음, 코드 미노출)은 문구 그대로 유지.
- [ ] **Q-5. quality_contract.py 보강**: 고객 출력 검사(--output) 시 내부 용어 누출을
  Violation 으로 검출 — 금지어: "실행 장치", "완료 기준", "산출 카드", "성향 카드",
  "계산 관찰", "행동 후보", "관찰 지표". 대응 테스트를 tests/test_quality_contract.py 에 추가.
- [ ] **Q-6. 검증(전후 비교)**: 서로 다른 사주 3건(생시 미상 1건 포함)으로 평생사주·올해운세
  산출물을 생성해 ① 내부 용어 0건 ② 문장을 다른 사주에 바꿔 붙이면 어색해지는지(개인화)
  ③ 행동에 시점·동사·분량·끝났다는 신호가 있는지 점검. 개정 전 산출물과 나란히 비교해
  차이가 없으면 Q-2~Q-4를 다시 손본다.

**검증**: pytest 전체 통과 + Q-6 비교 기록을 커밋 메시지 또는 PR 본문에 남긴다.

---

## Phase 1 — 배포 안정화

### 1-1. 낡은 문서 3종 제거·통합

아래 3개 파일은 v0.4.0 시절 내용이라 **지금 따라 하면 역효과**가 난다
(특히 FIX 문서의 JSON 스니펫을 붙여넣으면 현행 0.7.1 매니페스트가 옛 버전으로 덮인다).

- [ ] `FIX_MARKETPLACE_RECOGNITION.md` 삭제
- [ ] `PUSH_GUIDE.md` 삭제 (옛 경로 `D:/Cowork/...`, 옛 레포명 `samsin-saju-marketplace` 기준)
- [ ] `PUSH_MBTI_UPLOAD.ps1` 삭제 (이미 완료된 일회성 업로드 스크립트)
- [ ] 대체 문서 `docs/RELEASE.md` 신설 — 다음 내용만 간결히:
  - 현재 레포 경로(`D:\repos\samsin-saju`) 기준 push 절차 (`git add -A` → commit → push)
  - "GitHub 웹 드래그&드롭 업로드 금지" 경고 (숨김 폴더 누락 사고 이력)
  - 버전 올릴 때 체크리스트: 3개 매니페스트 버전 동기(1-2 참조) → 테스트 → `python3 openai-submission/build_archive.py` → push
  - 참고: 레포 루트에는 docs/ 폴더가 없고 `plugins/samsin-saju/docs/`만 있다. RELEASE.md는 레포 루트에 `RELEASE.md`로 두거나 루트 `docs/`를 새로 만들어도 된다(권장: 루트에 `RELEASE.md`).

### 1-2. 버전 동기화 자동 검사

버전이 세 곳에 흩어져 있다: 루트 `.claude-plugin/marketplace.json`(plugins[0].version),
`plugins/samsin-saju/.claude-plugin/plugin.json`(version), `plugins/samsin-saju/.codex-plugin/plugin.json`(version).
현재는 셋 다 0.7.1로 일치하지만 자동 검사가 없다.

- [ ] `scripts/quality_contract.py` 의 `validate_prompt_contract()` 에 검사 추가:
  세 파일의 버전이 모두 존재하고 동일하지 않으면 `VERSION_MISMATCH` Violation 반환.
  (이 함수는 `tests/test_quality_contract.py::TestLivePromptContract` 가 이미 레포 전체를 대상으로
  호출하므로, 여기에 넣으면 별도 테스트 없이 pytest가 자동으로 잡는다.)
  주의: 이 함수는 스킬 루트 기준 상대 경로로 동작한다 — 기존 `PRIVACY.md` 등 레포 루트 파일을
  찾는 로직과 같은 방식으로 루트를 해석할 것.

### 1-3. Windows 경로 안전 검사 (이번 사고 재발 방지)

- [ ] 같은 `validate_prompt_contract()` 에 추가: 레포 내 모든 추적 파일 경로에
  Windows 금지 문자(`< > : " | ? *`, 제어문자)나 후행 점·공백이 있으면 `WINDOWS_UNSAFE_PATH` Violation.
  (`.git/` 제외, `git ls-files` 대신 os.walk 사용 시 `.git`·`__pycache__` 스킵)

**검증**: `python -m pytest tests/ scripts/test_mbti_engine.py` 전체 통과(현재 106개 + 신규).
일부러 버전 하나를 바꿔 실패가 나는지 확인 후 원복.

---

## Phase 2 — 스토어 등록 정보 정합화

### 2-1. 카테고리 불일치 해소

현재 `openai-submission/listing.md` 는 `Category: Lifestyle`,
루트 marketplace.json 은 `entertainment`, `.agents/plugins/marketplace.json` 은 `Entertainment`.

- [ ] **Entertainment 로 통일** (풀이 성격상 오락·참고용 포지셔닝과 일치, 면책 문구와도 정합).
  listing.md 의 Category 를 Entertainment 로 수정. 제출 포털의 실제 카테고리 목록에
  Entertainment 가 없고 Lifestyle 만 있으면 그때 반대로 통일하고 이 계획서에 메모.

### 2-2. 스타터 프롬프트 ↔ 엔진 능력 모순 수정 (중요)

`listing.md` 스타터 프롬프트 2번: "올해 운세에서 하면 좋은 행동과 조심할 습관을 **월별로** 알려 줘."
그러나 엔진 `sewoon` 카드에는 연간 간지(`ganZhi`)와 충 목록만 있고 **월별 데이터가 없다**.
SKILL 규칙("카드에 없는 특정 월을 만들지 않는다")과 정면 충돌 — AI가 답을 못 하거나 지어내게 유도하는 문구다.

- [ ] Phase 3-A(세운 월운 추가)를 진행하는 경우: 프롬프트 유지, 엔진 보강 후 재검증.
- [ ] Phase 3-A를 미루는 경우: 프롬프트를 "올해 운세에서 하면 좋은 행동과 조심할 습관을
  실행 카드로 정리해 줘."로 수정.

### 2-3. README 구조 정리

- [ ] 설치 경로 3종(Claude 데스크톱 / ChatGPT·Codex / ChatGPT 모바일) 중 부차적 경로는
  `<details>` 접기로 이동해 첫 화면을 짧게.
- [ ] 링크 전수 확인(현재 developers.openai.com 링크는 learn.chatgpt.com 으로 리다이렉트됨 —
  동작은 하므로 유지 가능, 깨진 링크만 수정).
- [ ] 15메뉴 표가 상단·중단 두 번 나오는 중복 정리(예시 발화 표 하나로 병합 검토).

**검증**: `python3 openai-submission/build_archive.py` 성공 + zip 루트가 `samsin-saju/` 단일인지,
tests/docs/agents/quality_contract.py 가 zip에 없는지 확인. pytest 전체 통과.

---

## Phase 3 — 엔진·기능 개선 (아래 표의 승인 상태에 따라 진행)

| 항목 | 내용 | 권장 | 승인 |
|---|---|---|---|
| A. 세운 월운 추가 | `sewoon.monthly[]`: 대상 연도 12개월의 월주 간지·오행·일간 기준 십신·원국과의 충합. lunar-python으로 결정론 산출 가능. 2-2 모순의 근본 해결 | ◎ 강력 권장 | 대기 |
| B. 출생 시간대 한계 명시 | 엔진은 KST(135°E 표준시) 출생 가정. 최소안: SKILL 입력 표와 README에 "한국 출생 기준, 해외 출생은 보정 미지원" 명시. 확장안: `--utc-offset` 옵션 추가 | ○ 최소안 권장 | 대기 |
| C. 분 단위 생시 노출 | 엔진에 이미 있는 `--time-hm HH:MM` 을 SKILL.md 7장 호출 예시와 5장 입력 표에 문서화. 시 경계(예: 07:29/07:31) 오차 방지 | ◎ 권장(코드 변경 없음) | 대기 |
| D. E2E 발화 테스트 | `openai-submission/test-cases.md` P1~P5·N1~N3을 반자동 검증하는 체크 스크립트 | △ 여유 시 | 대기 |

- A 구현 시: 카드 스키마 변경이므로 `menus/02-olhae.md` 의 세운 해석 지침에 월운 사용 규칙 1~2줄 추가,
  `tests/test_engine.py` 에 월운 12개·간지 형식·재현성 테스트 추가.
- 어떤 항목이든 완료 후 pytest 전체 + build_archive 재실행.

---

## 마무리 공통 절차

- [ ] 버전 결정: Phase Q(풀이 품질 개정)가 포함되므로 0.8.0 권장 — 3개 매니페스트 동시 변경
- [ ] pytest 전체 통과 확인 후 커밋·푸시 (커밋은 Phase 단위로 분리 권장)
- [ ] 푸시 후 GitHub에서 삭제 문서가 사라졌는지, Windows 신규 clone이 되는지 최종 확인
- [ ] 이 계획서(IMPROVEMENT_PLAN.md)는 작업 완료 후 삭제하거나 docs로 이동
