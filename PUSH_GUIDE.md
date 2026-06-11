# 🚀 PUSH_GUIDE — GitHub 공개 + 마켓플레이스 설치 검증

이 폴더(`samsin-saju-marketplace`)를 **그대로** GitHub에 공개로 올리고, Claude Code 마켓플레이스에서 설치되는지 검증하는 복붙용 가이드입니다.
아래 명령을 위에서부터 차례대로 실행하세요. `<...>` 부분만 본인 값으로 바꾸면 됩니다.

> 사전 준비: `git` 설치. (선택) GitHub CLI `gh` 설치 시 레포 생성·푸시가 한 번에 됩니다.

---

## 0단계 — 이 폴더로 이동

```bash
cd "D:/Cowork/Cowork/Projects/사주/05_공개_레포/samsin-saju-marketplace"
```

> Windows PowerShell도 위 경로 그대로 동작합니다. (경로에 한글이 있어도 큰따옴표로 감싸면 됩니다.)

---

## 1단계 — git 저장소 초기화 & 첫 커밋

```bash
git init
git add .
git status        # ← 올라갈 파일 확인 (cache/pyc/bak이 없어야 정상)
git commit -m "feat: 삼신이 사주풀이(samsin-saju) v0.4.0 마켓플레이스 공개"
git branch -M main
```

> `.gitignore` 가 Python 캐시·OS 파일을 자동 제외합니다. `git status` 에 `__pycache__`, `*.pyc`, `.pytest_cache` 가 보이면 안 됩니다.

---

## 2단계 — GitHub 공개(public) 레포 생성 & 푸시

### 방법 A) GitHub CLI(`gh`) — 한 번에 (권장)

```bash
gh auth status                      # 로그인 안 됐으면: gh auth login
gh repo create samsin-saju-marketplace --public --source=. --remote=origin --push
```

→ 레포 생성 + `origin` 연결 + `main` 푸시까지 한 번에 끝납니다.

### 방법 B) 웹에서 수동으로

1. https://github.com/new 접속
2. **Repository name**: `samsin-saju-marketplace`
3. 공개 범위: **Public** 선택
4. **README/.gitignore/license 추가 체크박스는 모두 해제** (이미 폴더에 있으므로 충돌 방지)
5. **Create repository** 클릭 후, 다음 명령 실행:

```bash
git remote add origin https://github.com/<GitHub사용자명>/samsin-saju-marketplace.git
git push -u origin main
```

---

## 3단계 — 푸시 결과 확인

```bash
git remote -v        # origin 주소 확인
git log --oneline -1 # 첫 커밋 확인
```

브라우저로 `https://github.com/<GitHub사용자명>/samsin-saju-marketplace` 를 열어
`.claude-plugin/marketplace.json` 과 `plugins/samsin-saju/` 가 보이면 업로드 성공입니다.

---

## 4단계 — (권장) 마켓플레이스 매니페스트 검증

푸시 전이나 후에 매니페스트 문법을 검증할 수 있습니다.

```bash
claude plugin validate .
```

또는 Claude Code 세션 안에서:

```
/plugin validate .
```

> `marketplace.json` 스키마·중복 플러그인명·경로(`..`) 등을 점검합니다. 오류가 없어야 합니다.

---

## 5단계 — 마켓플레이스 추가 & 설치 검증 (실제 동작 확인 단계)

Claude Code 세션에서 아래를 실행합니다.

```
/plugin marketplace add <GitHub사용자명>/samsin-saju-marketplace
```

```
/plugin install samsin-saju@samsin-saju-marketplace
```

### ✅ 정상 설치 확인 체크리스트

아래가 모두 확인되어야 "설치 가능"이 검증된 것입니다. (하나라도 안 되면 6단계 참고)

1. `/plugin marketplace add` 실행 후 마켓플레이스가 목록에 뜬다.
   - 확인: `claude plugin marketplace list`
2. `/plugin install` 후 오류 없이 설치 완료 메시지가 뜬다.
3. 새 세션에서 **"사주 봐줘"** 라고 입력하면 삼신이가 응답한다.
4. (Python) 만세력 엔진이 동작한다. `lunar_python` 미설치 시 자동 설치 안내가 뜨는지 확인.

---

## 6단계 — 잘 안 될 때

- **상대경로(`./plugins/...`)가 안 풀림** → 마켓플레이스를 **URL이 아니라 GitHub 레포(Git)** 로 추가했는지 확인하세요. URL 직접 추가 방식은 `marketplace.json` 만 받아오므로 상대경로가 풀리지 않습니다. `/plugin marketplace add <사용자명>/<레포명>` 형식(Git)을 쓰세요.
- **레포가 private 이라 설치 실패** → 레포를 **Public** 으로 전환하거나, 인증 토큰(`GITHUB_TOKEN`)을 설정하세요.
- **마켓플레이스 이름 충돌** → 같은 이름의 마켓플레이스가 이미 있으면 덮어씁니다. `claude plugin marketplace remove samsin-saju-marketplace` 후 다시 추가.
- **변경 후 반영 안 됨** → 커밋·푸시 후 `/plugin marketplace update samsin-saju-marketplace` 로 갱신.

---

## 7단계 — 업데이트 배포(나중에)

소스를 고친 뒤 새 버전을 내보낼 때:

```bash
git add .
git commit -m "chore: <변경 요약>"
git push
```

> 사용자에게 업데이트를 확실히 내보내려면 `plugins/samsin-saju/.claude-plugin/plugin.json` 의 `version` 을 올리세요(예: `0.4.0` → `0.4.1`). 버전 문자열이 그대로면 기존 설치자에게 갱신이 안 갈 수 있습니다. 사용자는 `/plugin marketplace update` 로 새로고침합니다.
