// TaskPet chat watcher: ChatGPT·Claude 데스크톱 앱 창을 화면 읽기(UI Automation)로 읽어,
// 왼쪽 대화 목록에서 '작업 중'(ChatGPT) / '실행 중'(Claude) 표시가 붙은 대화 제목을 2초마다 알려 준다.
// 일반 채팅은 컴퓨터에 기록이 남지 않아서 이 방법으로만 알 수 있다. 창은 읽기만 한다.
//
//   taskpet-chatgpt.exe <TaskPet PID>
//   표준 출력: {"ok":true,"hwnd":1234,"working":["제목",...],
//               "claude_ok":true,"claude_hwnd":5678,"claude":["제목",...]}   (바뀔 때, 그리고 30초마다)
//     ok / claude_ok 가 false 면 그 앱 창이 없거나 채팅 목록이 안 보이는 화면 → 판단을 미룬다
//   표준 입력: open<TAB>제목 / openclaude<TAB>제목   → 그 대화 줄을 눌러 연다 (로봇에서 더블 클릭했을 때만)
//              replyclaude<TAB>세션 제목<TAB>글(base64) → Claude 앱 그 Code 세션에 글을 넣어 보냄 (로봇에서 선택지를 눌렀을 때만)
//              cardclaude<TAB>세션 제목<TAB>선택지(base64)<TAB>기타 글(base64) → 그 세션의 질문 카드에서 골라 제출
//              replyvscode / cardvscode (같은 모양) → VS Code의 Claude Code 패널(제목이 그 세션인 것)에 같은 일
//              gptchat<TAB>대화 제목 → ChatGPT 앱에 지금 열린 대화가 그것이면 최근 메시지를 읽어
//                {"gptchat":{"title":"…","ok":true,"msgs":[["me","…"],["ai","…"]]}} (로봇에서 그 줄을 펼쳐 볼 때만)
//              replygpt<TAB>대화 제목<TAB>글(base64) → ChatGPT 앱 그 대화에 글을 넣어 보냄 → {"reply":"ok"|이유}
//   Claude 창은 앞으로 가져오지 않는다. 다른 창 뒤에 가려져 있으면 그대로 두고 클릭 신호만 창에 보낸다.
//   최소화돼 있으면 앱이 완전히 쉬어서, 처리하는 동안만 눈에 안 보이게(투명·클릭 통과) 되살렸다가 다시 최소화한다.
//   쓰던 창의 포커스와 마우스는 건드리지 않는다. 단계 기록은 이 프로그램 옆 card.log 에 남긴다.
//
//   화면 읽기는 Windows 의 COM 화면 읽기(IUIAutomation)를 직접 쓴다. .NET 의 System.Windows.Automation 은
//   읽을 때마다 윈도우 쪽 메모리가 조금씩 새서(2초마다 읽으면 1분에 약 1.2MB, GC 를 해도 그대로) 하루면 1~2GB 가 됐다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using UIA = Interop.UIAutomationClient;

// 화면 읽기 요소 하나 (COM IUIAutomationElement 를 감싼 것)
class El
{
    public static readonly UIA.IUIAutomation A = new UIA.CUIAutomation8();
    public const UIA.TreeScope Children = UIA.TreeScope.TreeScope_Children;
    public const UIA.TreeScope Descendants = UIA.TreeScope.TreeScope_Descendants;
    public const int Button = 50000, Edit = 50004, Hyperlink = 50005, Image = 50006, RadioButton = 50013,
                     StatusBar = 50017, Text = 50020, Group = 50026, DataItem = 50029, Document = 50030;
    public const int InvokeId = 10000, ValueId = 10002, SelectionItemId = 10010, ToggleId = 10015, ScrollItemId = 10017;
    const int TypeP = 30003, NameP = 30005, ClassP = 30012, RectP = 30001, AutoIdP = 30011;

    // 목록을 훑을 땐 이름·클래스·종류를 한 번에 받아 온다 (요소마다 앱에 따로 묻지 않게)
    static readonly UIA.IUIAutomationCacheRequest Cache = MakeCache();
    static UIA.IUIAutomationCacheRequest MakeCache()
    {
        var c = A.CreateCacheRequest();
        c.AddProperty(TypeP);
        c.AddProperty(NameP);
        c.AddProperty(ClassP);
        c.AddProperty(RectP);
        c.AddProperty(AutoIdP);
        return c;
    }

    public readonly UIA.IUIAutomationElement E;
    readonly bool cached;
    El(UIA.IUIAutomationElement e, bool cached) { E = e; this.cached = cached; }
    static El Of(UIA.IUIAutomationElement e, bool cached) { return e == null ? null : new El(e, cached); }

    public static El Root { get { return Of(A.GetRootElement(), false); } }
    public static UIA.IUIAutomationCondition True { get { return A.CreateTrueCondition(); } }
    public static UIA.IUIAutomationCondition TypeIs(int type) { return A.CreatePropertyCondition(TypeP, type); }
    public static UIA.IUIAutomationCondition TypeIn(int a, int b) { return A.CreateOrCondition(TypeIs(a), TypeIs(b)); }
    public static UIA.IUIAutomationCondition IdIs(string id) { return A.CreatePropertyCondition(AutoIdP, id); }
    public static UIA.IUIAutomationCondition NameAndType(string name, int type)
    {
        return A.CreateAndCondition(A.CreatePropertyCondition(NameP, name), TypeIs(type));
    }

    // 이름·클래스·종류는 목록으로 받은 요소면 받아 둔 값, 아니면 지금 값. 나머지는 늘 지금 값
    public string Name { get { return (cached ? E.CachedName : E.CurrentName) ?? ""; } }
    public string ClassName { get { return (cached ? E.CachedClassName : E.CurrentClassName) ?? ""; } }
    public int Type { get { return cached ? E.CachedControlType : E.CurrentControlType; } }
    public int ProcessId { get { return E.CurrentProcessId; } }
    public IntPtr Hwnd { get { return E.CurrentNativeWindowHandle; } }
    public bool Enabled { get { return E.CurrentIsEnabled != 0; } }
    public UIA.tagRECT Rect { get { return E.CurrentBoundingRectangle; } }
    public UIA.tagRECT CachedRect { get { return cached ? E.CachedBoundingRectangle : E.CurrentBoundingRectangle; } }
    public string AutomationId { get { return (cached ? E.CachedAutomationId : E.CurrentAutomationId) ?? ""; } }

    public List<El> FindAll(UIA.TreeScope scope, UIA.IUIAutomationCondition cond)
    {
        var arr = E.FindAllBuildCache(scope, cond, Cache);
        var list = new List<El>();
        if (arr != null)
            for (int i = 0; i < arr.Length; i++) list.Add(new El(arr.GetElement(i), true));
        return list;
    }

    public El FindFirst(UIA.TreeScope scope, UIA.IUIAutomationCondition cond)
    {
        return Of(E.FindFirstBuildCache(scope, cond, Cache), true);
    }

    public El Parent() { return Of(A.ControlViewWalker.GetParentElementBuildCache(E, Cache), true); }
    public El PrevSibling() { return Of(A.ControlViewWalker.GetPreviousSiblingElementBuildCache(E, Cache), true); }

    // 그 기능(누르기·값·토글 …)이 없으면 null
    public T Pattern<T>(int id) where T : class { return E.GetCurrentPattern(id) as T; }
}

class ChatGptWatch
{
    static readonly object Lock = new object();
    static readonly Queue<string> Commands = new Queue<string>();

    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOACTIVATE = 0x10, SWP_SHOWWINDOW = 0x40;
    struct POINT { public int X, Y; }
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern bool ScreenToClient(IntPtr h, ref POINT p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
    [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr h, int i, int v);
    [DllImport("user32.dll")] static extern bool GetLayeredWindowAttributes(IntPtr h, out uint key, out byte alpha, out uint flags);
    [DllImport("user32.dll")] static extern bool SetLayeredWindowAttributes(IntPtr h, uint key, byte alpha, uint flags);
    const int GWL_EXSTYLE = -20, WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20;
    const uint LWA_ALPHA = 0x2;

    // 화면 읽기의 '누르기'(Invoke·Toggle)와 글 넣기(SetValue)는 Claude 앱이 창을 맨 앞으로 끌어와 포커스까지 가져가므로,
    // 그 자리에 클릭 신호만 창에 직접 보낸다. 실제 마우스 포인터는 움직이지 않고 포커스도 바꾸지 않는다.
    static bool ClickOn(El e, IntPtr hwnd)
    {
        try
        {
            var si = e.Pattern<UIA.IUIAutomationScrollItemPattern>(El.ScrollItemId);
            if (si != null) si.ScrollIntoView();
            Thread.Sleep(150);
            var r = e.Rect;
            if (r.right - r.left < 2) return false;
            var pt = new POINT { X = r.left + Math.Min(40, (r.right - r.left) / 2), Y = r.top + (r.bottom - r.top) / 2 };
            ScreenToClient(hwnd, ref pt);
            var lp = new IntPtr((pt.Y << 16) | (pt.X & 0xFFFF));
            PostMessage(hwnd, 0x0200, IntPtr.Zero, lp);       // WM_MOUSEMOVE
            PostMessage(hwnd, 0x0201, new IntPtr(1), lp);     // WM_LBUTTONDOWN
            Thread.Sleep(60);
            PostMessage(hwnd, 0x0202, IntPtr.Zero, lp);       // WM_LBUTTONUP
            return true;
        }
        catch { return false; }
    }

    // 글을 키 입력 신호(WM_CHAR)로 한 글자씩 보낸다. 줄바꿈은 '보내기'가 돼 버리므로 띄어쓰기로 바꾼다.
    static void TypeText(IntPtr hwnd, string text)
    {
        foreach (char c in text)
            PostMessage(hwnd, 0x0102, new IntPtr(c == '\r' || c == '\n' ? ' ' : c), new IntPtr(1));
    }

    // 입력창에 실제로 들어가는 모양 (줄바꿈 → 띄어쓰기). 들어갔는지·보내졌는지 확인할 때도 이 글로 비교한다
    static string OneLine(string text)
    {
        return text.Replace("\r\n", " ").Replace('\r', ' ').Replace('\n', ' ');
    }

    // 잘못 들어간 글을 지운다 (Backspace 신호)
    static void Erase(IntPtr hwnd, int n)
    {
        for (int i = 0; i < n; i++)
        {
            PostMessage(hwnd, 0x0100, new IntPtr(0x08), new IntPtr(0x000E0001));            // WM_KEYDOWN VK_BACK
            PostMessage(hwnd, 0x0101, new IntPtr(0x08), new IntPtr(unchecked((int)0xC00E0001)));
        }
    }

    class Shown { public IntPtr Hwnd, Above; public bool Ghost, Iconic, Layered; public int ExStyle; public uint Key, Flags; public byte Alpha; }

    // 창이 화면에 보이면(맨 앞이든 나란히 띄워 둔 것이든) 그대로 둔다.
    // 최소화됐거나 거의 가려졌으면 앱이 쉬고 있으므로, 거의 투명(알파 1)하고 클릭이 통과하는 상태로
    // 포커스 없이 맨 위에 올린다 → 눈에는 안 보이고 쓰던 창의 클릭도 그대로 아래 창으로 간다.
    // 되살린 직후 1~2초 동안 보낸 신호는 버려지므로, 받는 쪽에서 반영될 때까지 다시 보낸다.
    static Shown Wake(IntPtr hwnd)
    {
        var s = new Shown { Hwnd = hwnd, Iconic = IsIconic(hwnd) };
        // 화면에 보이는 창(맨 앞이 아니어도)은 앱이 깨어 있어 신호를 받으므로 그대로 둔다
        // (투명하게 바꾸면 보던 창이 잠깐 사라졌다 돌아오는 것처럼 보임)
        if (!s.Iconic && (GetForegroundWindow() == hwnd || OnScreen(hwnd))) return s;
        s.Ghost = true;
        // 원래 바로 위에 있던 보통 창(맨 위 고정 창 제외)을 기억해 두었다가 그 아래로 돌려놓는다
        for (IntPtr x = GetWindow(hwnd, 3); x != IntPtr.Zero; x = GetWindow(x, 3))      // GW_HWNDPREV
            if (IsWindowVisible(x) && (GetWindowLong(x, GWL_EXSTYLE) & 0x8) == 0) { s.Above = x; break; }   // WS_EX_TOPMOST 아님
        s.ExStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
        s.Layered = (s.ExStyle & WS_EX_LAYERED) != 0
                    && GetLayeredWindowAttributes(hwnd, out s.Key, out s.Alpha, out s.Flags);
        SetWindowLong(hwnd, GWL_EXSTYLE, s.ExStyle | WS_EX_LAYERED | WS_EX_TRANSPARENT);
        SetLayeredWindowAttributes(hwnd, 0, 1, LWA_ALPHA);
        if (s.Iconic) ShowWindow(hwnd, 4);                                    // SW_SHOWNOACTIVATE
        SetWindowPos(hwnd, new IntPtr(-1), 0, 0, 0, 0,                        // HWND_TOPMOST
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
        Thread.Sleep(300);
        return s;
    }

    static void Unwake(Shown s)
    {
        if (s == null || !s.Ghost) return;
        SetWindowPos(s.Hwnd, new IntPtr(-2), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);  // HWND_NOTOPMOST
        if (s.Iconic) ShowWindow(s.Hwnd, 7);                                  // SW_SHOWMINNOACTIVE (다시 최소화)
        else if (s.Above != IntPtr.Zero)                                      // 원래 자리(그 창 바로 아래)로
            SetWindowPos(s.Hwnd, s.Above, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        if (s.Layered && (s.Flags & LWA_ALPHA) != 0) SetLayeredWindowAttributes(s.Hwnd, s.Key, s.Alpha, s.Flags);
        else SetLayeredWindowAttributes(s.Hwnd, 0, 255, LWA_ALPHA);           // 완전히 불투명하게
        SetWindowLong(s.Hwnd, GWL_EXSTYLE, s.ExStyle);
    }

    static string Json(string s)
    {
        var b = new StringBuilder("\"");
        foreach (char c in s)
        {
            if (c == '"' || c == '\\') b.Append('\\').Append(c);
            else if (c < 0x20) b.AppendFormat("\\u{0:x4}", (int)c);
            else b.Append(c);
        }
        return b.Append('"').ToString();
    }

    static List<El> AppWindows(string process)
    {
        // ChatGPT 데스크톱 앱은 프로세스 이름이 'ChatGPT Classic' 으로 바뀌었다 → 둘 다
        var names = process == "ChatGPT" ? new[] { "ChatGPT", "ChatGPT Classic" } : new[] { process };
        var pids = new HashSet<int>(names.SelectMany(n => Process.GetProcessesByName(n)).Select(p => p.Id));
        var list = new List<El>();
        if (pids.Count == 0) return list;
        foreach (var w in El.Root.FindAll(El.Children, El.True))
        {
            try { if (pids.Contains(w.ProcessId)) list.Add(w); } catch { }
        }
        return list;
    }

    // ChatGPT 사이드바 대화 줄 = ClassName에 sidebar-item 이 들어간 버튼
    static bool IsGptRow(El e)
    {
        if (e.Type == El.Button && e.ClassName.Contains("sidebar-item")) return true;
        if (e.Type != El.Hyperlink || !e.ClassName.Contains("__menu-item") || e.Name.Trim().Length == 0) return false;
        try
        {
            var v = e.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
            return v != null && (v.CurrentValue ?? "").Contains("/c/");
        }
        catch { return false; }
    }

    // Claude 사이드바 대화 줄 = 이름 있는 text-start 버튼 ('…에 대한 더 많은 옵션' 버튼은 제외)
    static bool IsClaudeRow(El e)
    {
        if (e.Type != El.Button) return false;
        string n = e.Name;
        return n.Trim().Length > 0 && !n.EndsWith("옵션") && !n.EndsWith("options")
            && e.ClassName.Contains("text-start");
    }

    // 상태 표시가 줄 안에 있으면 위로, 줄 바로 옆에 있으면 앞 형제에서 찾는다
    static El RowOf(El e, Func<El, bool> isRow)
    {
        for (int i = 0; i < 6 && e != null; i++)
        {
            try
            {
                var prev = e.PrevSibling();
                if (prev != null && isRow(prev)) return prev;
                e = e.Parent();
                if (e != null && isRow(e)) return e;
            }
            catch { return null; }
        }
        return null;
    }

    static List<string> WorkingTitles(El w, Func<El, bool> isRow)
    {
        var titles = new List<string>();
        foreach (var s in w.FindAll(El.Descendants, El.TypeIs(El.StatusBar)))
        {
            try
            {
                string status = s.Name.Trim();
                if (status.Length == 0) continue;   // '작업 중'·'실행 중' 같은 이름이 있는 표시만
                var row = RowOf(s, isRow);
                if (row == null) continue;
                string t = row.Name.Trim();
                // Claude 앱은 줄 이름 끝에 상태 글자까지 붙여 준다 ("제목 실행 중") → 떼어 낸다
                if (t.EndsWith(status) && t.Length > status.Length)
                    t = t.Substring(0, t.Length - status.Length).Trim();
                if (t.Length > 0 && !titles.Contains(t)) titles.Add(t);
            }
            catch { }
        }
        return titles;
    }

    // Claude 창이 채팅 화면인지 (Code 탭이면 채팅 목록이 안 보이므로 '끝남'으로 착각하지 않게 판단을 미룬다),
    // 그리고 지금 보이는 대화가 답하는 중인지 ('응답 중지' 버튼)
    static void ClaudeView(El w, out bool chatView, out bool stopShown, out string session)
    {
        chatView = true;
        stopShown = false;
        session = null;                 // Code 화면에 띄워 둔 세션 제목 ("제목, 세션 이름 바꾸기" 버튼)
        foreach (var b in w.FindAll(El.Descendants, El.TypeIs(El.Button)))
        {
            string n;
            try { n = b.Name; } catch { continue; }
            if (n == "터미널" || n == "세션 패널" || n == "Terminal") chatView = false;
            if (n == "응답 중지" || n == "Stop response") stopShown = true;
            foreach (var tail in new[] { ", 세션 이름 바꾸기", ", Rename session" })
                if (session == null && n.EndsWith(tail)) session = n.Substring(0, n.Length - tail.Length);
        }
    }

    struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);

    // 창이 화면에 실제로 보이는지: 창 안에 점을 고르게 찍어 그 자리 맨 위가 이 창인 비율이 1/4 이상이면 보인다.
    // 맨 앞이 아니어도 나란히 띄워 두면 보는 중이고, 최소화되거나 거의 가려지면 안 보는 중으로 친다.
    static bool OnScreen(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero || IsIconic(hwnd) || !IsWindowVisible(hwnd)) return false;
        RECT r;
        if (!GetWindowRect(hwnd, out r) || r.R - r.L < 50 || r.B - r.T < 50) return false;
        int hit = 0, n = 0;
        for (int i = 1; i <= 6; i++)
            for (int j = 1; j <= 6; j++)
            {
                var pt = new POINT { X = r.L + (r.R - r.L) * i / 7, Y = r.T + (r.B - r.T) * j / 7 };
                n++;
                if (GetAncestor(WindowFromPoint(pt), 2) == hwnd) hit++;   // GA_ROOT
            }
        return hit * 4 >= n;
    }

    static void Open(string process, Func<El, bool> isRow, string title)
    {
        foreach (var w in AppWindows(process))
        {
            foreach (var b in w.FindAll(El.Descendants, El.TypeIn(El.Button, El.Hyperlink)))
            {
                try
                {
                    if (b.Name == title && isRow(b))
                    {
                        var p = b.Pattern<UIA.IUIAutomationInvokePattern>(El.InvokeId);
                        if (p != null) p.Invoke();
                        return;
                    }
                }
                catch { }
            }
        }
    }

    // ---- ChatGPT 앱: 지금 열린 대화의 메시지 읽기 · 그 대화에 답 보내기 ----
    // 화면 구조: main 아래에 메시지 글(Text·목록·표)이 평평하게 늘어서고, 메시지마다 끝에 '작업' 묶음(복사·편집 버튼)이 온다.
    // 답 쪽 묶음에는 radix- 로 시작하는 버튼(평가·모델 바꾸기)이 있고, 내 메시지 쪽에는 없다 → 언어와 상관없이 구분.
    static string GptOpenTitle(El w)
    {
        var doc = w.FindFirst(El.Descendants, El.TypeIs(El.Document));
        return doc == null ? "" : doc.Name.Trim();
    }

    static List<string[]> GptMessages(El w, int max)
    {
        var msgs = new List<string[]>();
        var main = w.FindFirst(El.Descendants, El.IdIs("main"));
        if (main == null) return msgs;
        var buf = new StringBuilder();
        var live = new StringBuilder();      // 마지막 묶음 뒤, 답 칸(text-message)에서 나온 글 = 아직 쓰는 중인 답
        int lastTop = int.MinValue, lastBottom = int.MinValue, liveTop = int.MinValue, liveBottom = int.MinValue;
        bool lastAi = false;
        Action<StringBuilder, El> add = (b, x) =>
        {
            string n = x.Name;
            if (n.Trim().Length == 0) return;
            var r = x.CachedRect;
            bool isLive = b == live;
            int pt = isLive ? liveTop : lastTop, pb = isLive ? liveBottom : lastBottom;
            // 앞 조각과 위아래로 겹치면 같은 줄(굵게 쓴 부분·줄 끝에서 이어진 조각)이라 붙이고, 아니면 줄바꿈.
            // 표 칸끼리는 같은 줄이어도 ' | ' 로 나눈다
            if (b.Length > 0)
            {
                bool sameLine = r.top < pb - 2 && r.bottom > pt + 2;
                b.Append(sameLine ? (x.Type == El.DataItem ? " | " : "") : "\n");
            }
            b.Append(n);
            if (isLive) { liveTop = r.top; liveBottom = r.bottom; } else { lastTop = r.top; lastBottom = r.bottom; }
        };
        foreach (var c in main.FindAll(El.Children, El.True))
        {
            try
            {
                if (c.Type == El.Group && c.ClassName.Contains("touch:-m"))      // 메시지 하나 끝 ('작업' 묶음)
                {
                    lastAi = c.FindAll(El.Descendants, El.TypeIs(El.Button)).Any(b => b.AutomationId.StartsWith("radix-"));
                    // 그림만 보낸 내 메시지는 빈 글로 (로봇이 '(이미지)'로 보여 줌)
                    if (buf.Length > 0 || !lastAi) msgs.Add(new[] { lastAi ? "ai" : "me", buf.ToString() });
                    buf.Clear();
                    live.Clear();
                    lastTop = liveTop = lastBottom = liveBottom = int.MinValue;
                    continue;
                }
                bool answerBox = c.ClassName.Contains("text-message");
                if (c.Type == El.Text) { add(buf, c); continue; }
                foreach (var d in c.FindAll(El.Descendants, El.TypeIn(El.Text, El.DataItem)))
                {
                    add(buf, d);
                    if (answerBox) add(live, d);
                }
            }
            catch { }
        }
        // 마지막이 내 메시지였으면 그 뒤 답 칸의 글은 쓰는 중인 답 (맨 아래 안내문 등 다른 글은 뺀다)
        if (!lastAi && live.Length > 0) msgs.Add(new[] { "ai", live.ToString() });
        return msgs.Count > max ? msgs.GetRange(msgs.Count - max, max) : msgs;
    }

    static string GptChat(string title)
    {
        foreach (var w in AppWindows("ChatGPT"))
        {
            if (GptOpenTitle(w) != title) continue;
            var msgs = GptMessages(w, 24);
            var sb = new StringBuilder("{\"gptchat\":{\"title\":" + Json(title) + ",\"ok\":true,\"msgs\":[");
            for (int i = 0; i < msgs.Count; i++)
            {
                string t = msgs[i][1];
                if (t.Length > 6000) t = "…" + t.Substring(t.Length - 6000);
                sb.Append(i > 0 ? "," : "").Append("[" + Json(msgs[i][0]) + "," + Json(t) + "]");
            }
            return sb.Append("]}}").ToString();
        }
        return "{\"gptchat\":{\"title\":" + Json(title) + ",\"ok\":false,\"msgs\":[]}}";
    }

    // 열어 둔 대화가 답하는 중인지: 보내기 자리(composer-submit-button)가 '답변 중지' 버튼으로 바뀐다.
    // 이름은 앱 언어마다 달라서 '중지' 낱말로 본다 (확장 content.js 와 같은 낱말들)
    static readonly Regex StopName = new Regex(
        @"중지|停止|中止|ストップ|(?<![\p{L}\p{N}])(stop|detener|parar|interromp|arr[êe]t|anhalten|abbrechen|ferma|zatrzym|останов|стоп|hentikan|dừng|durdur)",
        RegexOptions.IgnoreCase);

    static bool GptAnswering(El w)
    {
        var b = w.FindFirst(El.Descendants, El.IdIs("composer-submit-button"));
        return b != null && StopName.IsMatch(b.Name);
    }

    // 입력창에 쓰던 글. 비어 있으면 화면 읽기 값으로 안내 글('ChatGPT에게 물어보세요' 등)이 나오는데,
    // 그때는 맨 앞 칸이 class="placeholder" 문단이므로 빈 것으로 본다
    static string GptDraft(El ed, UIA.IUIAutomationValuePattern vp)
    {
        try
        {
            var first = El.A.RawViewWalker.GetFirstChildElement(ed.E);
            if (first != null && (first.CurrentClassName ?? "").Contains("placeholder")) return "";
        }
        catch { }
        return Value(vp).Trim();
    }

    // 그 대화로 바꾸고(필요하면) 입력창에 글을 넣어 Enter. 창은 앞으로 가져오지 않는다 (Claude 앱 답 보내기와 같은 방식)
    static string ReplyGpt(string title, string text)
    {
        var wins = AppWindows("ChatGPT");
        if (wins.Count == 0) return "ChatGPT 앱이 열려 있지 않아요";
        var w = wins.FirstOrDefault(x => GptOpenTitle(x) == title)
                ?? wins.FirstOrDefault(x => x.FindAll(El.Descendants, El.TypeIn(El.Button, El.Hyperlink))
                                             .Any(b => b.Name == title && IsGptRow(b)))
                ?? wins[0];
        var shown = Wake(w.Hwnd);
        string before = "";             // 보내기 전에 보던 대화 — 다 보내면 그리로 돌려놓는다 (Claude 앱 답 보내기처럼)
        try
        {
            Log("ChatGPT 시작: " + title);
            before = GptOpenTitle(w);
            if (before != title)
            {
                if (!GptSwitch(w, title)) return "그 대화로 바꾸지 못했어요";
                Log("대화 바꿈");
                Thread.Sleep(400);
            }
            var ed = w.FindFirst(El.Descendants, El.IdIs("prompt-textarea"));
            var vp = ed == null ? null : ed.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
            if (vp == null) return "입력창을 찾지 못했어요";
            if (GptDraft(ed, vp).Length > 0) return "그 대화 입력창에 쓰던 글이 있어서 보내지 않았어요";
            text = OneLine(text);
            string head = text.Trim();
            head = head.Substring(0, Math.Min(10, head.Length));
            if (!ClickOn(ed, w.Hwnd)) return "입력창 자리를 찾지 못했어요";
            Thread.Sleep(200);
            TypeText(w.Hwnd, text);
            string got = "";
            if (!WaitFor(() => (got = Value(vp)).Contains(head), 3000))
            {
                Erase(w.Hwnd, got.Length + 2);
                return "입력창에 글을 넣지 못했어요";
            }
            Log("입력창에 글 넣음");
            for (int k = 0; k < 3; k++)
            {
                PostMessage(w.Hwnd, 0x0100, new IntPtr(0x0D), new IntPtr(0x001C0001));                  // WM_KEYDOWN Enter
                PostMessage(w.Hwnd, 0x0101, new IntPtr(0x0D), new IntPtr(unchecked((int)0xC01C0001)));
                if (WaitFor(() => !Value(vp).Contains(head), 2000)) { Log("보냄"); return "ok"; }
            }
            Erase(w.Hwnd, Value(vp).Length + 2);
            return "보내기를 하지 못했어요";
        }
        finally
        {
            // 보던 대화가 따로 있었으면 돌려놓는다 (새 채팅 화면 'ChatGPT' 는 목록 줄이 없어 그대로)
            try
            {
                if (before.Length > 0 && before != title && before != "ChatGPT" && GptOpenTitle(w) != before)
                    Log("돌려놓기: " + (GptSwitch(w, before) ? "됨" : "못 함"));
            }
            catch { }
            Unwake(shown);
            Log("끝");
        }
    }

    // 목록에서 그 대화 줄을 눌러 연다. 먼저 클릭 신호(창을 앞으로 끌어오지 않음), 안 바뀌면 화면 읽기 '누르기'
    static bool GptSwitch(El w, string title)
    {
        El row = null;
        foreach (var b in w.FindAll(El.Descendants, El.TypeIn(El.Button, El.Hyperlink)))
            if (b.Name == title && IsGptRow(b)) { row = b; break; }
        if (row == null) return false;
        ClickOn(row, w.Hwnd);
        if (WaitFor(() => GptOpenTitle(w) == title, 2000)) return true;
        try
        {
            var inv = row.Pattern<UIA.IUIAutomationInvokePattern>(El.InvokeId);
            if (inv != null) inv.Invoke();
        }
        catch { }
        return WaitFor(() => GptOpenTitle(w) == title, 3000);
    }

    // ---- Claude 앱 Code 세션에 답 보내기 (창을 앞으로 가져오지 않음) ----
    static El ByName(El w, string name, int type)
    {
        return w.FindFirst(El.Descendants, El.NameAndType(name, type));
    }

    // 지금 화면의 세션 제목 = "제목, 세션 이름 바꾸기" 버튼
    static string CurrentSession(El w)
    {
        foreach (var b in w.FindAll(El.Descendants, El.TypeIs(El.Button)))
        {
            string n;
            try { n = b.Name; } catch { continue; }
            foreach (var tail in new[] { ", 세션 이름 바꾸기", ", Rename session" })
                if (n.EndsWith(tail)) return n.Substring(0, n.Length - tail.Length);
        }
        return null;
    }

    // 왼쪽 목록의 세션 줄 (이름이 제목과 같거나 "제목 Claude 시작 위치: …"처럼 뒤에 덧붙은 것)
    static El SessionRow(El w, string title)
    {
        foreach (var b in w.FindAll(El.Descendants, El.TypeIs(El.Button)))
        {
            try
            {
                string n = b.Name;
                if ((n == title || n.StartsWith(title + " ")) && IsClaudeRow(b)) return b;
            }
            catch { }
        }
        return null;
    }

    // 그 세션으로 화면을 바꾸고(필요하면) 입력창에 글을 넣어 '보내기'를 누른 뒤, 원래 보던 세션으로 돌려놓는다.
    // 돌려주는 값: "ok" 또는 사용자에게 보여 줄 이유
    // 창을 안 보이게 깨우고 → 그 세션으로 바꾸고 → work → 원래 세션으로 돌려놓고 → 창도 원래대로
    static string InSession(string title, Func<El, string> work)
    {
        var wins = AppWindows("claude");
        if (wins.Count == 0) return "Claude 앱이 열려 있지 않아요";
        var w = wins[0];
        Shown shown = null;
        try
        {
            Log("시작: " + title);
            var hwnd = w.Hwnd;
            shown = Wake(hwnd);
            if (shown.Ghost) Log(shown.Iconic ? "최소화돼 있어서 안 보이게 되살림" : "뒤에 있어서 안 보이게 깨움");
            w.FindAll(El.Descendants, El.True);   // 처음 읽을 땐 일부만 보여서 한 번 깨운다
            string back = CurrentSession(w);
            if (back == null) return "Claude 앱을 Code 화면으로 두고 다시 보내 주세요";
            if (back != title)
            {
                var row = SessionRow(w, title);
                if (row == null) return "Claude 앱 목록에서 그 세션을 찾지 못했어요";
                // 막 되살린 창은 누른 게 버려질 수 있어 바뀔 때까지 1.5초마다 다시 누른다
                bool moved = false;
                for (int k = 0; k < 6 && !moved; k++)
                {
                    ClickOn(row, hwnd);
                    moved = WaitFor(() => CurrentSession(w) == title, 1500);
                }
                if (!moved) return "그 세션으로 바꾸지 못했어요";
                Log("세션 바꿈");
                Thread.Sleep(400);
            }
            else back = null;                 // 이미 그 세션이면 돌아갈 필요 없음
            Log("세션 준비됨");
            string result = work(w);
            Log("결과: " + result);
            if (back != null)
            {
                Thread.Sleep(500);
                var row = SessionRow(w, back);   // 원래 보던 세션으로 화면을 돌려놓음
                if (row != null) ClickOn(row, hwnd);
                Thread.Sleep(300);
            }
            return result;
        }
        finally { Unwake(shown); Log("끝"); }
    }

    // 답 보내기 단계 기록 (로봇에선 화면 출력이 안 보이므로 파일로). 커지면 새로 시작한다.
    static readonly string LogPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "card.log");
    static void Log(string s)
    {
        try
        {
            var f = new System.IO.FileInfo(LogPath);
            if (f.Exists && f.Length > 200000) f.Delete();
            System.IO.File.AppendAllText(LogPath, DateTime.Now.ToString("MM-dd HH:mm:ss.fff ") + s + "\r\n");
        }
        catch { }
    }

    static bool WaitFor(Func<bool> ok, int ms)
    {
        for (int i = 0; i * 100 < ms; i++)
        {
            try { if (ok()) return true; } catch { }
            Thread.Sleep(100);
        }
        return false;
    }

    // ---- 이미지 진짜 첨부 ----
    // 붙여넣기(Ctrl+V)는 키보드 포커스가 있는 창에서만 처리되므로, 그 동안만 창에 포커스를 주고(창은 투명이라 안 보임)
    // 클립보드에 이미지를 올려 붙여넣은 뒤, 포커스는 사용자가 쓰던 창으로, 클립보드는 원래 내용으로 돌려놓는다.
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr h);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);

    static bool ToFront(IntPtr h)
    {
        if (h == IntPtr.Zero || !IsWindow(h)) return false;
        if (GetForegroundWindow() == h) return true;
        uint pid;
        uint fgThread = GetWindowThreadProcessId(GetForegroundWindow(), out pid), me = GetCurrentThreadId();
        bool attached = fgThread != 0 && fgThread != me && AttachThreadInput(me, fgThread, true);
        SetForegroundWindow(h);
        if (attached) AttachThreadInput(me, fgThread, false);
        return WaitFor(() => GetForegroundWindow() == h, 1000);
    }

    // 클립보드는 STA 스레드에서만 다룰 수 있다
    static void Sta(Action a)
    {
        var th = new Thread(() => { try { a(); } catch (Exception ex) { Log("클립보드 오류: " + ex.Message); } });
        th.SetApartmentState(ApartmentState.STA);
        th.Start();
        th.Join();
    }

    class Clip { public string Text; public System.Drawing.Image Img; public System.Collections.Specialized.StringCollection Files; }

    static Clip SaveClip()
    {
        var c = new Clip();
        Sta(() =>
        {
            if (System.Windows.Forms.Clipboard.ContainsText()) c.Text = System.Windows.Forms.Clipboard.GetText();
            if (System.Windows.Forms.Clipboard.ContainsImage()) c.Img = System.Windows.Forms.Clipboard.GetImage();
            if (System.Windows.Forms.Clipboard.ContainsFileDropList()) c.Files = System.Windows.Forms.Clipboard.GetFileDropList();
        });
        return c;
    }

    static void RestoreClip(Clip c)
    {
        Sta(() =>
        {
            var d = new System.Windows.Forms.DataObject();
            if (c.Text != null) d.SetText(c.Text);
            if (c.Img != null) d.SetImage(c.Img);
            if (c.Files != null) d.SetFileDropList(c.Files);
            if (c.Text == null && c.Img == null && c.Files == null) System.Windows.Forms.Clipboard.Clear();
            else System.Windows.Forms.Clipboard.SetDataObject(d, true);
        });
    }

    static bool ClipImage(string path)
    {
        bool ok = false;
        Sta(() =>
        {
            using (var img = System.Drawing.Image.FromFile(path))
            {
                var d = new System.Windows.Forms.DataObject();
                d.SetImage(new System.Drawing.Bitmap(img));
                var ms = new System.IO.MemoryStream();            // 크롬 계열 앱은 PNG 형식을 먼저 읽는다
                img.Save(ms, System.Drawing.Imaging.ImageFormat.Png);
                d.SetData("PNG", false, ms);
                System.Windows.Forms.Clipboard.SetDataObject(d, true);
                ok = true;
            }
        });
        return ok;
    }

    static HashSet<string> ButtonNames(El scope)
    {
        var names = new HashSet<string>();
        foreach (var b in scope.FindAll(El.Descendants, El.True))
            try
            {
                int ct = b.Type;
                if (ct == El.Button) names.Add("Button:" + b.Name);
                else if (ct == El.Image) names.Add("Image:" + b.Name);
            }
            catch { }
        return names;
    }

    // 입력창에 이미지를 붙여넣는다. 실패하면 이유, 성공하면 null
    static string PasteImages(El scope, IntPtr hwnd, El input, List<string> images, IntPtr restore)
    {
        if (images.Count == 0) return null;
        var before = ButtonNames(scope);
        var clip = SaveClip();
        if (restore == IntPtr.Zero) restore = GetForegroundWindow();
        try
        {
            if (!ToFront(hwnd)) return "이미지를 붙이려고 창에 포커스를 주지 못했어요";
            Log("포커스 받음");
            ClickOn(input, hwnd);
            Thread.Sleep(250);
            foreach (var path in images)
            {
                if (!ClipImage(path)) return "이미지 파일을 열지 못했어요: " + path;
                Thread.Sleep(120);
                keybd_event(0x11, 0, 0, UIntPtr.Zero);            // Ctrl
                keybd_event(0x56, 0, 0, UIntPtr.Zero);            // V
                keybd_event(0x56, 0, 2, UIntPtr.Zero);
                keybd_event(0x11, 0, 2, UIntPtr.Zero);
                Thread.Sleep(800);                                // 앱이 클립보드를 읽어 갈 시간
                Log("이미지 붙여넣음: " + path);
            }
        }
        finally
        {
            Log("포커스 돌려놓음: " + ToFront(restore));
            RestoreClip(clip);
            Log("클립보드 돌려놓음");
        }
        // 첨부되면 입력창 둘레에 새 버튼(지우기 등)이나 그림이 생긴다
        var added = ButtonNames(scope).Where(n => !before.Contains(n)).ToList();
        Log("새로 생긴 것: " + string.Join(" | ", added));
        return added.Count > 0 ? null : "이미지가 입력창에 붙지 않았어요";
    }

    static string Value(UIA.IUIAutomationValuePattern vp) { return vp.CurrentValue ?? ""; }

    // 입력창(다음 단계 상자 답)에 글을 넣고 '보내기'
    static string Reply(string title, string text, List<string> images = null, IntPtr restore = default(IntPtr))
    {
        return InSession(title, w =>
        {
            var ed = ByName(w, "프롬프트", El.Edit) ?? ByName(w, "Prompt", El.Edit);
            var vp = ed == null ? null : ed.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
            if (vp == null) return "입력창을 찾지 못했어요";
            if (Value(vp).Trim().Length > 0) return "그 세션 입력창에 쓰던 글이 있어서 보내지 않았어요";
            var hwnd = w.Hwnd;
            string pasted = PasteImages(w, hwnd, ed, images ?? new List<string>(), restore);
            if (pasted != null) return pasted;
            text = OneLine(text);
            string head = text.Trim();
            head = head.Substring(0, Math.Min(10, head.Length));
            // 입력창을 클릭 신호로 고르고 글자를 신호로 넣는다 (화면 읽기로 넣으면 앱이 창을 앞으로 가져옴)
            if (!ClickOn(ed, hwnd)) return "입력창 자리를 찾지 못했어요";
            Thread.Sleep(200);
            TypeText(hwnd, text);
            string got = "";
            bool put = WaitFor(() => (got = Value(vp)).Contains(head), 3000);
            if (!put || got.Trim().Length > text.Trim().Length + 2)
            {
                Erase(hwnd, got.Length + 2);           // 반쯤 들어갔거나 엉뚱하게 들어간 글은 지운다
                return "입력창에 글을 넣지 못했어요";
            }
            Log("입력창에 글 넣음");
            // 보내지면 입력창이 비워진다. 안 비워졌으면 아직 안 간 것이라 다시 누른다
            for (int k = 0; k < 3; k++)
            {
                // 글자가 들어간 뒤 '보내기'가 켜지기까지 조금 걸린다
                El send = null;
                WaitFor(() => (send = ByName(w, "보내기", El.Button) ?? ByName(w, "Send", El.Button)) != null
                              && send.Enabled, 3000);
                if (send == null || !send.Enabled || !ClickOn(send, hwnd)) break;
                if (WaitFor(() => !Value(vp).Contains(head), 2000)) { Log("보냄"); return "ok"; }
            }
            Erase(hwnd, Value(vp).Length + 2);
            return "보내기 버튼을 누르지 못했어요";
        });
    }

    // 질문 카드(AskUserQuestion)에서 선택지(또는 '기타' + 글)를 고르고, 골라진 게 확인되면 '제출'
    static string Card(string title, string label, string other)
    {
        return InSession(title, w =>
        {
            bool isOther = !string.IsNullOrEmpty(other);
            El opt = null;
            UIA.IUIAutomationTogglePattern tp = null;
            foreach (var b in w.FindAll(El.Descendants, El.TypeIs(El.Button)))
            {
                string n;
                try { n = b.Name; } catch { continue; }
                bool hit = isOther ? n == "기타" || n == "Other"
                                   : n == label || n.StartsWith(label + " ");
                if (!hit) continue;
                try { tp = b.Pattern<UIA.IUIAutomationTogglePattern>(El.ToggleId); } catch { continue; }
                if (tp != null) { opt = b; break; }
            }
            if (opt == null) return "그 세션에서 질문 카드를 찾지 못했어요 (이미 답했을 수 있어요)";
            var hwnd = w.Hwnd;
            Func<bool> isOn = () => tp.CurrentToggleState == UIA.ToggleState.ToggleState_On;
            Log("선택지 찾음: " + opt.Name + " / 상태 " + (isOn() ? "On" : "Off"));
            // 막 되살린 창은 처음 1~2초의 클릭을 버리므로(나중에 처리되지도 않음) 골라질 때까지 0.7초마다 다시 누른다
            bool on = isOn();
            for (int k = 0; k < 14 && !on; k++)
            {
                if (!ClickOn(opt, hwnd)) return "선택지 자리를 찾지 못했어요";
                on = WaitFor(isOn, 700);
                Log("선택지 클릭 " + (k + 1) + "번째 → " + (on ? "골라짐" : "아직"));
            }
            if (!on) return "선택이 확인되지 않아 제출하지 않았어요";
            if (isOther)
            {
                El box = null;
                WaitFor(() => (box = ByName(w, "기타 옵션", El.Edit)) != null, 3000);
                var vp = box == null ? null : box.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
                if (vp == null) return "기타 입력칸을 찾지 못해 제출하지 않았어요";
                string head = other.Trim();
                head = head.Substring(0, Math.Min(10, head.Length));
                if (!ClickOn(box, hwnd)) return "기타 입력칸 자리를 찾지 못했어요";
                Thread.Sleep(200);
                Erase(hwnd, Value(vp).Length);   // 전에 써 둔 글이 있으면 비운다
                TypeText(hwnd, other);
                if (!WaitFor(() => Value(vp).Contains(head), 3000))
                    return "기타 입력칸에 글을 넣지 못해 제출하지 않았어요";
            }
            // 제출되면 카드(제출 버튼)가 사라진다. 남아 있으면 아직 안 간 것이라 다시 누른다
            for (int k = 0; k < 3; k++)
            {
                var submit = ByName(w, "제출", El.Button) ?? ByName(w, "Submit", El.Button);
                if (submit == null) return k == 0 ? "제출 버튼을 찾지 못했어요" : "ok";
                if (!submit.Enabled || !ClickOn(submit, hwnd)) return "제출 버튼을 누르지 못했어요";
                Log("제출 클릭 " + (k + 1) + "번째");
                if (WaitFor(() => ByName(w, "제출", El.Button) == null
                                  && ByName(w, "Submit", El.Button) == null, 2500)) return "ok";
            }
            return "제출이 확인되지 않았어요. Claude 앱에서 확인해 주세요";
        });
    }

    // ---- VS Code의 Claude Code 패널 (창마다 웹 화면 안에 있고, 위쪽 제목 버튼이 세션 이름) ----
    // 그 세션 패널을 찾아 창을 안 보이게 깨운 뒤 work(패널, 창) → 창 원래대로. 세션을 바꿔 주지는 않는다.
    static string InVsCode(string title, Func<El, IntPtr, string> work)
    {
        var wins = AppWindows("Code");
        if (wins.Count == 0) return "VS Code가 열려 있지 않아요";
        foreach (var w in wins)
        {
            El panel = null;
            try
            {
                w.FindAll(El.Descendants, El.True);   // 처음엔 일부만 보여서 한 번 깨운다
                foreach (var b in w.FindAll(El.Descendants, El.TypeIs(El.Button)))
                {
                    if (b.ClassName.Contains("titleText") && b.Name.Trim() == title)
                    {
                        // 제목 버튼에서 위로 올라가 그 패널의 웹 화면 전체(Document)를 범위로 쓴다
                        for (var p = b.Parent(); p != null; p = p.Parent())
                            if (p.Type == El.Document) { panel = p; break; }
                        break;
                    }
                }
            }
            catch { continue; }
            if (panel == null) continue;
            var hwnd = w.Hwnd;
            Shown shown = null;
            try
            {
                Log("시작(VS Code): " + title);
                shown = Wake(hwnd);
                if (shown.Ghost) Log(shown.Iconic ? "최소화돼 있어서 안 보이게 되살림" : "뒤에 있어서 안 보이게 깨움");
                string result = work(panel, hwnd);
                Log("결과: " + result);
                return result;
            }
            finally { Unwake(shown); Log("끝"); }
        }
        return "VS Code에서 그 세션(" + title + ") 화면을 찾지 못했어요. Claude 패널에 그 세션을 열어 두세요";
    }

    static El ByClass(El scope, string part, int type)
    {
        foreach (var e in scope.FindAll(El.Descendants, El.TypeIs(type)))
            try { if (e.ClassName.Contains(part)) return e; } catch { }
        return null;
    }

    // VS Code 입력창은 비어 있으면 안내 문구("Ask Claude to edit…", "Queue another message…")를 값으로 돌려준다
    static string VsText(UIA.IUIAutomationValuePattern vp)
    {
        string v = Value(vp);
        return v.EndsWith("…") && v.Length < 80 && v.IndexOf('\n') < 0 ? "" : v;
    }

    static string ReplyVsCode(string title, string text, List<string> images = null, IntPtr restore = default(IntPtr))
    {
        return InVsCode(title, (p, hwnd) =>
        {
            var ed = ByClass(p, "messageInput", El.Edit);
            var vp = ed == null ? null : ed.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
            if (vp == null) return "입력창을 찾지 못했어요";
            Log("입력창 값: [" + Value(vp) + "]");
            if (VsText(vp).Trim().Length > 0) return "그 세션 입력창에 쓰던 글이 있어서 보내지 않았어요";
            string pasted = PasteImages(p, hwnd, ed, images ?? new List<string>(), restore);
            if (pasted != null) return pasted;
            text = OneLine(text);
            string head = text.Trim();
            head = head.Substring(0, Math.Min(10, head.Length));
            if (!ClickOn(ed, hwnd)) return "입력창 자리를 찾지 못했어요";
            Thread.Sleep(200);
            TypeText(hwnd, text);
            string got = "";
            if (!WaitFor(() => (got = Value(vp)).Contains(head), 3000))
            {
                Erase(hwnd, got.Length + 2);
                return "입력창에 글을 넣지 못했어요";
            }
            Log("입력창에 글 넣음");
            for (int k = 0; k < 3; k++)
            {
                // 답하는 중엔 이 버튼이 Stop 이라 누르면 멈춰 버린다 → Stop 이 아닐 때만 누르고,
                // 계속 Stop 이면 Enter 신호로 보낸다 (답하는 중이면 VS Code가 대기열에 넣음)
                El send = null;
                WaitFor(() => (send = ByClass(p, "sendButton", El.Button)) != null
                              && send.Enabled && send.Name != "Stop", 1500);
                if (send != null && send.Enabled && send.Name != "Stop")
                {
                    if (!ClickOn(send, hwnd)) break;
                }
                else
                {
                    Log("보내기 버튼이 Stop → Enter 신호");
                    PostMessage(hwnd, 0x0100, new IntPtr(0x0D), new IntPtr(0x001C0001));            // WM_KEYDOWN Enter
                    PostMessage(hwnd, 0x0102, new IntPtr(0x0D), new IntPtr(0x001C0001));            // WM_CHAR
                    PostMessage(hwnd, 0x0101, new IntPtr(0x0D), new IntPtr(unchecked((int)0xC01C0001)));
                }
                if (WaitFor(() => !Value(vp).Contains(head), 2000)) { Log("보냄"); return "ok"; }
            }
            Erase(hwnd, VsText(vp).Length + 2);
            return "보내기 버튼을 누르지 못했어요 (아직 답하는 중일 수 있어요)";
        });
    }

    static string CardVsCode(string title, string label, string other)
    {
        return InVsCode(title, (p, hwnd) =>
        {
            bool isOther = !string.IsNullOrEmpty(other);
            El opt = null;
            foreach (var b in p.FindAll(El.Descendants, El.TypeIs(El.RadioButton)))
            {
                string n;
                try { n = b.Name.Trim(); } catch { continue; }
                if (isOther ? n == "Other" || n == "기타" : n == label || n.StartsWith(label + " ")) { opt = b; break; }
            }
            if (opt == null) return "그 세션에서 질문 카드를 찾지 못했어요 (이미 답했을 수 있어요)";
            var sel = opt.Pattern<UIA.IUIAutomationSelectionItemPattern>(El.SelectionItemId);
            if (sel == null) return "그 세션에서 질문 카드를 찾지 못했어요 (이미 답했을 수 있어요)";
            Func<bool> isOn = () => sel.CurrentIsSelected != 0;
            Log("선택지 찾음: " + opt.Name + " / 골라짐 " + isOn());
            bool on = isOn();
            for (int k = 0; k < 14 && !on; k++)
            {
                if (!ClickOn(opt, hwnd)) return "선택지 자리를 찾지 못했어요";
                on = WaitFor(isOn, 700);
                Log("선택지 클릭 " + (k + 1) + "번째 → " + (on ? "골라짐" : "아직"));
            }
            if (!on) return "선택이 확인되지 않아 제출하지 않았어요";
            if (isOther)
            {
                // Other 를 고르면 카드 안에 입력칸이 생긴다 (아래 메시지 입력창과는 다른 것)
                El box = null;
                WaitFor(() =>
                {
                    foreach (var x in p.FindAll(El.Descendants, El.TypeIs(El.Edit)))
                        if (!x.ClassName.Contains("messageInput")) { box = x; return true; }
                    return false;
                }, 3000);
                var vp = box == null ? null : box.Pattern<UIA.IUIAutomationValuePattern>(El.ValueId);
                if (vp == null) return "기타 입력칸을 찾지 못해 제출하지 않았어요";
                string head = other.Trim();
                head = head.Substring(0, Math.Min(10, head.Length));
                if (!ClickOn(box, hwnd)) return "기타 입력칸 자리를 찾지 못했어요";
                Thread.Sleep(200);
                Erase(hwnd, Value(vp).Length);
                TypeText(hwnd, other);
                if (!WaitFor(() => Value(vp).Contains(head), 3000))
                    return "기타 입력칸에 글을 넣지 못해 제출하지 않았어요";
            }
            Func<El> submitBtn = () =>
            {
                foreach (var b in p.FindAll(El.Descendants, El.TypeIs(El.Button)))
                    try { if (b.Name.Contains("Submit")) return b; } catch { }
                return null;
            };
            for (int k = 0; k < 3; k++)
            {
                var submit = submitBtn();
                if (submit == null) return k == 0 ? "제출 버튼을 찾지 못했어요" : "ok";
                if (!submit.Enabled || !ClickOn(submit, hwnd)) return "제출 버튼을 누르지 못했어요";
                Log("제출 클릭 " + (k + 1) + "번째");
                if (WaitFor(() => submitBtn() == null, 2500)) return "ok";
            }
            return "제출이 확인되지 않았어요. VS Code에서 확인해 주세요";
        });
    }

    // 답장 명령 뒤쪽 칸: [3] 이미지 경로들(base64, 줄바꿈 구분) [4] 끝나고 포커스를 돌려놓을 창
    static void ReplyExtras(string[] parts, out List<string> images, out IntPtr restore)
    {
        images = new List<string>();
        restore = IntPtr.Zero;
        if (parts.Length > 3 && parts[3].Length > 0)
            images = Encoding.UTF8.GetString(Convert.FromBase64String(parts[3]))
                .Split('\n').Where(x => x.Trim().Length > 0).ToList();
        long h;
        if (parts.Length > 4 && long.TryParse(parts[4], out h)) restore = new IntPtr(h);
    }

    static long Hwnd(List<El> wins)
    {
        foreach (var w in wins)
            try { return w.Hwnd.ToInt64(); } catch { }
        return 0;
    }

    static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        Console.InputEncoding = new UTF8Encoding(false);
        SetProcessDPIAware();     // 화면 읽기 좌표와 클릭 좌표를 같은 실제 픽셀로 맞춘다
        int parent = args.Length > 0 ? int.Parse(args[0]) : -1;

        var reader = new Thread(() =>
        {
            try
            {
                string line;
                while ((line = Console.In.ReadLine()) != null)
                    lock (Lock) Commands.Enqueue(line);
            }
            catch { }
        });
        reader.IsBackground = true;
        reader.Start();

        string last = null;
        var lastSent = DateTime.MinValue;
        while (true)
        {
            if (parent > 0)
            {
                try { Process.GetProcessById(parent); }
                catch { return 0; }   // 로봇이 꺼지면 같이 끝난다
            }

            string cmd = null;
            lock (Lock) if (Commands.Count > 0) cmd = Commands.Dequeue();
            try
            {
                if (cmd != null && cmd.StartsWith("open\t")) Open("ChatGPT", IsGptRow, cmd.Substring(5));
                if (cmd != null && cmd.StartsWith("openclaude\t")) Open("claude", IsClaudeRow, cmd.Substring(11));
                if (cmd != null && cmd.StartsWith("replyclaude\t"))
                {
                    // replyclaude<TAB>세션 제목<TAB>보낼 글(base64, UTF-8)[<TAB>이미지 경로들(base64, 줄바꿈으로 구분)<TAB>돌려놓을 창]
                    // → {"reply":"ok"} 또는 {"reply":"이유"}
                    var parts = cmd.Split('\t');
                    string r;
                    try
                    {
                        List<string> imgs; IntPtr back;
                        ReplyExtras(parts, out imgs, out back);
                        r = Reply(parts[1], Encoding.UTF8.GetString(Convert.FromBase64String(parts[2])), imgs, back);
                    }
                    catch (Exception ex) { r = "보내는 중 오류: " + ex.Message; }
                    Console.Out.WriteLine("{\"reply\":" + Json(r) + "}");
                    Console.Out.Flush();
                }
                if (cmd != null && (cmd.StartsWith("replyvscode\t") || cmd.StartsWith("cardvscode\t")))
                {
                    // replyvscode<TAB>세션 제목<TAB>글(base64) / cardvscode<TAB>세션 제목<TAB>선택지(base64)<TAB>기타(base64)
                    var parts = cmd.Split('\t');
                    string r;
                    try
                    {
                        Func<string, string> dec = x => Encoding.UTF8.GetString(Convert.FromBase64String(x));
                        List<string> imgs; IntPtr back;
                        ReplyExtras(parts, out imgs, out back);
                        r = parts[0] == "replyvscode" ? ReplyVsCode(parts[1], dec(parts[2]), imgs, back)
                            : CardVsCode(parts[1], dec(parts[2]), parts.Length > 3 ? dec(parts[3]) : "");
                    }
                    catch (Exception ex) { r = "보내는 중 오류: " + ex.Message; }
                    Console.Out.WriteLine("{\"reply\":" + Json(r) + "}");
                    Console.Out.Flush();
                }
                if (cmd != null && cmd.StartsWith("gptchat\t"))
                {
                    Console.Out.WriteLine(GptChat(cmd.Substring(8)));
                    Console.Out.Flush();
                }
                if (cmd != null && cmd.StartsWith("replygpt\t"))
                {
                    var parts = cmd.Split('\t');
                    string r;
                    try { r = ReplyGpt(parts[1], Encoding.UTF8.GetString(Convert.FromBase64String(parts[2]))); }
                    catch (Exception ex) { r = "보내는 중 오류: " + ex.Message; }
                    Console.Out.WriteLine("{\"reply\":" + Json(r) + "}");
                    Console.Out.Flush();
                }
                if (cmd != null && cmd.StartsWith("cardclaude\t"))
                {
                    // cardclaude<TAB>세션 제목<TAB>선택지(base64)<TAB>기타 글(base64) → {"reply":"ok"|이유}
                    var parts = cmd.Split('\t');
                    string r;
                    try
                    {
                        Func<string, string> dec = x => Encoding.UTF8.GetString(Convert.FromBase64String(x));
                        r = Card(parts[1], dec(parts[2]), parts.Length > 3 ? dec(parts[3]) : "");
                    }
                    catch (Exception ex) { r = "보내는 중 오류: " + ex.Message; }
                    Console.Out.WriteLine("{\"reply\":" + Json(r) + "}");
                    Console.Out.Flush();
                }
            }
            catch { }

            string msg;
            try
            {
                var gpt = AppWindows("ChatGPT");
                var titles = new List<string>();
                // 화면에 보이는 앱 (Claude 앱·ChatGPT 앱은 띄워 둔 대화까지, VS Code는 패널의 세션이 다 보이므로 앱만)
                var seen = new List<string>();
                string seenSession = "", gptSession = "";
                foreach (var w in gpt)
                {
                    titles.AddRange(WorkingTitles(w, IsGptRow).Where(t => !titles.Contains(t)));
                    // 새 화면은 목록 줄에 '작업 중' 표시가 없다 → 열어 둔 대화가 답하는 중이면 그 제목
                    try
                    {
                        string open = GptAnswering(w) ? GptOpenTitle(w) : "";
                        if (open.Length > 0 && open != "ChatGPT" && !titles.Contains(open)) titles.Add(open);
                    }
                    catch { }
                    if (!seen.Contains("chatgpt") && OnScreen(w.Hwnd))
                    {
                        // 웹 화면 전체(Document)의 이름 = 지금 열어 둔 대화 제목
                        var doc = w.FindFirst(El.Descendants, El.TypeIs(El.Document));
                        seen.Add("chatgpt");
                        gptSession = doc == null ? "" : doc.Name.Trim();
                    }
                }

                var cla = AppWindows("claude");
                var ctitles = new List<string>();
                bool claudeOk = false;
                foreach (var w in AppWindows("Code"))
                    if (!seen.Contains("code") && OnScreen(w.Hwnd)) seen.Add("code");
                foreach (var w in cla)
                {
                    bool chatView, stopShown;
                    string session;
                    ClaudeView(w, out chatView, out stopShown, out session);
                    if (session != null && seenSession == "" && OnScreen(w.Hwnd))
                    {
                        seen.Add("claude");
                        seenSession = session;
                    }
                    if (!chatView) continue;
                    claudeOk = true;
                    var found = WorkingTitles(w, IsClaudeRow);
                    // 목록을 접어 둬서 줄이 안 보여도, 보고 있는 대화가 답하는 중이면 한 줄로 알린다
                    if (found.Count == 0 && stopShown) found.Add("Claude");
                    ctitles.AddRange(found.Where(t => !ctitles.Contains(t)));
                }

                msg = "{\"ok\":" + (gpt.Count > 0 ? "true" : "false") + ",\"hwnd\":" + Hwnd(gpt)
                      + ",\"working\":[" + string.Join(",", titles.Select(Json)) + "]"
                      + ",\"claude_ok\":" + (claudeOk ? "true" : "false") + ",\"claude_hwnd\":" + Hwnd(cla)
                      + ",\"claude\":[" + string.Join(",", ctitles.Select(Json)) + "]"
                      + ",\"seen\":[" + string.Join(",", seen.Select(Json)) + "]"
                      + ",\"seen_session\":" + Json(seenSession) + ",\"seen_gpt\":" + Json(gptSession) + "}";
            }
            catch (Exception)
            {
                msg = null;   // 창이 바뀌는 중이면 다음에 다시
            }

            if (msg != null && (msg != last || (DateTime.Now - lastSent).TotalSeconds > 30))
            {
                Console.Out.WriteLine(msg);
                Console.Out.Flush();
                last = msg;
                lastSent = DateTime.Now;
            }
            // 다 쓴 화면 읽기 요소(COM)를 바로 놓아 준다. 안 하면 .NET 이 언젠가 치울 때까지 앱 쪽 연결이 남는다
            GC.Collect();
            GC.WaitForPendingFinalizers();
            Thread.Sleep(cmd != null ? 300 : 2000);
        }
    }
}
