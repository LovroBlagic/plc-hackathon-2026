<#
hmi_build.ps1 - PROVISIONAL (HMI agent still working; its final pipeline is not settled as of 7 Nov 16:00).
Wraps the current HMI pipeline hmi-tia\regen.ps1 (layout.json -> gen_hmi.py -> HmiGen.exe --import --compile).

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\hmi_build.ps1 [-Project <dir>] [-Export] [-Offline]
        [-AllowRunningTia] [-DryRun]

  (default)  regen.ps1 -Project <P>  : generate from hmi-tia\export, import (Override) into <P>, compile HMI
  -Export    regen.ps1 -Export        : re-export the human prototypes first
  -Offline   regen.ps1 -DryRun        : generate + check + preview only, no TIA (OVERWRITES hmi-tia\out - do not use
                                        while the HMI agent is importing from it)
  -DryRun    print the steps only (touches nothing)
Lock: HmiGen takes tia-work\openness.lock itself as "hmi" (waits up to 15 min; since 7 Nov 16:32 a takeover needs >= 45 min AND no TIA process).
This wrapper therefore REFUSES to start when the lock is held by anyone or a TIA/Openness process runs, and lets
HmiGen take the lock. Default project tia-work\crane\PLC_hackathon_2026_V21 (has HMI_RT_1); the HMI agent's lab
copy is tia-work\hmibuild\PLC_hackathon_2026_V21 (HmiLab.exe, not wrapped here).
Final line: HMI_RESULT errors=N warnings=M (HmiGen's) + HMIBUILD_RESULT ok=0|1 provisional=1.
#>
param([string]$Project = "tia-work\crane\PLC_hackathon_2026_V21", [switch]$Export, [switch]$Offline,
      [switch]$AllowRunningTia, [switch]$DryRun)
. "$PSScriptRoot\_common.ps1"
$regen = Join-Path $script:Repo "hmi-tia\regen.ps1"
if (-not (Test-Path $regen)) { Write-Host "HMIBUILD_RESULT ok=0 provisional=1 reason=regen.ps1-missing"; exit 2 }
$proj = Resolve-ProjectDir $Project
if (-not $proj -and -not $Offline) { Write-Host "HMIBUILD_RESULT ok=0 provisional=1 reason=project-not-found ($Project)"; exit 2 }
$ra = @("-ExecutionPolicy", "Bypass", "-File", $regen)
if ($Offline) { $ra += "-DryRun" } else { $ra += @("-Project", $proj); if ($Export) { $ra += "-Export" } }
$log = New-LogPath "hmi_build"
Write-Host "NOTE: provisional wrapper - the HMI agent's final pipeline may differ (see hmi-tia\README.md)."

if ($DryRun) {
  Write-Host "DRYRUN hmi_build"
  Write-Host "  project : $proj"
  $li = Get-LockInfo; Write-Host ("  lock    : " + $(if ($li) { "HELD by '$($li.Who)' ($($li.AgeMin) min) -> a real run would refuse" } else { "free" }))
  Write-Host ("  TIA     : " + $(if ((Get-TiaProcesses).Count) { "running -> a real run would refuse" } else { "not running" }))
  Write-Host ("  export  : " + $(if (Test-Path (Join-Path $script:Repo "hmi-tia\export\screens\Proto.xml")) { "hmi-tia\export has Proto.xml (full generation)" } else { "hmi-tia\export has no Proto.xml -> regen does base/mock only" }))
  Invoke-Logged $log "powershell" $ra -DryRun | Out-Null
  Write-Host "HMIBUILD_RESULT ok=1 provisional=1 dryrun=1"
  exit 0
}

if (-not $Offline) {
  # regen.ps1 silently falls back to a MOCK dry run (exit 0, nothing imported) when hmi-tia\export is missing.
  if (-not $Export -and -not (Test-Path (Join-Path $script:Repo "hmi-tia\export\tags"))) {
    Write-Host "hmi-tia\export missing -> regen.ps1 would only do a mock dry run. Use -Export (needs the human prototypes in the project)."
    Write-Host "HMIBUILD_RESULT ok=0 provisional=1 reason=no-export"; exit 2
  }
  if (-not (Test-TiaFree -AllowRunningTia:$AllowRunningTia)) { Write-Host "HMIBUILD_RESULT ok=0 provisional=1 reason=tia-running"; exit 3 }
  $li = Get-LockInfo
  if ($li) { Write-Host "LOCK held by '$($li.Who)' ($($li.AgeMin) min) -> refusing"; Write-Host "HMIBUILD_RESULT ok=0 provisional=1 reason=lock-held"; exit 3 }
}
$t0 = Get-Date
$code = Invoke-Logged $log "powershell" $ra
$hr = Find-Line $log "HMI_RESULT"
$dt = [int]((Get-Date) - $t0).TotalSeconds
if ($hr) { Write-Host $hr }
$ok = ($code -eq 0)
Write-Host ("HMIBUILD_RESULT ok={0} provisional=1 exit={1} secs={2} log={3}" -f [int]$ok, $code, $dt, $log)
if ($ok) { exit 0 } else { exit 1 }
