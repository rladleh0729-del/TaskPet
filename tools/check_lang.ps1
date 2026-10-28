# 설치된 로봇에서 실제 메뉴로 언어를 바꿔 보고(우클릭 → 설정 → 언어 · Language → 고르기),
# 로봇이 다시 떠서 그 언어로 보이는지 화면을 찍어 둔다.
# 키 입력은 전체 화면이 아니라 로봇의 메뉴 창에만 보낸다(PostMessage) — 다른 창에 글자가 들어가지 않게.
# 메뉴 항목은 메뉴 메시지(MN_GETHMENU)로 읽어서, 고를 칸이 정말 선택됐는지 확인한 뒤에만 Enter.
#   powershell -File tools\check_lang.ps1 -Langs "日本語","简体中文","English","auto"   (auto = 맨 위 '자동(Windows 설정)')
param([string[]]$Langs = @("日本語", "简体中文", "English", "auto"),
      [string]$OutDir = "$PSScriptRoot\..\dist")

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class M {
  public struct RECT { public int L, T, R, B; }
  delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr w, EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetMenuString(IntPtr m, uint i, StringBuilder s, int n, uint f);
  [DllImport("user32.dll")] static extern uint GetMenuState(IntPtr m, uint i, uint f);
  static List<IntPtr> Wins(uint pid, string cls) { var r = new List<IntPtr>();
    EnumWindows((h,p)=>{ uint q; GetWindowThreadProcessId(h, out q); var c=new StringBuilder(64); GetClassName(h,c,64);
      if (q==pid && IsWindowVisible(h) && c.ToString()==cls) r.Add(h); return true; }, IntPtr.Zero); return r; }
  public static List<IntPtr> Menus(uint pid) { return Wins(pid, "#32768"); }
  public static List<IntPtr> Tops(uint pid) { return Wins(pid, "TkTopLevel"); }
  public static IntPtr Inner(IntPtr top) { IntPtr last = top;
    EnumChildWindows(top, (h,p)=>{ last = h; return true; }, IntPtr.Zero); return last; }
  public static IntPtr HMenu(IntPtr w) { return SendMessage(w, 0x01E1, IntPtr.Zero, IntPtr.Zero); }
  public static string[] Names(IntPtr w) { IntPtr m = HMenu(w); int n = GetMenuItemCount(m); var r = new string[Math.Max(n,0)];
    for (int i=0;i<n;i++){ var s=new StringBuilder(256); GetMenuString(m,(uint)i,s,256,0x400); r[i]=s.ToString(); } return r; }
  public static int Hilite(IntPtr w) { IntPtr m = HMenu(w); int n = GetMenuItemCount(m);
    for (int i=0;i<n;i++) if ((GetMenuState(m,(uint)i,0x400) & 0x80) != 0) return i; return -1; }
  public static bool HasSub(IntPtr w, int i) { return (GetMenuState(HMenu(w),(uint)i,0x400) & 0x10) != 0; }
  public static void Key(IntPtr w, int vk) { PostMessage(w, 0x100, (IntPtr)vk, IntPtr.Zero); PostMessage(w, 0x101, (IntPtr)vk, IntPtr.Zero); }
}
"@
$dir = Join-Path $env:LOCALAPPDATA "TaskPet"
$exe = Join-Path $dir "TaskPet.exe"
$lines = @("언어 바꾸기 확인 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")

function Robot { Get-CimInstance Win32_Process -Filter "Name='TaskPet.exe'" | Where-Object { $_.ExecutablePath -eq $exe } | Select-Object -First 1 }
function WaitFor([scriptblock]$cond, [int]$ms) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $ms) { $v = & $cond; if ($v) { return $v }; Start-Sleep -Milliseconds 100 }
    return $null
}
function NewMenu($procId, $known) { WaitFor { [M]::Menus([uint32]$procId) | Where-Object { $known -notcontains $_ } | Select-Object -First 1 } 3000 }
# 메뉴 창 w 에서 index 칸이 선택될 때까지 ↓ (최대 20번)
function MoveTo($w, [int]$index) {
    for ($k = 0; $k -lt 20; $k++) {
        if ([M]::Hilite($w) -eq $index) { return $true }
        [M]::Key($w, 0x28); Start-Sleep -Milliseconds 120
    }
    return ([M]::Hilite($w) -eq $index)
}
function Close-Menus($procId) { foreach ($i in 1..4) { $m = [M]::Menus([uint32]$procId) | Select-Object -Last 1; if ($m) { [M]::Key($m, 0x1B); Start-Sleep -Milliseconds 150 } } }
function Shot($procId, $name, $hwnds) {
    $rs = foreach ($h in $hwnds) { $r = New-Object M+RECT; [void][M]::GetWindowRect($h, [ref]$r); $r }
    if (-not $rs) { return "창 없음" }
    $l = [int](($rs | ForEach-Object L | Measure-Object -Minimum).Minimum) - 8
    $t = [int](($rs | ForEach-Object T | Measure-Object -Minimum).Minimum) - 8
    $w = [int](($rs | ForEach-Object R | Measure-Object -Maximum).Maximum) + 8 - $l
    $h = [int](($rs | ForEach-Object B | Measure-Object -Maximum).Maximum) + 8 - $t
    $bmp = New-Object Drawing.Bitmap $w, $h
    [Drawing.Graphics]::FromImage($bmp).CopyFromScreen($l, $t, 0, 0, $bmp.Size)
    $path = Join-Path $OutDir "realcheck_lang_$name.png"; $bmp.Save($path); return $path
}

$n = 0
foreach ($want in $Langs) {
    $n++
    $p = Robot
    if (-not $p) { $lines += "[$want] 로봇이 안 떠 있음"; break }
    $procId = $p.ProcessId
    # 로봇 창(두 창 중 작은 쪽) 그림 칸에 우클릭 신호
    $robot = [M]::Tops([uint32]$procId) | Sort-Object { $r = New-Object M+RECT; [void][M]::GetWindowRect($_, [ref]$r); ($r.R - $r.L) * ($r.B - $r.T) } | Select-Object -First 1
    $inner = [M]::Inner($robot)
    $lp = [IntPtr]((40 -shl 16) -bor 40)
    [void][M]::PostMessage($inner, 0x0204, [IntPtr]2, $lp)
    [void][M]::PostMessage($inner, 0x0205, [IntPtr]0, $lp)
    $main = NewMenu $procId @()
    if (-not $main) { $lines += "[$want] 메뉴가 안 뜸"; continue }
    $names = [M]::Names($main)
    $lines += "[$want] 메뉴: " + ($names -join " | ")
    $si = (0..($names.Count - 1) | Where-Object { [M]::HasSub($main, $_) } | Select-Object -First 1)   # 하위 메뉴가 있는 첫 칸 = 설정
    if ($null -eq $si -or -not (MoveTo $main $si)) { $lines += "[$want] 설정 칸으로 못 감"; Close-Menus $procId; continue }
    [M]::Key($main, 0x27)                                          # → 펼치기
    $sm = NewMenu $procId @($main)
    if (-not $sm) { $lines += "[$want] 설정 하위 메뉴가 안 뜸"; Close-Menus $procId; continue }
    $snames = [M]::Names($sm)
    $li = (0..($snames.Count - 1) | Where-Object { $snames[$_] -like "*Language*" } | Select-Object -First 1)
    if ($null -eq $li -or -not (MoveTo $sm $li)) { $lines += "[$want] 언어 칸으로 못 감: " + ($snames -join " | "); Close-Menus $procId; continue }
    [M]::Key($sm, 0x27)
    $lm = NewMenu $procId @($main, $sm)
    if (-not $lm) { $lines += "[$want] 언어 메뉴가 안 뜸"; Close-Menus $procId; continue }
    $lnames = [M]::Names($lm)
    $lines += "[$want] 언어 메뉴: " + ($lnames -join " | ")
    $ti = if ($want -eq "auto") { 0 } else { (0..($lnames.Count - 1) | Where-Object { $lnames[$_] -like "*$want*" } | Select-Object -First 1) }
    if ($null -eq $ti -or -not (MoveTo $lm $ti)) { $lines += "[$want] 고를 칸으로 못 감"; Close-Menus $procId; continue }
    Start-Sleep -Milliseconds 300
    $lines += "[$want] 메뉴 화면: " + (Shot $procId "menu_$n" @($main, $sm, $lm))
    $old = $procId
    $sw = [Diagnostics.Stopwatch]::StartNew()
    [M]::Key($lm, 0x0D)                                            # Enter (선택 확인된 칸)
    $new = WaitFor { $q = Robot; if ($q -and $q.ProcessId -ne $old -and [M]::Tops([uint32]$q.ProcessId).Count -ge 1) { $q } } 15000
    if (-not $new) { $lines += "[$want] 새 로봇이 안 뜸 (옛 로봇 살아 있음: $([bool](Get-Process -Id $old -ErrorAction SilentlyContinue)))"; continue }
    $lines += "[$want] 다시 뜨기까지 $($sw.ElapsedMilliseconds) ms, 옛 로봇 꺼짐: $(-not (Get-Process -Id $old -ErrorAction SilentlyContinue))"
    Start-Sleep -Seconds 3
    $lines += "[$want] settings.json: " + ((Get-Content (Join-Path $dir "settings.json") -Raw -Encoding utf8) -replace "\s+", " ")
    $lines += "[$want] 감시 프로그램 수: " + @(Get-Process taskpet-chatgpt -ErrorAction SilentlyContinue).Count
    $lines += "[$want] 로봇 화면: " + (Shot $new.ProcessId "robot_$n" ([M]::Tops([uint32]$new.ProcessId)))
}
$lines | Set-Content -Path (Join-Path $OutDir "realcheck_lang.txt") -Encoding utf8
