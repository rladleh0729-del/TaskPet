# Claude 데스크톱 앱(MSIX) 가상 공간에 남은 옛 TaskPet 도우미를 설치 폴더의 새 것으로 덮어쓴다 (앱 바깥에서 실행).
# 설치 프로그램(1.8.0~)이 하는 일과 같음 — 이미 설치된 PC 를 바로 고칠 때 쓴다.
param([string]$Out = "$PSScriptRoot\..\dist\realcheck_pkghook.txt")
$lines = @()
foreach ($d in Get-ChildItem (Join-Path $env:LOCALAPPDATA "Packages\*\LocalCache\Local\TaskPet") -Directory -ErrorAction SilentlyContinue) {
    foreach ($n in "taskpet-hook.exe", "taskpet-chatgpt.exe", "taskpet-native.exe", "taskpet-term.exe") {
        $t = Join-Path $d.FullName $n
        if (-not (Test-Path $t)) { continue }
        $s = Join-Path $env:LOCALAPPDATA "TaskPet\$n"
        try { Copy-Item $s $t -Force -ErrorAction Stop; $lines += "$n 덮어씀 ($((Get-Item $t).Length) bytes) — $($d.FullName)" }
        catch {
            try { Rename-Item $t "$n.$([DateTimeOffset]::Now.ToUnixTimeSeconds()).old" -Force -ErrorAction Stop; Copy-Item $s $t -Force; $lines += "$n 비켜 두고 덮어씀" }
            catch { $lines += "$n 실패: $($_.Exception.Message)" }
        }
    }
}
if (-not $lines) { $lines = @("남은 옛 사본 없음") }
$lines | Set-Content -Path $Out -Encoding utf8
