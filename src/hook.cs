// TaskPet hook: Claude Code가 훅으로 부르면 받은 JSON을 events.jsonl에 한 줄 덧붙이고 끝낸다.
// 판단은 전부 TaskPet.exe가 하므로 여기서는 기록만 한다. 아무것도 출력하지 않는다.
// 덧붙이는 것: 이 훅을 부른 Claude Code 프로세스 번호·시작 시각("cc_pid","cc_start") —
// 터미널에서 돌아가는 Claude Code 에 로봇이 답을 넣을 때, 그 터미널을 찾는 데 쓴다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

class TaskPetHook
{
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
    [DllImport("kernel32.dll")] static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32FirstW(IntPtr snap, ref PROCESSENTRY32 e);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool Process32NextW(IntPtr snap, ref PROCESSENTRY32 e);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);

    // 부모를 거슬러 올라가 처음 만나는 claude(또는 node) = 이 훅을 부른 Claude Code. 사이에 낀 셸은 건너뜀
    static string CallerInfo()
    {
        var parent = new Dictionary<int, int>();
        var name = new Dictionary<int, string>();
        IntPtr snap = CreateToolhelp32Snapshot(2, 0);
        if (snap == IntPtr.Zero || snap == new IntPtr(-1)) return "";
        try
        {
            var e = new PROCESSENTRY32();
            e.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
            for (bool ok = Process32FirstW(snap, ref e); ok; ok = Process32NextW(snap, ref e))
            {
                parent[(int)e.th32ProcessID] = (int)e.th32ParentProcessID;
                name[(int)e.th32ProcessID] = Path.GetFileNameWithoutExtension(e.szExeFile ?? "").ToLowerInvariant();
            }
        }
        finally { CloseHandle(snap); }
        int pid = Process.GetCurrentProcess().Id;
        for (int i = 0; i < 8 && parent.ContainsKey(pid); i++)
        {
            pid = parent[pid];
            string n;
            if (!name.TryGetValue(pid, out n)) return "";
            if (n != "claude" && n != "node") continue;
            try
            {
                long start = (long)(Process.GetProcessById(pid).StartTime.ToUniversalTime()
                                    - new DateTime(1970, 1, 1)).TotalMilliseconds;
                return "\"cc_pid\":" + pid + ",\"cc_start\":" + start;
            }
            catch { return ""; }
        }
        return "";
    }

    static string Pick(string raw, string key)
    {
        var m = Regex.Match(raw, "\"" + key + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
        return m.Success ? "\"" + key + "\":\"" + m.Groups[1].Value + "\"" : null;
    }

    static int Main(string[] args)
    {
        try
        {
            string ev = args.Length > 0 ? Regex.Replace(args[0], "[^a-z]", "") : "";
            string raw;
            using (var s = Console.OpenStandardInput())
            using (var r = new StreamReader(s, new UTF8Encoding(false)))
                raw = r.ReadToEnd();
            int i = raw.IndexOf('{');
            raw = i >= 0 ? raw.Substring(i).Trim() : "{}";
            raw = raw.Replace("\r", " ").Replace("\n", " ");

            // 도구 결과처럼 큰 데이터는 필요한 값만 남긴다
            if (ev == "resume" || raw.Length > 100000)
            {
                var keep = new StringBuilder("{");
                foreach (var k in new[] { "session_id", "transcript_path", "cwd" })
                {
                    var v = Pick(raw, k);
                    if (v != null) { if (keep.Length > 1) keep.Append(","); keep.Append(v); }
                }
                raw = keep.Append("}").ToString();
            }
            if (raw.Length == 0) raw = "{}";
            string who = "";
            try { who = CallerInfo(); } catch { }
            if (who.Length > 0 && raw.StartsWith("{"))
                raw = "{" + who + (raw.Trim() == "{}" ? "" : ",") + raw.Substring(1);

            string dir = Path.GetDirectoryName(
                System.Reflection.Assembly.GetExecutingAssembly().Location);
            string path = Path.Combine(dir, "events.jsonl");
            long ms = (long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalMilliseconds;
            byte[] line = new UTF8Encoding(false).GetBytes(
                "{\"ev\":\"" + ev + "\",\"t\":" + ms + ",\"d\":" + raw + "}\n");

            for (int k = 0; k < 25; k++)
            {
                try
                {
                    using (var f = new FileStream(path, FileMode.Append, FileAccess.Write,
                                                  FileShare.ReadWrite | FileShare.Delete))
                        f.Write(line, 0, line.Length);
                    break;
                }
                catch (IOException) { System.Threading.Thread.Sleep(20); }
            }
        }
        catch { }
        return 0;
    }
}
