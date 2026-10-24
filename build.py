# TaskPet 빌드: 아이콘 만들기 → 훅(C#) 컴파일 → PyInstaller로 TaskPet.exe 한 파일 만들기
#   python build.py   →   dist\TaskPet.exe
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
WPF = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF"


def make_icon(path):
    """로봇 도트를 그대로 아이콘으로."""
    src = open(os.path.join(SRC, "taskpet.py"), encoding="utf-8").read()
    start = src.index("IDLE = [")
    end = src.index("]", start) + 1
    ns = {}
    exec(src[start:end], ns)
    grid = ns["IDLE"]
    palette = {"O": "#f5942b", "D": "#a85a0e", "F": "#2a2230",
               "M": "#ffb15e", "E": "#ffd84d"}
    n = 16
    img = Image.new("RGBA", (n * 16, n * 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox = (n - len(grid[0])) // 2
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != ".":
                d.rectangle([(x + ox) * 16, y * 16, (x + ox + 1) * 16 - 1, (y + 1) * 16 - 1],
                            fill=palette[ch])
    img.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                          (128, 128), (256, 256)])


def main():
    shutil.rmtree(BUILD, ignore_errors=True)
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(DIST, exist_ok=True)

    icon = os.path.join(BUILD, "taskpet.ico")
    make_icon(icon)
    print("아이콘 완료")

    hook = os.path.join(BUILD, "taskpet-hook.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{hook}", f"/win32icon:{icon}",
                    os.path.join(SRC, "hook.cs")], check=True)
    print("훅 완료")

    gpt = os.path.join(BUILD, "taskpet-chatgpt.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{gpt}", f"/win32icon:{icon}",
                    rf"/r:{WPF}\UIAutomationClient.dll", rf"/r:{WPF}\UIAutomationTypes.dll",
                    rf"/r:{WPF}\WindowsBase.dll",
                    os.path.join(SRC, "chatgpt_watch.cs")], check=True)
    print("ChatGPT 감시 완료")

    native = os.path.join(BUILD, "taskpet-native.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{native}", f"/win32icon:{icon}",
                    os.path.join(SRC, "native_host.cs")], check=True)
    print("Native Messaging 연결 완료")

    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", "TaskPet",
        "--icon", icon,
        "--add-binary", f"{hook};.",
        "--add-binary", f"{gpt};.",
        "--add-binary", f"{native};.",
        "--add-data", f"{os.path.join(ROOT, 'extension')};chrome-extension",
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyi"),
        "--specpath", BUILD,
        os.path.join(SRC, "taskpet.py"),
    ], check=True)
    out = os.path.join(DIST, "TaskPet.exe")
    print(f"완료: {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
