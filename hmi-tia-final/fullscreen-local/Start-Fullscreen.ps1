param([string]$ProjectDirectory=(Join-Path $env:USERPROFILE 'Documents\plc-hackathon\tia-work\hmi-side\project\PLC_hackathon_2026_V21'))
$ErrorActionPreference='Stop'
$runtimeExe='C:\Program Files (x86)\Siemens\Automation\WinCC RT Advanced\HmiRTm.exe'
$runtimeConfig=Join-Path $ProjectDirectory 'IM\HMI\C\0\Generates\pdata.fwc'
if(-not(Test-Path -LiteralPath $runtimeConfig)){throw 'Open the project in TIA V21, rebuild the HMI, and start simulation once before using this launcher.'}
Get-CimInstance Win32_Process -Filter "name='HmiRTm.exe'" | Where-Object {$_.CommandLine -and $_.CommandLine.Contains($runtimeConfig)} | ForEach-Object {Stop-Process -Id $_.ProcessId}
Start-Sleep -Milliseconds 800
$launch=New-Object System.Diagnostics.ProcessStartInfo
$launch.FileName=$runtimeExe
$launch.Arguments='"'+$runtimeConfig+'" /ShowLayout /Simulation /Restart /L1033'
$launch.UseShellExecute=$false
$launch.EnvironmentVariables['__COMPAT_LAYER']='DPIUNAWARE'
[Diagnostics.Process]::Start($launch) | Out-Null
