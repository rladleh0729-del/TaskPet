// TaskPet ChatGPT watcher: ChatGPT 데스크톱 앱 창을 화면 읽기(UI Automation)로 읽어,
// 왼쪽 대화 목록에서 '작업 중' 표시가 붙은 대화 제목을 2초마다 알려 준다.
// 일반 채팅은 컴퓨터에 기록이 남지 않아서 이 방법으로만 알 수 있다. 창은 읽기만 한다.
//
//   taskpet-chatgpt.exe <TaskPet PID>
//   표준 출력: {"ok":true,"hwnd":1234,"working":["제목",...]}   (바뀔 때, 그리고 30초마다)
//   표준 입력: open<TAB>제목   → 그 대화 줄을 눌러 연다 (사용자가 로봇에서 더블 클릭했을 때만)
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

    static List<AutomationElement> ChatGptWindows()
    {
        var pids = new HashSet<int>(Process.GetProcessesByName("ChatGPT").Select(p => p.Id));
        var list = new List<AutomationElement>();
        if (pids.Count == 0) return list;
        foreach (AutomationElement w in AutomationElement.RootElement.FindAll(
                     TreeScope.Children, Condition.TrueCondition))
        {
            try { if (pids.Contains(w.Current.ProcessId)) list.Add(w); } catch { }
        }
        return list;
    }

    // 사이드바 대화 줄 = ClassName에 sidebar-item 이 들어간 버튼
    static AutomationElement RowOf(AutomationElement e)
    {
        var walker = TreeWalker.ControlViewWalker;
        for (int i = 0; i < 6 && e != null; i++)
        {
            e = walker.GetParent(e);
            if (e == null) break;
            try
            {
                if (e.Current.ControlType == ControlType.Button
                    && (e.Current.ClassName ?? "").Contains("sidebar-item"))
                    return e;
            }
            catch { return null; }
        }
        return null;
    }

    static List<string> WorkingTitles(AutomationElement w)
    {
        var titles = new List<string>();
        var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.StatusBar);
        foreach (AutomationElement s in w.FindAll(TreeScope.Descendants, cond))
        {
            try
            {
                if (string.IsNullOrWhiteSpace(s.Current.Name)) continue;   // '작업 중' 같은 이름이 있는 표시만
                var row = RowOf(s);
                if (row == null) continue;
                string t = (row.Current.Name ?? "").Trim();
                if (t.Length > 0 && !titles.Contains(t)) titles.Add(t);
            }
            catch { }
        }
        return titles;
    }

    static void Open(string title)
    {
        foreach (var w in ChatGptWindows())
        {
            var cond = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
            foreach (AutomationElement b in w.FindAll(TreeScope.Descendants, cond))
            {
                try
                {
                    if (b.Current.Name == title && (b.Current.ClassName ?? "").Contains("sidebar-item"))
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
            if (cmd != null && cmd.StartsWith("open\t"))
            {
                try { Open(cmd.Substring(5)); } catch { }
            }

            string msg;
            try
            {
                var wins = ChatGptWindows();
                var titles = new List<string>();
                long hwnd = 0;
                foreach (var w in wins)
                {
                    if (hwnd == 0) try { hwnd = w.Current.NativeWindowHandle; } catch { }
                    titles.AddRange(WorkingTitles(w).Where(t => !titles.Contains(t)));
                }
                msg = "{\"ok\":" + (wins.Count > 0 ? "true" : "false") + ",\"hwnd\":" + hwnd
                      + ",\"working\":[" + string.Join(",", titles.Select(Json)) + "]}";
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
