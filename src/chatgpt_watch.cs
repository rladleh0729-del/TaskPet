// TaskPet chat watcher: ChatGPT·Claude 데스크톱 앱 창을 화면 읽기(UI Automation)로 읽어,
// 왼쪽 대화 목록에서 '작업 중'(ChatGPT) / '실행 중'(Claude) 표시가 붙은 대화 제목을 2초마다 알려 준다.
// 일반 채팅은 컴퓨터에 기록이 남지 않아서 이 방법으로만 알 수 있다. 창은 읽기만 한다.
//
//   taskpet-chatgpt.exe <TaskPet PID>
//   표준 출력: {"ok":true,"hwnd":1234,"working":["제목",...],
//               "claude_ok":true,"claude_hwnd":5678,"claude":["제목",...]}   (바뀔 때, 그리고 30초마다)
//     ok / claude_ok 가 false 면 그 앱 창이 없거나 채팅 목록이 안 보이는 화면 → 판단을 미룬다
//   표준 입력: open<TAB>제목 / openclaude<TAB>제목   → 그 대화 줄을 눌러 연다 (로봇에서 더블 클릭했을 때만)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading;
using System.Windows.Automation;

class ChatGptWatch
{
    static readonly object Lock = new object();
    static readonly Queue<string> Commands = new Queue<string>();

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
