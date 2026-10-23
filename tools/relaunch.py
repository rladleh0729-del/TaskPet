# 설치된 TaskPet 로봇을 끄고, Claude Code 세션과 분리된 독립 프로그램으로 다시 띄운다.
# (명령 창에서 그냥 띄우면 세션이 다시 시작될 때 같이 꺼진다)
#   python tools\relaunch.py
import ctypes
import os
import subprocess
import time

DIR = os.path.join(os.environ["LOCALAPPDATA"], "TaskPet")
EXE = os.path.join(DIR, "TaskPet.exe")
FLAG = os.path.join(DIR, "quit.flag")

open(FLAG, "w").close()
for _ in range(30):
    h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, "TaskPetWidget")
    if not h:
        break
    ctypes.windll.kernel32.CloseHandle(h)
    time.sleep(0.1)
os.remove(FLAG)
subprocess.run(["taskkill", "/f", "/im", "TaskPet.exe"], capture_output=True)
time.sleep(1)

# 작업 묶음 탈출 + 새 프로세스 그룹 + 분리
p = subprocess.Popen([EXE], cwd=DIR, close_fds=True,
                     creationflags=0x01000000 | 0x00000200 | 0x00000008)
print("다시 띄움 PID", p.pid)
