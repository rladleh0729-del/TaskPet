# 훅 exe가 받은 JSON을 그대로 한 줄로 기록하는지, 큰 입력은 줄이는지 시험한다.
#   python tests\test_hook.py build\taskpet-hook.exe
import json
import os
import subprocess
import sys
import time

hook = os.path.abspath(sys.argv[1])
events = os.path.join(os.path.dirname(hook), "events.jsonl")
if os.path.exists(events):
    os.remove(events)

t0 = time.time()
r = subprocess.run([hook, "start"], capture_output=True, input=json.dumps(
    {"session_id": "abc", "prompt": '한글 "따옴표" \\ 역슬래시', "cwd": r"C:\x"},
    ensure_ascii=False).encode("utf-8"))
print("출력:", repr(r.stdout), "코드:", r.returncode,
      f"시간: {(time.time() - t0) * 1000:.0f}ms")

big = {"session_id": "abc", "tool_response": "x" * 300000,
       "cwd": r"C:\x", "transcript_path": r"C:\t\abc.jsonl"}
subprocess.run([hook, "resume"], input=json.dumps(big).encode("utf-8"))

with open(events, encoding="utf-8") as f:
    lines = f.readlines()
for line in lines:
    d = json.loads(line)
    print(d["ev"], d["d"])
assert json.loads(lines[0])["d"]["prompt"] == '한글 "따옴표" \\ 역슬래시'
assert "tool_response" not in json.loads(lines[1])["d"]
print("통과")
