# 🛠️ 마켓플레이스 인식 오류 복구 가이드

> Claude 데스크톱 앱 "마켓플레이스 추가"에서 `https://github.com/davidchoi0313/samsin-saju` 를 넣었을 때
> **"이 리포지토리는 마켓플레이스가 아닙니다. .claude-plugin/marketplace.json에서 매니페스트를 찾을 수 없습니다"** 오류가 나는 경우의 복구 절차입니다.
> 아래 **방법 A**(웹에서 클릭만으로)만 따라 해도 복구됩니다. git을 쓰실 수 있으면 **방법 B**가 더 깔끔합니다.

---

## 0. 한 줄 원인

**점(`.`)으로 시작하는 `.claude-plugin` 폴더가 GitHub 업로드에서 통째로 빠졌습니다.**

GitHub 웹 화면에 폴더를 마우스로 끌어다 놓는(드래그 & 드롭) 방식은 점으로 시작하는 숨김 폴더·파일을 자동으로 건너뜁니다. 그래서 마켓플레이스임을 알려주는 두 개의 핵심 파일이 레포에 올라가지 않았고, 앱이 "이건 마켓플레이스가 아니다"라고 판단한 것입니다.

빠진 두 파일:

| 빠진 파일 | 역할 | 현재 상태 |
|---|---|---|
| `.claude-plugin/marketplace.json` (레포 맨 위) | "이 레포는 마켓플레이스다"라고 알려주는 명패 | ❌ 없음 |
| `plugins/samsin-saju/.claude-plugin/plugin.json` | "이 플러그인은 samsin-saju다"라고 알려주는 명패 | ❌ 없음 |

> 점 없는 파일(`SKILL.md` 등)은 정상 업로드됐는데 점으로 시작하는 것만 빠진 것이 그 증거입니다.

이 두 파일만 다시 채워 넣으면 됩니다.

---

## 방법 A — GitHub 웹에서 직접 만들기 (추천 · git 몰라도 됨)

GitHub 레포 화면에서 새 파일을 만들 때, **파일 이름 칸에 `/` 가 들어간 경로를 그대로 입력하면 폴더가 자동으로 생깁니다.** 점(`.`)으로 시작하는 이름도 그대로 입력하면 됩니다. 이 성질을 이용해 빠진 두 파일을 채워 넣습니다.

### 만들 파일 ① — `.claude-plugin/marketplace.json`

1. 브라우저로 `https://github.com/davidchoi0313/samsin-saju` 의 **레포 맨 위(루트)** 화면을 엽니다.
2. 오른쪽 위 **"Add file" → "Create new file"** 클릭.
3. 파일 이름 칸(상단의 `Name your file...`)에 아래를 **그대로** 입력합니다.

   ```
   .claude-plugin/marketplace.json
   ```

   > `/` 를 입력하는 순간 `.claude-plugin` 이 폴더로 잡히고, 그 안에 `marketplace.json` 이 들어갑니다. 맨 앞의 점(`.`)도 그냥 입력하면 됩니다 — 웹 화면에서는 숨김 처리되지 않습니다.

4. 아래쪽 큰 입력칸에 **[붙여넣기 내용 A]** 를 통째로 붙여넣습니다.
5. 화면 아래 **"Commit changes"** (또는 "Commit new file") 클릭.

### 만들 파일 ② — `plugins/samsin-saju/.claude-plugin/plugin.json`

1. 다시 레포 화면에서 **"Add file" → "Create new file"**. (어느 위치에서 시작해도 됩니다 — 경로를 전부 적을 것이므로)
2. 파일 이름 칸에 아래를 **그대로** 입력합니다.

   ```
   plugins/samsin-saju/.claude-plugin/plugin.json
   ```

   > 슬래시(`/`)마다 폴더가 한 단계씩 생깁니다. `plugins` → `samsin-saju` → `.claude-plugin` 순으로 폴더가 만들어지고 그 안에 `plugin.json` 이 들어갑니다.

3. 아래 입력칸에 **[붙여넣기 내용 B]** 를 통째로 붙여넣습니다.
4. **"Commit changes"** 클릭.

### [붙여넣기 내용 A] — `.claude-plugin/marketplace.json`

```json
{
  "name": "samsin-saju-marketplace",
  "owner": {
    "name": "MEBRIC"
  },
  "description": "삼신이 사주풀이 플러그인을 배포하는 마켓플레이스. 정밀 만세력 엔진 + 15메뉴 해석을 다정한 견습 도사 '삼신이'가 한 목소리로 풀어줍니다. (오락·참고용)",
  "plugins": [
    {
      "name": "samsin-saju",
      "source": "./plugins/samsin-saju",
      "description": "삼신이 사주풀이 — 결정론 만세력 엔진이 사주팔자·오행·십신·대운·신살을 계산하면, AI가 그 산출 카드만 근거로 15메뉴(평생사주·올해운세·궁합·오늘의운세·귀신사주·전생사주·신살풀이·토정비결·대운풀이·용신사주·직업운·결혼연애운·건강운·사업궁합·인재채용 참고)를 풀이합니다. 전통 명리·무속 기반 오락·참고용.",
      "version": "0.4.0",
      "author": {
        "name": "MEBRIC"
      },
      "license": "SEE LICENSE IN LICENSE",
      "category": "entertainment",
      "keywords": [
        "saju",
        "사주",
        "만세력",
        "명리",
        "운세",
        "궁합",
        "토정비결"
      ]
    }
  ]
}
```

### [붙여넣기 내용 B] — `plugins/samsin-saju/.claude-plugin/plugin.json`

```json
{
  "name": "samsin-saju",
  "version": "0.4.0",
  "description": "삼신이 사주풀이 — 정밀 만세력 엔진(결정론 산출)이 사주팔자·오행·십신·십이운성·대운·세운·신살을 계산하면, AI가 그 산출 카드만 근거로 15메뉴(평생사주·올해운세·궁합·오늘의운세·귀신사주·전생사주·신살풀이·토정비결·대운풀이·용신사주·직업운·결혼연애운·건강운·사업궁합·인재채용 참고)를 메뉴별 톤으로 풀이합니다. 전통 명리·무속 기반 오락·참고용.",
  "author": {
    "name": "MEBRIC"
  },
  "keywords": [
    "saju",
    "사주",
    "만세력",
    "명리",
    "운세",
    "궁합",
    "토정비결",
    "사업궁합",
    "채용참고"
  ],
  "license": "SEE LICENSE IN LICENSE"
}
```

> 위 두 내용은 로컬 정상본(`05_공개_레포\samsin-saju-marketplace\`)의 실제 파일을 그대로 옮긴 것입니다. 한 글자도 고치지 말고 통째로 복사·붙여넣기 하세요.

---

## 방법 B — git 명령으로 다시 올리기 (대안 · 더 깔끔함)

git을 쓸 수 있다면, 로컬 정상본 폴더에서 한 번에 다시 올리는 쪽이 빠뜨림 없이 확실합니다.

> ⚠️ **드래그 & 드롭 업로드는 다시 쓰지 마세요.** 그 방식이 바로 점(`.`)으로 시작하는 폴더를 빠뜨린 원인입니다. 아래 `git add -A` 는 점으로 시작하는 파일·폴더까지 **전부** 포함해 올립니다.

로컬 정상본 폴더에서:

```bash
cd "D:/Cowork/Cowork/Projects/사주/05_공개_레포/samsin-saju-marketplace"

git init
git add -A                # ← 점(.)으로 시작하는 .claude-plugin 폴더까지 전부 포함
git status                # ← .claude-plugin/marketplace.json 이 목록에 보이는지 확인
git commit -m "fix: 누락된 .claude-plugin 매니페스트 복구"
git branch -M main
git remote add origin https://github.com/davidchoi0313/samsin-saju.git
git push -u origin main
```

> 이미 `git init`·`origin` 이 잡혀 있으면 `git add -A` → `git commit` → `git push` 만 하면 됩니다.
> 푸시가 거부되면(원격에 다른 이력이 있을 때) `git push -u origin main --force` 로 덮어쓸 수 있습니다 — 단, 공개 레포를 덮어쓰는 것이므로 다른 협업자가 없을 때만 쓰세요.

기존 `PUSH_GUIDE.md` 의 1~2단계와 같은 흐름이며, 핵심은 **`git add -A` 가 숨김 파일까지 포함한다**는 점입니다.

---

## 복구 확인

두 파일을 올린 뒤 다음을 확인하세요.

1. GitHub 레포 화면 맨 위에 **`.claude-plugin`** 폴더가 보이고, 그 안에 `marketplace.json` 이 있는지.
   그리고 `plugins/samsin-saju/.claude-plugin/plugin.json` 도 들어갔는지.
2. Claude 데스크톱 앱의 **"마켓플레이스 추가"(Add marketplace → Add from a repository)** 에
   `https://github.com/davidchoi0313/samsin-saju` (또는 짧은 형태 `davidchoi0313/samsin-saju`) 를 다시 넣습니다.
3. 이번에는 매니페스트가 **인식되는지** 확인합니다. 인식되면 목록에 `samsin-saju` 가 뜨고, **"Install"** 로 설치를 진행합니다.
4. 설치 후 대화창에 **"사주 봐줘"** 를 입력해 삼신이가 응답하는지 봅니다.

> 만약 그래도 인식이 안 되면, 두 파일의 **경로·파일명에 오타가 없는지**(특히 맨 앞 점 `.` 과 폴더 철자 `claude-plugin`) 먼저 확인하세요. 그다음 PUSH_GUIDE.md 의 "6단계 — 잘 안 될 때"를 참고하시면 됩니다.

---

## 한 가지만 안심하세요 — 레포명과 폴더명이 달라도 됩니다

- 로컬 폴더 이름과 PUSH_GUIDE 예시는 **`samsin-saju-marketplace`** 입니다.
- 실제로 올린 GitHub 레포 이름은 **`samsin-saju`** 입니다 (`davidchoi0313/samsin-saju`).

**이 둘이 달라도 전혀 문제되지 않습니다.** 마켓플레이스 인식은 레포 이름이 아니라 **레포 안에 `.claude-plugin/marketplace.json` 파일이 있는지**로 판단합니다. 그래서 이번 복구도 "레포 이름을 바꾸는 일"이 아니라 "빠진 매니페스트 파일을 채워 넣는 일"입니다.

> 참고: PUSH_GUIDE.md 안의 `<GitHub사용자명>` 자리에는 `davidchoi0313` 을 넣고, 레포명은 실제 올리신 `samsin-saju` 로 읽으시면 됩니다.
