# TaskPet — Claude Code · Codex 작업 알림 펫
#
# 화면 오른쪽 아래에 주황 픽셀 로봇이 떠서, AI 코딩 도구가
# 일하는 중인지 / 끝났는지 / 내 승인을 기다리는지 알려 준다.
#
#   TaskPet.exe              처음 실행하면 설치, 설치된 곳에서 실행하면 로봇
#   TaskPet.exe --uninstall  제거
#
# Claude Code: 훅(taskpet-hook.exe)이 events.jsonl에 신호를 적으면 여기서 읽는다.
# Codex(ChatGPT 앱·CLI): ~/.codex/sessions 기록 파일을 지켜본다 (설정 변경 없음).
import ctypes
import glob
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
import wave
import winreg
import winsound
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont, ImageTk

APP = "TaskPet"
VERSION = "1.4.5"
HOME = os.path.expanduser("~")
INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HOME), APP)
HOOK_EXE = "taskpet-hook.exe"
GPT_EXE = "taskpet-chatgpt.exe"
NATIVE_EXE = "taskpet-native.exe"
NATIVE_NAME = "kr.querybot.taskpet"
# 확장 'TaskPet for ChatGPT'의 ID (manifest.json의 key로 고정됨)
# 연결을 허용할 브라우저 확장: Chrome 웹 스토어판, 직접 불러온 개발판(manifest "key"로 고정)
EXT_IDS = ["ojhigjdohhpkdkolpeeobffggkejpakn", "dmbfmfooilahmdclgfkkkdnpickfbilm"]
NATIVE_KEYS = [r"Software\Google\Chrome\NativeMessagingHosts",
               r"Software\Chromium\NativeMessagingHosts",
               r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
               r"Software\Microsoft\Edge\NativeMessagingHosts"]
FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
EVENTS = os.path.join(APP_DIR, "events.jsonl")
STATE = os.path.join(APP_DIR, "state.json")
SETTINGS = os.path.join(APP_DIR, "settings.json")   # 로봇 위치, 소리 끄기
QUIT_FLAG = os.path.join(APP_DIR, "quit.flag")
WEB_CMD = os.path.join(APP_DIR, "web-cmd.jsonl")   # 로봇 → 브라우저 확장 (탭 열기)
# Claude 데스크톱은 MSIX 앱이라 그 안에서 실행된 훅이 쓰는 %LOCALAPPDATA% 는
# Packages\<앱>\LocalCache\Local 로 옮겨진다 (바깥 프로그램에는 안 보임). 그쪽 신호 파일도 읽는다.
PKG_EVENTS = os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Packages", "*",
                          "LocalCache", "Local", APP, "events.jsonl")
CLAUDE_DIR = os.path.join(HOME, ".claude")
CODEX_DIR = os.path.join(HOME, ".codex")
NO_WINDOW = 0x08000000

# ---- 언어 ----
KO = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF == 0x12
T = {
    "working": ("{d} 진행 중", "working {d}"),
    "waiting": ("응답 대기 {d}째", "waiting for you {d}"),
    "bg": ("백그라운드 {n}개 기다리는 중 · {d}", "{n} background task(s) · {d}"),
    "done": ("완료 {w} · {d}", "done {w} · {d}"),
    "more": ("… 외 {n}개", "… {n} more"),
    "update_title": ("새 버전 {v}", "New version {v}"),
    "update_ready": ("더블 클릭해서 업데이트", "double-click to update"),
    "update_dl": ("받는 중 {p}%", "downloading {p}%"),
    "update_run": ("설치 프로그램 실행", "installer started"),
    "update_fail": ("받기 실패 · 더블 클릭해서 다시", "download failed · double-click to retry"),
    "clear": ("완료 기록 모두 지우기", "Clear finished"),
    "quit": ("종료", "Quit"),
    "mute": ("소리 끄기", "Mute sounds"),
    "ext_menu": ("브라우저 확장 받기", "Get browser extension"),
    "ext_done": ("확장 폴더를 받았습니다:\n{p}\n\n(폴더 주소는 복사해 두었습니다)\n\n"
                 "1. 브라우저 주소창에 chrome://extensions 입력\n"
                 "   (Brave는 brave://extensions, Edge는 edge://extensions)\n"
                 "2. 오른쪽 위 '개발자 모드' 켜기\n"
                 "3. '압축해제된 확장 프로그램 로드' → 주소 칸에 Ctrl+V → 폴더 선택\n\n"
                 "처음 설치라면 브라우저를 완전히 껐다 켜 주세요.",
                 "Extension folder saved to:\n{p}\n\n(The path is copied to the clipboard)\n\n"
                 "1. Open chrome://extensions (brave://, edge:// for Brave, Edge)\n"
                 "2. Turn on 'Developer mode'\n"
                 "3. 'Load unpacked' → paste with Ctrl+V → select the folder\n\n"
                 "On first install, fully restart the browser."),
    "ext_fail": ("확장 폴더를 받지 못했습니다.\n{e}", "Could not get the extension folder.\n{e}"),
    "uninstall": ("TaskPet 제거", "Uninstall TaskPet"),
    "installed": ("TaskPet 설치 완료!\n\n화면 오른쪽 아래 주황 로봇이 Claude Code와 Codex 작업을 알려 줍니다.\n\n· 이미 열려 있던 Claude Code 세션은 새로 시작해야 잡힙니다.\n· 로봇 클릭 = 말풍선 숨기기, 줄 더블 클릭 = 그 대화 열기, 우클릭 = 메뉴",
                  "TaskPet installed!\n\nThe orange robot at the bottom right shows your Claude Code and Codex tasks.\n\n· Claude Code sessions that were already open need to be restarted.\n· Click robot = hide bubble, double-click a row = open that chat, right-click = menu"),
    "updated": ("TaskPet을 새 버전으로 업데이트했습니다.", "TaskPet has been updated."),
    "no_claude": ("\n\n(Claude Code 설정을 찾지 못해 Codex만 연결했습니다.)",
                  "\n\n(Claude Code settings not found, only Codex is connected.)"),
    "bad_settings": ("~/.claude/settings.json 을 읽을 수 없어 Claude Code 연결을 건너뛰었습니다. 파일 형식을 확인해 주세요.",
                     "Could not read ~/.claude/settings.json, so Claude Code was not connected. Please check the file."),
    "ask_uninstall": ("TaskPet을 제거할까요?\nClaude Code 훅 설정과 자동 실행도 함께 지워집니다.",
                      "Uninstall TaskPet?\nIts Claude Code hooks and auto-start will be removed."),
    "uninstalled": ("TaskPet을 제거했습니다.", "TaskPet has been uninstalled."),
}


def t(key, **kw):
    return T[key][0 if KO else 1].format(**kw)


def msgbox(text, flags=0x40):
    return ctypes.windll.user32.MessageBoxW(None, text, APP, flags | 0x10000)


# ---- 화면 배율 ----
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
DPI = 1.0


def S(v):
    return int(round(v * DPI))


# ---- 색 ----
KEY = "#0b0c0d"      # 이 색이 투명해짐
INNER = "#221c28"
HOVER = "#3a3042"    # 마우스를 올린 줄
BORDER = "#f5942b"
FG = "#e8e8ec"
SUB = "#9a9aa6"
ACCENT = "#f5942b"
GREEN = "#4cc46a"
RED = "#ff6b6b"
BLUE = "#4ea1ff"
PURPLE = "#a98bff"
SILVER = "#cfd3dc"
TEAL = "#3dd6c6"
# Claude 주황, GPT 쪽 파랑, Gemini 보라, Grok 은색, Kimi 청록
SRC_COLOR = {"claude": ACCENT, "claudeweb": ACCENT, "claudechat": ACCENT, "codex": BLUE, "chatgpt": BLUE,
             "chatweb": BLUE, "gemini": PURPLE, "grok": SILVER, "kimi": TEAL, "update": GREEN}
SRC_LABEL = {"claude": "Claude", "claudeweb": "Claude 웹", "claudechat": "Claude 채팅",
             "codex": "Codex", "chatgpt": "ChatGPT",
             "chatweb": "ChatGPT 웹", "gemini": "Gemini", "grok": "Grok", "kimi": "Kimi",
             "update": "TaskPet"}
UPDATE_API = "https://api.github.com/repos/rladleh0729-del/TaskPet/releases/latest"
# 줄 앞 아이콘 종류 (공식 로고 파일은 쓰지 않고, 각 회사를 떠올리게 하는 모양을 직접 그린다)
ICON_KIND = {"claude": "claude", "claudeweb": "claude", "claudechat": "claude",
             "codex": "gpt", "chatgpt": "gpt", "chatweb": "gpt", "gemini": "gemini",
             "grok": "grok", "kimi": "kimi", "update": "update"}


def brand_icon(kind, size):
    k = 4                                  # 4배로 그려 줄여서 매끈하게
    n = size * k
    c = n / 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "gpt":                      # 둥근 고리 셋을 60도씩 돌려 겹친 매듭
        for i in range(3):
            ring = Image.new("RGBA", (n, n), (0, 0, 0, 0))
            ImageDraw.Draw(ring).rounded_rectangle(
                [n * 0.31, n * 0.05, n * 0.69, n * 0.95], radius=n * 0.19,
                outline="#e8e8ec", width=max(2, int(n * 0.09)))
            img.alpha_composite(ring.rotate(60 * i, resample=Image.BICUBIC, center=(c, c)))
    elif kind == "gemini":                 # 파랑→보라 네 갈래 반짝이 별
        pts = []
        for i in range(8):
            a = -math.pi / 2 + math.pi * i / 4
            r = n * 0.49 if i % 2 == 0 else n * 0.15
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        mask = Image.new("L", (n, n), 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        grad = Image.new("RGBA", (n, n))
        gd = ImageDraw.Draw(grad)
        for y in range(n):
            t = y / (n - 1)
            gd.line([(0, y), (n, y)], fill=(int(78 + 91 * t), int(140 - 17 * t), 255, 255))
        img.paste(grad, (0, 0), mask)
    elif kind == "grok":                   # 원을 가르는 사선
        w = max(2, int(n * 0.1))
        d.arc([n * 0.08, n * 0.08, n * 0.92, n * 0.92], start=150, end=330, fill="#e8e8ec", width=w)
        d.line([(n * 0.22, n * 0.9), (n * 0.9, n * 0.1)], fill="#e8e8ec", width=w)
    elif kind == "kimi":                   # 흰 상자에 K, 파란 점
        d.rounded_rectangle([n * 0.04, n * 0.04, n * 0.96, n * 0.96], radius=n * 0.24, fill="#e8e8ec")
        try:
            f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                "Fonts", "arialbd.ttf"), int(n * 0.66))
            d.text((n * 0.44, c + n * 0.03), "K", font=f, fill="#1b1c20", anchor="mm")
        except OSError:
            pass
        d.ellipse([n * 0.7, n * 0.16, n * 0.86, n * 0.32], fill="#3d8bff")
    elif kind == "update":                 # 초록 동그라미에 위 화살표
        d.ellipse([0, 0, n - 1, n - 1], fill=GREEN)
        d.polygon([(c, n * 0.17), (n * 0.8, n * 0.52), (n * 0.2, n * 0.52)], fill="#1b1c20")
        d.rectangle([c - n * 0.1, n * 0.5, c + n * 0.1, n * 0.8], fill="#1b1c20")
    else:                                  # Claude: 길이를 번갈아 둔 주황 빛살
        for i in range(12):
            a = math.pi * i / 6 + math.pi / 12
            r = n * 0.48 if i % 2 == 0 else n * 0.36
            d.line([(c, c), (c + r * math.cos(a), c + r * math.sin(a))],
                   fill="#d97757", width=max(2, int(n * 0.1)))
        d.ellipse([c - n * 0.12, c - n * 0.12, c + n * 0.12, c + n * 0.12], fill="#d97757")
    return img.resize((size, size), Image.LANCZOS)
# 브라우저 확장이 보내는 사이트 이름 → (줄 종류, 이름)
WEB_SITES = {"chatgpt": ("chatweb", "ChatGPT"), "gemini": ("gemini", "Gemini"),
             "claude": ("claudeweb", "Claude"), "grok": ("grok", "Grok"), "kimi": ("kimi", "Kimi")}
WEB_SRCS = tuple(src for src, _ in WEB_SITES.values())
BROWSER_NAME = {"chrome": "Chrome", "brave": "Brave", "msedge": "Edge", "chromium": "Chromium",
                "vivaldi": "Vivaldi", "opera": "Opera", "whale": "Whale"}
FONT = "맑은 고딕" if KO else "Segoe UI"

# ---- 픽셀 로봇 (15 x 16) ----
IDLE = [
    ".......O.......",
    "......OOO......",
    ".......D.......",
    "..DDDDDDDDDDD..",
    ".DOOOOOOOOOOOD.",
    ".DOFFFFFFFFFOD.",
    ".DOFEEFFFEEFOD.",
    ".DOFFFFFFFFFOD.",
    ".DOFFMMMMMFFOD.",
    ".DOOOOOOOOOOOD.",
    "..DDDDDDDDDDD..",
    "...DOOOOOOOD...",
    "..ODOOOOOOODO..",
    "...DDDDDDDDD...",
    "....DD...DD....",
    "....DD...DD....",
]
BLINK = IDLE[:6] + [".DOFFFFFFFFFOD."] + IDLE[7:]
WORK_A = IDLE[:11] + ["..ODOOOOOOOD...", "...DOOOOOOODO.."] + IDLE[13:]
WORK_B = IDLE[:11] + ["...DOOOOOOODO..", "..ODOOOOOOOD..."] + IDLE[13:]
PALETTE = {"O": "#f5942b", "D": "#a85a0e", "F": "#2a2230", "M": "#ffb15e"}
EYE = {"idle": "#ffffff", "work": "#ffd84d", "happy": "#76ff9e", "alert": RED}


def fmt_dur(sec):
    sec = max(0, int(sec))
    if KO:
        if sec < 60:
            return f"{sec}초"
        if sec < 3600:
            return f"{sec // 60}분 {sec % 60}초"
        return f"{sec // 3600}시간 {sec % 3600 // 60}분"
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60}s"
    return f"{sec // 3600}h {sec % 3600 // 60}m"


def work_area():
    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                    ("r", ctypes.c_long), ("b", ctypes.c_long)]
    r = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    return r.l, r.t, r.r, r.b


# ---- 알림음 ----
# Windows 기본 소리는 사람마다 꺼져 있거나 너무 작아서, 직접 만든 소리를 튼다.
VOLUME = 0.15  # 최대 음량 대비 (0~1)
SOUNDS = {
    # (시작 초, 주파수 Hz, 울림 초, 세기) — 음이 겹치며 종처럼 울린다
    "done": [(0.00, 1567.98, 0.9, 0.8),     # 띠 (솔)
             (0.09, 2093.00, 1.2, 1.0)],    # 링 (높은 도)
    "wait": [(0.00, 987.77, 0.45, 0.8),     # 똑 (시)
             (0.22, 987.77, 0.45, 0.8),     # 똑
             (0.44, 783.99, 0.7, 0.7)],     # 똑 (솔, 내려감)
}


def make_sounds():
    rate = 44100
    for name, notes in SOUNDS.items():
        path = os.path.join(APP_DIR, f"{name}.wav")
        total = max(s + d for s, _, d, _ in notes)
        buf = [0.0] * int(rate * total)
        for start, freq, dur, amp in notes:
            s0 = int(rate * start)
            n = int(rate * dur)
            for i in range(n):
                tt = i / rate
                env = min(1.0, i / (rate * 0.004)) * math.exp(-5.0 * tt / dur)
                # 기본음 + 맑은 배음 + 살짝 어긋난 종소리 배음
                v = (math.sin(2 * math.pi * freq * tt)
                     + 0.35 * math.sin(2 * math.pi * freq * 2 * tt) * math.exp(-8 * tt)
                     + 0.15 * math.sin(2 * math.pi * freq * 2.76 * tt) * math.exp(-12 * tt))
                buf[s0 + i] += amp * env * v / 1.5
        peak = max(1e-9, max(abs(v) for v in buf))
        frames = b"".join(struct.pack("<h", int(v / peak * VOLUME * 32767)) for v in buf)
        try:
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(frames)
        except OSError:
            pass


MUTED = False   # 우클릭 메뉴 '소리 끄기' (settings.json 에 기억)


def play(name):
    if MUTED:
        return
    path = os.path.join(APP_DIR, f"{name}.wav")
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC
                           | winsound.SND_NODEFAULT)
    except Exception:
        pass


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ======================================================================
# 설치 / 제거
# ======================================================================
HOOK_EVENTS = {
    "UserPromptSubmit": "start",
    "Stop": "stop",
    "Notification": "wait",
    "PostToolUse": "resume",
    "SessionEnd": "end",
}
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TaskPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# 레지스트리 Run에 넣으면 로그온 때 건너뛰는 PC가 있어서(시작 앱 승인 기록이 없으면 무시됨)
# 시작 프로그램 폴더 바로가기로 자동 실행한다.
STARTUP_LNK = os.path.join(os.environ.get("APPDATA", HOME), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup", "TaskPet.lnk")


def make_startup_shortcut(exe):
    script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TP_LNK);"
              "$s.TargetPath=$env:TP_EXE;$s.WorkingDirectory=$env:TP_DIR;"
              "$s.Description='TaskPet';$s.Save()")
    env = dict(os.environ, TP_LNK=STARTUP_LNK, TP_EXE=exe, TP_DIR=os.path.dirname(exe))
    os.makedirs(os.path.dirname(STARTUP_LNK), exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   env=env, creationflags=NO_WINDOW, timeout=30)
    return os.path.exists(STARTUP_LNK)


def register_native_host():
    """브라우저 확장이 taskpet-native.exe를 부를 수 있게 Chrome·Brave·Edge에 등록한다."""
    manifest = os.path.join(INSTALL_DIR, NATIVE_NAME + ".json")
    write_json(manifest, {
        "name": NATIVE_NAME,
        "description": "TaskPet ChatGPT web notifier",
        "path": os.path.join(INSTALL_DIR, NATIVE_EXE),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{i}/" for i in EXT_IDS],
    })
    for base in NATIVE_KEYS:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + "\\" + NATIVE_NAME) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, manifest)
        except OSError:
            pass


def unregister_native_host():
    for base in NATIVE_KEYS:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base + "\\" + NATIVE_NAME)
        except OSError:
            pass


def remove_run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP)
    except OSError:
        pass


def is_ours(hook):
    return HOOK_EXE in str(hook.get("command", ""))


def strip_our_hooks(settings):
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for ev in list(hooks):
        groups = hooks[ev]
        if not isinstance(groups, list):
            continue
        new_groups = []
        for g in groups:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                g["hooks"] = [h for h in g["hooks"] if not is_ours(h)]
                if not g["hooks"]:
                    continue
            new_groups.append(g)
        if new_groups:
            hooks[ev] = new_groups
        else:
            del hooks[ev]
    if not hooks:
        del settings["hooks"]


def install_claude_hooks(hook_path):
    """~/.claude/settings.json에 우리 훅을 더한다. 남의 설정은 건드리지 않는다."""
    if not os.path.isdir(CLAUDE_DIR):
        return "none"
    path = os.path.join(CLAUDE_DIR, "settings.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                settings = json.load(f)
            if not isinstance(settings, dict):
                raise ValueError
        except Exception:
            return "bad"
        backup = path + ".taskpet-backup"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
    else:
        settings = {}
    strip_our_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    for ev, arg in HOOK_EVENTS.items():
        hooks.setdefault(ev, []).append({"hooks": [{
            "type": "command",
            "command": f'"{hook_path}" {arg}',
            "timeout": 5,
        }]})
    write_json(path, settings)
    return "ok"


def remove_claude_hooks():
    path = os.path.join(CLAUDE_DIR, "settings.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
        strip_our_hooks(settings)
        write_json(path, settings)
    except Exception:
        pass


def stop_running_widget(folder):
    flag = os.path.join(folder, "quit.flag")
    try:
        open(flag, "w").close()
    except OSError:
        return
    for _ in range(30):  # 최대 3초 기다림
        h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, "TaskPetWidget")
        if not h:
            break
        ctypes.windll.kernel32.CloseHandle(h)
        time.sleep(0.1)
    try:
        os.remove(flag)
    except OSError:
        pass


def copy_retry(src, dst):
    """실행 중이던 옛 TaskPet이 완전히 꺼질 때까지 잠깐 기다리며 덮어쓴다."""
    for _ in range(50):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            time.sleep(0.2)
    # 브라우저가 붙잡고 있는 연결 프로그램 등은 안 꺼지므로, 옛 파일 이름을 바꿔 비켜 두고 복사한다
    # (실행 중인 exe도 이름 바꾸기는 됨. 비켜 둔 파일은 다음 설치 때 지움)
    old = f"{dst}.{int(time.time())}.old"
    os.replace(dst, old)
    shutil.copy2(src, dst)


def remove_old_copies(folder):
    for p in glob.glob(os.path.join(folder, "*.old")):
        try:
            os.remove(p)
        except OSError:
            pass


def install():
    try:
        _install()
    except Exception as ex:
        msgbox(("설치 중 오류가 났습니다:\n\n" if KO else "Install failed:\n\n")
               + f"{type(ex).__name__}: {ex}", 0x10)


def _install():
    os.makedirs(INSTALL_DIR, exist_ok=True)
    stop_running_widget(INSTALL_DIR)
    exe = os.path.join(INSTALL_DIR, "TaskPet.exe")
    updating = os.path.exists(exe)
    remove_old_copies(INSTALL_DIR)
    copy_retry(sys.executable, exe)
    hook = os.path.join(INSTALL_DIR, HOOK_EXE)
    copy_retry(os.path.join(sys._MEIPASS, HOOK_EXE), hook)
    copy_retry(os.path.join(sys._MEIPASS, GPT_EXE), os.path.join(INSTALL_DIR, GPT_EXE))
    copy_retry(os.path.join(sys._MEIPASS, NATIVE_EXE), os.path.join(INSTALL_DIR, NATIVE_EXE))
    register_native_host()
    # 브라우저 확장(압축 해제본)도 설치 폴더에 넣어 둔다 → 브라우저에서 '압축해제된 확장 로드'로 고르면 됨
    ext_src = os.path.join(sys._MEIPASS, "chrome-extension")
    if os.path.isdir(ext_src):
        shutil.copytree(ext_src, os.path.join(INSTALL_DIR, "chrome-extension"), dirs_exist_ok=True)

    result = install_claude_hooks(hook)

    remove_run_value()             # 1.0.0이 넣었던 Run 등록은 치운다
    make_startup_shortcut(exe)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", "TaskPet"),
                          ("DisplayVersion", VERSION),
                          ("Publisher", "TaskPet"),
                          ("DisplayIcon", exe),
                          ("InstallLocation", INSTALL_DIR),
                          ("UninstallString", f'"{exe}" --uninstall')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)

    if result == "bad":
        msgbox(t("bad_settings"), 0x30)
    # 설치 프로그램의 임시 폴더를 물려받지 않고 새로 시작하도록 (PyInstaller 6.10+)
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    subprocess.Popen([exe], cwd=INSTALL_DIR, creationflags=0x00000008, env=env)
    if updating:
        msgbox(t("updated"))
    else:
        msgbox(t("installed") + (t("no_claude") if result == "none" else ""))


def uninstall(ask=True, from_widget=False):
    if ask and msgbox(t("ask_uninstall"), 0x24) != 6:  # 6 = 예
        return
    if not from_widget:
        stop_running_widget(INSTALL_DIR)
    remove_claude_hooks()
    remove_run_value()
    unregister_native_host()
    try:
        os.remove(STARTUP_LNK)
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    msgbox(t("uninstalled"))
    # 실행 중인 자기 자신은 못 지우니, 끝난 뒤 지우도록 맡긴다
    subprocess.Popen(
        f'cmd /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{INSTALL_DIR}"',
        creationflags=NO_WINDOW | 0x00000008, cwd=HOME)


# ======================================================================
# 대화 열기
# ======================================================================
def claude_local_id(sid):
    """Claude 앱 로그에서 세션 ID → 앱 내부(local_) ID를 찾는다 (비공식)."""
    found = None
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")):
        for name in ("main.log.old", "main.log"):
            p = os.path.join(base, "Claude", "logs", name)
            try:
                size = os.path.getsize(p)
                with open(p, "rb") as f:
                    f.seek(max(0, size - 8_000_000))
                    text = f.read().decode("utf-8", "ignore")
                for m in re.finditer(r"Mapping internal session (local_[A-Za-z0-9-]+)"
                                     r" to CLI session " + re.escape(sid), text):
                    found = m.group(1)
            except OSError:
                pass
    return found


class ChatGptWatcher:
    """taskpet-chatgpt.exe를 띄워 두고, ChatGPT 창에서 '작업 중'인 대화 제목 목록을 받는다.
    일반 채팅은 컴퓨터에 기록이 남지 않아 창을 화면 읽기 기능으로 읽는 수밖에 없다."""

    def __init__(self):
        self.report = None        # 가장 최근 {"ok", "hwnd", "working"}
        self.fresh = False
        self.proc = None
        exe = next((p for p in (os.path.join(APP_DIR, GPT_EXE),
                                os.path.join(APP_DIR, "..", "build", GPT_EXE))
                    if os.path.exists(p)), None)
        if not exe:
            return
        try:
            self.proc = subprocess.Popen(
                [exe, str(os.getpid())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        except OSError:
            return
        import threading
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                self.report = json.loads(line.decode("utf-8", "ignore"))
                self.fresh = True
            except Exception:
                pass

    def take(self):
        if not self.fresh:
            return None
        self.fresh = False
        return self.report

    def open(self, title, app="chatgpt"):
        cmd, hkey = ("openclaude", "claude_hwnd") if app == "claude" else ("open", "hwnd")
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write((cmd + "\t" + title + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except OSError:
                pass
        hwnd = (self.report or {}).get(hkey) or 0
        if hwnd:   # 로봇을 방금 누른 참이라 창을 앞으로 가져올 수 있다
            u = ctypes.windll.user32
            if u.IsIconic(hwnd):
                u.ShowWindow(hwnd, 9)
            u.SetForegroundWindow(hwnd)


GPT = None   # Pet이 띄운 ChatGptWatcher


def version_tuple(v):
    return tuple(int(n) for n in re.findall(r"\d+", str(v))[:3])


class Updater:
    """켤 때와 10분마다 GitHub 최신 릴리스를 확인한다. '새 버전' 줄을 더블 클릭하면 받아서 설치 프로그램을 실행
    (설치 프로그램이 지금 로봇을 끄고 덮어쓴 뒤 새 로봇을 띄운다)."""

    def __init__(self):
        self.found = None                 # (태그, 받을 주소, 크기) — 화면 쪽이 가져감
        self.next_check = time.time() + 20

    def tick(self):
        if time.time() >= self.next_check:
            self.next_check = time.time() + 10 * 60    # 10분마다 (GitHub 한도 시간당 60번 중 6번)
            threading.Thread(target=self._check, daemon=True).start()

    def take(self):
        found, self.found = self.found, None
        return found

    def _check(self):
        try:
            req = urllib.request.Request(UPDATE_API, headers={
                "User-Agent": "TaskPet/" + VERSION, "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                rel = json.load(r)
            asset = next(a for a in rel.get("assets", []) if a.get("name") == "TaskPet.exe")
            self.found = (rel["tag_name"], asset["browser_download_url"], asset.get("size", 0))
        except Exception:
            self.next_check = time.time() + 3600   # 인터넷이 안 되면 1시간 뒤 다시

    @staticmethod
    def install(e):
        if e.get("phase") in ("dl", "run"):
            return
        e.update(phase="dl", pct=0)
        threading.Thread(target=Updater._download, args=(e,), daemon=True).start()

    @staticmethod
    def _download(e):
        folder = os.path.join(tempfile.gettempdir(), "TaskPet-update")
        path = os.path.join(folder, "TaskPet.exe")
        try:
            os.makedirs(folder, exist_ok=True)
            req = urllib.request.Request(e["url"], headers={"User-Agent": "TaskPet/" + VERSION})
            with urllib.request.urlopen(req, timeout=60) as r, open(path + ".part", "wb") as f:
                total = int(r.headers.get("Content-Length") or e.get("size") or 0)
                got = 0
                while True:
                    b = r.read(256 * 1024)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if total:
                        e["pct"] = got * 100 // total
            if e.get("size") and os.path.getsize(path + ".part") != e["size"]:
                raise OSError("크기가 다름")
            os.replace(path + ".part", path)
            env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
            subprocess.Popen([path], cwd=folder, creationflags=0x00000008, env=env)
            e["phase"] = "run"
        except Exception:
            e["phase"] = "fail"


def downloads_dir():
    """Windows '다운로드' 폴더 (사용자가 옮겨 둔 경우까지 따름)."""
    try:
        import uuid
        guid = (ctypes.c_byte * 16).from_buffer_copy(
            uuid.UUID("374DE290-123F-4565-9164-39C4925E467B").bytes_le)
        buf = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                                       ctypes.byref(buf)) == 0:
            path = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except Exception:
        pass
    return os.path.join(HOME, "Downloads")


def fetch_extension():
    """브라우저 확장 폴더를 '다운로드\\TaskPet-extension' 에 둔다. 지금 로봇 버전 태그의 GitHub 소스에서
    extension/ 만 꺼내고, 인터넷이 안 되면 설치 폴더에 들어 있는 확장을 복사한다. 만든 폴더 경로를 돌려준다."""
    dest = os.path.join(downloads_dir(), "TaskPet-extension")
    tmp = dest + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    got = False
    for ref in ("refs/tags/v" + VERSION, "refs/heads/main"):
        try:
            url = f"https://codeload.github.com/rladleh0729-del/TaskPet/zip/{ref}"
            req = urllib.request.Request(url, headers={"User-Agent": "TaskPet/" + VERSION})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for name in z.namelist():
                    parts = name.split("/", 2)      # "TaskPet-1.4.2/extension/…"
                    if len(parts) == 3 and parts[1] == "extension" and parts[2] and not name.endswith("/"):
                        out = os.path.join(tmp, *parts[2].split("/"))
                        os.makedirs(os.path.dirname(out), exist_ok=True)
                        with open(out, "wb") as f:
                            f.write(z.read(name))
            if os.path.exists(os.path.join(tmp, "manifest.json")):
                got = True
                break
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
    if not got:
        local = next((p for p in (os.path.join(APP_DIR, "chrome-extension"),
                                  os.path.join(APP_DIR, "..", "extension"))
                      if os.path.exists(os.path.join(p, "manifest.json"))), None)
        if not local:
            raise OSError("GitHub에서도, 설치 폴더에서도 확장을 찾지 못했습니다")
        shutil.copytree(local, tmp)
    # 이미 받아 둔 폴더가 있으면 새것으로 바꾼다 (브라우저가 같은 경로를 계속 쓰도록 이름은 그대로)
    if os.path.isdir(dest):
        for name in os.listdir(dest):
            p = os.path.join(dest, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        for name in os.listdir(tmp):
            shutil.move(os.path.join(tmp, name), os.path.join(dest, name))
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        os.replace(tmp, dest)
    return dest


def open_task(key, e):
    if e.get("src") == "update":
        Updater.install(e)
        return
    if e.get("src") in WEB_SRCS:
        # 브라우저가 켜져 있으면 연결 프로그램을 거쳐 그 탭을 앞으로, 아니면 그 대화를 새로 연다
        # 그 줄이 나온 브라우저에서만 연다 (브라우저마다 계정이 다를 수 있음)
        url = e.get("url") or (f"https://chatgpt.com/c/{e['conv']}" if e.get("conv")
                               else "https://chatgpt.com/")
        browser = e.get("browser", "")
        exe = (browser + ".exe") if browser else NATIVE_EXE
        alive = subprocess.run(
            ["tasklist", "/fi", f"imagename eq {exe}", "/nh"], capture_output=True,
            creationflags=NO_WINDOW).stdout.decode("cp949", "ignore").lower().find(exe) >= 0
        if alive:
            with open(WEB_CMD, "a", encoding="utf-8") as f:
                f.write(json.dumps({"cmd": "open", "tab": e.get("tab"), "conv": e.get("conv", ""),
                                    "url": url, "browser": browser}) + "\n")
        else:
            try:
                path = e.get("browser_path", "")
                if path and os.path.exists(path):
                    subprocess.Popen([path, url], creationflags=0x00000008)
                else:
                    os.startfile(url)
            except OSError:
                pass
        return
    if e.get("src") in ("chatgpt", "claudechat"):
        if GPT:
            GPT.open(e.get("title", ""), "claude" if e.get("src") == "claudechat" else "chatgpt")
        return
    if e.get("src") == "codex":
        url = f"codex://threads/{e.get('id')}"
    else:
        lid = claude_local_id(e.get("id", ""))
        url = (f"claude://code/continue?session={lid}" if lid
               else "claude://code/continue?session=last")
    try:
        os.startfile(url)
    except OSError:
        pass


# ======================================================================
# 작업 상태 추적
# ======================================================================
IMAGE_MARK = re.compile(r"\[(?:Image|이미지)[^\]]*\]", re.I)


def clean_prompt(p):
    """보여 줄 질문 글. 시스템 자동 메시지면 None(직전 질문 유지), 글 없이 이미지만 보냈으면 '(이미지)'."""
    p = " ".join(str(p or "").split())
    if p.startswith("<") or "system-reminder" in p:
        return None
    p = " ".join(IMAGE_MARK.sub(" ", p).split())
    # 글이 하나도 없으면 이미지(또는 파일)만 보낸 것
    return p[:80] if p else "(이미지)"


BG_START = re.compile(rb"Command running in background with ID: ([A-Za-z0-9]+)"
                      rb"|Async agent launched successfully[^\"]{0,200}?agentId: ([A-Za-z0-9]+)")
BG_END = re.compile(rb"<task-notification>(?:\\n|\s)*<task-id>([A-Za-z0-9]+)</task-id>")
BG_TS = re.compile(rb'"timestamp":\s*"([0-9T:.\-]+)')
BG_WINDOW = 2 * 3600   # 이보다 오래전에 시작한 건 앱 재시작 등으로 사라진 것으로 본다


def claude_bg_pending(transcript):
    """대화 기록에서 아직 끝나지 않은 최근 백그라운드 작업 수를 센다.
    Claude는 백그라운드 작업이 남아 있으면 그게 끝날 때 저절로 다시 일을 시작하므로,
    그 사이에 끝난 턴은 '완료'가 아니다."""
    started, ended = {}, set()
    now = time.time()
    try:
        with open(transcript, "rb") as f:
            for line in f:
                if b"<task-notification>" in line:
                    ended.update(m.decode() for m in BG_END.findall(line))
                if b"background with ID" in line or b"Async agent launched" in line:
                    m = BG_TS.search(line)
                    try:
                        ts = datetime.fromisoformat(m.group(1).decode() + "+00:00").timestamp()
                    except Exception:
                        continue   # 시각을 모르면 옛 기록으로 보고 세지 않는다
                    for a, b in BG_START.findall(line):
                        started[(a or b).decode()] = ts
    except OSError:
        return 0
    return sum(1 for k, ts in started.items() if k not in ended and now - ts < BG_WINDOW)


def claude_turn_asks(transcript, since):
    """이번 턴이 사용자에게 질문(데스크톱 앱 아래 상자의 선택 버튼)을 남기고 끝났는지 본다.
    이때는 Claude Code가 승인 대기 신호를 보내지 않으므로 기록을 직접 읽는다."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as f:
            f.seek(max(0, size - 600_000))
            tail = f.read()
    except OSError:
        return False
    for line in reversed(tail.splitlines()):
        if b'"mcp__ccd_turn__wrap_up"' not in line:
            continue
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ts < since - 2:
            return False          # 이번 턴 전에 한 것
        for part in (rec.get("message") or {}).get("content") or []:
            if (isinstance(part, dict) and part.get("name") == "mcp__ccd_turn__wrap_up"
                    and str((part.get("input") or {}).get("ask") or "").strip()):
                return True
        return False
    return False


def claude_title(d):
    tp = d.get("transcript_path") or ""
    sid = d.get("session_id") or ""
    if not tp or not sid:
        return ""
    p = os.path.join(os.path.dirname(tp), sid, "custom-title.json")
    return str(read_json(p, {}).get("customTitle", ""))[:60]


class Tracker:
    """Claude 훅 신호와 Codex 기록 파일을 읽어 작업 목록(self.tasks)을 만든다."""

    def __init__(self, on_event):
        saved = read_json(STATE, {})
        # '새 버전' 줄은 저장해 두지 않고 켤 때마다 다시 확인한다 (받는 도중 꺼졌던 상태가 남지 않게)
        self.tasks = {k: v for k, v in saved.get("tasks", {}).items() if not k.startswith("u:")}
        self.ev_off = saved.get("events_offset", 0)
        self.pkg_off = saved.get("pkg_offsets", {})   # 앱 가상 공간 신호 파일 → 읽은 위치
        # 사용자가 지운 Codex 줄: 키 → 지운 시각. Codex 기록은 다시 읽으므로 이보다 옛 일은 무시
        now = time.time()
        self.dismissed = {k: v for k, v in saved.get("dismissed", {}).items()
                          if now - v < 24 * 3600}
        self.on_event = on_event          # (종류, 키) — 소리·말풍선용
        self.codex_off = {}               # 파일 → 읽은 위치
        self.codex_rest = {}              # 파일 → 덜 읽힌 줄 조각
        self.codex_ignore = set()
        self.codex_titles = {}
        self.codex_index_mtime = 0
        self.last_codex_scan = 0
        self.gpt_working = None           # 직전에 '작업 중'이던 일반 채팅 제목들 (처음엔 모름)
        self.claude_working = None        # Claude 앱 일반 채팅도 같은 방식
        self.dirty = False

    def save(self):
        if self.dirty:
            self.dirty = False
            try:
                write_json(STATE, {"tasks": self.tasks,
                                   "events_offset": self.ev_off,
                                   "pkg_offsets": self.pkg_off,
                                   "dismissed": self.dismissed})
            except OSError:
                pass

    def prune(self):
        now = time.time()
        for k in list(self.tasks):
            e = self.tasks[k]
            if (now - e.get("start", now) > 12 * 3600
                    or (e.get("status") == "done" and now - e.get("end", now) > 3600)):
                del self.tasks[k]
                self.dirty = True

    def poll(self):
        self.read_claude_events()
        if time.time() - self.last_codex_scan > 1.5:
            self.last_codex_scan = time.time()
            self.scan_codex()
        self.prune()
        self.save()

    # ---- 일반 ChatGPT 채팅 (창 화면 읽기) ----
    def codex_title_set(self):
        s = set(self.codex_titles.values())
        s.update(e.get("title", "") for e in self.tasks.values() if e.get("src") == "codex")
        s.discard("")
        return s

    def apply_chatgpt(self, report):
        """감시 프로그램이 보낸 '작업 중' 제목 목록(ChatGPT 앱, Claude 앱)으로 일반 채팅의 시작·완료를 정한다."""
        if not report:
            return
        if report.get("ok"):              # ChatGPT 창이 없으면 판단을 미룬다
            codex = self.codex_title_set()
            # 브라우저에서 돌리는 대화가 데스크톱 앱 목록에도 '작업 중'으로 보이면 한 번만 띄운다
            codex.update(e.get("title", "") for e in self.tasks.values()
                         if e.get("src") == "chatweb" and e.get("status") == "working")
            # Codex 대화로 밝혀진 줄은 일반 채팅 목록에서 뺀다 (Codex는 기록 파일로 따로 잡음)
            self._apply_app_chats("g:", "chatgpt", "ChatGPT", report.get("working"), codex,
                                  "gpt_working")
        if report.get("claude_ok"):       # Claude 창이 없거나 Code 탭이면 판단을 미룬다
            # Claude Code 세션(훅으로 잡음)·claude.ai 탭과 같은 제목이면 한 번만 띄운다
            same = {e.get("title", "") for e in self.tasks.values()
                    if e.get("src") == "claude"
                    or (e.get("src") == "claudeweb" and e.get("status") == "working")}
            same.discard("")
            self._apply_app_chats("k:", "claudechat", "Claude", report.get("claude"), same,
                                  "claude_working")

    def _apply_app_chats(self, prefix, src, folder, titles, skip, attr):
        now = time.time()
        cur = {t for t in titles or [] if t and t not in skip}
        first = getattr(self, attr) is None
        prev = set() if first else getattr(self, attr)
        for k in [k for k, e in self.tasks.items()
                  if e.get("src") == src and e.get("title") in skip]:
            del self.tasks[k]
            self.dirty = True
        added, removed = cur - prev, prev - cur
        # 답하는 도중 제목이 바뀌면(새 채팅 → 자동 제목) 같은 대화로 잇는다
        if len(added) == 1 and len(removed) == 1:
            old, new = prefix + next(iter(removed)), prefix + next(iter(added))
            e = self.tasks.pop(old, None)
            if e and e.get("status") == "working":
                e["title"] = new[len(prefix):]
                self.tasks[new] = e
                added, removed = set(), set()
                self.dirty = True
        for t in added:
            key = prefix + t
            e = self.tasks.get(key)
            if e and e.get("status") == "working":
                continue
            self.tasks[key] = {"src": src, "id": t, "title": t, "prompt": "",
                               "folder": folder, "start": now, "status": "working"}
            self.dirty = True
            if not first:
                self.on_event("start", key)
        for k, e in self.tasks.items():
            if e.get("src") == src and e.get("status") == "working" and e["title"] not in cur:
                e["status"] = "done"     # 로봇을 다시 켰을 때 이미 끝나 있던 것도 여기서 정리
                e["end"] = now
                self.dirty = True
                if not first:
                    self.on_event("done", k)
        setattr(self, attr, cur)

    # ---- Claude Code ----
    def read_claude_events(self):
        self.read_pkg_events()
        try:
            size = os.path.getsize(EVENTS)
        except OSError:
            return
        if size < self.ev_off:
            self.ev_off = 0
        if size > self.ev_off:
            with open(EVENTS, "rb") as f:
                f.seek(self.ev_off)
                data = f.read()
            end = data.rfind(b"\n") + 1
            self.ev_off += end
            self.dirty = True
            for line in data[:end].splitlines():
                try:
                    self.claude_event(json.loads(line.decode("utf-8", "ignore")))
                except Exception:
                    pass
        # 다 읽은 큰 파일은 비운다
        if self.ev_off >= size > 512 * 1024:
            old = EVENTS + ".old"
            try:
                os.replace(EVENTS, old)
                with open(old, "rb") as f:
                    f.seek(self.ev_off)
                    rest = f.read()
                self.ev_off = 0
                for line in rest.splitlines():
                    try:
                        self.claude_event(json.loads(line.decode("utf-8", "ignore")))
                    except Exception:
                        pass
                os.remove(old)
            except OSError:
                pass

    def read_pkg_events(self):
        for p in glob.glob(PKG_EVENTS):
            try:
                if os.path.samefile(p, EVENTS):   # 로봇도 같은 앱 안에서 도는 경우
                    continue
            except OSError:
                pass
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            off = self.pkg_off.get(p)
            if off is None or size < off:
                # 처음 본 파일은 옛 기록을 건너뛴다 (지난 일로 소리가 나지 않게)
                off = size if off is None else 0
                self.pkg_off[p] = off
                self.dirty = True
            if size <= off:
                continue
            with open(p, "rb") as f:
                f.seek(off)
                data = f.read()
            end = data.rfind(b"\n") + 1
            self.pkg_off[p] = off + end
            self.dirty = True
            for line in data[:end].splitlines():
                try:
                    self.claude_event(json.loads(line.decode("utf-8", "ignore")))
                except Exception:
                    pass
            # 다 읽은 큰 파일은 비운다 (지우면 앱 쪽이 실제 파일을 복사해 와서 이어 쓰므로 자르기만)
            if off + end == size > 512 * 1024:
                try:
                    with open(p, "r+b") as f:
                        f.seek(0, 2)
                        if f.tell() == size:
                            f.truncate(0)
                            self.pkg_off[p] = 0
                except OSError:
                    pass

    def web_event(self, rec):
        """브라우저 확장(chatgpt.com, gemini.google.com, claude.ai, grok.com, kimi.ai)이 보낸 신호. 키는 탭 번호라서, 새 채팅이 답하는 도중
        주소·제목이 바뀌어도 같은 줄로 이어진다."""
        d = rec.get("d") or {}
        tab = d.get("tab")
        if tab is None:
            return
        ts = rec.get("t", 0) / 1000
        live = time.time() - ts < 30
        # 탭 번호는 브라우저마다 따로 매겨지므로 브라우저 이름까지 붙여 구분한다
        browser = d.get("browser", "")
        key = f"w:{browser}:{tab}" if browser else f"w:{tab}"
        e = self.tasks.get(key)
        state = d.get("state")
        if state == "closed":
            if e:
                del self.tasks[key]
                self.dirty = True
            return
        src, name = WEB_SITES.get(d.get("site"), WEB_SITES["chatgpt"])
        title = str(d.get("title") or name)[:80]
        conv = d.get("conv") or (e or {}).get("conv", "")
        url = d.get("url") or (e or {}).get("url", "")
        if state == "working":
            if e is None or e.get("status") != "working":
                if ts <= self.dismissed.get(key, 0):
                    return
                self.tasks[key] = {"src": src, "id": str(tab),
                                   "tab": tab, "conv": conv, "url": url,
                                   "browser": browser, "browser_path": d.get("browser_path", ""),
                                   "title": title, "prompt": "", "folder": name,
                                   "start": ts, "status": "working"}
                if live:
                    self.on_event("start", key)
            else:
                e.update(title=title, conv=conv, url=url)
        elif state == "done" and e and e.get("status") == "working":
            e.update(status="done", end=ts, title=title, conv=conv, url=url)
            if live:
                self.on_event("done", key)
        elif state == "done" and e and e.get("status") == "done":
            # 끝난 뒤에 붙은 제목(새 채팅 → 자동 제목)이나 대화 주소만 고친다 (소리 없음)
            e.update(title=title, conv=conv, url=url)
        self.dirty = True

    def claude_event(self, rec):
        if rec.get("ev") == "web":
            return self.web_event(rec)
        ev, d = rec.get("ev"), rec.get("d") or {}
        ts = rec.get("t", 0) / 1000
        sid = d.get("session_id")
        if not sid:
            return
        key = "c:" + sid
        live = time.time() - ts < 30
        e = self.tasks.get(key)
        if ev == "start":
            prompt = clean_prompt(d.get("prompt"))
            if prompt is None:            # 자동 메시지 → 직전 질문 그대로
                prompt = (e or {}).get("prompt", "")
            self.tasks[key] = {
                "src": "claude", "id": sid,
                "title": claude_title(d) or (e or {}).get("title", ""),
                "prompt": prompt,
                "folder": os.path.basename(d.get("cwd", "")) or "Claude",
                "transcript": d.get("transcript_path", ""),
                "start": ts, "status": "working",
            }
            if live:
                self.on_event("start", key)
        elif ev == "wait":
            msg = str(d.get("message", ""))
            if "waiting for your input" in msg:   # 대답 후 한가할 때 오는 알림
                return
            if live and (e is None or e.get("status") == "done"):
                e = self.tasks[key] = {
                    "src": "claude", "id": sid,
                    "title": claude_title(d) or (e or {}).get("title", ""),
                    "prompt": (e or {}).get("prompt", ""),
                    "folder": os.path.basename(d.get("cwd", "")) or "Claude",
                    "transcript": d.get("transcript_path", ""),
                    "start": ts, "status": "working",
                }
            if e and e.get("status") == "working":
                e["status"] = "waiting"
                e["wait_start"] = ts
                if live:
                    self.on_event("wait", key)
        elif ev == "resume":
            if e is None or e.get("status") == "done":
                # 지웠거나 끝난 세션이 저절로 다시 일을 시작함 (백그라운드 작업이 끝나서 등)
                if not live:
                    return
                self.tasks[key] = {
                    "src": "claude", "id": sid,
                    "title": claude_title(d) or (e or {}).get("title", ""),
                    "prompt": (e or {}).get("prompt", ""),
                    "folder": os.path.basename(d.get("cwd", "")) or "Claude",
                    "transcript": d.get("transcript_path", ""),
                    "start": ts, "status": "working",
                }
                self.on_event("start", key)
            elif e.get("status") == "waiting":
                e["status"] = "working"
                e.pop("wait_start", None)
        elif ev == "stop":
            if e and e.get("status") in ("working", "waiting"):
                e.pop("wait_start", None)
                e["title"] = claude_title(d) or e.get("title", "")
                tp = d.get("transcript_path") or e.get("transcript", "")
                bg = claude_bg_pending(tp) if live else 0
                if live and claude_turn_asks(tp, e.get("start", ts)):
                    e["status"] = "waiting"   # 답을 기다리며 멈춤
                    e["wait_start"] = ts
                    e.pop("bg", None)
                    self.on_event("wait", key)
                elif bg:
                    e["status"] = "working"   # 백그라운드가 끝나면 다시 이어서 하므로 아직 완료 아님
                    e["bg"] = bg
                else:
                    e["status"] = "done"
                    e["end"] = ts
                    e.pop("bg", None)
                    if live:
                        self.on_event("done", key)
        elif ev == "end":
            # 앱이 쉬는 세션을 닫기만 한 것일 수 있으니 줄은 남긴다 (질문 대기는 그대로)
            if e and e.get("status") == "working":
                e["status"] = "done"
                e["end"] = ts
                e.pop("bg", None)
        self.dirty = True

    def apply_update(self, tag, url, size):
        """GitHub 최신 릴리스가 지금보다 새것이면 '새 버전' 줄을 하나 둔다 (✕로 지우면 하루 동안 안 뜸)."""
        newer = version_tuple(tag) > version_tuple(VERSION)
        key = "u:" + tag
        for k in [k for k in self.tasks if k.startswith("u:") and (k != key or not newer)]:
            del self.tasks[k]
            self.dirty = True
        if newer and key not in self.tasks and key not in self.dismissed:
            self.tasks[key] = {"src": "update", "id": tag, "prompt": "", "folder": APP,
                               "title": t("update_title", v=tag.lstrip("vV")),
                               "start": time.time(), "status": "update", "url": url, "size": size}
            self.dirty = True

    def drop_deleted(self):
        """앱에서 대화를 지우면 기록 파일도 지워지므로, 파일이 사라진 줄은 목록에서 뺀다."""
        for key in list(self.tasks):
            e = self.tasks[key]
            path = e.get("transcript") or e.get("rollout")
            if not path:
                continue
            if os.path.exists(path):
                if not e.get("seen"):
                    e["seen"] = True
                    self.dirty = True
            elif e.get("seen") or time.time() - e.get("start", 0) > 60:
                del self.tasks[key]    # 있던(또는 진작 생겼어야 할) 파일이 없음 = 삭제됨
                self.dirty = True

    def refresh_claude_titles(self):
        self.drop_deleted()
        for key, e in self.tasks.items():
            # '백그라운드 기다리는 중'이 실제로는 끝나 있고 질문으로 멈춘 상태면 바로잡는다
            if e.get("src") == "claude" and e.get("bg") and e.get("transcript"):
                bg = claude_bg_pending(e["transcript"])
                if bg != e["bg"]:
                    self.dirty = True
                    if bg:
                        e["bg"] = bg
                    else:
                        e.pop("bg", None)
                        if claude_turn_asks(e["transcript"], e.get("start", 0)):
                            e["status"] = "waiting"
                            e["wait_start"] = time.time()
                            self.on_event("wait", key)
            if e.get("src") == "claude" and not e.get("title") and e.get("transcript"):
                title = claude_title({"transcript_path": e["transcript"],
                                      "session_id": e["id"]})
                if title:
                    e["title"] = title
                    self.dirty = True

    # ---- Codex ----
    def load_codex_titles(self):
        p = os.path.join(CODEX_DIR, "session_index.jsonl")
        try:
            m = os.path.getmtime(p)
        except OSError:
            return
        if m == self.codex_index_mtime:
            return
        self.codex_index_mtime = m
        with open(p, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("thread_name"):
                        self.codex_titles[d["id"]] = d["thread_name"]
                except Exception:
                    pass
        for k, e in self.tasks.items():
            if e.get("src") == "codex":
                title = self.codex_titles.get(e["id"])
                if title and title != e.get("title"):
                    e["title"] = title
                    self.dirty = True

    def recent_codex_rollouts(self):
        """예전 대화를 이어 쓰면 기록은 처음 시작한 날짜 폴더에 덧붙여지므로,
        Codex 대화 목록 DB에서 최근 12시간 안에 움직인 대화의 기록 파일을 찾는다."""
        now = time.time()
        if now - getattr(self, "_db_checked", 0) < 10:
            return getattr(self, "_db_files", [])
        self._db_checked = now
        files = []
        for db in sorted(glob.glob(os.path.join(CODEX_DIR, "state_*.sqlite")))[-1:]:
            try:
                import sqlite3
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
                try:
                    rows = con.execute("select rollout_path from threads "
                                       "where updated_at > ? and rollout_path is not null",
                                       (int(now) - 12 * 3600,)).fetchall()
                finally:
                    con.close()
                files = [r[0] for r in rows if r[0] and r[0].endswith(".jsonl")]
            except Exception:
                pass
        self._db_files = files
        return files

    def scan_codex(self):
        base = os.path.join(CODEX_DIR, "sessions")
        if not os.path.isdir(base):
            return
        self.load_codex_titles()
        now = time.time()
        files = []
        for days in (0, 1):
            d = datetime.now() - timedelta(days=days)
            files += glob.glob(os.path.join(base, d.strftime("%Y"), d.strftime("%m"),
                                            d.strftime("%d"), "*.jsonl"))
        seen = {os.path.normcase(f) for f in files}
        for f in self.recent_codex_rollouts():
            if os.path.normcase(f) not in seen and os.path.exists(f):
                files.append(f)
                seen.add(os.path.normcase(f))
        for f in files:
            if f in self.codex_ignore:
                continue
            try:
                size = os.path.getsize(f)
                if now - os.path.getmtime(f) > 12 * 3600:
                    continue
            except OSError:
                continue
            first = f not in self.codex_off
            off = self.codex_off.get(f, 0)
            if size <= off:
                continue
            with open(f, "rb") as fh:
                fh.seek(off)
                data = self.codex_rest.pop(f, b"") + fh.read()
            self.codex_off[f] = size
            end = data.rfind(b"\n") + 1
            if end < len(data):
                self.codex_rest[f] = data[end:]
            m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
                          r"\.jsonl$", f)
            tid = m.group(1) if m else os.path.basename(f)
            for line in data[:end].splitlines():
                try:
                    rec = json.loads(line.decode("utf-8", "ignore"))
                except Exception:
                    continue
                if not self.codex_record(f, tid, rec, live=not first):
                    break
            e = self.tasks.get("x:" + tid)
            if e is not None and e.get("rollout") != f:
                e["rollout"] = f

    def codex_record(self, f, tid, rec, live):
        typ = rec.get("type")
        p = rec.get("payload") or {}
        key = "x:" + tid
        if typ == "session_meta":
            if p.get("thread_source") not in (None, "user"):   # 하위 에이전트는 제외
                self.codex_ignore.add(f)
                self.tasks.pop(key, None)
                return False
            return True
        if typ != "event_msg":
            return True
        kind = p.get("type")
        try:
            ts = datetime.fromisoformat(
                rec.get("timestamp", "").replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = time.time()
        if ts <= self.dismissed.get(key, 0):
            return True            # 지우기 전에 있었던 일
        e = self.tasks.get(key)
        if kind == "task_started":
            self.tasks[key] = {
                "src": "codex", "id": tid,
                "title": self.codex_titles.get(tid, ""),
                "prompt": "", "folder": "Codex",
                "start": ts, "status": "working",
            }
            if live:
                self.on_event("start", key)
        elif kind == "task_complete" and e and e.get("status") == "working":
            e["status"] = "done"
            e["end"] = ts
            if live:
                self.on_event("done", key)
        elif kind == "turn_aborted":
            self.tasks.pop(key, None)
        else:
            return True
        self.dirty = True
        return True


# ======================================================================
# 화면
# ======================================================================
class Pet:
    def __init__(self):
        global DPI
        self.root = tk.Tk()
        DPI = self.root.winfo_fpixels("1i") / 96.0
        self.root.title(APP)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)

        self.px = S(5)
        self.pad_x, self.pad_y = S(5), S(12)
        self.cw = 15 * self.px + self.pad_x * 2
        self.ch = 16 * self.px + self.pad_y + S(4)
        self.canvas = tk.Canvas(self.root, width=self.cw, height=self.ch,
                                bg=KEY, highlightthickness=0)
        self.canvas.pack()

        self.tick_n = 0
        self.happy_until = 0.0
        self.hidden = False
        self._press = None
        self._last_click = ("", 0.0)
        self._bub_sig = None
        self._pos_sig = None
        self._infos = []
        self._icons = {}
        # 사용자 설정: 로봇 위치, 소리 끄기
        global MUTED
        self.settings = read_json(SETTINGS, {})
        MUTED = bool(self.settings.get("mute"))

        self.bubble = tk.Toplevel(self.root)
        self.bubble.overrideredirect(True)
        self.bubble.attributes("-topmost", True)
        self.bubble.configure(bg=KEY)
        self.bubble.attributes("-transparentcolor", KEY)
        self.bub_c = tk.Canvas(self.bubble, bg=KEY, highlightthickness=0)
        self.bub_c.pack()
        self.bub_box = tk.Frame(self.bub_c, bg=INNER)
        self.bub_c.create_window(0, 0, window=self.bub_box, anchor="nw",
                                 tags="boxwin")
        self.bubble.withdraw()

        self.tracker = Tracker(self.on_event)
        self.updater = Updater()
        global GPT
        GPT = ChatGptWatcher()

        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", self.menu)

        l, t_, r, b = work_area()
        x, y = r - self.cw - S(260), b - self.ch - S(10)
        pos = self.settings.get("pos")
        # 옮겨 둔 자리를 기억하되, 화면 배치가 바뀌어 밖으로 나가면 기본 자리로
        if (isinstance(pos, list) and len(pos) == 2
                and l <= pos[0] <= r - self.cw and t_ <= pos[1] <= b - self.ch):
            x, y = pos
        self.root.geometry(f"{self.cw}x{self.ch}+{x}+{y}")
        self.tick()
        self.root.mainloop()

    # ---- 신호 ----
    def on_event(self, kind, key):
        self.hidden = False
        if kind == "done":
            self.happy_until = time.time() + 8
            play("done")
        elif kind == "wait":
            play("wait")

    # ---- 마우스 ----
    def press(self, e):
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y(), False)

    def drag(self, e):
        if not self._press:
            return
        x0, y0, wx, wy, _ = self._press
        dx, dy = e.x_root - x0, e.y_root - y0
        if abs(dx) > 6 or abs(dy) > 6:
            self._press = (x0, y0, wx, wy, True)
            self.root.geometry(f"+{wx + dx}+{wy + dy}")
            self.position_bubble()

    def release(self, e):
        moved = self._press[4] if self._press else False
        self._press = None
        if moved:
            self.save_setting("pos", [self.root.winfo_x(), self.root.winfo_y()])
        else:
            self.hidden = not self.hidden
            if not self.hidden:
                self.happy_until = 0.0
            self.update_bubble(force=True)

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=INNER, fg=FG,
                    activebackground=ACCENT, activeforeground="#1b1c20")
        m.add_command(label=f"{APP} {VERSION}", state="disabled")
        m.add_separator()
        m.add_command(label=t("clear"), command=self.clear_done)
        m.add_command(label=("✓ " if MUTED else "   ") + t("mute"), command=self.toggle_mute)
        m.add_command(label=t("ext_menu"), command=self.get_extension)
        m.add_separator()
        m.add_command(label=t("uninstall"), command=self.do_uninstall)
        m.add_command(label=t("quit"), command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def get_extension(self):
        def work():
            try:
                path = fetch_extension()
            except Exception as ex:
                msgbox(t("ext_fail", e=ex), 0x30)
                return
            # 폴더 주소를 복사하고 폴더를 연 뒤 안내 (tk 는 화면 쪽에서만 만지도록 after 로 넘김)
            self.root.after(0, lambda: (self.root.clipboard_clear(), self.root.clipboard_append(path)))
            try:
                os.startfile(path)
            except OSError:
                pass
            msgbox(t("ext_done", p=path))
        threading.Thread(target=work, daemon=True).start()

    def toggle_mute(self):
        global MUTED
        MUTED = not MUTED
        self.save_setting("mute", MUTED)

    def save_setting(self, key, value):
        self.settings[key] = value
        try:
            write_json(SETTINGS, self.settings)
        except OSError:
            pass

    def do_uninstall(self):
        if msgbox(t("ask_uninstall"), 0x24) == 6:
            self.root.destroy()
            uninstall(ask=False, from_widget=True)

    def clear_done(self):
        tasks = self.tracker.tasks
        for k in [k for k, e in tasks.items() if e.get("status") == "done"]:
            self.tracker.dismissed[k] = time.time()
            del tasks[k]
        self.tracker.dirty = True
        self.update_bubble(force=True)

    def dismiss(self, key):
        self.tracker.tasks.pop(key, None)
        self.tracker.dismissed[key] = time.time()
        self.tracker.dirty = True
        self.update_bubble(force=True)

    def row_click(self, key):
        now = time.time()
        last, when = self._last_click
        if key == last and now - when < 0.5:
            self._last_click = ("", 0.0)
            e = self.tracker.tasks.get(key)
            if e:
                open_task(key, e)
        else:
            self._last_click = (key, now)

    # ---- 반복 ----
    def tick(self):
        if os.path.exists(QUIT_FLAG):
            self.root.destroy()
            return
        self.tick_n += 1
        if self.tick_n % 2 == 1:
            rep = GPT.take() if GPT else None
            if rep:
                self.tracker.apply_chatgpt(rep)
            self.tracker.poll()
            self.updater.tick()
            found = self.updater.take()
            if found:
                self.tracker.apply_update(*found)
            if self.tick_n % 10 == 1:
                self.tracker.refresh_claude_titles()
            self.update_bubble()
        self.draw()
        self.root.after(400, self.tick)

    def mode(self):
        st = [e.get("status") for e in self.tracker.tasks.values()]
        if "waiting" in st:
            return "alert"
        if "working" in st:
            return "work"
        if time.time() < self.happy_until:
            return "happy"
        return "idle"

    def draw(self):
        c = self.canvas
        c.delete("all")
        mode = self.mode()
        if mode == "work":
            grid = WORK_A if self.tick_n % 2 == 0 else WORK_B
        elif mode == "idle":
            grid = BLINK if random.random() < 0.12 else IDLE
        else:
            grid = IDLE
        bounce = -S(2) if (mode != "idle" and self.tick_n % 2 == 0) else 0
        px = self.px
        for ry, row in enumerate(grid):
            for rx, ch in enumerate(row):
                if ch == ".":
                    continue
                color = EYE[mode] if ch == "E" else PALETTE[ch]
                x = self.pad_x + rx * px
                y = self.pad_y + ry * px + bounce
                c.create_rectangle(x, y, x + px, y + px, fill=color, width=0)

        st = [e.get("status") for e in self.tracker.tasks.values()]
        n = st.count("working")
        badge = None
        if "waiting" in st:
            badge = (RED, "!")
        elif n:
            srcs = {e.get("src") for e in self.tracker.tasks.values()
                    if e.get("status") == "working"}
            # 진행 중인 것이 모두 같은 색이면 그 색, 섞여 있으면 기본 주황
            colors = {SRC_COLOR.get(s, ACCENT) for s in srcs}
            badge = (colors.pop() if len(colors) == 1 else ACCENT, str(n))
        elif "done" in st:
            badge = (GREEN, "✓")
        if badge:
            d = S(16)
            x, y = self.cw - d, S(4)
            c.create_oval(x, y, x + d, y + d, fill=badge[0], width=0)
            c.create_text(x + d / 2, y + d / 2, text=badge[1], fill="#1b1c20",
                          font=(FONT, 8, "bold"))

    # ---- 말풍선 ----
    @staticmethod
    def info_text(e, now):
        if e.get("status") == "update":
            phase = e.get("phase")
            body = (t("update_dl", p=e.get("pct", 0)) if phase == "dl" else
                    t("update_run") if phase == "run" else
                    t("update_fail") if phase == "fail" else t("update_ready"))
        elif e.get("status") == "done":
            when = time.strftime("%H:%M", time.localtime(e.get("end", now)))
            body = t("done", w=when, d=fmt_dur(e.get("end", now) - e.get("start", now)))
        elif e.get("status") == "waiting":
            body = t("waiting", d=fmt_dur(now - e.get("wait_start", now)))
        elif e.get("bg"):
            body = t("bg", n=e["bg"], d=fmt_dur(now - e.get("start", now)))
        else:
            body = t("working", d=fmt_dur(now - e.get("start", now)))
        return f" · {body}"

    def update_bubble(self, force=False):
        order = {"waiting": 0, "working": 1, "done": 2}
        items = sorted(self.tracker.tasks.items(),
                       key=lambda kv: (order.get(kv[1].get("status"), 3),
                                       -kv[1].get("start", 0)))
        if not items or self.hidden:
            self.bubble.withdraw()
            self._bub_sig = None
            return
        shown = items[:8]
        compact = len(items) >= 4
        now = time.time()

        sig = (compact, len(items) > 8, tuple(
            (k, e.get("status"), e.get("title", ""),
             "" if compact else e.get("prompt", "")) for k, e in shown))
        if not force and sig == self._bub_sig:
            for k, lbl in self._infos:     # 시간 글자만 바꿔 깜빡임 방지
                e = self.tracker.tasks.get(k)
                if e:
                    lbl.configure(text=self.info_text(e, now))
            self.show_bubble()
            return
        self._bub_sig = sig
        self._infos = []
        for w in self.bub_box.winfo_children():
            w.destroy()

        for key, e in shown:
            status = e.get("status")
            src_color = SRC_COLOR.get(e.get("src"), ACCENT)
            color = {"done": GREEN, "waiting": RED}.get(status, src_color)
            mark = {"done": "✅ ", "waiting": "❗ "}.get(status, "")
            row = tk.Frame(self.bub_box, bg=INNER)
            row.pack(fill="x", padx=S(2), pady=S(2) if compact else S(3))
            top = tk.Frame(row, bg=INNER)
            top.pack(fill="x")
            name = e.get("title") or e.get("prompt") or e.get("folder", "?")
            # 맨 앞 아이콘으로 어느 AI인지, 글자 색·✅/❗로 상태를 보인다
            head = tk.Label(top, text=" " + mark + name[:28], image=self.icon(e.get("src")),
                            compound="left", bg=INNER, fg=color, font=(FONT, 9, "bold"))
            head.pack(side="left")
            label = SRC_LABEL.get(e.get("src"), "Claude")
            if e.get("browser"):                 # 웹 줄은 어느 브라우저인지도
                label += " · " + BROWSER_NAME.get(e["browser"], e["browser"].capitalize())
            srcl = tk.Label(top, text="  " + label,
                            bg=INNER, fg=src_color, font=(FONT, 8, "bold"))
            srcl.pack(side="left")
            info = tk.Label(top, text=self.info_text(e, now), bg=INNER,
                            fg=RED if status == "waiting" else SUB,
                            font=(FONT, 8, "bold" if status == "waiting" else "normal"))
            info.pack(side="left")
            self._infos.append((key, info))
            x = tk.Label(top, text=" ✕", bg=INNER, fg=SUB, font=(FONT, 9),
                         cursor="hand2")
            x.pack(side="right")
            x.bind("<Button-1>", lambda ev, k=key: self.dismiss(k))
            widgets = [row, top, head, srcl, info]
            prompt = e.get("prompt")
            if (not compact and status != "waiting" and prompt
                    and e.get("title") and prompt != e.get("title")):
                p = tk.Label(row, text=prompt[:60], bg=INNER, fg=FG, font=(FONT, 8),
                             anchor="w", wraplength=S(220), justify="left")
                p.pack(fill="x")
                widgets.append(p)
            for w in widgets:
                w.bind("<Button-1>", lambda ev, k=key: self.row_click(k))
                w.configure(cursor="hand2")
            # 마우스를 올린 줄은 배경을 살짝 밝게 (더블 클릭할 줄이 어느 것인지 보이게)
            parts = widgets + [x]
            for w in parts:
                w.bind("<Enter>", lambda ev, ps=parts: self.hover(ps, True), add="+")
                w.bind("<Leave>", lambda ev, ps=parts: self.hover(ps, False, ev), add="+")
        if len(items) > 8:
            tk.Label(self.bub_box, text=t("more", n=len(items) - 8), bg=INNER,
                     fg=SUB, font=(FONT, 8)).pack(anchor="w", padx=S(2))
        self.show_bubble()

    def icon(self, src):
        kind = ICON_KIND.get(src, "claude")
        if kind not in self._icons:
            self._icons[kind] = ImageTk.PhotoImage(brand_icon(kind, S(14)))
        return self._icons[kind]

    @staticmethod
    def hover(parts, on, ev=None):
        if not on and ev is not None:
            # 같은 줄 안의 다른 글자로 옮겨 갔을 뿐이면 그대로 둔다
            try:
                if parts[0].winfo_containing(ev.x_root, ev.y_root) in parts:
                    return
            except (tk.TclError, KeyError):
                pass
        for w in parts:
            try:
                w.configure(bg=HOVER if on else INNER)
            except tk.TclError:
                pass

    def show_bubble(self):
        if self.bubble.state() == "withdrawn":
            self.bubble.deiconify()
        self.position_bubble()

    def bubble_image(self, bw, bh, rect_w, rect_h, ty):
        """4배로 크게 그린 뒤 줄여서 모서리를 매끈하게."""
        k = 4
        img = Image.new("RGBA", (bw * k, bh * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        o = S(2)
        d.rounded_rectangle([o * k, o * k, (o + rect_w) * k, (o + rect_h) * k],
                            radius=S(22) * k, fill=INNER, outline=BORDER, width=S(2) * k)
        bx = (o + rect_w) * k - S(2) * k
        tw = S(13)
        d.polygon([(bx, ty * k), ((rect_w + o + tw) * k, (ty + S(8)) * k),
                   (bx, (ty + S(16)) * k)], fill=BORDER)
        d.polygon([(bx - k, (ty + S(3)) * k), ((rect_w + o + tw - S(5)) * k, (ty + S(8)) * k),
                   (bx - k, (ty + S(13)) * k)], fill=INNER)
        bg = Image.new("RGB", img.size, KEY)
        bg.paste(img, mask=img.getchannel("A"))
        return ImageTk.PhotoImage(bg.resize((bw, bh), Image.LANCZOS))

    def position_bubble(self):
        if self.hidden or self.bubble.state() == "withdrawn":
            return
        self.bub_box.update_idletasks()
        pad = S(13)
        rect_w = self.bub_box.winfo_reqwidth() + pad * 2
        rect_h = self.bub_box.winfo_reqheight() + pad * 2
        bw = rect_w + S(16)
        bh = max(rect_h + S(4), S(44))
        l, t_, r, b = work_area()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        x = max(l + 4, rx - bw - S(2))
        y = max(t_ + 4, min(ry + self.ch - bh - S(24), b - bh - 4))
        ty = max(S(12), min(ry + S(30) - y, bh - S(28)))
        sig = (bw, bh, x, y, ty)
        if sig == self._pos_sig:
            return
        self._pos_sig = sig
        c = self.bub_c
        c.configure(width=bw, height=bh)
        if (bw, bh, rect_w, rect_h, ty) != getattr(self, "_img_sig", None):
            self._img_sig = (bw, bh, rect_w, rect_h, ty)
            self._img = self.bubble_image(bw, bh, rect_w, rect_h, ty)
        c.delete("bg")
        c.create_image(0, 0, anchor="nw", image=self._img, tags="bg")
        c.coords("boxwin", S(2) + pad, S(2) + pad)
        c.tag_raise("boxwin")
        self.bubble.geometry(f"{bw}x{bh}+{x}+{y}")


def main():
    if "--uninstall" in sys.argv:
        uninstall()
        return
    if FROZEN and os.path.normcase(APP_DIR) != os.path.normcase(INSTALL_DIR):
        install()
        return
    ctypes.windll.kernel32.CreateMutexW(None, False, "TaskPetWidget")
    if ctypes.windll.kernel32.GetLastError() == 183:  # 이미 실행 중
        return
    # 창 없는 exe는 오류를 보여 줄 곳이 없어서, 오류가 나면 error.log에 남긴다
    if sys.stderr is None:
        try:
            log = os.path.join(APP_DIR, "error.log")
            if os.path.exists(log) and os.path.getsize(log) > 200_000:
                os.remove(log)
            sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
            sys.stderr.write(f"\n--- 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} v{VERSION}\n")
        except OSError:
            pass
    make_sounds()
    Pet()


if __name__ == "__main__":
    main()
