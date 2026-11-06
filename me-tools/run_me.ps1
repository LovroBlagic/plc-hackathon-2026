# Run a Machine Expert IronPython script headless.  Usage: .\run_me.ps1 <script.py> [args...]
param([Parameter(Mandatory)][string]$Script, [Parameter(ValueFromRemainingArguments)][string[]]$Rest)
$shell = "C:\Program Files\Schneider Electric\EcoStruxure Machine Expert\V2.3\LogicBuilderShell.exe"
& $shell (Resolve-Path $Script).Path @Rest
