# 설치된 TaskPet 이 켜지는 데 걸리는 시간 재기 (앱 바깥 PowerShell 에서 실행)
#   1) 켜져 있는 로봇을 끄고 → 다시 켜서 로봇 창이 화면에 보일 때까지
#   2) 이미 켜져 있을 때 하나 더 켜면 바로 끝나기까지 (= 프로그램이 뜨는 데만 드는 시간)
# 결과는 -Out 파일에 적는다.
param([string]$Out = "$PSScriptRoot\..\dist\realcheck_start.txt", [int]$Runs = 3)

$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
$exe = Join-Path $dir "TaskPet.exe"
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class W {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    public static bool RobotVisible() {
        bool found = false;
        EnumWindows((h, p) => {
            if (!IsWindowVisible(h)) return true;
            var t = new StringBuilder(64); var c = new StringBuilder(64);
            GetWindowText(h, t, 64); GetClassName(h, c, 64);
            if (t.ToString() == "TaskPet" && c.ToString() == "TkTopLevel") { found = true; return false; }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@

function Stop-Robot {
    $flag = Join-Path $dir "quit.flag"
    New-Item $flag -ItemType File -Force | Out-Null
    for ($i = 0; $i -lt 100 -and [W]::RobotVisible(); $i++) { Start-Sleep -Milliseconds 50 }
    Start-Sleep -Milliseconds 800
    Remove-Item $flag -ErrorAction SilentlyContinue
}

$lines = @("측정 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $exe  $((Get-Item $exe).Length) bytes  버전 $((Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\TaskPet' -ErrorAction SilentlyContinue).DisplayVersion)")
for ($r = 1; $r -le $Runs; $r++) {
    Stop-Robot
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Process $exe -WorkingDirectory $dir
    while (-not [W]::RobotVisible() -and $sw.ElapsedMilliseconds -lt 30000) { Start-Sleep -Milliseconds 10 }
    $show = $sw.ElapsedMilliseconds
    Start-Sleep -Seconds 3
    $sw2 = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process $exe -WorkingDirectory $dir -PassThru
    $p.WaitForExit(30000) | Out-Null
    $lines += "회차 $r : 로봇 보이기까지 $show ms / 두 번째 실행이 끝나기까지 $($sw2.ElapsedMilliseconds) ms"
}
$lines += "chatgpt 감시 프로그램: " + ((Get-Process taskpet-chatgpt -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Id) $([math]::Round($_.WorkingSet64/1MB))MB" }) -join ", ")
$lines | Set-Content -Path $Out -Encoding utf8
