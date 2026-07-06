# =====================================================================
#  PUSH_MBTI_업로드.ps1
#  삼신이 사주 레포 -> GitHub 업로드 도우미 (MBTI 프로토타입 반영)
#
#  대상 원격: https://github.com/davidchoi0313/samsin-saju.git
#
#  [사용법] Windows PowerShell 창에서 이 파일이 있는 폴더로 이동한 뒤
#     powershell -ExecutionPolicy Bypass -File .\PUSH_MBTI_업로드.ps1
#  또는 파일 우클릭 후 "PowerShell에서 실행".
#
#  [안전 설계]
#   - 무조건 force 안 함. 원격에 기존 내용이 있으면 "안전 병합"을 먼저 권합니다.
#   - 각 위험 단계 전에 Y/N 로 담당자님 확인을 받습니다.
#   - 오류가 나면 그 자리에서 멈춥니다(그대로 밀어붙이지 않음).
#   - 이 스크립트는 담당자님 PC에서, 담당자님 GitHub 자격증명으로만 동작합니다.
# =====================================================================

$ErrorActionPreference = "Stop"   # 오류 나면 즉시 멈춤

# --- 설정값 (필요하면 이 3줄만 바꾸면 됩니다) -------------------------
$RepoUrl    = "https://github.com/davidchoi0313/samsin-saju.git"
$Branch     = "main"
$CommitMsg  = "feat(mbti): 삼신이 MBTI 개인화 레이어 프로토타입(파일럿 07,08,12) 추가"
# ---------------------------------------------------------------------

function Ask-YesNo($question) {
    while ($true) {
        $ans = Read-Host "$question (Y/N)"
        if ($ans -match '^[Yy]') { return $true }
        if ($ans -match '^[Nn]') { return $false }
        Write-Host "  Y 또는 N 으로 답해주세요." -ForegroundColor Yellow
    }
}

function Stop-With($msg) {
    Write-Host ""
    Write-Host "[중단] $msg" -ForegroundColor Red
    Write-Host "필요하면 위 메시지를 그대로 복사해 매니저에게 전달해주세요." -ForegroundColor Red
    exit 1
}

# 이 스크립트가 놓인 폴더로 이동 (한글 경로 안전)
Set-Location -LiteralPath $PSScriptRoot
Write-Host "작업 폴더: $PSScriptRoot" -ForegroundColor Cyan

# 0) git 설치 확인 -----------------------------------------------------
try { git --version | Out-Null }
catch { Stop-With "git 이 설치돼 있지 않습니다. https://git-scm.com 에서 설치 후 다시 실행해주세요." }

# 1) git 저장소 초기화 (필요 시에만) ----------------------------------
if (-not (Test-Path ".git")) {
    Write-Host "`n[1] 이 폴더는 아직 git 저장소가 아닙니다. 초기화합니다." -ForegroundColor Green
    git init | Out-Null
    git branch -M $Branch
} else {
    Write-Host "`n[1] 이미 git 저장소입니다. 초기화는 건너뜁니다." -ForegroundColor Green
}

# 2) 변경분 담기 + 상태 확인 ------------------------------------------
Write-Host "`n[2] 변경 파일을 담고, 무엇이 올라갈지 보여드립니다." -ForegroundColor Green
git add .

Write-Host "`n---- 올라갈 파일 목록(git status) ----" -ForegroundColor Cyan
git status --short
Write-Host "--------------------------------------" -ForegroundColor Cyan

# __pycache__ / *.pyc 가 섞였는지 자동 점검 (.gitignore 가 잘 도는지)
$leak = git status --short | Select-String -Pattern '__pycache__|\.pyc'
if ($leak) {
    Write-Host "`n[주의] 캐시 파일이 올라가려 합니다(.gitignore 확인 필요):" -ForegroundColor Yellow
    $leak | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
    if (-not (Ask-YesNo "이대로 계속할까요?")) { Stop-With "담당자님이 중단을 선택했습니다." }
} else {
    Write-Host "캐시(__pycache__/*.pyc) 유출 없음 - 정상." -ForegroundColor Green
}

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "`n담을 변경분이 없습니다(이미 커밋됐거나 변경 없음). 그래도 push 는 시도합니다." -ForegroundColor Yellow
} else {
    if (-not (Ask-YesNo "`n위 목록을 커밋할까요?")) { Stop-With "담당자님이 커밋을 취소했습니다." }
    # 3) 커밋 (커밋할 게 있을 때만) ------------------------------------
    Write-Host "`n[3] 커밋합니다: $CommitMsg" -ForegroundColor Green
    git commit -m $CommitMsg
}

# 4) origin 원격 연결 (있으면 주소만 갱신, 없으면 추가) -----------------
Write-Host "`n[4] 원격(origin) 연결을 확인합니다." -ForegroundColor Green
$existing = ""
try { $existing = (git remote get-url origin) 2>$null } catch { $existing = "" }

if ($existing) {
    if ($existing -ne $RepoUrl) {
        Write-Host "  기존 origin: $existing -> 새 주소로 갱신합니다." -ForegroundColor Yellow
        git remote set-url origin $RepoUrl
    } else {
        Write-Host "  origin 이 이미 올바르게 연결돼 있습니다." -ForegroundColor Green
    }
} else {
    git remote add origin $RepoUrl
    Write-Host "  origin 을 새로 연결했습니다: $RepoUrl" -ForegroundColor Green
}

# 5) 원격 상태 파악 (비어있음 vs 기존내용 있음) ------------------------
Write-Host "`n[5] 원격 레포에 이미 내용이 있는지 확인합니다..." -ForegroundColor Green
$remoteHasContent = $false
try {
    $lsr = git ls-remote --heads origin 2>$null
    if ($lsr) { $remoteHasContent = $true }
} catch {
    Write-Host "  원격 조회에 실패했습니다(인증/네트워크). 아래 인증 안내를 참고해주세요." -ForegroundColor Yellow
}

# 6) 상황별 push --------------------------------------------------------
if (-not $remoteHasContent) {
    # (a) 원격이 비어 있음 -> 그대로 첫 push
    Write-Host "`n[6-a] 원격이 비어 있습니다. 그대로 첫 업로드를 진행합니다." -ForegroundColor Green
    if (-not (Ask-YesNo "지금 push 할까요?")) { Stop-With "담당자님이 push 를 취소했습니다." }
    git push -u origin $Branch
}
else {
    # (b) 원격에 기존 내용 있음 -> 안전 병합을 먼저 권함
    Write-Host "`n[6-b] 원격에 이미 내용이 있습니다(README 등)." -ForegroundColor Yellow
    Write-Host "  안전한 방법은 '원격 내용을 먼저 내려받아 합치기(병합)' 입니다." -ForegroundColor Yellow
    Write-Host "  (원격 내용을 통째로 덮어쓰는 --force 는 기본으로 쓰지 않습니다.)" -ForegroundColor Yellow

    if (Ask-YesNo "`n[권장] 원격 내용을 내려받아 합친 뒤 올릴까요?") {
        Write-Host "  원격을 내려받아 병합합니다..." -ForegroundColor Green
        # 서로 관련 없는 두 히스토리를 합치므로 --allow-unrelated-histories 필요
        git pull origin $Branch --allow-unrelated-histories --no-edit
        Write-Host "  병합 성공. 이제 올립니다." -ForegroundColor Green
        git push -u origin $Branch
    }
    else {
        Write-Host "`n  [위험 경고] 병합을 건너뛰면 원격 내용을 덮어쓸 수 있습니다." -ForegroundColor Red
        Write-Host "  이 경우 원격 레포에 있던 파일(README 등)이 사라질 수 있습니다." -ForegroundColor Red
        Write-Host "  꼭 필요할 때만, 원격 내용이 사라져도 괜찮다고 확신할 때만 진행하세요." -ForegroundColor Red
        if (Ask-YesNo "그래도 강제로 덮어쓰기(--force-with-lease) 할까요?") {
            # --force 가 아니라 --force-with-lease : 남이 그새 올린 게 있으면 자동으로 막아줌
            git push -u origin $Branch --force-with-lease
        } else {
            Stop-With "담당자님이 강제 덮어쓰기를 취소했습니다. 원격을 확인한 뒤 다시 실행해주세요."
        }
    }
}

# 7) 마무리 확인 --------------------------------------------------------
Write-Host "`n[완료] 업로드 명령이 끝났습니다. 아래로 결과를 확인하세요." -ForegroundColor Green
git remote -v
git log --oneline -1
Write-Host "`n브라우저에서 https://github.com/davidchoi0313/samsin-saju 를 열어" -ForegroundColor Cyan
Write-Host "방금 올린 MBTI 파일들이 보이면 성공입니다." -ForegroundColor Cyan
Write-Host ""
Write-Host "만약 위에서 'Authentication failed / 403' 이 떴다면:" -ForegroundColor Yellow
Write-Host "  - (권장) GitHub CLI 설치 후  gh auth login  으로 로그인한 뒤 다시 실행," -ForegroundColor Yellow
Write-Host "  - 또는 github.com > Settings > Developer settings 에서 PAT(토큰) 발급 후" -ForegroundColor Yellow
Write-Host "    push 시 비밀번호 자리에 그 토큰을 붙여넣으세요." -ForegroundColor Yellow
