// TaskPet Native Messaging host: 브라우저 확장(TaskPet for ChatGPT)과 TaskPet 로봇을 잇는다.
// 브라우저가 확장의 요청으로 이 프로그램을 띄우고, 표준 입출력으로 [4바이트 길이 + UTF-8 JSON]을 주고받는다.
//   확장 → 여기: {"type":"state","state":"working|done|closed","tab":1,"conv":"...","title":"..."}
//          → 같은 폴더 events.jsonl 에 {"ev":"web","t":ms,"d":{...}} 한 줄 덧붙임 (로봇이 읽음)
//   로봇 → 여기: 같은 폴더 web-cmd.jsonl 에 {"cmd":"open","tab":1,"conv":"...","browser":"chrome"} 한 줄
//          → 확장에게 그대로 전달 (그 탭을 앞으로 가져옴)
// 브라우저마다 이 프로그램이 하나씩 뜨므로, 자기를 띄운 브라우저(brave·chrome·msedge…)를 알아내
// 신호에 "browser"를 붙이고, 명령도 자기 브라우저 것만 넘긴다 (탭 번호는 브라우저마다 따로라서).
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

class TaskPetNative
{
    static readonly object WriteLock = new object();
    static Stream Out;
    static string Browser = "";       // 예: "brave", "chrome", "msedge"
    static string BrowserPath = "";

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct PROCESSENTRY32
    {
        public uint dwSize, cntUsage, th32ProcessID;
        public IntPtr th32DefaultHeapID;
        public uint th32ModuleID, cntThreads, th32ParentProcessID;
        public int pcPriClassBase;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExeFile;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern bool Process32FirstW(IntPtr snap, ref PROCESSENTRY32 e);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern bool Process32NextW(IntPtr snap, ref PROCESSENTRY32 e);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);

    // 부모를 거슬러 올라가 cmd·conhost(브라우저가 이 프로그램을 띄울 때 끼는 것)가 아닌 첫 프로세스 = 브라우저
    static void FindBrowser()
    {
        var parent = new System.Collections.Generic.Dictionary<int, int>();
        var name = new System.Collections.Generic.Dictionary<int, string>();
        IntPtr snap = CreateToolhelp32Snapshot(2, 0);   // TH32CS_SNAPPROCESS
        if (snap == IntPtr.Zero || snap == new IntPtr(-1)) return;
        try
        {
            var e = new PROCESSENTRY32();
            e.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
            for (bool ok = Process32FirstW(snap, ref e); ok; ok = Process32NextW(snap, ref e))
            {
                parent[(int)e.th32ProcessID] = (int)e.th32ParentProcessID;
                name[(int)e.th32ProcessID] = e.szExeFile ?? "";
            }
        }
        finally { CloseHandle(snap); }
        int pid = Process.GetCurrentProcess().Id;
        for (int i = 0; i < 6 && parent.ContainsKey(pid); i++)
        {
            pid = parent[pid];
            string n;
            if (!name.TryGetValue(pid, out n)) return;
            n = Path.GetFileNameWithoutExtension(n).ToLowerInvariant();
            if (n == "cmd" || n == "conhost") continue;
            Browser = n;
            try { BrowserPath = Process.GetProcessById(pid).MainModule.FileName; } catch { }
            return;
        }
    }

    static string Json(string s)
    {
        return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    static void Send(string json)
    {
        byte[] body = Encoding.UTF8.GetBytes(json);
        lock (WriteLock)
        {
            Out.Write(BitConverter.GetBytes(body.Length), 0, 4);
            Out.Write(body, 0, body.Length);
            Out.Flush();
        }
    }

    static bool ReadExactly(Stream s, byte[] buf, int n)
    {
        int got = 0;
        while (got < n)
        {
            int r = s.Read(buf, got, n - got);
            if (r <= 0) return false;
            got += r;
        }
        return true;
    }

    static void AppendEvent(string dir, string msg)
    {
        long ms = (long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalMilliseconds;
        byte[] line = new UTF8Encoding(false).GetBytes(
            "{\"ev\":\"web\",\"t\":" + ms + ",\"d\":" + msg.Replace("\r", " ").Replace("\n", " ") + "}\n");
        string path = Path.Combine(dir, "events.jsonl");
        for (int k = 0; k < 25; k++)
        {
            try
            {
                using (var f = new FileStream(path, FileMode.Append, FileAccess.Write,
                                              FileShare.ReadWrite | FileShare.Delete))
                    f.Write(line, 0, line.Length);
                return;
            }
            catch (IOException) { Thread.Sleep(20); }
        }
    }

    // 로봇이 web-cmd.jsonl 에 적은 명령을 확장에게 넘긴다 (켜진 뒤 새로 적힌 것만)
    static void WatchCommands(string dir)
    {
        string path = Path.Combine(dir, "web-cmd.jsonl");
        long off = File.Exists(path) ? new FileInfo(path).Length : 0;
        var rest = new StringBuilder();
        while (true)
        {
            Thread.Sleep(400);
            try
            {
                if (!File.Exists(path)) { off = 0; continue; }
                long len = new FileInfo(path).Length;
                if (len < off) off = 0;
                if (len == off) continue;
                using (var f = new FileStream(path, FileMode.Open, FileAccess.Read,
                                              FileShare.ReadWrite | FileShare.Delete))
                {
                    f.Seek(off, SeekOrigin.Begin);
                    var buf = new byte[len - off];
                    int n = f.Read(buf, 0, buf.Length);
                    off += n;
                    rest.Append(Encoding.UTF8.GetString(buf, 0, n));
                }
                string all = rest.ToString();
                int cut = all.LastIndexOf('\n');
                if (cut < 0) continue;
                rest.Clear().Append(all.Substring(cut + 1));
                foreach (var line in all.Substring(0, cut).Split('\n'))
                {
                    string t = line.Trim();
                    if (!t.StartsWith("{")) continue;
                    // 다른 브라우저에게 온 명령은 넘기지 않는다 (예전 로봇처럼 browser 가 없으면 넘김)
                    var m = Regex.Match(t, "\"browser\"\\s*:\\s*\"([^\"]*)\"");
                    if (m.Success && m.Groups[1].Value.Length > 0 && Browser.Length > 0
                        && m.Groups[1].Value != Browser) continue;
                    Send(t);
                }
            }
            catch { }
        }
    }

    static int Main(string[] args)
    {
        string dir = Path.GetDirectoryName(
            System.Reflection.Assembly.GetExecutingAssembly().Location);
        Out = Console.OpenStandardOutput();
        var input = Console.OpenStandardInput();
        try { FindBrowser(); } catch { }

        var watcher = new Thread(() => WatchCommands(dir));
        watcher.IsBackground = true;
        watcher.Start();

        var head = new byte[4];
        while (true)
        {
            if (!ReadExactly(input, head, 4)) return 0;       // 브라우저가 연결을 끊음
            int len = BitConverter.ToInt32(head, 0);
            if (len <= 0 || len > 1024 * 1024) return 1;
            var body = new byte[len];
            if (!ReadExactly(input, body, len)) return 0;
            string msg = Encoding.UTF8.GetString(body).Trim();
            if (msg.StartsWith("{") && Regex.IsMatch(msg, "\"type\"\\s*:\\s*\"state\""))
            {
                // 어느 브라우저 탭인지 붙여 둔다
                if (Browser.Length > 0)
                    msg = "{\"browser\":" + Json(Browser) + ",\"browser_path\":" + Json(BrowserPath)
                          + (msg.Length > 2 ? "," : "") + msg.Substring(1);
                AppendEvent(dir, msg);
            }
        }
    }
}
