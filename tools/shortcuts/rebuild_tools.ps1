<#
rebuild_tools.ps1 - rebuild the Openness/PLCSIM exes from source, ONLY when none of them is running
(a running exe cannot be replaced, and a half-replaced tool mid-run is worse).

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\rebuild_tools.ps1 [-Only TiaRun,HmiGen,plcsim] [-DryRun]

  TiaRun  -> .claude\skills\tia-portal\scripts\build.ps1   (TiaRun.exe)
  HmiGen  -> hmi-tia\build_hmigen.ps1                       (HmiGen.exe; HMI agent's tool, source fix 7 Nov = lock rule)
  plcsim  -> tools\plcsim\build.ps1                         (SimHost.exe, TiaDownload.exe)
HmiLab.exe is the HMI agent's lab tool and is NOT rebuilt here.
Final line: REBUILD_RESULT ok=0|1 built=<list>.
#>
param([string]$Only = "TiaRun,HmiGen,plcsim", [switch]$DryRun)
. "$PSScriptRoot\_common.ps1"
$map = [ordered]@{
  TiaRun = @{ build = ".claude\skills\tia-portal\scripts\build.ps1"; procs = @("TiaRun") }
  HmiGen = @{ build = "hmi-tia\build_hmigen.ps1"; procs = @("HmiGen") }
  plcsim = @{ build = "tools\plcsim\build.ps1"; procs = @("SimHost", "TiaDownload") }
}
$want = $Only.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $map.Contains($_) }
$busy = @()
foreach ($k in $want) { $p = Get-Process -Name $map[$k].procs -ErrorAction SilentlyContinue; if ($p) { $busy += ($p | ForEach-Object { "$($_.Name)#$($_.Id)" }) } }
if ($busy.Count) { Write-Host "in use: $($busy -join ', ') -> not rebuilding (try again when idle)"; Write-Host "REBUILD_RESULT ok=0 reason=in-use"; exit 3 }
$built = @(); $failed = @()
foreach ($k in $want) {
  $b = Join-Path $script:Repo $map[$k].build
  if ($DryRun) { Write-Host "  DRYRUN> powershell -ExecutionPolicy Bypass -File $b"; continue }
  & powershell -ExecutionPolicy Bypass -File $b
  if ($LASTEXITCODE -eq 0) { $built += $k } else { $failed += $k }
}
if ($DryRun) { Write-Host "REBUILD_RESULT ok=1 dryrun=1"; exit 0 }
Write-Host ("REBUILD_RESULT ok={0} built={1}{2}" -f [int]($failed.Count -eq 0), ($built -join ","), $(if ($failed.Count) { " failed=" + ($failed -join ",") } else { "" }))
if ($failed.Count) { exit 1 } else { exit 0 }
