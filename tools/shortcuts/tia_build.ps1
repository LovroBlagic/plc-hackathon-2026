<#
tia_build.ps1 - import all of tia-src into a TIA project and compile it (headless TiaRun, holds the Openness lock).

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\tia_build.ps1 [-Project <dir|.ap21>] [-Archive <out.zap21>]
        [-Src tia-src] [-Owner shortcuts-build] [-WaitLock <sec>] [-AllowRunningTia] [-DryRun]

Default project: tia-work\crane\PLC_hackathon_2026_V21 (shared integration project).
Use -Project tia-work\simtest to refresh the PLCSIM test copy.
TiaRun flags: --headless --src tia-src --numbers tia-src\numbers.txt --ob30-ms 1000 (+ --archive to a staging file;
the staging archive is copied to -Archive ONLY when TIA_RESULT errors=0).
Takes tia-work\openness.lock itself (refuses if held by anyone, never takes over), refuses when a TIA Portal is running.
Final line: TIA_RESULT errors=N warnings=M (exactly TiaRun's) + BUILD_RESULT ok=0|1 ... ; exit 0 only when errors=0.
Typical time: 3-6 min (TIA start ~1.5 min, import, compile, save).
#>
param([string]$Project = "tia-work\crane\PLC_hackathon_2026_V21", [string]$Archive = "", [string]$Src = "tia-src",
      [string]$Owner = "shortcuts-build", [int]$WaitLock = 0, [switch]$AllowRunningTia, [switch]$DryRun)
. "$PSScriptRoot\_common.ps1"
$proj = Resolve-ProjectDir $Project
if (-not $proj) { Write-Host "BUILD_RESULT ok=0 reason=project-not-found ($Project)"; exit 2 }
$srcDir = if ([System.IO.Path]::IsPathRooted($Src)) { $Src } else { Join-Path $script:Repo $Src }
$numbers = Join-Path $script:Repo "tia-src\numbers.txt"
if (-not (Test-Path $script:TiaRun)) { Write-Host "BUILD_RESULT ok=0 reason=TiaRun.exe missing (run .claude\skills\tia-portal\scripts\build.ps1)"; exit 2 }
$arch = $null; $stage = $null
if ($Archive) {
  $arch = if ([System.IO.Path]::IsPathRooted($Archive)) { $Archive } else { Join-Path $script:Repo $Archive }
  $stage = Join-Path $script:Repo ("tia-work\_stage_" + [System.IO.Path]::GetFileName($arch))
}
$args2 = @("--project", $proj, "--headless", "--src", $srcDir, "--numbers", $numbers, "--ob30-ms", "1000")
if ($stage) { $args2 += @("--archive", $stage) }
$log = New-LogPath "tia_build"

if ($DryRun) {
  Write-Host "DRYRUN tia_build"
  Write-Host "  project : $proj"
  Write-Host "  src     : $srcDir ($(@(Get-ChildItem -Path "$srcDir\*" -Include *.udt,*.db,*.scl,*.awl -File).Count) source files)"
  $li = Get-LockInfo; Write-Host ("  lock    : " + $(if ($li) { "HELD by '$($li.Who)' ($($li.AgeMin) min) -> a real run would refuse" } else { "free" }))
  Write-Host ("  TIA     : " + $(if ((Get-TiaProcesses).Count) { "running -> a real run would refuse (unless -AllowRunningTia)" } else { "not running" }))
  Write-Host "  1. take lock '$Owner'"
  Invoke-Logged $log $script:TiaRun $args2 -DryRun | Out-Null
  if ($arch) { Write-Host "  3. if TIA_RESULT errors=0: copy $stage -> $arch" }
  Write-Host "  4. release lock"
  Write-Host "BUILD_RESULT ok=1 dryrun=1"
  exit 0
}

if (-not (Test-TiaFree -AllowRunningTia:$AllowRunningTia)) { Write-Host "BUILD_RESULT ok=0 reason=tia-running"; exit 3 }
if (-not (Enter-OpennessLock $Owner $WaitLock)) { Write-Host "BUILD_RESULT ok=0 reason=lock-held"; exit 3 }
$code = 99
try {
  $t0 = Get-Date
  $code = Invoke-Logged $log $script:TiaRun $args2
  $tr = Find-Line $log "TIA_RESULT"
  $errs = if ($tr -match "errors=(\d+)") { [int]$Matches[1] } else { -1 }
  $archMsg = ""
  if ($arch) {
    if ($errs -eq 0 -and (Test-Path $stage)) {
      New-Item -ItemType Directory -Force (Split-Path $arch) | Out-Null
      Copy-Item $stage $arch -Force; Remove-Item $stage -Force
      $archMsg = " archive=$arch"
    } else {
      if (Test-Path $stage) { Remove-Item $stage -Force }
      $archMsg = " archive=SKIPPED(errors)"
    }
  }
  $dt = [int]((Get-Date) - $t0).TotalSeconds
  if (-not $tr) { $tr = "TIA_RESULT missing (exit $code)" }
  Write-Host ""
  Write-Host "  errors are listed above as [ERROR] lines; full log: $log"
  Write-Host $tr
  Write-Host ("BUILD_RESULT ok={0} project={1} secs={2}{3}" -f [int]($errs -eq 0), $proj, $dt, $archMsg)
} finally { Exit-OpennessLock }
if ($errs -eq 0) { exit 0 } else { exit 1 }
