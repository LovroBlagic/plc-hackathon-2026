param([string]$Name, [string]$Action = 'invoke', [string]$Text = '', [int]$X = 0, [int]$Y = 0, [int]$X2 = 0, [int]$Y2 = 0)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class HmiNative {
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
}
'@
[HmiNative]::SetProcessDPIAware() | Out-Null
if ($Action -eq 'screenshot') {
    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save((Join-Path $PSScriptRoot 'screen.png'))
    $graphics.Dispose(); $bitmap.Dispose(); exit
}
$appProcess = Get-Process Siemens.Automation.Portal | Where-Object { $_.MainWindowHandle -ne 0 } | Sort-Object StartTime -Descending | Select-Object -First 1
$processCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $appProcess.Id)
$roots = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $processCondition)
$root = $roots | Where-Object { $_.Current.Name -like '*PLC_hackathon_2026_V21*' } | Select-Object -First 1
if (-not $root) { $root = $roots | Where-Object { $_.Current.Name -like '*TIA Portal*' } | Select-Object -First 1 }
[uint32]$foregroundProcessId = 0
[HmiNative]::GetWindowThreadProcessId([HmiNative]::GetForegroundWindow(), [ref]$foregroundProcessId) | Out-Null
$needsForeground = $Action -in @('keys', 'paste', 'click', 'rightclick', 'doubleclick', 'drag', 'scroll')
if ($needsForeground -and $foregroundProcessId -ne $appProcess.Id) {
    $activationShell = New-Object -ComObject WScript.Shell
    $activationShell.AppActivate($appProcess.Id) | Out-Null
    try { $root.SetFocus() } catch { }
    [HmiNative]::SetForegroundWindow([IntPtr]$appProcess.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 200
}
[HmiNative]::GetWindowThreadProcessId([HmiNative]::GetForegroundWindow(), [ref]$foregroundProcessId) | Out-Null
if ($needsForeground -and $foregroundProcessId -ne $appProcess.Id) {
    $activationShell.SendKeys('%')
    $activationShell.AppActivate($appProcess.Id) | Out-Null
    [HmiNative]::SetForegroundWindow([IntPtr]$appProcess.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 600
    [HmiNative]::GetWindowThreadProcessId([HmiNative]::GetForegroundWindow(), [ref]$foregroundProcessId) | Out-Null
}
if ($needsForeground -and $foregroundProcessId -ne $appProcess.Id) {
    [uint32]$focusPid = 0
    $focusThread = [HmiNative]::GetWindowThreadProcessId([HmiNative]::GetForegroundWindow(), [ref]$focusPid)
    $ourThread = [HmiNative]::GetCurrentThreadId()
    [HmiNative]::AttachThreadInput($ourThread, $focusThread, $true) | Out-Null
    try { [HmiNative]::BringWindowToTop([IntPtr]$appProcess.MainWindowHandle) | Out-Null; [HmiNative]::SetForegroundWindow([IntPtr]$appProcess.MainWindowHandle) | Out-Null } finally { [HmiNative]::AttachThreadInput($ourThread, $focusThread, $false) | Out-Null }
    Start-Sleep -Milliseconds 300
    [HmiNative]::GetWindowThreadProcessId([HmiNative]::GetForegroundWindow(), [ref]$foregroundProcessId) | Out-Null
}
if ($needsForeground -and $foregroundProcessId -ne $appProcess.Id) { throw 'Focus is outside TIA Portal; refusing input.' }
if ($Action -eq 'keys') { [System.Windows.Forms.SendKeys]::SendWait($Text); exit }
if ($Action -eq 'paste') {
    [System.Windows.Forms.Clipboard]::SetText($Text)
    [System.Windows.Forms.SendKeys]::SendWait('^v')
    exit
}
if ($Action -eq 'scroll') {
    [HmiNative]::SetCursorPos($X, $Y) | Out-Null
    1..([int]$Text) | ForEach-Object { [HmiNative]::mouse_event(2048, 0, 0, 4294967176, [UIntPtr]::Zero) }
    Start-Sleep -Milliseconds 350
    exit
}
if ($Action -eq 'click' -or $Action -eq 'rightclick' -or $Action -eq 'doubleclick' -or $Action -eq 'drag') {
    [HmiNative]::SetCursorPos($X, $Y) | Out-Null
    if ($Action -eq 'rightclick') { $down = 8; $up = 16 } else { $down = 2; $up = 4 }
    [HmiNative]::mouse_event($down, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 100
    if ($Action -eq 'drag') {
        Start-Sleep -Milliseconds 100
        [HmiNative]::SetCursorPos($X2, $Y2) | Out-Null
        Start-Sleep -Milliseconds 200
    }
    [HmiNative]::mouse_event($up, 0, 0, 0, [UIntPtr]::Zero)
    if ($Action -eq 'doubleclick') { Start-Sleep -Milliseconds 80; [HmiNative]::mouse_event($down, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 80; [HmiNative]::mouse_event($up, 0, 0, 0, [UIntPtr]::Zero) }
    Start-Sleep -Milliseconds 1000
    exit
}
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $Name)
$element = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
if (-not $element) { throw "Element not found: $Name" }
switch ($Action) {
 'close_window' { $root.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern).Close() }
 'maximize' { $root.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern).SetWindowVisualState([System.Windows.Automation.WindowVisualState]::Maximized) }
 'invoke' { $element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }
 'select' { $element.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select() }
 'expand' { $element.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand() }
 'value' { $element.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($Text) }
 'focus' { $element.SetFocus() }
}
