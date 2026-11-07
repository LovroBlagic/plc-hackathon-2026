<#
crane_check.ps1 - fast OFFLINE crane loop (no TIA, no lock needed): parity mirrors, stress, FB10 model, eval.

  powershell -ExecutionPolicy Bypass -File tools\shortcuts\crane_check.ps1 [-Quick] [-Only mirror12,mirror13,stress,fb10,eval] [-DryRun]

Steps (all read tia-src + tools, write nothing outside tools\shortcuts\logs):
  mmode     World.CfgMMode (tia-src\02_World.db) == crane_plan.py --mmode default (the PLCSIM harness model uses it)
  fb10      tools\fb10_init_model.py                    -> FB10_INIT_RESULT failures=0
  mirror12  tia-src\12_planner_mirror.py (background)   -> TOTAL runs=N fails=0          (~4 min, 1 core)
  stress    tools\crane_stress.py [--random 300]        -> STRESS_RESULT failures=0
  eval      tools\crane_eval.py --mmode <CfgMMode>      -> "PLC DEFAULT" mean/max J per group, deterministic
  mirror13  tools\mirror13_par.py [400 3]               -> IMPROVE_MIRROR runs=N fails=0  (all cores)
-Quick: stress --random 40 --evals 300, eval --evals 600, mirror13 budget 150 (numbers differ from the full run).
Final line: CHECK_RESULT ok=0|1 fails=<steps> (...). Exit 0 only when every step passed.
#>
param([switch]$Quick, [string]$Only = "mmode,fb10,mirror12,stress,eval,mirror13", [switch]$DryRun)
. "$PSScriptRoot\_common.ps1"
$steps = $Only.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Host "CHECK_RESULT ok=0 fails=python (python not on PATH)"; exit 2 }
$mm = Get-WorldMMode
$tag = Get-Date -Format "yyyyMMdd_HHmmss"
$res = [ordered]@{}; $fails = @()
function LogOf($n) { Join-Path $script:LogDir ("check_{0}_{1}.log" -f $n, $tag) }

$defs = [ordered]@{
  fb10     = @("tools\fb10_init_model.py")
  mirror12 = @("tia-src\12_planner_mirror.py")
  stress   = $(if ($Quick) { @("tools\crane_stress.py", "--random", "40", "--evals", "300") } else { @("tools\crane_stress.py") })
  eval     = $(if ($Quick) { @("tools\crane_eval.py", "--mmode", "$mm", "--evals", "600") } else { @("tools\crane_eval.py", "--mmode", "$mm") })
  mirror13 = $(if ($Quick) { @("tools\mirror13_par.py", "150", "3") } else { @("tools\mirror13_par.py") })
}
$pat = @{ fb10 = "FB10_INIT_RESULT"; mirror12 = "^TOTAL runs="; stress = "STRESS_RESULT"; mirror13 = "IMPROVE_MIRROR runs=" }

function Start-Py($n) {
  $log = LogOf $n
  $err = "$log.err"
  $p = Start-Process -FilePath $py -ArgumentList $defs[$n] -WorkingDirectory $script:Repo -NoNewWindow -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError $err
  $null = $p.Handle   # PS 5.1 quirk: without touching Handle, ExitCode stays $null after the process exits
  return $p
}
function Judge($n, $code) {
  $log = LogOf $n
  if (Test-Path "$log.err") { Get-Content "$log.err" | Add-Content $log; Remove-Item "$log.err" }
  if ($n -eq "eval") {
    $lines = @(Select-String -Path $log -Pattern "^== |PLC DEFAULT|lower bound|deterministic all" | ForEach-Object { $_.Line.Trim() })
    $det = ($lines | Where-Object { $_ -like "deterministic all*" }) -join ";"
    $ok = ($code -eq 0) -and ($lines.Count -gt 0) -and ($det -notmatch "False")
    $dflt = @($lines | Where-Object { $_ -like "PLC DEFAULT*" } | ForEach-Object { ($_ -split ":")[1].Trim() })
    $summary = "mmode=$mm PLC-default J(mean max) " + ($dflt -join " | ")
    $lines | ForEach-Object { Write-Host "    $_" }
  } else {
    $line = Find-Line $log $pat[$n]
    $ok = ($code -eq 0) -and $line -and ($line -match "fail(s|ures)=0(\D|$)")
    $summary = if ($line) { $line } else { "no result line (exit $code)" }
  }
  $script:res[$n] = $summary
  if (-not $ok) { $script:fails += $n; Write-Host "  FAIL $n ($summary) - log: $log" } else { Write-Host "  OK   $n : $summary" }
}

if ($DryRun) {
  Write-Host "DRYRUN crane_check (World.CfgMMode=$mm, python=$py, cwd=$($script:Repo))"
  foreach ($n in $steps) {
    if ($n -eq "mmode") { Write-Host "  DRYRUN> compare World.CfgMMode ($mm) with crane_plan.parse_args default"; continue }
    Write-Host ("  DRYRUN> python {0}   > {1}" -f ($defs[$n] -join " "), (LogOf $n))
  }
  Write-Host "CHECK_RESULT ok=1 dryrun=1 steps=$($steps -join ',')"
  exit 0
}

$t0 = Get-Date
Write-Step "crane_check: World.CfgMMode=$mm, steps=$($steps -join ','), logs tools\shortcuts\logs\check_*_$tag.log"
if ($steps -contains "mmode") {
  $pm = & $py -c "import sys; sys.path.insert(0, r'$($script:Repo)\tools'); import crane_plan as cp; print(cp.parse_args(['x.json']).mmode)" 2>$null
  $ok = ("$pm".Trim() -eq "$mm")
  $res["mmode"] = "World.CfgMMode=$mm crane_plan default=$("$pm".Trim())"
  if ($ok) { Write-Host "  OK   mmode : $($res['mmode'])" } else { $fails += "mmode"; Write-Host "  FAIL mmode : $($res['mmode']) (PLCSIM harness model would not match the PLC)" }
}
$bg = $null
if ($steps -contains "mirror12") { $bg = Start-Py "mirror12"; Write-Step "mirror12 started in background (PID $($bg.Id))" }
foreach ($n in @("fb10", "stress", "eval", "mirror13")) {
  if ($steps -notcontains $n) { continue }
  Write-Step "$n ..."
  $p = Start-Py $n; $p.WaitForExit(); Judge $n $p.ExitCode
}
if ($bg) { Write-Step "waiting for mirror12 ..."; $bg.WaitForExit(); Judge "mirror12" $bg.ExitCode }

$dt = [int]((Get-Date) - $t0).TotalSeconds
Write-Host ""
Write-Host "== crane_check summary (${dt} s)"
foreach ($k in $res.Keys) { Write-Host ("  {0,-9} {1}" -f $k, $res[$k]) }
$okAll = ($fails.Count -eq 0)
Write-Host ("CHECK_RESULT ok={0} fails={1} mmode={2} secs={3}" -f [int]$okAll, $(if ($okAll) { "0" } else { $fails -join "," }), $mm, $dt)
if ($okAll) { exit 0 } else { exit 1 }
