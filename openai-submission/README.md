# OpenAI 공개 제출 준비

이 폴더는 일반 고객이 ChatGPT 모바일의 Plugins 탭에서 설치할 수 있도록 OpenAI Universal Plugins Directory에 제출할 때 사용하는 자료입니다.

## 1. 제출 아카이브 만들기

저장소 루트에서 실행합니다.

```text
python3 openai-submission/build_archive.py
```

생성 파일은 `openai-submission/samsin-saju-openai.zip`입니다. ZIP에는 단 하나의 최상위 `samsin-saju/` 폴더가 있고, 바로 아래에 `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `skills/`, `assets/`, 라이선스가 들어갑니다. 테스트·기획 문서·Claude 전용 에이전트는 공개 실행 번들에서 제외합니다.

## 2. 제출 전 계정 준비

1. OpenAI Platform 조직에서 제출자의 `Apps Management` 권한을 `Write`로 설정합니다. 조직 Owner는 기본 권한을 가집니다.
2. 같은 조직에서 MEBRIC 또는 실제 게시자 명의의 Developer Identity 인증을 완료합니다.
3. 게시자 이름, 웹사이트, 지원 이메일, 개인정보 처리방침, 약관의 운영 주체가 인증 정보와 일치하는지 확인합니다.

## 3. Portal 입력

1. https://platform.openai.com/plugins 에서 **Create plugin → Skills only**를 선택합니다.
2. `samsin-saju-openai.zip`을 업로드하고 생성된 manifest와 scan 결과를 검토합니다.
3. `listing.md`의 설명·URL·starter prompts·release notes를 입력합니다.
4. `test-cases.md`의 긍정 5개와 부정 3개를 등록합니다.
5. 국가, 정책 확인 항목을 계정 권한자가 직접 검토한 뒤 제출합니다.
6. OpenAI 승인 후 Portal에서 **Publish**해야 공개 디렉터리와 모바일 Plugins 탭에 나타납니다.

공개 심사 전 조직 내부에서 먼저 쓰려면 ChatGPT 데스크톱에 repo marketplace 플러그인을 설치하고, workspace admin이 Plugins → Personal → `…` → Publish에서 접근 역할을 지정합니다.
