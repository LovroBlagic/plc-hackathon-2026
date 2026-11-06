# Run me_run.py (or another ME IronPython script) headless in LogicBuilderShell.
#   me.ps1 --project C:/abs/X.project --src C:/abs/src [--tests C:/abs/tests.json] [--create]
#   me.ps1 -Script probe_devices.py
param([string]$Script = "me_run.py", [Parameter(ValueFromRemainingArguments)][string[]]$Rest)
$shell = "C:\Program Files\Schneider Electric\EcoStruxure Machine Expert\V2.3\LogicBuilderShell.exe"
if (-not (Test-Path $shell)) { Write-Error "LogicBuilderShell.exe not found at $shell"; exit 2 }
# Fast-fail: Logic Builder writes <name>.~u next to a project while it is open in the GUI (stale after a crash -> delete it)
$i = [array]::IndexOf($Rest, "--project")
if ($i -ge 0 -and $Rest.Count -gt $i + 1) {
    $lock = [IO.Path]::ChangeExtension($Rest[$i + 1], ".~u")
    if (Test-Path $lock) { Write-Output "FATAL: project is open in Logic Builder (lock $lock). Close it there or work on a copy."; exit 3 }
}
$path = if ([IO.Path]::IsPathRooted($Script)) { $Script } else { Join-Path $PSScriptRoot $Script }
& $shell $path @Rest
exit $LASTEXITCODE
