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


assert taskpet.clean_prompt("") == "(이미지)"                  # 이미지만 보냄
assert taskpet.clean_prompt("[Image #1]") == "(이미지)"
assert taskpet.clean_prompt("[Image #1] 이거 봐") == "이거 봐"
assert taskpet.clean_prompt("<system-reminder>...") is None    # 자동 메시지 → 직전 질문 유지
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
assert tr.tasks["c:s1"]["ask"] == "2라운드 더 돌릴까요?" and tr.tasks["c:s1"]["choices"] == []

# 선택지 버튼: 글로 답하는 버튼만 꺼내고(앱 동작 버튼은 뺌), 메시지가 없으면 이름을 보냄
ask_rec = {"timestamp": iso(0), "message": {"content": [
    {"type": "tool_use", "name": "mcp__ccd_turn__wrap_up",
     "input": {"recap": "끝", "ask": "어느 쪽으로 할까요?",
               "actions": [{"label": "A로", "message": "A로 해 줘"}, {"label": "B로"},
                           {"action": "commit"}]}}]}}
tp2 = os.path.join(tmp, "ask.jsonl")
with open(tp2, "w", encoding="utf-8") as f:
    f.write(json.dumps(ask_rec) + "\n")
got = taskpet.claude_turn_asks(tp2, time.time() - 5)
assert got == {"ask": "어느 쪽으로 할까요?",
               "choices": [{"label": "A로", "message": "A로 해 줘"},
                           {"label": "B로", "message": "B로"}]}, got
ask_rec["message"]["content"][0]["input"]["actions"] = json.dumps([{"label": "네"}])   # 글(JSON)로 온 목록
with open(tp2, "w", encoding="utf-8") as f:
    f.write(json.dumps(ask_rec) + "\n")
assert taskpet.claude_turn_asks(tp2, time.time() - 5)["choices"] == [{"label": "네", "message": "네"}]

# 질문 카드(AskUserQuestion): 답이 없으면 질문·선택지, 답(tool_result)이 생기면 None
tp3 = os.path.join(tmp, "card.jsonl")
card_use = {"message": {"content": [{"type": "tool_use", "id": "tu1", "name": "AskUserQuestion",
            "input": {"questions": [{"question": "무엇을 할까요?", "multiSelect": False,
                                     "options": [{"label": "A안", "description": "설명"},
                                                 {"label": "B안"}]}]}}]}}
with open(tp3, "w", encoding="utf-8") as f:
    f.write(json.dumps(card_use) + "\n")
got = taskpet.claude_pending_card(tp3)
assert got == {"ask": "무엇을 할까요?", "card": True,
               "choices": [{"label": "A안", "message": "A안"}, {"label": "B안", "message": "B안"}]}, got
with open(tp3, "a", encoding="utf-8") as f:
    f.write(json.dumps({"message": {"content": [{"type": "tool_result", "tool_use_id": "tu1"}]}}) + "\n")
assert taskpet.claude_pending_card(tp3) is None
card_use["message"]["content"][0]["id"] = "tu2"
card_use["message"]["content"][0]["input"]["questions"][0]["multiSelect"] = True
with open(tp3, "a", encoding="utf-8") as f:
    f.write(json.dumps(card_use) + "\n")
assert taskpet.claude_pending_card(tp3)["choices"] == []      # 여러 개 고르기는 질문만
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

# 앱에서 대화를 지우면(기록 파일 삭제) 목록에서도 빠짐
tr.drop_deleted()
assert tr.tasks["c:s1"].get("seen")
os.remove(transcript)
tr.drop_deleted()
assert "c:s1" not in tr.tasks

# Codex: 지운 줄은 기록을 다시 읽어도 안 살아나고, 그 뒤 새 작업만 다시 뜸
def cx(kind, sec_ago):
    tr.codex_record("f", "t1", {"type": "event_msg", "timestamp": iso(sec_ago),
                                "payload": {"type": kind}}, live=True)


cx("task_started", 100)
cx("task_complete", 90)
tr.tasks.pop("x:t1")
tr.dismissed["x:t1"] = time.time()
cx("task_started", 100)                    # 로봇을 다시 켜서 처음부터 읽음
cx("task_complete", 90)
assert "x:t1" not in tr.tasks
cx("task_started", -5)                     # 지운 뒤 새로 시작
assert tr.tasks["x:t1"]["status"] == "working"

# 일반 ChatGPT 채팅: '작업 중' 목록이 바뀌는 대로 시작·완료
events.clear()
tr.codex_titles["t1"] = "코덱스 대화"
gp = lambda *w: tr.apply_chatgpt({"ok": True, "hwnd": 1, "working": list(w)})
gp()                                                 # 처음 보고: 아무것도 없음
gp("새 채팅", "코덱스 대화")                        # 시작 (Codex 제목은 무시)
assert tr.tasks["g:새 채팅"]["status"] == "working" and "g:코덱스 대화" not in tr.tasks
gp("1분간 생각 테스트")                              # 답하는 중 제목이 바뀜 → 같은 줄로 이어짐
assert "g:새 채팅" not in tr.tasks and tr.tasks["g:1분간 생각 테스트"]["status"] == "working"
tr.apply_chatgpt({"ok": False, "hwnd": 0, "working": []})   # 창이 잠깐 안 보여도 그대로
assert tr.tasks["g:1분간 생각 테스트"]["status"] == "working"
gp()                                                 # 끝남
assert tr.tasks["g:1분간 생각 테스트"]["status"] == "done"
assert events == ["start", "done"], events

# 브라우저 chatgpt.com (확장 → 연결 프로그램 → events.jsonl 의 "web" 신호)
events.clear()
def web(state, sec_ago=0, **d):
    tr.claude_event({"ev": "web", "t": int((time.time() - sec_ago) * 1000),
                     "d": {"type": "state", "state": state, "tab": 5, **d}})
web("working", title="새 채팅")
web("working", title="웹 시험 대화", conv="c-123")    # 답하는 도중 제목·주소가 생김 → 같은 줄
assert tr.tasks["w:5"]["status"] == "working" and tr.tasks["w:5"]["title"] == "웹 시험 대화"
gp("웹 시험 대화")                                   # 데스크톱 앱 목록에도 보여도 한 번만
assert "g:웹 시험 대화" not in tr.tasks
web("done", title="웹 시험 대화", conv="c-123")
assert tr.tasks["w:5"]["status"] == "done" and tr.tasks["w:5"]["conv"] == "c-123"
web("working", sec_ago=120, title="옛 신호")         # 로봇을 다시 켜서 읽은 옛 신호는 소리 없음
web("closed")                                        # 탭을 닫으면 줄이 빠짐
assert "w:5" not in tr.tasks
assert events == ["start", "done"], events

# 브라우저 gemini.google.com: 같은 신호에 site=gemini → 보라 "Gemini" 줄, 주소 기억
events.clear()
web("working", tab=7, site="gemini", title="새 채팅", url="https://gemini.google.com/app")
web("done", tab=7, site="gemini", title="제미나이 시험", conv="abc123",
    url="https://gemini.google.com/app/abc123")
g = tr.tasks["w:7"]
assert g["src"] == "gemini" and g["status"] == "done" and g["title"] == "제미나이 시험", g
assert g["url"].endswith("/app/abc123") and taskpet.SRC_LABEL[g["src"]] == "Gemini"
assert events == ["start", "done"], events

# claude.ai → 주황 "Claude 웹", grok.com → "Grok"
web("working", tab=8, site="claude", title="클로드 웹 시험", url="https://claude.ai/chat/x1")
web("working", tab=9, site="grok", title="", url="https://grok.com/")
assert tr.tasks["w:8"]["src"] == "claudeweb" and taskpet.SRC_LABEL["claudeweb"] == "Claude 웹"
assert tr.tasks["w:9"]["src"] == "grok" and tr.tasks["w:9"]["title"] == "Grok"
web("done", tab=8, site="claude", title="클로드 웹 시험")
assert tr.tasks["w:8"]["status"] == "done" and tr.tasks["w:8"]["url"].endswith("/chat/x1")
web("working", tab=10, site="kimi", title="안녕", url="https://www.kimi.ai/chat/k1")
assert tr.tasks["w:10"]["src"] == "kimi" and taskpet.SRC_LABEL["kimi"] == "Kimi"

# 브라우저 두 개: 같은 탭 번호라도 브라우저가 다르면 다른 줄, 닫기도 그 브라우저 것만
web("working", tab=20, site="grok", title="그록 대화", browser="brave", browser_path=r"C:\b\brave.exe")
web("working", tab=20, site="gemini", title="제미나이 대화", browser="chrome")
assert tr.tasks["w:brave:20"]["title"] == "그록 대화" and tr.tasks["w:chrome:20"]["title"] == "제미나이 대화"
assert tr.tasks["w:brave:20"]["browser_path"].endswith("brave.exe")
web("closed", tab=20, browser="chrome")
assert "w:chrome:20" not in tr.tasks and "w:brave:20" in tr.tasks

# 끝난 뒤에 붙은 제목은 소리 없이 고쳐짐
events.clear()
web("working", tab=21, site="chatgpt", title="새 채팅", browser="brave")
web("done", tab=21, site="chatgpt", title="새 채팅", browser="brave")
web("done", tab=21, site="chatgpt", title="여행 계획", conv="c9", browser="brave")
assert tr.tasks["w:brave:21"]["title"] == "여행 계획" and tr.tasks["w:brave:21"]["conv"] == "c9"
assert events == ["start", "done"], events

# Claude 데스크톱 앱 일반 채팅: '실행 중' 목록으로 시작·완료, Code 탭(claude_ok=False)일 땐 판단 보류
events.clear()
cl = lambda ok, *w: tr.apply_chatgpt({"ok": False, "claude_ok": ok, "claude": list(w)})
cl(True)                                             # 처음 보고
cl(True, "번역 부탁", "작업 상태 표시 프로그램")      # 시작 (Claude Code 세션과 같은 제목은 무시)
tr.tasks["c:zz"] = {"src": "claude", "title": "작업 상태 표시 프로그램", "status": "working"}
cl(True, "번역 부탁", "작업 상태 표시 프로그램")
assert tr.tasks["k:번역 부탁"]["status"] == "working" and "k:작업 상태 표시 프로그램" not in tr.tasks
cl(False)                                            # Code 탭으로 옮김 → 그대로
assert tr.tasks["k:번역 부탁"]["status"] == "working"
cl(True)                                             # 채팅 화면에서 끝남
assert tr.tasks["k:번역 부탁"]["status"] == "done" and taskpet.SRC_LABEL["claudechat"] == "Claude 채팅"
assert events.count("done") == 1, events
del tr.tasks["c:zz"]

# 새 버전 알림: 지금보다 새것만, 지우면 안 뜸, 따라잡으면 사라짐
V = taskpet.VERSION
assert taskpet.version_tuple("v1.10.0") > taskpet.version_tuple("v1.9.9")
up = lambda tag: tr.apply_update(tag, "https://x/TaskPet.exe", 10)
up("v0.0.1")
assert not [k for k in tr.tasks if k.startswith("u:")]
up("v99.0.0")
assert tr.tasks["u:v99.0.0"]["status"] == "update" and tr.tasks["u:v99.0.0"]["title"] == "새 버전 99.0.0"
up("v99.0.1")                                       # 더 새 버전이 나오면 줄이 바뀜
assert "u:v99.0.0" not in tr.tasks and "u:v99.0.1" in tr.tasks
tr.tasks.pop("u:v99.0.1"); tr.dismissed["u:v99.0.1"] = time.time()
up("v99.0.1")
assert "u:v99.0.1" not in tr.tasks                 # ✕로 지운 버전은 다시 안 뜸
up("v" + V)
assert not [k for k in tr.tasks if k.startswith("u:")]

# Claude 앱(MSIX) 가상 공간에 쓰인 신호도 읽음. 처음 본 파일의 옛 기록은 건너뜀
pkg = os.path.join(tmp, "Packages", "Claude_x", "LocalCache", "Local", "TaskPet")
os.makedirs(pkg)
taskpet.PKG_EVENTS = os.path.join(tmp, "Packages", "*", "LocalCache", "Local", "TaskPet",
                                  "events.jsonl")
pfile = os.path.join(pkg, "events.jsonl")
def pkg_ev(name, sid):
    with open(pfile, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ev": name, "t": int(time.time() * 1000),
                            "d": {"session_id": sid, "transcript_path": "", "cwd": r"C:\p"}}) + "\n")
pkg_ev("start", "old")
tr.read_claude_events()
assert "c:old" not in tr.tasks
pkg_ev("resume", "s9")
tr.read_claude_events()
assert tr.tasks["c:s9"]["status"] == "working", tr.tasks.get("c:s9")

# 브라우저 확장 설치 권유: 브라우저는 있는데 확장이 없을 때만, 확장(스토어판 폴더·개발판 설정)이 있으면 안 뜸
old_local = os.environ.get("LOCALAPPDATA", "")
fake = os.path.join(tmp, "local")
prof = os.path.join(fake, "Google", "Chrome", "User Data", "Default")
os.makedirs(prof)
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "nobrowser")
assert taskpet.browser_extension_state() == (False, False)
os.environ["LOCALAPPDATA"] = fake
assert taskpet.browser_extension_state() == (True, False)
with open(os.path.join(prof, "Secure Preferences"), "w") as f:
    f.write('{"extensions":{"settings":{"%s":{}}}}' % taskpet.EXT_IDS[1])
assert taskpet.browser_extension_state() == (True, True)
os.remove(os.path.join(prof, "Secure Preferences"))
os.makedirs(os.path.join(prof, "Extensions", taskpet.EXT_IDS[0]))
assert taskpet.browser_extension_state() == (True, True)
os.environ["LOCALAPPDATA"] = old_local
tr.apply_ext_tip(True)
assert tr.tasks["t:ext"]["status"] == "tip"
tr.apply_ext_tip(False)
assert "t:ext" not in tr.tasks

# 마지막 답변: 마지막 도구 사용 뒤의 글만, 굵게·코드 표시는 빼고, 세션을 연 곳도 같이
tp4 = os.path.join(tmp, "answer.jsonl")
recs = [
    {"type": "user", "entrypoint": "claude-desktop", "message": {"role": "user", "content": "질문"}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "먼저 볼게요"}]}},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read"}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
    {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "..."},
                                                   {"type": "text", "text": "## 결과\n**됐어요** `a.py`"}]}},
]
with open(tp4, "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
assert taskpet.claude_last_answer(tp4) == ("## 결과\n**됐어요** `a.py`", "claude-desktop", "", "질문"), taskpet.claude_last_answer(tp4)
# 보여 줄 때: 소제목 굵게, 목록은 •, 빈 줄 뒤 문단은 띄움, 굵게·코드 표시와 표 세로줄은 걷음
assert taskpet.answer_lines("## 결과\n**됐어요** `a.py`\n\n- 하나\n1. 둘\n| a | b |\n|---|---|\n끝") == [
    ("h", "결과"), ("p", "됐어요 a.py"), ("li", "• 하나"), ("li", "1. 둘"), ("p", "a · b"), ("p", "끝")]
turns, more = taskpet.claude_turns(tp4)       # 대화 기록: 내 메시지 + 그 뒤 Claude 글 전부
assert turns == [{"me": "질문", "ai": ["먼저 볼게요", "## 결과\n**됐어요** `a.py`"]}] and not more, turns
with open(tp4, "a", encoding="utf-8") as f:   # 새 메시지가 오면 그 뒤 글만
    f.write(json.dumps({"type": "user", "message": {"content": "다음"}}, ensure_ascii=False) + "\n")
    f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "볼게요"}]}}, ensure_ascii=False) + "\n")
assert taskpet.claude_turns(tp4)[0][-1] == {"me": "다음", "ai": ["볼게요"]}
assert taskpet.fmt_short(35) == "35초" and taskpet.fmt_short(200) == "3분" and taskpet.fmt_short(7300) == "2시간"
# VS Code 세션은 자동 제목(ai-title)이 줄 제목이 된다 (패널에서 그 이름으로 찾음)
with open(tp4, "a", encoding="utf-8") as f:
    f.write(json.dumps({"type": "ai-title", "aiTitle": "인사", "entrypoint": "claude-vscode"}) + "\n")
row = {"id": "nosuch"}
taskpet.Tracker.note_answer(row, tp4)
assert row["entry"] == "claude-vscode" and row["title"] == "인사", row

# 보고 있는 세션은 알리지 않기: VS Code 창이 보이면 VS Code 세션 전부, Claude 앱은 띄워 둔 그 세션만 (둘 다 보일 수도 있음)
from types import SimpleNamespace
pet = SimpleNamespace(settings={}, seen=(("code",), "", ""))
vs = {"src": "claude", "entry": "claude-vscode", "title": "인사"}
app_row = {"src": "claude", "entry": "claude-desktop", "title": "선택지 요청"}
assert taskpet.Pet.viewed(pet, vs) and not taskpet.Pet.viewed(pet, app_row)
pet.seen = (("claude", "code"), "선택지 요청", "")
assert taskpet.Pet.viewed(pet, app_row) and taskpet.Pet.viewed(pet, vs)
assert not taskpet.Pet.viewed(pet, dict(app_row, title="다른 세션"))
# ChatGPT 앱: 띄워 둔 대화(일반 채팅·Codex)만
pet.seen = (("chatgpt",), "", "Join Moltbook")
assert taskpet.Pet.viewed(pet, {"src": "codex", "title": "Join Moltbook"})
assert not taskpet.Pet.viewed(pet, {"src": "chatgpt", "title": "작업 알림 로봇 소개"})
pet.settings["hide_viewed"] = False
assert not taskpet.Pet.viewed(pet, app_row)
print("통과", events)
