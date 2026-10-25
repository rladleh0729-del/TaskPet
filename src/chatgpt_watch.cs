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
//   Claude 창은 앞으로 가져오지 않는다. 다른 창 뒤에 가려져 있으면 그대로 두고 클릭 신호만 창에 보낸다.
//   최소화돼 있으면 앱이 완전히 쉬어서, 처리하는 동안만 눈에 안 보이게(투명·클릭 통과) 되살렸다가 다시 최소화한다.
//   쓰던 창의 포커스와 마우스는 건드리지 않는다. 단계 기록은 이 프로그램 옆 card.log 에 남긴다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Automation;

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
    static bool ClickOn(AutomationElement e, IntPtr hwnd)
    {
        try
        {
            object si;
            if (e.TryGetCurrentPattern(ScrollItemPattern.Pattern, out si)) ((ScrollItemPattern)si).ScrollIntoView();
            Thread.Sleep(150);
            var r = e.Current.BoundingRectangle;
            if (r.IsEmpty || r.Width < 2) return false;
            var pt = new POINT { X = (int)(r.X + Math.Min(40, r.Width / 2)), Y = (int)(r.Y + r.Height / 2) };
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

    // Claude 창이 맨 앞(사용자가 보고 있음)이면 그대로 둔다.
    // 아니면 가려졌거나 최소화돼 앱이 쉬고 있으므로, 거의 투명(알파 1)하고 클릭이 통과하는 상태로
    // 포커스 없이 맨 위에 올린다 → 눈에는 안 보이고 쓰던 창의 클릭도 그대로 아래 창으로 간다.
    // 되살린 직후 1~2초 동안 보낸 신호는 버려지므로, 받는 쪽에서 반영될 때까지 다시 보낸다.
    static Shown Wake(IntPtr hwnd)
    {
        var s = new Shown { Hwnd = hwnd, Iconic = IsIconic(hwnd) };
        if (!s.Iconic && GetForegroundWindow() == hwnd) return s;
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

    static List<AutomationElement> AppWindows(string process)
    {
        var pids = new HashSet<int>(Process.GetProcessesByName(process).Select(p => p.Id));
        var list = new List<AutomationElement>();
        if (pids.Count == 0) return list;
        foreach (AutomationElement w in AutomationElement.RootElement.FindAll(
                     TreeScope.Children, Condition.TrueCondition))
        {
            try { if (pids.Contains(w.Current.ProcessId)) list.Add(w); } catch { }
        }
        return list;
    }

    // ChatGPT 사이드바 대화 줄 = ClassName에 sidebar-item 이 들어간 버튼
    static bool IsGptRow(AutomationElement e)
    {
        return e.Current.ControlType == ControlType.Button
            && (e.Current.ClassName ?? "").Contains("sidebar-item");
    }

    // Claude 사이드바 대화 줄 = 이름 있는 text-start 버튼 ('…에 대한 더 많은 옵션' 버튼은 제외)
    static bool IsClaudeRow(AutomationElement e)
    {
        if (e.Current.ControlType != ControlType.Button) return false;
        string n = e.Current.Name ?? "";
        return n.Trim().Length > 0 && !n.EndsWith("옵션") && !n.EndsWith("options")
            && (e.Current.ClassName ?? "").Contains("text-start");
    }

    // 상태 표시가 줄 안에 있으면 위로, 줄 바로 옆에 있으면 앞 형제에서 찾는다
    static AutomationElement RowOf(AutomationElement e, Func<AutomationElement, bool> isRow)
    {
        var walker = TreeWalker.ControlViewWalker;
        for (int i = 0; i < 6 && e != null; i++)
        {
            try
            {
                var prev = walker.GetPreviousSibling(e);
                if (prev != null && isRow(prev)) return prev;
                e = walker.GetParent(e);
                if (e != null && isRow(e)) return e;
            }
            catch { return null; }
        }
        return null;
    }

    static List<string> WorkingTitles(AutomationElement w, Func<AutomationElement, bool> isRow)
    {
        var titles = new List<string>();
        var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.StatusBar);
        foreach (AutomationElement s in w.FindAll(TreeScope.Descendants, cond))
        {
            try
            {
                string status = (s.Current.Name ?? "").Trim();
                if (status.Length == 0) continue;   // '작업 중'·'실행 중' 같은 이름이 있는 표시만
                var row = RowOf(s, isRow);
                if (row == null) continue;
                string t = (row.Current.Name ?? "").Trim();
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
    static void ClaudeView(AutomationElement w, out bool chatView, out bool stopShown)
    {
        chatView = true;
        stopShown = false;
        var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
        foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
        {
            string n;
            try { n = b.Current.Name ?? ""; } catch { continue; }
            if (n == "터미널" || n == "세션 패널" || n == "Terminal") chatView = false;
            if (n == "응답 중지" || n == "Stop response") stopShown = true;
        }
    }

    static void Open(string process, Func<AutomationElement, bool> isRow, string title)
    {
        foreach (var w in AppWindows(process))
        {
            var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
            foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
            {
                try
                {
                    if (b.Current.Name == title && isRow(b))
                    {
                        object p;
                        if (b.TryGetCurrentPattern(InvokePattern.Pattern, out p))
                            ((InvokePattern)p).Invoke();
                        return;
                    }
                }
                catch { }
            }
        }
    }

    // ---- Claude 앱 Code 세션에 답 보내기 (창을 앞으로 가져오지 않음) ----
    static AutomationElement ByName(AutomationElement w, string name, ControlType type)
    {
        var cond = new AndCondition(
            new PropertyCondition(AutomationElement.NameProperty, name),
            new PropertyCondition(AutomationElement.ControlTypeProperty, type));
        return w.FindFirst(TreeScope.Descendants, cond);
    }

    // 지금 화면의 세션 제목 = "제목, 세션 이름 바꾸기" 버튼
    static string CurrentSession(AutomationElement w)
    {
        var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
        foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
        {
            string n;
            try { n = b.Current.Name ?? ""; } catch { continue; }
            foreach (var tail in new[] { ", 세션 이름 바꾸기", ", Rename session" })
                if (n.EndsWith(tail)) return n.Substring(0, n.Length - tail.Length);
        }
        return null;
    }

    // 왼쪽 목록의 세션 줄 (이름이 제목과 같거나 "제목 Claude 시작 위치: …"처럼 뒤에 덧붙은 것)
    static AutomationElement SessionRow(AutomationElement w, string title)
    {
        var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
        foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
        {
            try
            {
                string n = b.Current.Name ?? "";
                if ((n == title || n.StartsWith(title + " ")) && IsClaudeRow(b)) return b;
            }
            catch { }
        }
        return null;
    }

    // 그 세션으로 화면을 바꾸고(필요하면) 입력창에 글을 넣어 '보내기'를 누른 뒤, 원래 보던 세션으로 돌려놓는다.
    // 돌려주는 값: "ok" 또는 사용자에게 보여 줄 이유
    // 창을 안 보이게 깨우고 → 그 세션으로 바꾸고 → work → 원래 세션으로 돌려놓고 → 창도 원래대로
    static string InSession(string title, Func<AutomationElement, string> work)
    {
        var wins = AppWindows("claude");
        if (wins.Count == 0) return "Claude 앱이 열려 있지 않아요";
        var w = wins[0];
        Shown shown = null;
        try
        {
            Log("시작: " + title);
            var hwnd = new IntPtr(w.Current.NativeWindowHandle);
            shown = Wake(hwnd);
            if (shown.Ghost) Log(shown.Iconic ? "최소화돼 있어서 안 보이게 되살림" : "뒤에 있어서 안 보이게 깨움");
            w.FindAll(TreeScope.Descendants, Condition.TrueCondition);   // 처음 읽을 땐 일부만 보여서 한 번 깨운다
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

    // 입력창(다음 단계 상자 답)에 글을 넣고 '보내기'
    static string Reply(string title, string text)
    {
        return InSession(title, w =>
        {
            var ed = ByName(w, "프롬프트", ControlType.Edit);
            object vpo;
            if (ed == null || !ed.TryGetCurrentPattern(ValuePattern.Pattern, out vpo)) return "입력창을 찾지 못했어요";
            var vp = (ValuePattern)vpo;
            if ((vp.Current.Value ?? "").Trim().Length > 0) return "그 세션 입력창에 쓰던 글이 있어서 보내지 않았어요";
            var hwnd = new IntPtr(w.Current.NativeWindowHandle);
            string head = text.Trim();
            head = head.Substring(0, Math.Min(10, head.Length));
            // 입력창을 클릭 신호로 고르고 글자를 신호로 넣는다 (화면 읽기로 넣으면 앱이 창을 앞으로 가져옴)
            if (!ClickOn(ed, hwnd)) return "입력창 자리를 찾지 못했어요";
            Thread.Sleep(200);
            TypeText(hwnd, text);
            string got = "";
            bool put = WaitFor(() => (got = (vp.Current.Value ?? "")).Contains(head), 3000);
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
                AutomationElement send = null;
                WaitFor(() => (send = ByName(w, "보내기", ControlType.Button) ?? ByName(w, "Send", ControlType.Button)) != null
                              && send.Current.IsEnabled, 3000);
                if (send == null || !send.Current.IsEnabled || !ClickOn(send, hwnd)) break;
                if (WaitFor(() => !(vp.Current.Value ?? "").Contains(head), 2000)) { Log("보냄"); return "ok"; }
            }
            Erase(hwnd, (vp.Current.Value ?? "").Length + 2);
            return "보내기 버튼을 누르지 못했어요";
        });
    }

    // 질문 카드(AskUserQuestion)에서 선택지(또는 '기타' + 글)를 고르고, 골라진 게 확인되면 '제출'
    static string Card(string title, string label, string other)
    {
        return InSession(title, w =>
        {
            bool isOther = !string.IsNullOrEmpty(other);
            AutomationElement opt = null;
            var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
            foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
            {
                string n;
                try { n = b.Current.Name ?? ""; } catch { continue; }
                bool hit = isOther ? n == "기타" || n == "Other"
                                   : n == label || n.StartsWith(label + " ");
                object tpo;
                if (hit && b.TryGetCurrentPattern(TogglePattern.Pattern, out tpo)) { opt = b; break; }
            }
            if (opt == null) return "그 세션에서 질문 카드를 찾지 못했어요 (이미 답했을 수 있어요)";
            var hwnd = new IntPtr(w.Current.NativeWindowHandle);
            var tp = (TogglePattern)opt.GetCurrentPattern(TogglePattern.Pattern);
            Log("선택지 찾음: " + opt.Current.Name + " / 상태 " + tp.Current.ToggleState);
            // 막 되살린 창은 처음 1~2초의 클릭을 버리므로(나중에 처리되지도 않음) 골라질 때까지 0.7초마다 다시 누른다
            bool on = tp.Current.ToggleState == ToggleState.On;
            for (int k = 0; k < 14 && !on; k++)
            {
                if (!ClickOn(opt, hwnd)) return "선택지 자리를 찾지 못했어요";
                on = WaitFor(() => tp.Current.ToggleState == ToggleState.On, 700);
                Log("선택지 클릭 " + (k + 1) + "번째 → " + (on ? "골라짐" : "아직"));
            }
            if (!on) return "선택이 확인되지 않아 제출하지 않았어요";
            if (isOther)
            {
                AutomationElement box = null;
                WaitFor(() => (box = ByName(w, "기타 옵션", ControlType.Edit)) != null, 3000);
                object vpo;
                if (box == null || !box.TryGetCurrentPattern(ValuePattern.Pattern, out vpo))
                    return "기타 입력칸을 찾지 못해 제출하지 않았어요";
                var vp = (ValuePattern)vpo;
                string head = other.Trim();
                head = head.Substring(0, Math.Min(10, head.Length));
                if (!ClickOn(box, hwnd)) return "기타 입력칸 자리를 찾지 못했어요";
                Thread.Sleep(200);
                Erase(hwnd, (vp.Current.Value ?? "").Length);   // 전에 써 둔 글이 있으면 비운다
                TypeText(hwnd, other);
                if (!WaitFor(() => (vp.Current.Value ?? "").Contains(head), 3000))
                    return "기타 입력칸에 글을 넣지 못해 제출하지 않았어요";
            }
            // 제출되면 카드(제출 버튼)가 사라진다. 남아 있으면 아직 안 간 것이라 다시 누른다
            for (int k = 0; k < 3; k++)
            {
                var submit = ByName(w, "제출", ControlType.Button) ?? ByName(w, "Submit", ControlType.Button);
                if (submit == null) return k == 0 ? "제출 버튼을 찾지 못했어요" : "ok";
                if (!submit.Current.IsEnabled || !ClickOn(submit, hwnd)) return "제출 버튼을 누르지 못했어요";
                Log("제출 클릭 " + (k + 1) + "번째");
                if (WaitFor(() => ByName(w, "제출", ControlType.Button) == null
                                  && ByName(w, "Submit", ControlType.Button) == null, 2500)) return "ok";
            }
            return "제출이 확인되지 않았어요. Claude 앱에서 확인해 주세요";
        });
    }

    static long Hwnd(List<AutomationElement> wins)
    {
        foreach (var w in wins)
            try { return w.Current.NativeWindowHandle; } catch { }
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
                    // replyclaude<TAB>세션 제목<TAB>보낼 글(base64, UTF-8) → {"reply":"ok"} 또는 {"reply":"이유"}
                    var parts = cmd.Split('\t');
                    string r;
                    try { r = Reply(parts[1], Encoding.UTF8.GetString(Convert.FromBase64String(parts[2]))); }
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
                foreach (var w in gpt)
                    titles.AddRange(WorkingTitles(w, IsGptRow).Where(t => !titles.Contains(t)));

                var cla = AppWindows("claude");
                var ctitles = new List<string>();
                bool claudeOk = false;
                foreach (var w in cla)
                {
                    bool chatView, stopShown;
                    ClaudeView(w, out chatView, out stopShown);
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
                      + ",\"claude\":[" + string.Join(",", ctitles.Select(Json)) + "]}";
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
            Thread.Sleep(cmd != null ? 300 : 2000);
        }
    }
}
