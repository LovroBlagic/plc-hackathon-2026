# Build SimHost.exe (PLCSIM Runtime API 8.0) and TiaDownload.exe (TIA V21 Openness) with the .NET Framework 4.8 csc (C# 5).
#   powershell -ExecutionPolicy Bypass -File tools\plcsim\build.ps1 [SimHost|TiaDownload]   (default: both)
param([string]$Only = "")
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$sim = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
$api = "C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48"
$out = Join-Path $PSScriptRoot "bin"
New-Item -ItemType Directory -Force $out | Out-Null
if ($Only -eq "" -or $Only -eq "SimHost") {
  Copy-Item $sim $out -Force
  & $csc /nologo /target:exe /platform:x64 /out:"$out\SimHost.exe" /reference:"$sim" /reference:System.Core.dll "$PSScriptRoot\SimHost.cs"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($Only -eq "" -or $Only -eq "TiaDownload") {
  & $csc /nologo /target:exe /platform:x64 /out:"$out\TiaDownload.exe" `
    /reference:"$api\Siemens.Engineering.Base.dll" /reference:"$api\Siemens.Engineering.Step7.dll" `
    /reference:System.Core.dll "$PSScriptRoot\TiaDownload.cs"
}
exit $LASTEXITCODE
