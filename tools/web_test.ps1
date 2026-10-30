# 웹 탭 시험 (앱 바깥에서 실행): 로봇처럼 watch → send → (답 기다림) → 대화 파일·보낸 결과 확인 → unwatch·파일 지움
param([long]$Tab, [string]$TextB64, [int]$AnswerWait = 20, [string]$Out = "$PSScriptRoot\..\dist\realcheck_webtest.txt")
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
$cmdFile = Join-Path $dir "web-cmd.jsonl"
$chat = Join-Path $dir "web-chat\brave-$Tab.json"
$utf8 = New-Object Text.UTF8Encoding $false
function Cmd($obj) { [IO.File]::AppendAllText($cmdFile, ($obj | ConvertTo-Json -Compress) + "`n", $utf8) }
function ChatInfo($tag) {
    if (-not (Test-Path $chat)) { return "[$tag] 대화 파일 없음" }
    $j = Get-Content $chat -Raw -Encoding utf8 | ConvertFrom-Json
    $s = "[$tag] 대화 파일: working=$($j.working) 메시지 $(@($j.msgs).Count)개"
    foreach ($m in @($j.msgs) | Select-Object -Last 2) { $t = [string]$m[1]; $s += " | $($m[0]): $($t.Substring(0, [Math]::Min(30, $t.Length)) -replace "`n", ' / ')" }
    return $s
}
$lines = @("웹 시험 탭 $Tab $(Get-Date -Format 'HH:mm:ss')")
$evBefore = (Get-Item (Join-Path $dir "events.jsonl")).Length
Cmd ([ordered]@{ cmd = "watch"; tab = $Tab; browser = "brave" })
Start-Sleep -Seconds 3
$lines += ChatInfo "펼친 직후"
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextB64))
Cmd ([ordered]@{ cmd = "send"; tab = $Tab; browser = "brave"; text = $text; id = 1 })
Start-Sleep -Seconds 6
$lines += ChatInfo "보낸 뒤 6초"
Start-Sleep -Seconds $AnswerWait
$lines += ChatInfo "답 기다린 뒤"
# 이 시험 동안 새로 붙은 웹 신호 (보낸 결과·답하는 중·끝)
$fs = [IO.File]::Open((Join-Path $dir "events.jsonl"), 'Open', 'Read', 'ReadWrite')
$fs.Seek($evBefore, 'Begin') | Out-Null
$new = (New-Object IO.StreamReader($fs, $utf8)).ReadToEnd(); $fs.Close()
$lines += ($new -split "`n" | Where-Object { $_ -match '"ev":"web"' -and $_ -match "`"tab`":$Tab" } | ForEach-Object { $x = $_ -replace '"browser_path":"[^"]*",', ''; $x.Substring(0, [Math]::Min(200, $x.Length)) })
Cmd ([ordered]@{ cmd = "unwatch"; tab = $Tab; browser = "brave" })
Start-Sleep -Seconds 1
Remove-Item $chat -ErrorAction SilentlyContinue
$lines += "정리: unwatch·대화 파일 지움 (남음: $(Test-Path $chat))"
$lines | Set-Content -Path $Out -Encoding utf8
