# 로봇 → 브라우저 확장 명령을 설치 폴더 web-cmd.jsonl 에 한 줄 적는다 (로봇이 하는 일 흉내, 시험용 — 앱 바깥에서 실행)
#   -Json 은 base64(UTF-8) 로 넘긴다 (따옴표가 깨지지 않게). 결과로 web-chat 폴더·최근 신호를 -Out 에 적는다
param([string]$JsonB64, [string]$Out = "$PSScriptRoot\..\dist\realcheck_webcmd.txt", [int]$Wait = 3)
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
if ($JsonB64) {
    $line = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($JsonB64))
    [IO.File]::AppendAllText((Join-Path $dir "web-cmd.jsonl"), $line + "`n", (New-Object Text.UTF8Encoding $false))
}
Start-Sleep -Seconds $Wait
$lines = @("명령 $(Get-Date -Format 'HH:mm:ss'): $line")
$wc = Join-Path $dir "web-chat"
if (Test-Path $wc) {
    foreach ($f in Get-ChildItem $wc -File) {
        $lines += "파일 $($f.Name) $($f.Length) bytes $($f.LastWriteTime.ToString('HH:mm:ss'))"
        try { $j = Get-Content $f.FullName -Raw -Encoding utf8 | ConvertFrom-Json; $lines += "  working=$($j.working) 메시지 $(@($j.msgs).Count)개 title=$($j.title)"; foreach ($m in @($j.msgs) | Select-Object -Last 3) { $t = [string]$m[1]; $lines += "    $($m[0]): $($t.Substring(0, [Math]::Min(40, $t.Length)))" } } catch {}
    }
} else { $lines += "web-chat 폴더 없음" }
$lines += "--- 최근 웹 신호"
$lines += Get-Content (Join-Path $dir "events.jsonl") -Tail 30 -Encoding utf8 | Where-Object { $_ -match '"ev":"web"' } | Select-Object -Last 5 | ForEach-Object { $_.Substring(0, [Math]::Min(220, $_.Length)) }
$lines | Set-Content -Path $Out -Encoding utf8
