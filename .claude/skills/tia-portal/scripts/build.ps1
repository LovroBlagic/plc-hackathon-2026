# Compile TiaRun.exe with the .NET Framework 4.8 C# compiler (C# 5). Re-run after editing TiaRun.cs.
$api = "C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48"
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:exe /platform:x64 /out:"$PSScriptRoot\TiaRun.exe" `
  /reference:"$api\Siemens.Engineering.Base.dll" /reference:"$api\Siemens.Engineering.Step7.dll" `
  /reference:System.Core.dll "$PSScriptRoot\TiaRun.cs"
exit $LASTEXITCODE
