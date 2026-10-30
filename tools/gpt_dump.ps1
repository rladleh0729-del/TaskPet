# ChatGPT 앱이 답하는 동안의 화면 구조를 적는다 (작업 중 표시 찾기용, 대화 글은 안 적음 — 이름은 앞 12자만)
param([Parameter(Mandatory = $true)][string]$Title, [string]$Out = "$PSScriptRoot\..\dist\realcheck_gptdump.txt")
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]; $TS = [System.Windows.Automation.TreeScope]
$p = Get-Process | Where-Object { $_.ProcessName -match 'chatgpt' -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
$win = $A::FromHandle($p.MainWindowHandle)
$lines = @("덤프 $(Get-Date -Format 'HH:mm:ss.fff')")
$cut = { param($s) if ($s.Length -gt 12) { $s.Substring(0, 12) + "…" } else { $s } }
# 1) 사이드바의 그 대화 줄과 주변
$link = $win.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.AndCondition((New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::Hyperlink)), (New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, $Title)))))
if ($link) {
    $lines += "줄: cls=$($link.Current.ClassName)"
    $w = [System.Windows.Automation.TreeWalker]::RawViewWalker
    $par = $w.GetParent($link)
    $lines += "부모: $($par.Current.ControlType.ProgrammaticName) cls=$($par.Current.ClassName) name=[$(& $cut $par.Current.Name)]"
    foreach ($e in @($link) + @($par.FindAll($TS::Descendants, [System.Windows.Automation.Condition]::TrueCondition))) {
        $lines += "  · $($e.Current.ControlType.ProgrammaticName -replace 'ControlType.','') id=$($e.Current.AutomationId) cls=$($e.Current.ClassName) name=[$(& $cut $e.Current.Name)]"
    }
} else { $lines += "줄 못 찾음" }
# 2) 상태 표시(StatusBar)·진행(ProgressBar) 전부
foreach ($t in [System.Windows.Automation.ControlType]::StatusBar, [System.Windows.Automation.ControlType]::ProgressBar) {
    foreach ($e in $win.FindAll($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, $t)))) {
        $lines += "$($t.ProgrammaticName): id=$($e.Current.AutomationId) cls=$($e.Current.ClassName) name=[$(& $cut $e.Current.Name)]"
    }
}
# 3) 버튼 이름 (중지 버튼 찾기)
$names = $win.FindAll($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button))) | ForEach-Object { $n = $_.Current.Name; if ($n -match '중지|stop|Stop|정지') { "[중지?] $n id=$($_.Current.AutomationId) cls=$($_.Current.ClassName)" } }
$lines += $names
# 4) main 마지막 자식들
$main = $win.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::AutomationIdProperty, "main")))
if ($main) {
    $kids = $main.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)
    for ($i = [Math]::Max(0, $kids.Count - 6); $i -lt $kids.Count; $i++) { $c = $kids[$i].Current; $lines += "main[$i] $($c.ControlType.ProgrammaticName -replace 'ControlType.','') cls=$($c.ClassName) name=[$(& $cut $c.Name)]" }
}
$lines | Set-Content -Path $Out -Encoding utf8
