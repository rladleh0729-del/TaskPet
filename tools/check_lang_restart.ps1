# 설치된 로봇의 언어를 settings.json 으로 바꾸고 'TaskPet.exe --restart' 로 다시 띄워(메뉴에서 고를 때와 같은 다시 켜기),
# 로봇·말풍선 화면을 언어마다 찍는다. 끝나면 원래 settings.json 으로 되돌린다.  (앱 바깥 PowerShell 에서 실행)
param([string[]]$Langs = @("ja", "zh_CN", "zh_TW", "en", "de", "ru"), [string]$OutDir = "$PSScriptRoot\..\dist")

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class W {
  public struct RECT { public int L, T, R, B; }
  delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static List<IntPtr> Tops(uint pid) { var r = new List<IntPtr>();
    EnumWindows((h,p)=>{ uint q; GetWindowThreadProcessId(h, out q); var c=new StringBuilder(64); GetClassName(h,c,64);
      if (q==pid && IsWindowVisible(h) && c.ToString()=="TkTopLevel") r.Add(h); return true; }, IntPtr.Zero); return r; } }
"@
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
$exe = Join-Path $dir "TaskPet.exe"
$set = Join-Path $dir "settings.json"
$utf8 = New-Object Text.UTF8Encoding $false            # BOM 없이 (로봇의 json 읽기가 BOM 을 싫어함)
$orig = [IO.File]::ReadAllText($set, $utf8)
$lines = @("언어별 다시 켜기 확인 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  원래 설정: $($orig -replace '\s+', ' ')")

function Robot { Get-CimInstance Win32_Process -Filter "Name='TaskPet.exe'" | Where-Object { $_.ExecutablePath -eq $exe } | Select-Object -First 1 }
function Stop-Robot {
    $flag = Join-Path $dir "quit.flag"
    [IO.File]::WriteAllText($flag, "")
    for ($i = 0; $i -lt 60 -and (Robot); $i++) { Start-Sleep -Milliseconds 100 }
    Remove-Item $flag -ErrorAction SilentlyContinue
}
function Set-Lang($code) {
    $j = $orig | ConvertFrom-Json
    if ($j.PSObject.Properties.Name -contains "lang") { $j.lang = $code } else { $j | Add-Member lang $code }
    [IO.File]::WriteAllText($set, ($j | ConvertTo-Json -Compress), $utf8)
}
function Shot($procId, $name) {
    $rs = foreach ($h in [W]::Tops([uint32]$procId)) { $r = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$r); $r }
    if (-not $rs) { return "창 없음" }
    $l = [int](($rs | ForEach-Object L | Measure-Object -Minimum).Minimum) - 8
    $t = [int](($rs | ForEach-Object T | Measure-Object -Minimum).Minimum) - 8
    $w = [int](($rs | ForEach-Object R | Measure-Object -Maximum).Maximum) + 8 - $l
    $h = [int](($rs | ForEach-Object B | Measure-Object -Maximum).Maximum) + 8 - $t
    $bmp = New-Object Drawing.Bitmap $w, $h
    [Drawing.Graphics]::FromImage($bmp).CopyFromScreen($l, $t, 0, 0, $bmp.Size)
    $path = Join-Path $OutDir "realcheck_lang_$name.png"; $bmp.Save($path); return "$path (창 $($rs.Count)개)"
}

try {
    foreach ($code in $Langs) {
        Stop-Robot
        Set-Lang $code
        $sw = [Diagnostics.Stopwatch]::StartNew()
        Start-Process $exe -ArgumentList "--restart" -WorkingDirectory $dir
        $p = $null
        while ($sw.ElapsedMilliseconds -lt 15000) { $p = Robot; if ($p -and [W]::Tops([uint32]$p.ProcessId).Count) { break }; Start-Sleep -Milliseconds 50 }
        $show = $sw.ElapsedMilliseconds
        Start-Sleep -Seconds 4
        $lines += "[$code] 로봇 보이기까지 $show ms / 감시 프로그램 $(@(Get-Process taskpet-chatgpt -ErrorAction SilentlyContinue).Count)개 / " + (Shot $p.ProcessId $code)
    }
}
finally {
    Stop-Robot
    [IO.File]::WriteAllText($set, $orig, $utf8)             # 원래 설정으로
    Start-Process $exe -WorkingDirectory $dir
    Start-Sleep -Seconds 3
    $p = Robot
    $lines += "되돌림: 설정 $(([IO.File]::ReadAllText($set, $utf8)) -replace '\s+', ' ') / 로봇 $(if ($p) { $p.ProcessId } else { '없음' })"
    $lines | Set-Content -Path (Join-Path $OutDir "realcheck_lang.txt") -Encoding utf8
}
