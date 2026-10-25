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

    static bool Press(AutomationElement e)
    {
        object p;
        if (e == null || !e.TryGetCurrentPattern(InvokePattern.Pattern, out p)) return false;
        ((InvokePattern)p).Invoke();
        return true;
    }

    // 그 세션으로 화면을 바꾸고(필요하면) 입력창에 글을 넣어 '보내기'를 누른 뒤, 원래 보던 세션으로 돌려놓는다.
    // 돌려주는 값: "ok" 또는 사용자에게 보여 줄 이유
    static string Reply(string title, string text)
    {
        var wins = AppWindows("claude");
        if (wins.Count == 0) return "Claude 앱이 열려 있지 않아요";
        var w = wins[0];
        w.FindAll(TreeScope.Descendants, Condition.TrueCondition);   // 처음 읽을 땐 일부만 보여서 한 번 깨운다
        string back = CurrentSession(w);
        if (back == null) return "Claude 앱을 Code 화면으로 두고 다시 보내 주세요";
        if (back != title)
        {
            if (!Press(SessionRow(w, title))) return "Claude 앱 목록에서 그 세션을 찾지 못했어요";
            for (int i = 0; i < 30 && CurrentSession(w) != title; i++) Thread.Sleep(100);
            if (CurrentSession(w) != title) return "그 세션으로 바꾸지 못했어요";
            Thread.Sleep(300);
        }
        else back = null;                 // 이미 그 세션이면 돌아갈 필요 없음
        string result;
        var ed = ByName(w, "프롬프트", ControlType.Edit);
        object vpo;
        if (ed == null || !ed.TryGetCurrentPattern(ValuePattern.Pattern, out vpo)) result = "입력창을 찾지 못했어요";
        else
        {
            var vp = (ValuePattern)vpo;
            if ((vp.Current.Value ?? "").Trim().Length > 0)
                result = "그 세션 입력창에 쓰던 글이 있어서 보내지 않았어요";
            else
            {
                vp.SetValue(text);
                Thread.Sleep(300);
                string head = text.Trim();
                head = head.Substring(0, Math.Min(10, head.Length));
                if (!(vp.Current.Value ?? "").Contains(head)) result = "입력창에 글을 넣지 못했어요";
                else
                {
                    var send = ByName(w, "보내기", ControlType.Button) ?? ByName(w, "Send", ControlType.Button);
                    if (send == null || !send.Current.IsEnabled || !Press(send))
                    {
                        result = "보내기 버튼을 누르지 못했어요";
                        try { vp.SetValue(""); } catch { }
                    }
                    else result = "ok";
                }
            }
        }
        if (back != null)
        {
            Thread.Sleep(500);
            Press(SessionRow(w, back));      // 원래 보던 세션으로 화면을 돌려놓음
        }
        return result;
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
