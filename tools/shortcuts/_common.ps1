# _common.ps1 - shared helpers for tools/shortcuts/*.ps1 (dot-sourced, not run directly).
# Lock protocol (CONTRACT §5): tia-work\openness.lock = "<owner> yyyy-MM-dd HH:mm:ss".
# These shortcuts NEVER take over a foreign lock (also not a "stale" one): they refuse and exit 3.
$ErrorActionPreference = "Continue"
$script:Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$script:LockFile = Join-Path $script:Repo "tia-work\openness.lock"
$script:TiaRun = Join-Path $script:Repo ".claude\skills\tia-portal\scripts\TiaRun.exe"
$script:TiaDownload = Join-Path $script:Repo "tools\plcsim\bin\TiaDownload.exe"
$script:SimHost = Join-Path $script:Repo "tools\plcsim\bin\SimHost.exe"
$script:LogDir = Join-Path $script:Repo "tools\shortcuts\logs"
$script:LockOwner = $null
$env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force $script:LogDir | Out-Null

function New-LogPath([string]$name) { Join-Path $script:LogDir ("{0}_{1}.log" -f $name, (Get-Date -Format "yyyyMMdd_HHmmss")) }

function Write-Step([string]$msg) { Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) }

function Get-LockInfo {
  if (-not (Test-Path $script:LockFile)) { return $null }
  $who = ""; try { $who = (Get-Content $script:LockFile -Raw -ErrorAction Stop).Trim() } catch {}
  $age = ((Get-Date) - (Get-Item $script:LockFile).LastWriteTime).TotalMinutes
  return [pscustomobject]@{ Who = $who; AgeMin = [math]::Round($age, 1) }
}

# Returns $true when taken. Never steals. With -WaitSec waits for a free lock (polls every 15 s).
function Enter-OpennessLock([string]$owner, [int]$WaitSec = 0) {
  $until = (Get-Date).AddSeconds($WaitSec)
  while ($true) {
    $li = Get-LockInfo
    if ($null -eq $li) {
      New-Item -ItemType Directory -Force (Split-Path $script:LockFile) | Out-Null
      $text = "{0} {1}" -f $owner, (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
      Set-Content -Path $script:LockFile -Value $text -NoNewline -Encoding ASCII
      $script:LockOwner = $owner
      Start-LockHeartbeat $text
      Write-Step "LOCK taken by '$owner': $($script:LockFile) (heartbeat 150 s)"
      return $true
    }
    if ((Get-Date) -ge $until) {
      Write-Host "LOCK held by '$($li.Who)' ($($li.AgeMin) min old): $($script:LockFile)"
      Write-Host "  -> refusing (shortcuts never take over a lock). Wait for the owner, or ask the orchestrator."
      return $false
    }
    Write-Step "LOCK held by '$($li.Who)' ($($li.AgeMin) min), waiting..."
    Start-Sleep -Seconds 15
  }
}

# Heartbeat (rule after the 7 Nov double-TIA incident): a hidden helper process touches the lock every 150 s while
# its content is still ours AND this script's process is alive; it ends by itself after release or a crash.
function Start-LockHeartbeat([string]$text) {
  $f = $script:LockFile.Replace("'", "''"); $t = $text.Replace("'", "''")
  $loop = "`$f='$f'; `$t='$t'; `$pp=$PID; while ((Test-Path `$f) -and ((Get-Content `$f -Raw).Trim() -eq `$t) -and (Get-Process -Id `$pp -ErrorAction SilentlyContinue)) { (Get-Item `$f).LastWriteTime = Get-Date; Start-Sleep -Seconds 150 }"
  $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($loop))
  $script:HeartbeatProc = Start-Process powershell -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", $enc) -WindowStyle Hidden -PassThru
}

function Exit-OpennessLock {
  if ($script:HeartbeatProc -and -not $script:HeartbeatProc.HasExited) { try { $script:HeartbeatProc.Kill() } catch {} }
  $script:HeartbeatProc = $null
  if ($null -eq $script:LockOwner) { return }
  $li = Get-LockInfo
  if ($li -and $li.Who.StartsWith($script:LockOwner + " ")) { Remove-Item $script:LockFile -Force; Write-Step "LOCK released" }
  elseif ($li) { Write-Step "LOCK now belongs to '$($li.Who)', not removed" }
  $script:LockOwner = $null
}

# Keep the lock mtime fresh during long runs so nobody treats it as stale (>10 min).
function Update-OpennessLock {
  if ($script:LockOwner -and (Test-Path $script:LockFile)) { (Get-Item $script:LockFile).LastWriteTime = Get-Date }
}

# A headless Openness session runs INSIDE the client exe (TiaRun/HmiGen/HmiLab/TiaDownload), there is no
# Siemens.Automation.Portal process then - so look for both.
function Get-TiaProcesses {
  @(Get-Process -Name "Siemens.Automation.Portal", "TiaRun", "HmiGen", "HmiLab", "TiaDownload" -ErrorAction SilentlyContinue)
}

# RAM rule: only one TIA Portal instance on this laptop. Returns $true when it is OK to start one.
function Test-TiaFree([switch]$AllowRunningTia) {
  $p = Get-TiaProcesses
  if ($p.Count -eq 0) { return $true }
  Write-Host ("TIA Portal / Openness client already running: {0}." -f (($p | ForEach-Object { "$($_.Name)#$($_.Id)" }) -join ", "))
  if ($AllowRunningTia) { Write-Host "  -AllowRunningTia given: starting another headless instance anyway"; return $true }
  Write-Host "  -> refusing (RAM rule: one TIA instance). Close it, or pass -AllowRunningTia."
  return $false
}

# Run a native command, stream its output, append it to $Log, return the exit code. DryRun only prints it.
function Invoke-Logged([string]$Log, [string]$Exe, [string[]]$Arguments, [switch]$DryRun) {
  $show = '"' + $Exe + '" ' + (($Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' ')
  if ($DryRun) { Write-Host "  DRYRUN> $show"; return 0 }
  Write-Step "RUN $show"
  Add-Content -Path $Log -Value "### $show" -Encoding UTF8
  & $Exe @Arguments 2>&1 | ForEach-Object {
    $s = "$_"; Write-Host $s; Add-Content -Path $Log -Value $s -Encoding UTF8
    Update-OpennessLock
  }
  return $LASTEXITCODE
}

function Find-Line([string]$Log, [string]$Pattern) {
  if (-not (Test-Path $Log)) { return $null }
  $m = Select-String -Path $Log -Pattern $Pattern | Select-Object -Last 1
  if ($m) { return $m.Line.Trim() } else { return $null }
}

function Resolve-ProjectDir([string]$p) {
  # Accepts the project folder (holding *.ap21), the .ap21 itself, or a parent folder with exactly one project folder.
  if ([string]::IsNullOrWhiteSpace($p)) { return $null }
  if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $script:Repo $p }
  if ($p -like "*.ap21") { $p = Split-Path $p }
  if (-not (Test-Path $p)) { return $null }
  $p = (Resolve-Path $p).Path.TrimEnd('\')
  if (Get-ChildItem $p -Filter *.ap21 -ErrorAction SilentlyContinue) { return $p }
  $sub = @(Get-ChildItem $p -Directory | Where-Object { Get-ChildItem $_.FullName -Filter *.ap21 -ErrorAction SilentlyContinue })
  if ($sub.Count -eq 1) { return $sub[0].FullName }
  return $null
}

function Get-WorldMMode {
  $m = Select-String -Path (Join-Path $script:Repo "tia-src\02_World.db") -Pattern 'CfgMMode\s*:\s*USInt\s*:=\s*(\d+)' | Select-Object -First 1
  if ($m) { return [int]$m.Matches[0].Groups[1].Value } else { return -1 }
}
