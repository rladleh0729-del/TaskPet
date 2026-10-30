# TaskPet 빌드: 아이콘 만들기 → 훅(C#) 컴파일 → PyInstaller로 폴더판 TaskPet 만들기
#   → 그 폴더를 zip 으로 묶어 설치 프로그램(C#) 안에 넣기
#   python build.py   →   dist\TaskPet.exe (받는 파일은 여전히 이것 하나)
# 예전엔 PyInstaller 한 파일(onefile)이라 켤 때마다 33MB를 임시 폴더에 풀어 4~5초 걸렸다.
# 이제 설치할 때 한 번만 풀어 폴더째 두므로, 설치된 로봇은 풀지 않고 바로 뜬다.
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"


def make_icon(path):
    """화면 로봇과 같은 그림을 아이콘으로 (정사각형 가운데에)."""
    sys.path.insert(0, SRC)
    from taskpet import robot_image
    bot = robot_image("idle", 240, 256, hard=False)
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    img.paste(bot, (8, 0), bot)
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

    # 감시 프로그램은 Windows 의 COM 화면 읽기를 쓴다 → 그 형식 정보(interop)를 만들어 필요한 것만 exe 안에 넣는다(/link)
    gen = os.path.join(BUILD, "uia-interop.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/target:exe", f"/out:{gen}",
                    os.path.join(SRC, "uia_interop.cs")], check=True)
    core = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "UIAutomationCore.dll")
    subprocess.run([gen, core, BUILD], check=True)
    gpt = os.path.join(BUILD, "taskpet-chatgpt.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{gpt}", f"/win32icon:{icon}",
                    rf"/link:{os.path.join(BUILD, 'Interop.UIAutomationClient.dll')}",
                    "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll",
                    os.path.join(SRC, "chatgpt_watch.cs")], check=True)
    print("ChatGPT 감시 완료")

    native = os.path.join(BUILD, "taskpet-native.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{native}", f"/win32icon:{icon}",
                    os.path.join(SRC, "native_host.cs")], check=True)
    print("Native Messaging 연결 완료")

    term = os.path.join(BUILD, "taskpet-term.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:exe",
                    f"/out:{term}", f"/win32icon:{icon}",
                    os.path.join(SRC, "term.cs")], check=True)
    print("터미널 도우미 완료")

    app = os.path.join(BUILD, "app")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", "TaskPet",
        "--icon", icon,
        "--distpath", app, "--workpath", os.path.join(BUILD, "pyi"),
        "--specpath", BUILD,
        os.path.join(SRC, "taskpet.py"),
    ], check=True)
    folder = os.path.join(app, "TaskPet")
    # 훅·감시·연결 프로그램과 브라우저 확장은 설치 폴더 맨 위에 있어야 하는 것들 → _internal 이 아니라 맨 위에
    for f in (hook, gpt, native, term):
        shutil.copy2(f, folder)
    shutil.copytree(os.path.join(ROOT, "extension"), os.path.join(folder, "chrome-extension"))
    print("폴더판 완료")

    pack = os.path.join(BUILD, "app.zip")
    with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, _, files in os.walk(folder):
            for name in files:
                p = os.path.join(base, name)
                z.write(p, os.path.relpath(p, folder))
    out = os.path.join(DIST, "TaskPet.exe")
    subprocess.run([CSC, "/nologo", "/codepage:65001", "/optimize+", "/target:winexe",
                    f"/out:{out}", f"/win32icon:{icon}", f"/resource:{pack},app.zip",
                    "/r:System.IO.Compression.dll", "/r:System.IO.Compression.FileSystem.dll",
                    "/r:System.Windows.Forms.dll",
                    os.path.join(SRC, "setup.cs")], check=True)
    print(f"완료: {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
