<#
deliver.ps1 - PROVISIONAL final packaging of the TIA crane: PLC build + HMI build + archive.

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\deliver.ps1 [-Project <dir>] [-Out deliver\TIA_crane_final.zap21]
        [-SkipHmi] [-SkipPlc] [-AllowRunningTia] [-DryRun]

  1. tia_build.ps1 -Project <P>              (import tia-src, compile PLC; must give TIA_RESULT errors=0)
  2. hmi_build.ps1 -Project <P>              (PROVISIONAL: hmi-tia\regen.ps1; skip with -SkipHmi)
  3. TiaRun --project <P> --headless --no-compile --archive <tia-work\_stage_...>  (holds the lock)
     -> copied to -Out only when steps 1-3 all succeeded (an existing -Out is replaced only then).
Default project tia-work\crane\PLC_hackathon_2026_V21. If the HMI agent finishes in another copy
(e.g. tia-work\hmibuild\PLC_hackathon_2026_V21), pass that as -Project.
Each step takes/releases the Openness lock itself and refuses if anyone else holds it.
Final line: DELIVER_RESULT ok=0|1 out=<path>.
#>
param([string]$Project = "tia-work\crane\PLC_hackathon_2026_V21", [string]$Out = "deliver\TIA_crane_final.zap21",
      [switch]$SkipHmi, [switch]$SkipPlc, [switch]$AllowRunningTia, [switch]$DryRun, [string]$Owner = "shortcuts-deliver")
. "$PSScriptRoot\_common.ps1"
$proj = Resolve-ProjectDir $Project
if (-not $proj) { Write-Host "DELIVER_RESULT ok=0 reason=project-not-found ($Project)"; exit 2 }
$outAbs = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $script:Repo $Out }
$stage = Join-Path $script:Repo ("tia-work\_stage_" + [System.IO.Path]::GetFileName($outAbs))
$log = New-LogPath "deliver"
$common = @()
if ($AllowRunningTia) { $common += "-AllowRunningTia" }
if ($DryRun) { $common += "-DryRun" }
Write-Host "NOTE: provisional - HMI pipeline not final."

function Run-Sub([string]$script, [string[]]$a) {
  $al = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot $script)) + $a + $common
  & powershell @al 2>&1 | ForEach-Object { $s = "$_"; Write-Host "  | $s"; Add-Content -Path $log -Value $s -Encoding UTF8 }
  return $LASTEXITCODE
}

$t0 = Get-Date
if (-not $SkipPlc) {
  Write-Step "1/3 PLC build"
  if ((Run-Sub "tia_build.ps1" @("-Project", $proj)) -ne 0) { Write-Host "DELIVER_RESULT ok=0 step=plc log=$log"; exit 1 }
} else { Write-Step "1/3 PLC build skipped" }
if (-not $SkipHmi) {
  Write-Step "2/3 HMI build (provisional)"
  if ((Run-Sub "hmi_build.ps1" @("-Project", $proj)) -ne 0) { Write-Host "DELIVER_RESULT ok=0 step=hmi log=$log"; exit 1 }
} else { Write-Step "2/3 HMI build skipped" }

Write-Step "3/3 archive"
$aa = @("--project", $proj, "--headless", "--no-compile", "--archive", $stage)
if ($DryRun) {
  Invoke-Logged $log $script:TiaRun $aa -DryRun | Out-Null
  Write-Host "  then copy $stage -> $outAbs"
  Write-Host "DELIVER_RESULT ok=1 dryrun=1 out=$outAbs"
  exit 0
}
if (-not (Test-TiaFree -AllowRunningTia:$AllowRunningTia)) { Write-Host "DELIVER_RESULT ok=0 step=archive reason=tia-running"; exit 3 }
if (-not (Enter-OpennessLock $Owner 0)) { Write-Host "DELIVER_RESULT ok=0 step=archive reason=lock-held"; exit 3 }
try { $code = Invoke-Logged $log $script:TiaRun $aa } finally { Exit-OpennessLock }
if ($code -ne 0 -or -not (Test-Path $stage)) { Write-Host "DELIVER_RESULT ok=0 step=archive exit=$code log=$log"; exit 1 }
New-Item -ItemType Directory -Force (Split-Path $outAbs) | Out-Null
Copy-Item $stage $outAbs -Force; Remove-Item $stage -Force
$mb = [math]::Round((Get-Item $outAbs).Length / 1MB, 1)
Write-Host ("DELIVER_RESULT ok=1 out={0} size={1}MB secs={2}" -f $outAbs, $mb, [int]((Get-Date) - $t0).TotalSeconds)
exit 0
