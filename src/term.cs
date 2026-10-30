// TaskPet 터미널 도우미: 터미널(Windows Terminal·명령 프롬프트·VS Code 터미널 등)에서 돌아가는
// Claude Code 에 로봇에서 쓴 답을 넣거나, 그 터미널 창을 앞으로 가져온다.
//   taskpet-term.exe send  <pid> <시작시각 ms> <글 base64(UTF-8)>   → 그 콘솔 입력에 글자 + Enter
//   taskpet-term.exe focus <pid> <시작시각 ms>                        → 그 터미널 창을 앞으로
// 결과는 표준 출력 한 줄: ok / gone(그 Claude Code 가 꺼짐) / no_console / error
// 같은 번호를 다른 프로그램이 다시 쓰고 있을 수 있어서, 훅이 적어 둔 시작 시각이 맞을 때만 한다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

static class Term
{
    [StructLayout(LayoutKind.Explicit, CharSet = CharSet.Unicode)]
    struct INPUT_RECORD
    {
        [FieldOffset(0)] public ushort EventType;
        [FieldOffset(4)] public int bKeyDown;
        [FieldOffset(8)] public ushort wRepeatCount;
        [FieldOffset(10)] public ushort wVirtualKeyCode;
        [FieldOffset(12)] public ushort wVirtualScanCode;
        [FieldOffset(14)] public char UnicodeChar;
        [FieldOffset(16)] public uint dwControlKeyState;
    }

    [DllImport("kernel32.dll")] static extern bool FreeConsole();
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AttachConsole(uint pid);
    [DllImport("kernel32.dll")] static extern IntPtr GetConsoleWindow();
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr tmpl);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool WriteConsoleInputW(IntPtr h, INPUT_RECORD[] recs, uint n, out uint written);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);

    static int Main(string[] args)
    {
        string r;
        try { r = Run(args); }
        catch (Exception) { r = "error"; }
        Console.Out.WriteLine(r);
        return r == "ok" ? 0 : 1;
    }

    static string Run(string[] args)
    {
        if (args.Length < 3) return "error";
        uint pid = uint.Parse(args[1]);
        long start = long.Parse(args[2]);
        // 같은 프로그램인지: 훅이 적은 시작 시각과 2초 안에서 맞아야 함
        try
        {
            var p = Process.GetProcessById((int)pid);
            long st = (long)(p.StartTime.ToUniversalTime() - new DateTime(1970, 1, 1)).TotalMilliseconds;
            if (Math.Abs(st - start) > 2000) return "gone";
        }
        catch (Exception) { return "gone"; }

        var stdout = Console.Out;               // (콘솔을 바꾸기 전에 붙잡아 둠 — 결과를 로봇에게 돌려줄 통로)
        FreeConsole();
        if (!AttachConsole(pid)) return "no_console";
        try
        {
            if (args[0] == "focus") return Focus();
            if (args[0] != "send" || args.Length < 4) return "error";
            string text = Encoding.UTF8.GetString(Convert.FromBase64String(args[3]));
            return Send(text);
        }
        finally { FreeConsole(); }
    }

    static string Send(string text)
    {
        // 터미널 입력은 한 줄 — 여러 줄은 띄어쓰기로 잇는다 (줄바꿈이 Enter 로 들어가 반만 보내지는 일이 없게)
        text = text.Replace("\r\n", "\n").Replace('\r', '\n').Replace('\n', ' ').Trim();
        if (text.Length == 0) return "error";
        IntPtr h = CreateFileW("CONIN$", 0xC0000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);   // 읽기·쓰기, 공유
        if (h == new IntPtr(-1)) return "no_console";
        try
        {
            var recs = new List<INPUT_RECORD>();
            foreach (char c in text)
            {
                recs.Add(Key(c, 0, true));
                recs.Add(Key(c, 0, false));
            }
            uint n;
            if (!WriteConsoleInputW(h, recs.ToArray(), (uint)recs.Count, out n)) return "error";
            // 글자가 다 들어간 뒤 Enter 를 따로 (한꺼번에 보내면 붙여 넣기로 여겨 Enter 가 줄바꿈이 될 수 있음)
            Thread.Sleep(400);
            var enter = new[] { Key('\r', 0x0D, true, 0x1C), Key('\r', 0x0D, false, 0x1C) };
            if (!WriteConsoleInputW(h, enter, 2, out n)) return "error";
            return "ok";
        }
        finally { CloseHandle(h); }
    }

    static INPUT_RECORD Key(char c, ushort vk, bool down, ushort scan = 0)
    {
        var r = new INPUT_RECORD();
        r.EventType = 1;                      // KEY_EVENT
        r.bKeyDown = down ? 1 : 0;
        r.wRepeatCount = 1;
        r.wVirtualKeyCode = vk;
        r.wVirtualScanCode = scan;
        r.UnicodeChar = c;
        return r;
    }

    static string Focus()
    {
        IntPtr w = GetConsoleWindow();
        if (w == IntPtr.Zero) return "no_console";
        // Windows Terminal·VS Code 아래에서는 보이지 않는 대리 창이라, 그 주인(진짜 터미널 창)을 앞으로
        IntPtr top = GetAncestor(w, 3);       // GA_ROOTOWNER
        if (top == IntPtr.Zero) top = w;
        if (IsIconic(top)) ShowWindow(top, 9);   // SW_RESTORE
        else if (!IsWindowVisible(top)) ShowWindow(top, 5);
        return SetForegroundWindow(top) ? "ok" : "ok";
    }
}
