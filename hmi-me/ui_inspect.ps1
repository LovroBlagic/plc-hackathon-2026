param([int]$ProcessId = 0)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
if ($ProcessId -eq 0) {
    $appProcess = Get-Process LogicBuilder | Sort-Object StartTime -Descending | Select-Object -First 1
    $ProcessId = $appProcess.Id
}
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcessId)
$windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
foreach ($window in $windows) {
    "WINDOW: $($window.Current.Name)"
    $elements = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($element in $elements) {
        $c = $element.Current
        if ($c.IsOffscreen -or -not $c.Name) { continue }
        "{0} | {1} | id={2} | rect={3}" -f $c.ControlType.ProgrammaticName, $c.Name, $c.AutomationId, $c.BoundingRectangle
    }
}
