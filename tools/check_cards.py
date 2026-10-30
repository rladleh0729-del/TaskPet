# 펼친 카드가 제대로 그려지는지 진짜 TaskPet 코드로 그려 찍는다 (웹 탭·ChatGPT 앱·터미널 Claude Code).
#   python tools\check_cards.py   →   dist\cards\*.png   찍는 동안 2~3초씩 창이 뜬다. 마우스는 건드리지 않음.
import json
import os
import sys
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import taskpet  # noqa: E402
from PIL import ImageGrab  # noqa: E402

OUT = os.path.join(ROOT, "dist", "cards")
os.makedirs(OUT, exist_ok=True)
TMP = tempfile.mkdtemp()
taskpet.WEB_CHAT_DIR = os.path.join(TMP, "web-chat")
os.makedirs(taskpet.WEB_CHAT_DIR)
taskpet.WEB_CMD = os.path.join(TMP, "web-cmd.jsonl")
taskpet.DRAFTS = os.path.join(TMP, "drafts.json")
BACK = (1, 255, 1)
NOW = time.time()
MSGS = [["me", "주말에 갈 만한 곳 추천해 줘"],
        ["ai", "이런 곳은 어떠세요?\n\n- 남산 둘레길: 걷기 좋아요\n- 서울숲: 아이와 함께\n- 북촌 한옥마을: 사진 찍기 좋아요"],
        ["me", "그럼 서울숲으로 갈게. 주차는 어때?"],
        ["ai", "서울숲 공영 주차장이 있어요. 주말엔 일찍 가는 편이 좋아요."]]


def make_pet(tasks):
    P = taskpet.Pet
    pet = P.__new__(P)
    root = pet.root = tk.Tk()
    taskpet.DPI = root.winfo_fpixels("1i") / 96.0
    S = taskpet.S
    back = tk.Toplevel(root)
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
                     _img_src=None, ime=None).items():
        setattr(pet, k, v)
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
    back.attributes("-topmost", True)
    back.lift()
    root.lift()
    pet.bubble.lift()
    for _ in range(8):
        root.update()
        time.sleep(0.05)
    x0 = max(min(pet.bubble.winfo_rootx(), root.winfo_rootx()) - 6, back.winfo_rootx())
    y0 = max(min(pet.bubble.winfo_rooty(), root.winfo_rooty()) - 6, back.winfo_rooty())
    x1 = max(pet.bubble.winfo_rootx() + pet.bubble.winfo_width(), root.winfo_rootx() + root.winfo_width()) + 6
    y1 = max(pet.bubble.winfo_rooty() + pet.bubble.winfo_height(), root.winfo_rooty() + root.winfo_height()) + 6
    ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True).save(os.path.join(OUT, name + ".png"))
    print("저장", name)


def card(name, key, e, after_open=None):
    pet, root, back = make_pet({key: e})
    pet.draw()
    pet.update_bubble(force=True)
    print(name, "펼칠 수 있음:", pet.has_detail(e), "/ 보낼 수 있음:", pet.can_send(e))
    pet.open_detail(key)
    for _ in range(5):
        root.update()
        time.sleep(0.05)
    if after_open:
        after_open(pet, root)
    if pet._chat:
        pet._chat["cv"].yview_moveto(1.0)
    shot(pet, root, back, name)
    root.destroy()


base = {"id": "1", "prompt": "", "folder": "x", "start": NOW - 300, "end": NOW - 60, "status": "done"}

# 웹 탭: 확장이 보내 준 대화 파일로 그림
web = dict(base, src="chatweb", tab=5, browser="brave", title="주말 나들이 추천", url="https://chatgpt.com/c/x")
json.dump({"type": "chat", "tab": 5, "working": False, "msgs": MSGS},
          open(taskpet.web_chat_file(web), "w", encoding="utf-8"), ensure_ascii=False)
card("web", "w:brave:5", web)

# 웹 탭인데 아직 대화 글이 안 온 때 (빈 기록창 + 입력칸)
empty = dict(base, src="claudeweb", tab=6, browser="brave", title="새 대화")
card("web_empty", "w:brave:6", empty)

# ChatGPT 앱: 그 대화가 열려 있을 때 / 다른 대화를 보고 있을 때(안내 줄)
taskpet.GPT = SimpleNamespace(chat_result={"title": "앱 대화", "ok": True, "msgs": MSGS + [["me", ""]]},
                              ask_chat=lambda t: None)
card("gpt", "g:앱 대화", dict(base, src="chatgpt", title="앱 대화"))
taskpet.GPT = SimpleNamespace(chat_result={"title": "앱 대화", "ok": False, "msgs": []}, ask_chat=lambda t: None)
card("gpt_other", "g:앱 대화", dict(base, src="chatgpt", title="앱 대화"))
taskpet.GPT = None

# 터미널 Claude Code: 보통 / 선택 메뉴로 멈춤(입력칸 대신 안내)
tp = os.path.join(TMP, "term.jsonl")
with open(tp, "w", encoding="utf-8") as f:
    f.write(json.dumps({"type": "user", "timestamp": "2026-10-30T01:00:00.000Z", "entrypoint": "cli",
                        "message": {"content": "테스트 돌려 줘"}}, ensure_ascii=False) + "\n")
    f.write(json.dumps({"type": "assistant", "timestamp": "2026-10-30T01:00:05.000Z",
                        "message": {"content": [{"type": "text", "text": "테스트 12개 모두 통과했어요."}]}},
                       ensure_ascii=False) + "\n")
term = dict(base, src="claude", entry="cli", cc_pid=1234, cc_start=1, title="", prompt="테스트 돌려 줘",
            transcript=tp, folder="taskpet")
card("term", "c:t1", term)
card("term_menu", "c:t2", dict(term, status="waiting", wait_start=NOW - 30))
print("끝", OUT)
