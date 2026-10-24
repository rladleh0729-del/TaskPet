// TaskPet Native Messaging host: 브라우저 확장(TaskPet for ChatGPT)과 TaskPet 로봇을 잇는다.
// 브라우저가 확장의 요청으로 이 프로그램을 띄우고, 표준 입출력으로 [4바이트 길이 + UTF-8 JSON]을 주고받는다.
//   확장 → 여기: {"type":"state","state":"working|done|closed","tab":1,"conv":"...","title":"..."}
//          → 같은 폴더 events.jsonl 에 {"ev":"web","t":ms,"d":{...}} 한 줄 덧붙임 (로봇이 읽음)
//   로봇 → 여기: 같은 폴더 web-cmd.jsonl 에 {"cmd":"open","tab":1,"conv":"..."} 한 줄
//          → 확장에게 그대로 전달 (그 탭을 앞으로 가져옴)
using System;
using System.IO;
using System.Text;
using System.Threading;

class TaskPetNative
{
    static readonly object WriteLock = new object();
    static Stream Out;

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
                    if (t.StartsWith("{")) Send(t);
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
            if (msg.StartsWith("{") && System.Text.RegularExpressions.Regex.IsMatch(
                    msg, "\"type\"\\s*:\\s*\"state\""))
                AppendEvent(dir, msg);
        }
    }
}
