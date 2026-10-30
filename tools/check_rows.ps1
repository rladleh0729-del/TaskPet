# 설치된 로봇이 기억하는 줄(state.json)과 최근 신호를 앱 바깥에서 보여 준다 — 터미널·웹 줄 확인용
param([string]$Out = "$PSScriptRoot\..\dist\realcheck_rows.txt", [int]$Tail = 4)
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
$lines = @("줄 확인 $(Get-Date -Format 'HH:mm:ss')")
$st = Get-Content (Join-Path $dir "state.json") -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($pr in $st.tasks.PSObject.Properties) {
    $e = $pr.Value
    $lines += "줄 $($pr.Name) src=$($e.src) entry=$($e.entry) cc_pid=$($e.cc_pid) tab=$($e.tab) status=$($e.status) sending=$($e.sending) title=$($e.title)"
}
foreach ($f in @((Join-Path $dir "events.jsonl")) + @(Get-ChildItem (Join-Path $env:LOCALAPPDATA "Packages\*\LocalCache\Local\TaskPet\events.jsonl") -ErrorAction SilentlyContinue | ForEach-Object FullName)) {
    $lines += "--- $f"
    $lines += Get-Content $f -Tail $Tail -Encoding utf8 | ForEach-Object { $x = $_ -replace '"prompt":"[^"]*"', '"prompt":"…"'; $x.Substring(0, [Math]::Min(170, $x.Length)) }
}
$wc = Join-Path $dir "web-chat"
if (Test-Path $wc) { $lines += "--- web-chat: " + ((Get-ChildItem $wc | ForEach-Object { "$($_.Name)($($_.Length))" }) -join ", ") }
$lines | Set-Content -Path $Out -Encoding utf8
