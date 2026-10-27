# 소개 사이트·웹 스토어용 '실제 사용 화면'을 진짜 TaskPet 코드로 그려 찍는다.
#   python tools\make_scenes.py      →   dist\scenes\{list,ext,chat}_{ko,en}.png, robot.png
# 단색 배경(초록 1,255,1) 위에 로봇·말풍선을 띄워 찍고 그 배경색만 투명으로 바꾼다.
# (말풍선·로봇 가장자리는 원래 반투명 없이 딱 끊기게 그려서 배경을 빼도 테두리가 깨끗함)
# 화면 오른쪽 아래(Windows 알림·워터마크 자리)를 피해 왼쪽 위에서 찍는다. 찍는 동안 2~3초 창이 뜬다.
import json
import os
import sys
import time
import tkinter as tk
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import taskpet  # noqa: E402
from PIL import ImageGrab  # noqa: E402

OUT = os.path.join(ROOT, "dist", "scenes")
os.makedirs(OUT, exist_ok=True)
BACK = (1, 255, 1)
NOW = time.time()

# 예시 대화 (언어별)
WORDS = {
    "ko": {
        "list": [("waiting", "claude", "학습 서버 설정"), ("working", "codex", "로그인 버그 수정"),
                 ("done", "claude", "게임 결투장 만들기")],
        "ext": [("working", "chatweb", "보고서 요약해 줘", "chrome"), ("done", "gemini", "여행 계획 세우기", "chrome"),
                ("done", "claudeweb", "코드 리뷰 부탁해", "brave"), ("working", "grok", "오늘 뉴스 정리", "edge"),
                ("done", "kimi", "영어 문장 번역", "chrome")],
        "chat_title": "로그인 버그 수정", "other_title": "다크 모드 버튼",
        "me1": "메인 화면에 다크 모드 버튼 넣어 줘",
        "ai1": "다크 모드 버튼을 넣었어요.\n\n- 오른쪽 위에 🌙 버튼\n- 고른 모드는 다음에 켤 때도 그대로",
        "me2": "로그인할 때 가끔 튕기는 버그도 고쳐 줘",
        "ai2": "로그인 처리 코드를 먼저 살펴볼게요.",
        "ai3": "원인을 찾았어요. 로그인이 끝나기 전에 새로고침하면 토큰이 비어서 튕겨요. 토큰을 먼저 갱신하게 고칠게요.",
        "plan": ["튕기는 원인 찾기", "토큰 갱신 고치기", "시험 돌리기"],
    },
    "en": {
        "list": [("waiting", "claude", "Training server setup"), ("working", "codex", "Fix login bug"),
                 ("done", "claude", "Build arena mode")],
        "ext": [("working", "chatweb", "Sum up a report", "chrome"), ("done", "gemini", "Plan a trip", "chrome"),
                ("done", "claudeweb", "Review my code", "brave"), ("working", "grok", "Today's news", "edge"),
                ("done", "kimi", "Translate this", "chrome")],
        "chat_title": "Fix login bug", "other_title": "Dark mode button",
        "me1": "Add a dark mode button to the home screen",
        "ai1": "Added the dark mode button.\n\n- 🌙 button at the top right\n- Your choice is remembered next time",
        "me2": "Also fix the bug that sometimes kicks me out at login",
        "ai2": "Let me look at the login code first.",
        "ai3": "Found it. Refreshing before login finishes leaves the token empty, so you get kicked out. I'll refresh the token first.",
        "plan": ["Find why it kicks out", "Fix token refresh", "Run the tests"],
    },
}
AGO = {"waiting": 130, "working": 192, "done": 250}


def make_pet(tasks):
    P = taskpet.Pet
    pet = P.__new__(P)
    root = pet.root = tk.Tk()
    taskpet.DPI = root.winfo_fpixels("1i") / 96.0
    S = taskpet.S
    back = tk.Toplevel(root)                   # 뒤에 깔 단색 배경
    back.overrideredirect(True)
    back.configure(bg="#%02x%02x%02x" % BACK)
    back.geometry(f"{S(900)}x{S(820)}+{S(80)}+{S(60)}")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=taskpet.KEY)
    root.attributes("-transparentcolor", taskpet.KEY)
    pet.px = S(5)
    pet.pad_x, pet.pad_y = S(5), S(12)
    pet.cw = 15 * pet.px + pet.pad_x * 2
    pet.ch = 16 * pet.px + pet.pad_y + S(4)
    pet.canvas = tk.Canvas(root, width=pet.cw, height=pet.ch, bg=taskpet.KEY, highlightthickness=0)
    pet.canvas.pack()
    for k, v in dict(tick_n=0, happy_until=0.0, hidden=False, _press=None, _last_click=("", 0.0, 0),
                     _bub_sig=None, _pos_sig=None, _infos=[], _icons={}, _bot={}, _hist={}, _chat=None,
                     _typed_at=0.0, _rounds={}, detail=None, reply_imgs=[], prev_fg=0, reply_key=None,
                     seen=((), "", ""), shown_at=NOW, settings={}, drafts={}, _draft_key=None,
                     _want_focus=False, _refocus=None, _input_extra=0, _thumb_cache={}, _img_data={},
                     ime=None).items():
        setattr(pet, k, v)
    taskpet.DRAFTS = os.path.join(OUT, "drafts.json")
    pet.reply_var = tk.StringVar(root)
    pet.bubble = tk.Toplevel(root)
    pet.bubble.overrideredirect(True)
    pet.bubble.attributes("-topmost", True)
    pet.bubble.configure(bg=taskpet.KEY)
    pet.bubble.attributes("-transparentcolor", taskpet.KEY)
    pet.bub_c = tk.Canvas(pet.bubble, bg=taskpet.KEY, highlightthickness=0)
    pet.bub_c.pack()
    pet.bub_box = tk.Frame(pet.bub_c, bg=taskpet.INNER)
    pet.bub_c.create_window(0, 0, window=pet.bub_box, anchor="nw", tags="boxwin")
    pet.tracker = SimpleNamespace(tasks=tasks, dirty=False)
    root.geometry(f"{pet.cw}x{pet.ch}+{S(80) + S(900) - pet.cw - S(30)}+{S(60) + S(820) - pet.ch - S(30)}")
    return pet, root, back


def shot(pet, root, back, name):
    back.attributes("-topmost", True)          # 배경은 다른 프로그램보다 위, 로봇·말풍선보다 아래
    back.lift()
    root.lift()
    pet.bubble.lift()
    for _ in range(6):
        root.update()
        time.sleep(0.05)
    x0 = max(min(pet.bubble.winfo_rootx(), root.winfo_rootx()) - 6, back.winfo_rootx())
    y0 = max(min(pet.bubble.winfo_rooty(), root.winfo_rooty()) - 6, back.winfo_rooty())
    x1 = max(pet.bubble.winfo_rootx() + pet.bubble.winfo_width(), root.winfo_rootx() + root.winfo_width()) + 6
    y1 = max(pet.bubble.winfo_rooty() + pet.bubble.winfo_height(), root.winfo_rooty() + root.winfo_height()) + 6
    img = ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True).convert("RGBA")
    img.putdata([(0, 0, 0, 0) if p[:3] == BACK else p for p in img.getdata()])
    img.save(os.path.join(OUT, name + ".png"))
    print("저장", name, img.size)


def row(i, st, src, title, browser=None):
    e = {"src": src, "id": str(i), "title": title, "prompt": "", "folder": "x",
         "start": NOW - AGO[st] - (600 if st == "done" else 0), "status": st}
    if st == "waiting":
        e["wait_start"] = NOW - AGO[st]
    if st == "done":
        e["end"] = NOW - AGO[st]
    if src == "claude":
        e["entry"] = "claude-desktop"
    if browser:
        e["browser"] = browser
    return e


def scene_list(name, rows):
    pet, root, back = make_pet({f"k{i}": row(i, *r) for i, r in enumerate(rows)})
    pet.draw()
    pet.update_bubble(force=True)
    shot(pet, root, back, name)
    root.destroy()


def iso(ago):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(NOW - ago))


def scene_chat(name, w):
    tp = os.path.join(OUT, f"{name}.jsonl")

    def tool(tid, tname, **inp):
        return {"type": "assistant", "timestamp": iso(60),
                "message": {"content": [{"type": "tool_use", "id": tid, "name": tname, "input": inp}]}}

    def done(tid):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid}]}}

    def say(text, ago):
        return {"type": "assistant", "timestamp": iso(ago), "message": {"content": [{"type": "text", "text": text}]}}
    plan = "mcp__ccd_turn__update_plan"
    recs = [{"type": "user", "timestamp": iso(900), "entrypoint": "claude-desktop", "message": {"content": w["me1"]}},
            say(w["ai1"], 800),
            {"type": "user", "timestamp": iso(150), "message": {"content": w["me2"]}},
            say(w["ai2"], 140),
            tool("p1", plan, items=[{"content": c, "status": s} for c, s in
                                    zip(w["plan"], ("in_progress", "pending", "pending"))]),
            tool("r1", "Read", file_path="C:\\app\\login.py"), done("r1"),
            tool("g1", "Grep", pattern="refresh_token"), done("g1"),
            say(w["ai3"], 70),
            tool("p2", plan, advance=True),
            tool("e1", "Edit", file_path="C:\\app\\login.py")]
    with open(tp, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    chat = row(0, "working", "claude", w["chat_title"])
    chat.update(transcript=tp, start=NOW - 150)
    pet, root, back = make_pet({"c:0": chat, "c:1": row(1, "done", "claude", w["other_title"])})
    pet.draw()
    pet.update_bubble(force=True)
    pet.open_detail("c:0")
    for _ in range(5):
        root.update()
        time.sleep(0.05)
    if pet._chat:
        pet._chat["cv"].yview_moveto(1.0)
    shot(pet, root, back, name)
    root.destroy()


for lang in ("ko", "en"):
    taskpet.KO = lang == "ko"
    w = WORDS[lang]
    scene_list(f"list_{lang}", w["list"])
    scene_list(f"ext_{lang}", w["ext"])
    scene_chat(f"chat_{lang}", w)

# 로봇만 (사이트 첫 화면·아이콘용, 투명 배경)
robot = taskpet.robot_image("idle", 240, 256, hard=False)
robot.save(os.path.join(OUT, "robot.png"))
print("저장 robot", robot.size)
