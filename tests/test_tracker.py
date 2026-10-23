# Tracker가 백그라운드 작업이 남은 턴을 '완료'로 치지 않는지, 지운 세션이 다시 움직이면 되살아나는지 시험한다.
#   python tests\test_tracker.py
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import taskpet  # noqa: E402

tmp = tempfile.mkdtemp()
taskpet.STATE = os.path.join(tmp, "state.json")
taskpet.EVENTS = os.path.join(tmp, "events.jsonl")


def iso(sec_ago):
    return datetime.fromtimestamp(time.time() - sec_ago, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z")


transcript = os.path.join(tmp, "s1.jsonl")
lines = [
    {"timestamp": iso(8 * 3600), "content": "Command running in background with ID: old1"},
    {"content": "Command running in background with ID: notime1"},   # 시각 없음 → 안 셈
    {"timestamp": iso(60), "content": "Command running in background with ID: live1"},
]
with open(transcript, "w", encoding="utf-8") as f:
    for ln in lines:
        f.write(json.dumps(ln) + "\n")

events = []
tr = taskpet.Tracker(lambda kind, key: events.append(kind))
now_ms = int(time.time() * 1000)


def ev(name, **d):
    d.setdefault("session_id", "s1")
    d.setdefault("transcript_path", transcript)
    d.setdefault("cwd", r"C:\proj")
    tr.claude_event({"ev": name, "t": now_ms, "d": d})


ev("start", prompt="학습 돌려 줘")
ev("stop")
e = tr.tasks["c:s1"]
assert e["status"] == "working" and e["bg"] == 1, e      # 옛날 old1은 안 셈, live1만
assert "done" not in events

# 백그라운드 끝남 → 다음 턴 끝 → 완료
with open(transcript, "a", encoding="utf-8") as f:
    f.write(json.dumps({"timestamp": iso(1),
                        "content": "<task-notification>\n<task-id>live1</task-id>"}) + "\n")
ev("stop")
assert tr.tasks["c:s1"]["status"] == "done" and events.count("done") == 1

# 지운 뒤 저절로 다시 일함 → 다시 나타남
del tr.tasks["c:s1"]
ev("resume")
assert tr.tasks["c:s1"]["status"] == "working"

# 지운 뒤 승인 대기 → 빨간 대기로 다시 나타남
del tr.tasks["c:s1"]
ev("wait", message="Claude needs your permission to use Bash")
assert tr.tasks["c:s1"]["status"] == "waiting"

# 한가할 때 오는 알림은 무시
ev("stop")
ev("wait", message="Claude is waiting for your input")
assert tr.tasks["c:s1"]["status"] == "done"

# 턴이 선택 버튼 질문으로 끝나면 → 응답 대기
ev("start", prompt="결과 보고해 줘")
with open(transcript, "a", encoding="utf-8") as f:
    f.write(json.dumps({"timestamp": iso(0), "message": {"content": [
        {"type": "tool_use", "name": "mcp__ccd_turn__wrap_up",
         "input": {"recap": "끝", "ask": "2라운드 더 돌릴까요?"}}]}}) + "\n")
ev("stop")
assert tr.tasks["c:s1"]["status"] == "waiting", tr.tasks["c:s1"]
ev("end")                                   # 앱이 세션을 닫아도 질문 대기는 남음
assert tr.tasks["c:s1"]["status"] == "waiting"

# 답하면 다시 진행 중, 질문 없이 끝나면 완료
time.sleep(1.5)
now_ms = int(time.time() * 1000) + 3000
ev("start", prompt="2라운드 더")
with open(transcript, "a", encoding="utf-8") as f:
    f.write(json.dumps({"timestamp": iso(-3), "message": {"content": [
        {"type": "tool_use", "name": "mcp__ccd_turn__wrap_up", "input": {"recap": "끝"}}]}}) + "\n")
ev("stop")
assert tr.tasks["c:s1"]["status"] == "done", tr.tasks["c:s1"]
print("통과", events)
