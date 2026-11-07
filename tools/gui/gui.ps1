# gui.ps1 - minimal desktop automation without windows-mcp (user32 + System.Windows.Forms).
# Usage (one action per call, prints a result line):
#   powershell -File tools\gui\gui.ps1 shot [out.png] [-Region x,y,w,h]
#   powershell -File tools\gui\gui.ps1 click X Y [left|right|double]
#   powershell -File tools\gui\gui.ps1 drag X1 Y1 X2 Y2
#   powershell -File tools\gui\gui.ps1 type "text"          (SendKeys syntax: {ENTER} {TAB} ^s = Ctrl+S, %f = Alt+F)
#   powershell -File tools\gui\gui.ps1 keys "^s"
#   powershell -File tools\gui\gui.ps1 focus "window title substring"
# Notes: coordinates are physical screen pixels (1366x768 on this laptop, 100% scale).
param([Parameter(Position = 0)][string]$Cmd, [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class U32 {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  public const uint LD = 0x02, LU = 0x04, RD = 0x08, RU = 0x10;
}
"@
function Shot([string]$out) {
    if (-not $out) { $out = Join-Path $PSScriptRoot "..\..\tia-work\gui\shot.png" }
    $dir = Split-Path $out; if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save((Resolve-Path -LiteralPath $dir).Path + "\" + (Split-Path $out -Leaf)); $g.Dispose(); $bmp.Dispose()
    "SHOT $out"
}
function Click([int]$x, [int]$y, [string]$kind = "left") {
    [U32]::SetCursorPos($x, $y) | Out-Null; Start-Sleep -Milliseconds 80
    switch ($kind) {
        "right" { [U32]::mouse_event([U32]::RD, 0, 0, 0, [UIntPtr]::Zero); [U32]::mouse_event([U32]::RU, 0, 0, 0, [UIntPtr]::Zero) }
        "double" { 1..2 | ForEach-Object { [U32]::mouse_event([U32]::LD, 0, 0, 0, [UIntPtr]::Zero); [U32]::mouse_event([U32]::LU, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 60 } }
        default { [U32]::mouse_event([U32]::LD, 0, 0, 0, [UIntPtr]::Zero); [U32]::mouse_event([U32]::LU, 0, 0, 0, [UIntPtr]::Zero) }
    }
    "CLICK $kind $x $y"
}
function Drag([int]$x1, [int]$y1, [int]$x2, [int]$y2) {
    [U32]::SetCursorPos($x1, $y1) | Out-Null; Start-Sleep -Milliseconds 100
    [U32]::mouse_event([U32]::LD, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 150
    for ($i = 1; $i -le 20; $i++) { [U32]::SetCursorPos([int]($x1 + ($x2 - $x1) * $i / 20), [int]($y1 + ($y2 - $y1) * $i / 20)) | Out-Null; Start-Sleep -Milliseconds 30 }
    Start-Sleep -Milliseconds 200; [U32]::mouse_event([U32]::LU, 0, 0, 0, [UIntPtr]::Zero)
    "DRAG $x1 $y1 -> $x2 $y2"
}
function Focus([string]$title) {
    $p = Get-Process | Where-Object { $_.MainWindowTitle -like "*$title*" } | Select-Object -First 1
    if (-not $p) { "FOCUS not found: $title"; return }
    [U32]::ShowWindow($p.MainWindowHandle, 3) | Out-Null; [U32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    "FOCUS $($p.ProcessName) '$($p.MainWindowTitle)'"
}
if (-not $Rest) { $Rest = @() }
# seq "click 10 20 | wait 1500 | type abc{ENTER} | keys ^s | drag 1 2 3 4 | shot" : many actions, one process (fast)
if ($Cmd -eq "seq") {
    foreach ($a in ($Rest[0] -split '\s*\|\s*')) {
        $t = $a -split '\s+', 2; $args2 = if ($t.Count -gt 1) { $t[1] } else { "" }
        switch ($t[0]) {
            "click" { $p = $args2 -split '\s+'; Click ([int]$p[0]) ([int]$p[1]) ($(if ($p.Count -gt 2) { $p[2] } else { "left" })) }
            "drag" { $p = $args2 -split '\s+'; Drag ([int]$p[0]) ([int]$p[1]) ([int]$p[2]) ([int]$p[3]) }
            "wait" { Start-Sleep -Milliseconds ([int]$args2); "WAIT $args2" }
            "type" { [System.Windows.Forms.SendKeys]::SendWait($args2); "TYPED $args2" }
            "keys" { [System.Windows.Forms.SendKeys]::SendWait($args2); "KEYS $args2" }
            "focus" { Focus $args2 }
            "shot" { Shot $(if ($args2) { $args2 } else { $null }) }
        }
    }
    return
}
switch ($Cmd) {
    "shot" { Shot $(if ($Rest.Count -gt 0) { $Rest[0] } else { $null }) }
    "click" { Click ([int]$Rest[0]) ([int]$Rest[1]) ($(if ($Rest.Count -gt 2) { $Rest[2] } else { "left" })) }
    "drag" { Drag ([int]$Rest[0]) ([int]$Rest[1]) ([int]$Rest[2]) ([int]$Rest[3]) }
    "type" { [System.Windows.Forms.SendKeys]::SendWait($Rest[0]); "TYPED" }
    "keys" { [System.Windows.Forms.SendKeys]::SendWait($Rest[0]); "KEYS $($Rest[0])" }
    "focus" { Focus $Rest[0] }
    default { "usage: shot|click|drag|type|keys|focus" }
}
