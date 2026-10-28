// TaskPet 설치 프로그램 — 사람들이 받는 TaskPet.exe 는 이것 하나.
// 안에 품은 app.zip(파이썬 폴더판 TaskPet: TaskPet.exe + _internal)을 임시 폴더에 풀고 그 TaskPet.exe 를 실행한다.
// 실제 설치(옛 로봇 끄기·설치 폴더로 복사·Claude 훅·시작 프로그램 등록)는 풀린 TaskPet.exe 가 한다
// (설치 폴더가 아닌 곳에서 켜지면 설치 모드). 이렇게 하면 설치된 로봇은 켤 때마다 33MB를 풀지 않아 바로 뜬다.
// (csc v4 = C# 5 문법만)
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

static class Setup
{
    [STAThread]
    static int Main()
    {
        string temp = Path.GetTempPath();
        string dir = Path.Combine(temp, "TaskPet-setup-" + DateTime.Now.Ticks);
        // 풀린 폴더는 설치가 끝나면 스스로 지우지만, 혹시 남은 옛 폴더(10분 넘은 것)는 여기서 치운다
        try
        {
            foreach (string old in Directory.GetDirectories(temp, "TaskPet-setup-*"))
                if (DateTime.Now - Directory.GetCreationTime(old) > TimeSpan.FromMinutes(10))
                    try { Directory.Delete(old, true); } catch (Exception) { }
        }
        catch (Exception) { }
        try
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("app.zip"))
            using (ZipArchive z = new ZipArchive(s, ZipArchiveMode.Read))
                z.ExtractToDirectory(dir);
            ProcessStartInfo psi = new ProcessStartInfo(Path.Combine(dir, "TaskPet.exe"));
            psi.WorkingDirectory = temp;
            psi.UseShellExecute = false;
            // 설치가 끝날 때까지('완료' 상자를 닫을 때까지) 기다렸다가 풀어 둔 폴더를 지운다
            using (Process p = Process.Start(psi))
                p.WaitForExit();
            for (int i = 0; i < 20 && Directory.Exists(dir); i++)
            {
                try { Directory.Delete(dir, true); }
                catch (Exception) { System.Threading.Thread.Sleep(500); }
            }
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show("TaskPet 설치 파일을 풀지 못했습니다.\n\n" + e.Message, "TaskPet",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
