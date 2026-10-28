# dist\TaskPet.exe(설치 프로그램)를 실제로 돌려 설치가 제대로 됐는지 살피기 (앱 바깥 PowerShell 에서 실행)
#   설치 → '완료' 상자가 뜨면 확인을 눌러 닫고 → 임시 폴더가 지워졌는지, 설치 폴더·등록·시작 프로그램이 맞는지
param([string]$Out = "$PSScriptRoot\..\dist\realcheck_install.txt")

$setup = (Resolve-Path "$PSScriptRoot\..\dist\TaskPet.exe").Path
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
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
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr p, IntPtr after, string cls, string title);
    public static IntPtr Find(string title, string cls) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, p) => {
            if (!IsWindowVisible(h)) return true;
            var t = new StringBuilder(64); var c = new StringBuilder(64);
            GetWindowText(h, t, 64); GetClassName(h, c, 64);
            if (t.ToString() == title && c.ToString() == cls) { found = h; return false; }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@

$lines = @("설치 확인 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $setup  $((Get-Item $setup).Length) bytes")
$before = @(Get-ChildItem $env:TEMP -Directory -Filter "TaskPet-setup-*" | ForEach-Object Name)
$sw = [Diagnostics.Stopwatch]::StartNew()
Start-Process $setup
$box = [IntPtr]::Zero
while ($box -eq [IntPtr]::Zero -and $sw.ElapsedMilliseconds -lt 90000) {
    Start-Sleep -Milliseconds 50
    $box = [W]::Find("TaskPet", "#32770")
}
$lines += "완료 상자: $(if ($box -ne [IntPtr]::Zero) { "$($sw.ElapsedMilliseconds) ms 에 뜸" } else { '안 뜸(90초)' })"
$lines += "로봇 창 보임: $([W]::Find('TaskPet', 'TkTopLevel') -ne [IntPtr]::Zero)"
$new = @(Get-ChildItem $env:TEMP -Directory -Filter "TaskPet-setup-*" | Where-Object { $before -notcontains $_.Name })
$lines += "새 임시 폴더: $(($new | ForEach-Object Name) -join ', ')"
Start-Sleep -Seconds 2
if ($box -ne [IntPtr]::Zero) {   # 상자의 '확인' 버튼 누르기(BM_CLICK)
    [W]::PostMessage([W]::FindWindowEx($box, [IntPtr]::Zero, "Button", $null), 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
}
$sw3 = [Diagnostics.Stopwatch]::StartNew()
while ((Get-Process TaskPet -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $setup }) -and $sw3.ElapsedMilliseconds -lt 30000) { Start-Sleep -Milliseconds 100 }
$lines += "확인 누른 뒤 설치 파일이 끝나기까지: $($sw3.ElapsedMilliseconds) ms"
foreach ($d in $new) { $lines += "  $($d.Name) 남아 있음: $(Test-Path $d.FullName)" }
$lines += "남은 setup 폴더 수: $(@(Get-ChildItem $env:TEMP -Directory -Filter 'TaskPet-setup-*').Count)"

$lines += "--- 설치 폴더 맨 위"
Get-ChildItem $dir | Sort-Object Name | ForEach-Object {
    $lines += "  $($_.Name)  $(if ($_.PSIsContainer) { '<폴더> ' + @(Get-ChildItem $_.FullName -Recurse -File).Count + '개' } else { $_.Length })"
}
$lines += ".old 파일: $(@(Get-ChildItem $dir -Recurse -Filter '*.old').Count)"
$reg = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\TaskPet'
$lines += "등록: 버전 $($reg.DisplayVersion) / 지우기 $($reg.UninstallString)"
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) "TaskPet.lnk"
if (Test-Path $lnk) { $lines += "시작 프로그램: $((New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath)" } else { $lines += "시작 프로그램 바로가기 없음" }
$lines += "실행 중: " + ((Get-CimInstance Win32_Process -Filter "Name like 'taskpet%'" | ForEach-Object { "$($_.Name)($($_.ProcessId)) $($_.ExecutablePath)" }) -join " | ")
$err = Join-Path $dir "error.log"
if (Test-Path $err) { $lines += "--- error.log 끝"; $lines += Get-Content $err -Tail 8 -Encoding utf8 }
$lines | Set-Content -Path $Out -Encoding utf8
