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
# 로봇에서 펼쳐 보는 탭의 대화 글 → web-chat 파일 (두 번 오면 나중 것으로 덮음), 보낸 답 결과 → events.jsonl
p.stdin.write(frame({"type": "chat", "tab": 7, "working": True, "msgs": [["me", "처음"]]}))
p.stdin.write(frame({"type": "chat", "tab": 7, "working": False, "msgs": [["me", "안녕\n둘째 줄"], ["ai", "반가워요 \"따옴표\""]]}))
p.stdin.write(frame({"type": "sent", "tab": 7, "id": 3, "ok": False, "error": "draft"}))
p.stdin.flush()
time.sleep(0.8)

# 이 시험에서는 연결 프로그램을 띄운 쪽(파이썬)이 '브라우저'다.
# 다른 브라우저(chrome)에게 온 명령은 넘기지 않고, 자기 것(python)·브라우저 표시 없는 것은 넘긴다
me = os.path.splitext(os.path.basename(sys.executable))[0].lower()
with open(os.path.join(tmp, "web-cmd.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"cmd": "open", "tab": 1, "browser": "chrome-other"}) + "\n")
    f.write(json.dumps({"cmd": "open", "tab": 7, "conv": "abc", "browser": me}) + "\n")
    f.write(json.dumps({"cmd": "open", "tab": 8}) + "\n")
got = []
for _ in range(2):
    n = struct.unpack("<I", p.stdout.read(4))[0]
    got.append(json.loads(p.stdout.read(n).decode("utf-8")))
print("확장으로 보낸 명령:", got)
assert [g["tab"] for g in got] == [7, 8], got

p.stdin.close()               # 브라우저가 연결을 끊으면 끝나야 한다
p.wait(timeout=5)
print("끝난 코드:", p.returncode)

lines = open(os.path.join(tmp, "events.jsonl"), encoding="utf-8").read().splitlines()
rec = json.loads(lines[0])
print("기록:", rec["ev"], rec["d"])
assert rec["ev"] == "web" and rec["d"]["title"] == '한글 "제목"' and rec["d"]["tab"] == 7
assert rec["d"]["browser"] == me and rec["d"]["browser_path"].lower().endswith(".exe"), rec["d"]
assert len(lines) == 2, lines                       # 대화 글은 events.jsonl 에 안 들어감
sent = json.loads(lines[1])["d"]
assert sent["type"] == "sent" and sent["error"] == "draft" and sent["browser"] == me, sent
chat = json.load(open(os.path.join(tmp, "web-chat", f"{me}-7.json"), encoding="utf-8"))
print("대화 파일:", chat)
assert chat["msgs"] == [["me", "안녕\n둘째 줄"], ["ai", '반가워요 "따옴표"']] and chat["working"] is False
assert not [f for f in os.listdir(os.path.join(tmp, "web-chat")) if f.endswith(".tmp")]
print("통과")
