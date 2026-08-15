# OpenAI 공개 플러그인 등록 자료

## Listing

- Plugin name: 삼신이 사주풀이
- Developer: MEBRIC
- Category: Entertainment
- Short description: 만세력 계산을 쉬운 생활 조언과 오늘부터 해볼 실행 카드로 풀어드려요.
- Long description: 생년 정보를 재현 가능한 만세력 엔진으로 계산한 뒤, 카드에 실제 있는 값만 전통 명리 관점의 참고 해석으로 설명합니다. 어려운 용어는 일·관계·생활의 구체적인 장면으로 바꾸고, 오늘 10분·이번 주 한 번·7일 뒤 확인 기준까지 제안합니다. 다정한 할머니 느낌은 은은하게 살리되 운명이나 중대한 결정을 단정하지 않습니다. 선택 입력인 성향 정보는 계산 근거가 아니라 행동을 실천하기 편한 방식에만 반영합니다. 전통 명리·무속 기반 오락·자기이해 참고용입니다.
- Website: https://github.com/davidchoi0313/samsin-saju
- Support: https://github.com/davidchoi0313/samsin-saju/blob/main/SUPPORT.md
- Privacy: https://github.com/davidchoi0313/samsin-saju/blob/main/PRIVACY.md
- Terms: https://github.com/davidchoi0313/samsin-saju/blob/main/TERMS.md
- Countries: South Korea

> 제출 포털의 실제 카테고리 목록에 Entertainment 가 없고 Lifestyle 만 있으면,
> 그때는 반대로 Lifestyle 로 통일하고 `.agents/plugins/marketplace.json`·
> `.codex-plugin/plugin.json`·`quality_contract.py` 의 Entertainment 검사를 함께 바꾼다.

## Starter prompts

1. 1990년 3월 15일 양력, 오전 6시, 남성 기준 평생사주를 보고 오늘부터 해볼 행동까지 정리해 줘.
2. 올해 운세에서 하면 좋은 행동과 조심할 습관을 월별로 알려 줘.
3. 두 사람의 사주 궁합을 보고 이번 주에 시험할 대화 방법을 제안해 줘.
4. 내 직업운을 직업 이름보다 잘 맞을 수 있는 과제와 업무 환경 중심으로 풀어 줘.

## Release notes

첫 OpenAI 공개 제출 버전입니다. 15개 사주 메뉴, 재현 가능한 만세력 산출, 쉬운 한국어 풀이, 오늘·이번 주 실행 카드, 7일 검토 기준, 선택 성향 기반 실행 방식 조정, 건강·재정·채용 안전 가드를 포함합니다. 계산 라이브러리는 플러그인에 포함되어 실행 중 외부 패키지 설치나 네트워크 연결이 필요하지 않습니다.

## 제출 전 확인

- Developer Identity와 MEBRIC 이름·웹사이트·지원 이메일의 일치 확인
- Apps Management 권한이 Write인지 확인
- `openai-submission/samsin-saju-openai.zip` 업로드 후 clean environment scan 통과 확인
- 정책 확인 문구는 계정 권한자가 직접 읽고 동의
- 승인 후 Publish 실행
