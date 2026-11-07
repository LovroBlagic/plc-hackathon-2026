# One-command HMI regeneration: layout.json + exported prototypes -> XML -> import into tia-work\crane -> compile.
#   .\hmi-tia\regen.ps1 -Export    re-export the human prototypes, generate, import, compile (lock "hmi")
#   .\hmi-tia\regen.ps1            generate from the existing hmi-tia\export, import, compile
#   .\hmi-tia\regen.ps1 -DryRun    generate + check + preview only (no TIA); uses hmi-tia\mock if no export
# Round 1 (export has tags/text lists but no Proto screen yet): generates/imports only tags + text lists.
param([switch]$Export, [switch]$DryRun, [string]$Project = "$PSScriptRoot\..\tia-work\crane\PLC_hackathon_2026_V21")
$here = $PSScriptRoot
$exe = "$here\HmiGen.exe"
if (-not (Test-Path $exe)) { & "$here\build_hmigen.ps1"; if ($LASTEXITCODE) { exit 2 } }
if ($Export -and -not $DryRun) {
  $proj = (Resolve-Path $Project).Path
  & $exe --project $proj --lock hmi --export "$here\export" --no-save
  if ($LASTEXITCODE -eq 2) { exit 2 }
}
$out = "$here\out"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
$hasProto = Test-Path "$here\export\screens\Proto.xml"
$hasBase = (Test-Path "$here\export\tags") -and (Test-Path "$here\export\textlists")
if ($hasProto) { & python "$here\gen_hmi.py" all --export "$here\export" --out $out }
elseif ($hasBase -and -not $DryRun) { & python "$here\gen_hmi.py" base --export "$here\export" --out $out }
else { Write-Host "DRY RUN with mock prototypes"; & python "$here\gen_hmi.py" all --export "$here\mock" --out $out; $DryRun = $true }
if ($LASTEXITCODE) { Write-Host "GENERATOR CHECK FAILED"; exit 1 }
$sample = "$here\export\alarm_sample.xlsx"
if (Test-Path $sample) { & python "$here\alarms_gen.py" --sample $sample --out "$out\alarms" } else { & python "$here\alarms_gen.py" --out "$out\alarms" }
if (Test-Path "$out\screens") { & python "$here\preview.py" --out $out }
if ($DryRun) { exit 0 }
$proj = (Resolve-Path $Project).Path
& $exe --project $proj --lock hmi --import $out --compile
exit $LASTEXITCODE
