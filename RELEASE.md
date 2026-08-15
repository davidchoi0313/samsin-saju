# 배포 절차

이 저장소를 GitHub에 올리고 버전을 올릴 때 따르는 절차다. 로컬 저장소 경로는 `D:\repos\samsin-saju` 기준이다.

## ⚠️ GitHub 웹 드래그&드롭 업로드 금지

GitHub 웹 화면에 폴더를 끌어다 놓는 방식은 **점(`.`)으로 시작하는 숨김 폴더를 통째로 건너뛴다.**
과거 이 방식으로 올렸다가 `.claude-plugin/marketplace.json` 과 `plugins/samsin-saju/.claude-plugin/plugin.json` 이 빠져, 마켓플레이스 추가가 "이 리포지토리는 마켓플레이스가 아닙니다" 로 실패한 사고가 있었다.

**반드시 git 으로 push 한다.**

## push 절차

```bash
cd /d/repos/samsin-saju
git status -sb          # 올라갈 파일 확인
git add -A
git commit -m "<변경 요약>"
git push origin main
```

push 뒤 GitHub 웹에서 `.claude-plugin/` 폴더가 실제로 보이는지 한 번 확인한다.

## 버전 올릴 때 체크리스트

버전은 **세 곳**에 흩어져 있다. 하나라도 어긋나면 안 된다.

| 파일 | 위치 |
|---|---|
| `.claude-plugin/marketplace.json` | `plugins[0].version` |
| `plugins/samsin-saju/.claude-plugin/plugin.json` | `version` |
| `plugins/samsin-saju/.codex-plugin/plugin.json` | `version` |

1. 세 파일의 버전을 **동시에** 같은 값으로 올린다.
2. 테스트 전체 통과를 확인한다.
   ```bash
   cd plugins/samsin-saju/skills/saju-reading
   python -m pytest tests/ scripts/test_mbti_engine.py -q
   ```
   `quality_contract.py` 가 세 버전의 일치를 자동 검사하므로, 하나만 올리면 `VERSION_MISMATCH` 로 여기서 걸린다.
3. 제출용 아카이브가 빌드되는지 확인한다.
   ```bash
   python3 openai-submission/build_archive.py
   ```
4. push 한다.

## 경로 규칙

파일·폴더 이름에 Windows 가 쓸 수 없는 문자(`< > : " \ | ? *`)나 비ASCII 문자를 쓰지 않는다.
과거 루트에 따옴표로 시작하는 `"plugins` 폴더가 생겨 Windows 에서 `git clone` 이 `error: invalid path` 로 실패한 적이 있다.
`quality_contract.py` 의 `WINDOWS_CHECKOUT_PATH` 검사가 이를 잡는다.

## 참고

저장소 루트에는 `docs/` 폴더가 없다. 스킬 문서는 `plugins/samsin-saju/docs/` 에 있다.
