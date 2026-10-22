// TaskPet hook: Claude Code가 훅으로 부르면 받은 JSON을 events.jsonl에 한 줄 덧붙이고 끝낸다.
// 판단은 전부 TaskPet.exe가 하므로 여기서는 기록만 한다. 아무것도 출력하지 않는다.
using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

class TaskPetHook
{
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
