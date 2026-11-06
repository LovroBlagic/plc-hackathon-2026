# Team sync: mirror skills <-> repo, then pull (rebase) -> commit -> push.
#   .\sync.ps1 "message"      (message optional)
# Run by the orchestrator Claude session (single git operator). Teammates can run it too.
param([string]$Message = "")
$ErrorActionPreference = "Continue"
$repo = $PSScriptRoot
Set-Location $repo

# 1) Skills: user-level (~/.claude/skills) <-> repo (.claude/skills). Newer file wins both ways (robocopy /XO).
$userSkills = Join-Path $env:USERPROFILE ".claude\skills"
foreach ($s in @("machine-expert", "tia-portal")) {
    $u = Join-Path $userSkills $s; $r = Join-Path $repo ".claude\skills\$s"
    if (Test-Path $u) { robocopy $u $r /E /XO /XF *.exe *.pyc /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null }
    if (Test-Path $r) { robocopy $r $u /E /XO /XF *.exe *.pyc /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null }
}

# 2) Pull teammates' work first (autostash keeps our uncommitted changes)
git pull --rebase --autostash -q origin main
if ($LASTEXITCODE -ne 0) { Write-Output "SYNC_RESULT pull_failed (resolve conflicts, then rerun)"; exit 1 }

# 3) Commit everything that changed (respecting .gitignore)
git add -A
$changes = git diff --cached --name-only
if ($changes) {
    $n = ($changes | Measure-Object).Count
    if (-not $Message) { $Message = "Sync: $n file(s) updated $(Get-Date -Format 'yyyy-MM-dd HH:mm')" }
    git commit -q -m $Message -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01Sn3L6cbRF9NukZz3BtvYwi"
} else { $n = 0 }

# 4) Push
git push -q origin main
if ($LASTEXITCODE -ne 0) { Write-Output "SYNC_RESULT push_failed committed=$n"; exit 1 }
Write-Output "SYNC_RESULT ok committed=$n head=$(git rev-parse --short HEAD)"
