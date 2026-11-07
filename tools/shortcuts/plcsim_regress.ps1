<#
plcsim_regress.ps1 - full PLCSIM regression of the crane PLC on a virtual CPU 1515 (S7-PLCSIM V21 Runtime API 8.0).
Wraps the existing tools in tools\plcsim (TiaDownload.exe, SimHost.exe, simclient.py, crane_sim_test.py,
crane_scenarios.py) - recipe from tia-src\PLCSIM_RESULTS.md.

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\plcsim_regress.ps1 [-Project tia-work\simtest]
        [-Sets std | <name|path>,<name|path>,...] [-NoScenarios] [-Scenarios semi,stopstart,...]
        [-SkipDownload] [-KeepSim] [-Owner shortcuts-plcsim] [-WaitLock <sec>] [-AllowRunningTia] [-DryRun]

Use a TEST COPY as -Project (default tia-work\simtest). Refresh it first with
  tools\shortcuts\tia_build.ps1 -Project tia-work\simtest
Steps:
  1. (lock + no other TIA) TiaDownload.exe --project <P> --card <P-parent>\card  (virtual memory card,
     TargetForSoftware = PlcSimulationAdvanced). Online Openness download does NOT work ("Connect to module PLC_1 failed").
     Lock released right after the download; the rest needs no Openness.
  2. start SimHost.exe --name crane --cpu CPU1515 (127.0.0.1:50123) unless it already listens; PON once so the
     persistence folder exists, then POFF.
  3. copy card\SIMATIC.S7S (folder) + card\S7_JOB.S7S into
     %USERPROFILE%\Documents\Siemens\Simatic\Simulation\Runtime\Persistence\crane\SIMATIC_MC\
  4. sim_hwdb.ini: "CPU Ordering Number": "6ES7 515-2AM01-0AB0 " (trailing space!) - else RUN fails with -52 IsEmpty.
  5. PON, RUN (state must be Run), TAGS.
  6. crane_sim_test.py on each set (results -> tools\shortcuts\logs\plcsim_<stamp>\), then crane_scenarios.py
     (HUMAN_STEPS 1.x via tag writes).
  7. POFF + QUIT (only if this script started SimHost; -KeepSim leaves it running for manual pokes).
-Sets std = the 8 standard sets of PLCSIM_RESULTS.md. Names are looked up in tools\crane_data and tools\judge_sets.
Final line: PLCSIM_RESULT ok=0|1 sets=<pass>/<n> scen_fails=<k>. Real time: ~1 s per crane command (rand_04 ~5 min);
the std run takes ~20-25 min.
#>
param([string]$Project = "tia-work\simtest", [string]$Sets = "std", [switch]$NoScenarios, [string]$Scenarios = "",
      [switch]$SkipDownload, [switch]$KeepSim, [string]$Owner = "shortcuts-plcsim", [int]$WaitLock = 0,
      [switch]$AllowRunningTia, [string]$Name = "crane", [int]$Port = 50123,
      [string]$CpuOrder = "6ES7 515-2AM01-0AB0 ", [switch]$DryRun)
. "$PSScriptRoot\_common.ps1"
$STD = @("judge_sets\r1_jury_fig1_half", "crane_data\rand_05", "crane_data\edge_initial_imbalance",
         "crane_data\edge_invalid_dup_ids", "crane_data\edge_full_ship", "judge_sets\r2_jury_imb_a",
         "crane_data\rand_04", "judge_sets\r1_elimination_needless_fallback_s777_rand_0223")
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
$plc = Join-Path $script:Repo "tools\plcsim"
$proj = Resolve-ProjectDir $Project
if (-not $proj) { Write-Host "PLCSIM_RESULT ok=0 reason=project-not-found ($Project)"; exit 2 }
$card = Join-Path (Split-Path $proj) "card"
$persist = Join-Path $env:USERPROFILE "Documents\Siemens\Simatic\Simulation\Runtime\Persistence\$Name"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $script:LogDir "plcsim_$stamp"
$log = Join-Path $script:LogDir "plcsim_$stamp.log"

# resolve data sets
$setList = if ($Sets -eq "std") { $STD } else { $Sets.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ } }
$files = @()
foreach ($s in $setList) {
  $cands = @($s, "$s.json", (Join-Path $script:Repo $s), (Join-Path $script:Repo "$s.json"),
             (Join-Path $script:Repo "tools\$s.json"), (Join-Path $script:Repo "tools\crane_data\$s.json"),
             (Join-Path $script:Repo "tools\judge_sets\$s.json"))
  $f = $cands | Where-Object { Test-Path $_ -PathType Leaf } | Select-Object -First 1
  if (-not $f) { Write-Host "PLCSIM_RESULT ok=0 reason=set-not-found ($s)"; exit 2 }
  $files += (Resolve-Path $f).Path
}

function Test-Port { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $Port); $c.Close(); return $true } catch { return $false } }
function Sim([string]$line) {
  $out = & $py (Join-Path $plc "simclient.py") $line.Split(" ") 2>&1 | ForEach-Object { "$_" }
  $txt = ($out -join " ").Trim()
  Add-Content -Path $log -Value "SIM $line -> $txt" -Encoding UTF8
  Write-Step "SIM $line -> $(if ($txt.Length -gt 100) { $txt.Substring(0, 100) + '...' } else { $txt })"
  return $txt
}

if ($DryRun) {
  Write-Host "DRYRUN plcsim_regress"
  Write-Host "  project : $proj"
  Write-Host "  card    : $card"
  Write-Host "  persist : $persist"
  $li = Get-LockInfo; Write-Host ("  lock    : " + $(if ($li) { "HELD by '$($li.Who)' ($($li.AgeMin) min) -> a real run would refuse" } else { "free" }))
  Write-Host ("  TIA     : " + $(if ((Get-TiaProcesses).Count) { "running -> a real run would refuse" } else { "not running" }))
  Write-Host ("  SimHost : " + $(if (Test-Port) { "listening on $Port (would attach, not QUIT at end)" } else { "not running (would start $($script:SimHost))" }))
  if (-not $SkipDownload) {
    Write-Host "  1. take lock '$Owner'"
    Invoke-Logged $log $script:TiaDownload @("--project", $proj, "--card", $card) -DryRun | Out-Null
    Write-Host "     release lock"
  } else { Write-Host "  1. -SkipDownload: reuse $card" }
  Write-Host "  2. SimHost.exe --name $Name --cpu CPU1515 --port $Port ; simclient PON ; POFF"
  Write-Host "  3. copy $card\SIMATIC.S7S + S7_JOB.S7S -> $persist\SIMATIC_MC\"
  Write-Host "  4. patch $persist\sim_hwdb.ini  CPU Ordering Number = '$CpuOrder'"
  Write-Host "  5. simclient PON ; RUN ; TAGS"
  foreach ($f in $files) { Write-Host "  6. python tools\plcsim\crane_sim_test.py $f --out $outDir" }
  if (-not $NoScenarios) { Write-Host "  6. python tools\plcsim\crane_scenarios.py $(if ($Scenarios) { "--only $Scenarios" })" }
  Write-Host "  7. POFF$(if (-not $KeepSim) { ' ; QUIT (if started here)' })"
  Write-Host "PLCSIM_RESULT ok=1 dryrun=1 sets=$($files.Count)"
  exit 0
}

New-Item -ItemType Directory -Force $outDir | Out-Null
$t0 = Get-Date
foreach ($exe in @($script:SimHost, $script:TiaDownload)) {
  if (-not (Test-Path $exe)) {
    Write-Step "building tools\plcsim (missing $exe)"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $plc "build.ps1")
    if (-not (Test-Path $exe)) { Write-Host "PLCSIM_RESULT ok=0 reason=build-failed"; exit 2 }
  }
}

# 1. card image
if (-not $SkipDownload) {
  if (-not (Test-TiaFree -AllowRunningTia:$AllowRunningTia)) { Write-Host "PLCSIM_RESULT ok=0 reason=tia-running"; exit 3 }
  if (-not (Enter-OpennessLock $Owner $WaitLock)) { Write-Host "PLCSIM_RESULT ok=0 reason=lock-held"; exit 3 }
  try { $null = Invoke-Logged $log $script:TiaDownload @("--project", $proj, "--card", $card) } finally { Exit-OpennessLock }
  $dr = Find-Line $log "DOWNLOAD_RESULT"
  if (-not ($dr -match "state=Success errors=0")) { Write-Host "PLCSIM_RESULT ok=0 reason=card-download ($dr) log=$log"; exit 1 }
}
if (-not (Test-Path "$card\S7_JOB.S7S")) { Write-Host "PLCSIM_RESULT ok=0 reason=no-card-image ($card)"; exit 1 }

# 2. SimHost
$started = $false; $hostProc = $null
if (-not (Test-Port)) {
  $hostProc = Start-Process -FilePath $script:SimHost -ArgumentList @("--name", $Name, "--cpu", "CPU1515", "--port", "$Port") `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput "$outDir\simhost.out" -RedirectStandardError "$outDir\simhost.err"
  $started = $true
  $deadline = (Get-Date).AddSeconds(90)
  while (-not (Test-Port) -and (Get-Date) -lt $deadline -and -not $hostProc.HasExited) { Start-Sleep -Milliseconds 500 }
  if (-not (Test-Port)) { Write-Host "PLCSIM_RESULT ok=0 reason=simhost-not-listening (see $outDir\simhost.out)"; exit 1 }
  Write-Step "SimHost started (PID $($hostProc.Id))"
} else { Write-Step "SimHost already listening on $Port - attaching" }

$setRows = @(); $scenFails = -1
try {
  if (-not (Test-Path "$persist\sim_hwdb.ini")) { Sim "PON" | Out-Null }
  Sim "POFF" | Out-Null
  # 3. card files
  $mc = Join-Path $persist "SIMATIC_MC"
  New-Item -ItemType Directory -Force $mc | Out-Null
  if (Test-Path "$mc\SIMATIC.S7S") { Remove-Item "$mc\SIMATIC.S7S" -Recurse -Force }
  Copy-Item "$card\SIMATIC.S7S" "$mc\SIMATIC.S7S" -Recurse -Force
  Copy-Item "$card\S7_JOB.S7S" "$mc\S7_JOB.S7S" -Force
  Write-Step "card image copied to $mc"
  # 4. article number
  $ini = "$persist\sim_hwdb.ini"
  if (Test-Path $ini) {
    $txt = [IO.File]::ReadAllText($ini)
    $new = [regex]::Replace($txt, '("CPU Ordering Number"\s*:\s*")[^"]*(")', ('${1}' + $CpuOrder + '${2}'))
    if ($new -ne $txt) { [IO.File]::WriteAllText($ini, $new, (New-Object Text.UTF8Encoding($false))); Write-Step "sim_hwdb.ini patched -> '$CpuOrder'" }
    else { Write-Step "sim_hwdb.ini already '$CpuOrder'" }
  } else { Write-Step "WARNING: $ini missing - RUN may fail with -52 IsEmpty" }
  # 5. power on + run
  Sim "PON" | Out-Null
  $r = Sim "RUN"
  $stt = Sim "STATE"
  if ($stt -notmatch "Run") { Write-Host "PLCSIM_RESULT ok=0 reason=cpu-not-in-run ($stt) log=$log"; exit 1 }
  Sim "TAGS" | Out-Null
  # 6. data sets
  foreach ($f in $files) {
    $nm = [IO.Path]::GetFileNameWithoutExtension($f)
    $code = Invoke-Logged $log $py @((Join-Path $plc "crane_sim_test.py"), $f, "--port", "$Port", "--out", $outDir)
    $rj = Join-Path $outDir "$nm.result.json"
    $row = [ordered]@{ set = $nm; pass = $false; M = "-"; T_ds = "-"; MSpec = "-"; J = "-"; cmds = "-"; bays = "-"; maxbal = "-"; plan_ms = "-" }
    if (Test-Path $rj) {
      $j = Get-Content $rj -Raw -Encoding UTF8 | ConvertFrom-Json
      $row.pass = [bool]$j.pass
      $row.M = "$($j.plc_M)/$($j.model.M)"; $row.T_ds = "$($j.plc_T_ds)/$($j.model.T_ds)"
      $row.MSpec = "$($j.plc_MSpec)"; $row.J = if ($j.plc_J) { "{0:N5}" -f [double]$j.plc_J } else { "-" }
      $row.cmds = "$($j.plc_cmds_reconstructed)/$($j.model_cmds) $(if ($j.cmds_match) { '=' } else { '~' })"
      $row.bays = if ($j.bay0_match -and $j.bay1_match) { "=" } else { "DIFF" }
      $row.maxbal = "$($j.max_abs_balance)"; $row.plan_ms = if ($j.planner_max_call_ms) { "{0:N1}" -f [double]$j.planner_max_call_ms } else { "-" }
    }
    $setRows += [pscustomobject]$row
  }
  if (-not $NoScenarios) {
    $sa = @((Join-Path $plc "crane_scenarios.py"))
    if ($Scenarios) { $sa += @("--only", $Scenarios) }
    $null = Invoke-Logged $log $py $sa
    $sl = Find-Line $log "SCEN_RESULT"
    $scenFails = if ($sl -match "fails=(\d+)") { [int]$Matches[1] } else { 999 }
    $sj = Join-Path $plc "results\scenarios.json"
    if (Test-Path $sj) { Copy-Item $sj (Join-Path $outDir "scenarios.json") -Force }
  }
} finally {
  # 7. power off / quit
  try { Sim "POFF" | Out-Null } catch {}
  if ($started -and -not $KeepSim) { try { Sim "QUIT" | Out-Null } catch {}; Start-Sleep 2; if ($hostProc -and -not $hostProc.HasExited) { $hostProc.Kill() } }
}

$dt = [int]((Get-Date) - $t0).TotalSeconds
Write-Host ""
Write-Host "== PLCSIM regression ($dt s) - PLC/model; results in $outDir"
$setRows | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
$np = @($setRows | Where-Object { $_.pass }).Count
$sf = if ($NoScenarios) { "skipped" } else { "$scenFails" }
$ok = ($np -eq $setRows.Count) -and ($NoScenarios -or $scenFails -eq 0)
Write-Host ("PLCSIM_RESULT ok={0} sets={1}/{2} scen_fails={3} secs={4} log={5}" -f [int]$ok, $np, $setRows.Count, $sf, $dt, $log)
if ($ok) { exit 0 } else { exit 1 }
