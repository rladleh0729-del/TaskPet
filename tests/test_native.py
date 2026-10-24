# Native Messaging host가 확장 메시지를 events.jsonl로 옮기고, web-cmd.jsonl 명령을 확장으로 보내는지 시험한다.
#   python tests\test_native.py build\taskpet-native.exe
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

src = os.path.abspath(sys.argv[1])
tmp = tempfile.mkdtemp()
host = os.path.join(tmp, os.path.basename(src))
shutil.copy(src, host)


def frame(obj):
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return struct.pack("<I", len(b)) + b


p = subprocess.Popen([host, "chrome-extension://x/"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
p.stdin.write(frame({"type": "state", "state": "working", "tab": 7, "conv": "abc", "title": "한글 \"제목\""}))
p.stdin.flush()
time.sleep(0.8)

with open(os.path.join(tmp, "web-cmd.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"cmd": "open", "tab": 7, "conv": "abc"}) + "\n")
n = struct.unpack("<I", p.stdout.read(4))[0]
back = json.loads(p.stdout.read(n).decode("utf-8"))
print("확장으로 보낸 명령:", back)
assert back == {"cmd": "open", "tab": 7, "conv": "abc"}

p.stdin.close()               # 브라우저가 연결을 끊으면 끝나야 한다
p.wait(timeout=5)
print("끝난 코드:", p.returncode)

lines = open(os.path.join(tmp, "events.jsonl"), encoding="utf-8").read().splitlines()
rec = json.loads(lines[0])
print("기록:", rec["ev"], rec["d"])
assert rec["ev"] == "web" and rec["d"]["title"] == '한글 "제목"' and rec["d"]["tab"] == 7
print("통과")
