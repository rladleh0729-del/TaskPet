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
import base64
import ctypes
import glob
import hashlib
import io
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
import tkinter.font as tkfont
import urllib.request
import wave
import winreg
import winsound
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont, ImageTk

from i18n import FONTS, LANG_NAMES, TOOL_TR, TR, UNITS

APP = "TaskPet"
VERSION = "1.8.0"
HOME = os.path.expanduser("~")
INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HOME), APP)
HOOK_EXE = "taskpet-hook.exe"
GPT_EXE = "taskpet-chatgpt.exe"
NATIVE_EXE = "taskpet-native.exe"
TERM_EXE = "taskpet-term.exe"      # 터미널에서 도는 Claude Code 에 답 넣기·그 창 앞으로
NATIVE_NAME = "kr.querybot.taskpet"
# 확장 'TaskPet for ChatGPT'의 ID (manifest.json의 key로 고정됨)
# 연결을 허용할 브라우저 확장: Chrome 웹 스토어판, 직접 불러온 개발판(manifest "key"로 고정)
EXT_IDS = ["ojhigjdohhpkdkolpeeobffggkejpakn", "dmbfmfooilahmdclgfkkkdnpickfbilm"]
STORE_URL = "https://chromewebstore.google.com/detail/" + EXT_IDS[0]
NATIVE_KEYS = [r"Software\Google\Chrome\NativeMessagingHosts",
               r"Software\Chromium\NativeMessagingHosts",
               r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
               r"Software\Microsoft\Edge\NativeMessagingHosts"]
FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
EVENTS = os.path.join(APP_DIR, "events.jsonl")
STATE = os.path.join(APP_DIR, "state.json")
SETTINGS = os.path.join(APP_DIR, "settings.json")   # 로봇 위치, 소리 끄기
DRAFTS = os.path.join(APP_DIR, "drafts.json")       # 세션마다 로봇에서 쓰던 글·붙인 이미지
QUIT_FLAG = os.path.join(APP_DIR, "quit.flag")
WEB_CMD = os.path.join(APP_DIR, "web-cmd.jsonl")   # 로봇 → 브라우저 확장 (탭 열기·대화 보기·답 보내기)
WEB_CHAT_DIR = os.path.join(APP_DIR, "web-chat")    # 확장이 보낸 탭 대화 글 (로봇에서 펼쳐 보는 동안만, 닫으면 지움)
# Claude 데스크톱은 MSIX 앱이라 그 안에서 실행된 훅이 쓰는 %LOCALAPPDATA% 는
# Packages\<앱>\LocalCache\Local 로 옮겨진다 (바깥 프로그램에는 안 보임). 그쪽 신호 파일도 읽는다.
PKG_EVENTS = os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Packages", "*",
                          "LocalCache", "Local", APP, "events.jsonl")
CLAUDE_DIR = os.path.join(HOME, ".claude")
CODEX_DIR = os.path.join(HOME, ".codex")
NO_WINDOW = 0x08000000

# ---- 언어 ----
# 설정 메뉴에서 고른 언어(settings.json 의 "lang"), 없으면 Windows 표시 언어. 한국어·영어는 아래 T 표, 나머지는 i18n.py
def pick_lang():
    # 설치·업데이트 중(설치 폴더 밖에서 켜짐)에는 설치된 로봇의 설정을 본다 → 안내 상자도 고른 언어로
    for path in (SETTINGS, os.path.join(INSTALL_DIR, "settings.json")):
        try:
            with open(path, encoding="utf-8") as f:
                v = json.load(f).get("lang")
            if isinstance(v, str) and v in dict(LANG_NAMES):
                return v
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    main_id, sub = lid & 0x3FF, lid >> 10
    if main_id == 0x04:                                   # 중국어: 대만·홍콩·마카오는 번체
        return "zh_TW" if sub in (0x01, 0x03, 0x05) else "zh_CN"
    return {0x12: "ko", 0x11: "ja", 0x0a: "es", 0x16: "pt_BR", 0x0c: "fr",
            0x07: "de", 0x19: "ru"}.get(main_id, "en")


LANG = pick_lang()
KO = LANG == "ko"
T = {
    "working": ("{d} 진행 중", "working {d}"),
    "working_short": ("진행 {d}", "working {d}"),
    "waiting_short": ("응답 대기 {d}", "waiting {d}"),
    "bg_short": ("백그라운드 {n}개", "{n} in background"),
    "done_short": ("완료 · {d} 전", "done · {d} ago"),
    "waiting": ("응답 대기 {d}째", "waiting for you {d}"),
    "bg": ("백그라운드 {n}개 기다리는 중 · {d}", "{n} background task(s) · {d}"),
    "done": ("완료 {w} · {d}", "done {w} · {d}"),
    "more": ("… 외 {n}개", "… {n} more"),
    "update_title": ("새 버전 {v}", "New version {v}"),
    "update_ready": ("더블 클릭해서 업데이트", "double-click to update"),
    "ext_tip_title": ("브라우저 AI 채팅도 보려면 확장 설치", "Install the browser extension for web AI chats"),
    "ext_tip_body": ("더블 클릭하면 웹 스토어가 열려요", "double-click to open the Web Store"),
    "update_dl": ("받는 중 {p}%", "downloading {p}%"),
    "update_run": ("설치 프로그램 실행", "installer started"),
    "update_fail": ("받기 실패 · 더블 클릭해서 다시", "download failed · double-click to retry"),
    "clear": ("완료 기록 모두 지우기", "Clear finished"),
    "quit": ("종료", "Quit"),
    "mute": ("소리 끄기", "Mute sounds"),
    "settings": ("설정", "Settings"),
    "autohide": ("말풍선 자동 숨기기", "Auto-hide bubble"),
    "autohide_off": ("안 함", "Never"),
    "sec": ("{n}초 뒤", "after {n}s"),
    "min1": ("1분 뒤", "after 1 min"),
    "autohide_ask": ("직접 정하기…", "Custom…"),
    "thinking": ("생각 중…", "Thinking…"),
    "older_hint": ("▲ 위로 올리면 이전 대화", "▲ Scroll up for older messages"),
    "omitted": ("… 앞의 {n}개 생략", "… {n} earlier steps"),
    "plan": ("계획", "Plan"),
    "n_items": ("{n}개", "{n}"),
    "autohide_mine": ("직접: {d} 뒤", "custom: after {d}"),
    "autohide_prompt": ("몇 초 뒤에 말풍선을 숨길까요? (3 ~ 3600초)",
                        "Hide the bubble after how many seconds? (3–3600)"),
    "hide_viewed": ("화면에 보이는 세션은 알리지 않기", "Don't notify for sessions on screen"),
    "answer_preview": ("끝난 답변 미리보기", "Show finished answers"),
    "ext_menu": ("브라우저 확장 설치 (웹 스토어)", "Install browser extension (Web Store)"),
    "back": ("목록", "list"),
    "answer_in_app": ("여러 문항 질문이라 앱에서 답해 주세요", "Multi-question card: answer it in the app"),
    "gpt_open_hint": ("ChatGPT 앱에서 이 대화를 열어 두면 여기에 보여요", "Open this chat in the ChatGPT app to see it here"),
    "answer_in_term": ("이 질문은 터미널에서 골라 주세요 (더블 클릭하면 그 터미널로)",
                       "Pick an answer in the terminal (double-click to go there)"),
    "img_hint": ("누르면 빼기", "click to remove"),
    "img_pick": ("이미지", "Images"),
    "img_broken": ("(그림 열기 실패)", "(could not open image)"),
    "img_default": ("이 이미지를 봐 주세요.", "Please look at this image."),
    "reply_send": ("➤", "➤"),
    "reply_hint": ("메시지 입력 · Shift+Enter 줄바꿈", "Message · Shift+Enter for new line"),
    "reply_sending": ("보내는 중…", "sending…"),
    "reply_fail": ("답을 보내지 못했습니다.\n{e}", "Could not send the answer.\n{e}"),
    "reply_nohelper": ("감시 프로그램이 꺼져 있어요", "The helper is not running"),
    "reply_notitle": ("이 세션은 이름이 없어서 찾을 수 없어요. Claude 앱에서 답해 주세요.",
                      "This session has no name, so it can't be found. Please answer in the Claude app."),
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
    "img_tag": ("(이미지)", "(image)"),
    "src_claudeweb": ("Claude 웹", "Claude Web"),
    "src_claudechat": ("Claude 채팅", "Claude Chat"),
    "src_chatweb": ("ChatGPT 웹", "ChatGPT Web"),
    "install_failed": ("설치 중 오류가 났습니다:\n\n", "Install failed:\n\n"),
    "lang_menu": ("언어 · Language", "Language"),
    "lang_auto": ("자동 (Windows 설정)", "Automatic (Windows setting)"),
    # 웹 탭에 답 보내기가 안 됐을 때 (확장이 짧은 이름으로 알려 줌)
    # 터미널 Claude Code 에 답 넣기가 안 됐을 때
    "term_err_gone": ("그 터미널의 Claude Code 가 꺼져 있어요", "The Claude Code in that terminal is no longer running"),
    "term_err_no_console": ("그 터미널에 연결하지 못했어요", "Couldn't connect to that terminal"),
    "term_err_no_helper": ("터미널 도우미 프로그램이 없어요. TaskPet 을 다시 설치해 주세요",
                           "The terminal helper is missing. Please reinstall TaskPet"),
    "web_err_no_editor": ("그 탭에서 입력창을 찾지 못했어요", "Couldn't find the message box in that tab"),
    "web_err_busy": ("AI가 아직 답하는 중이에요. 끝난 뒤에 보내 주세요", "The AI is still answering. Send it after it finishes"),
    "web_err_draft": ("그 탭 입력창에 쓰던 글이 있어서 보내지 않았어요", "That tab's message box already has text, so nothing was sent"),
    "web_err_no_send": ("보내기 버튼을 찾지 못했어요", "Couldn't find the send button"),
    "web_err_not_sent": ("보내기를 눌렀지만 보내지지 않았어요", "Pressed send, but the message didn't go out"),
    "web_err_no_tab": ("그 탭이 닫혔거나 새로 고침이 필요해요", "That tab was closed or needs to be reloaded"),
    "web_err_timeout": ("브라우저 확장이 답하지 않아요. 확장을 1.3.0 이상으로 업데이트하고 탭을 새로 고쳐 주세요",
                        "The browser extension didn't respond. Update it to 1.3.0 or later and reload the tab"),
}


def ui_lang():
    """지금 화면 언어. KO 를 바꿔 쓰는 그림 만들기 도구(make_scenes)를 위해 KO 를 먼저 본다."""
    return "ko" if KO else ("en" if LANG == "ko" else LANG)


def t(key, **kw):
    if KO:
        s = T[key][0]
    else:
        s = TR.get(ui_lang(), {}).get(key) or T[key][1]
    return s.format(**kw)


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
# 말풍선: 로봇과 같은 결의 옅은 주황 바탕 + 로봇 주황 테두리 + 진한 갈색 글자
INNER = "#fff1e1"
HOVER = "#d9700f"    # 마우스를 올린 줄의 제목 글자 (진한 주황)
BORDER = "#f39a3f"
LINE = "#f6d6b4"     # 줄 사이 구분선
FG = "#43260f"
SUB = "#9a6b45"
TXT_RED = "#d63a2f"  # 밝은 바탕 위 '응답 대기' 글자
ICON_INK = "#3a2e26"  # 밝은 바탕 위 흑백 아이콘(GPT·Grok) 색
ACCENT = "#f5942b"
GREEN = "#4cc46a"
RED = "#ff6b6b"
BLUE = "#4ea1ff"
PURPLE = "#a98bff"
SILVER = "#cfd3dc"
TEAL = "#3dd6c6"
# 말풍선 안 답변·버튼: 바탕보다 한 단계 밝은 파랑 면에 흰 글자
ANS_BG = "#fffaf3"        # 답변 칸: 거의 흰색에 주황을 살짝 섞음
ANS_FG = "#1e1e1e"        # 답변 글자: 검은색
ANS_HEAD = "#000000"
HINT_FG = "#b9a08a"       # 빈 입력칸의 흐린 안내 글
SELECT_BG = "#fde0c2"     # 입력칸에서 고른 글 (파랑 대신 옅은 주황)
DONE_FG = "#1f9a4b"       # 끝난 줄: 제목·상태 글자 초록 (옅은 주황 바탕에서도 잘 보이게 조금 진하게)
MY_BG = "#fbc98f"         # 내가 보낸 메시지 말풍선: 로봇 얼굴 같은 주황
MY_FG = "#2a1608"
CHIP_BG = "#f39a3f"       # 선택지 버튼: 로봇 주황 + 흰 글자
CHIP_FG = "#ffffff"
CHIP_HOVER = "#e0801f"    # 버튼에 마우스를 올리면 조금 진한 주황
CHIP_SUB_BG = "#fbd3a8"   # 이미지·보내기: 연한 주황 + 갈색 글자
CHIP_SUB_FG = "#6b3f17"
ENTRY_BG = "#ffffff"      # 입력칸: 흰 바탕 + 진한 글자, 테두리는 연한 주황
ENTRY_FG = "#3b200b"
ENTRY_LINE = "#f0b27a"
WORKING = "#c8640f"       # '진행 중' 글자
# 어느 AI인지 보이는 알약 모양 이름표 (바탕, 글자)
PILL = {"claude": ("#fbcf9f", "#8a4310"), "claudeweb": ("#fbcf9f", "#8a4310"),
        "claudechat": ("#fbcf9f", "#8a4310"), "chatgpt": ("#c6eee4", "#0d6b5c"),
        "chatweb": ("#c6eee4", "#0d6b5c"), "codex": ("#d6e2ff", "#2851b8"),
        "gemini": ("#e6dcff", "#5a3aa8"), "grok": ("#e4e7ee", "#4a5163"),
        "kimi": ("#cdf3ef", "#0e6b63"), "update": ("#d4f2dc", "#1f7a3d"), "tip": ("#d4f2dc", "#1f7a3d")}
# Claude 주황, GPT 쪽 파랑, Gemini 보라, Grok 은색, Kimi 청록
SRC_COLOR = {"claude": ACCENT, "claudeweb": ACCENT, "claudechat": ACCENT, "codex": BLUE, "chatgpt": BLUE,
             "chatweb": BLUE, "gemini": PURPLE, "grok": SILVER, "kimi": TEAL, "update": GREEN, "tip": GREEN}
SRC_LABEL = {"claude": "Claude", "claudeweb": "Claude 웹", "claudechat": "Claude 채팅",
             "codex": "Codex", "chatgpt": "ChatGPT",
             "chatweb": "ChatGPT 웹", "gemini": "Gemini", "grok": "Grok", "kimi": "Kimi",
             "update": "TaskPet", "tip": "TaskPet"}
UPDATE_API = "https://api.github.com/repos/rladleh0729-del/TaskPet/releases/latest"
# 줄 앞 아이콘 종류 (공식 로고 파일은 쓰지 않고, 각 회사를 떠올리게 하는 모양을 직접 그린다)
ICON_KIND = {"claude": "claude", "claudeweb": "claude", "claudechat": "claude",
             "codex": "gpt", "chatgpt": "gpt", "chatweb": "gpt", "gemini": "gemini",
             "grok": "grok", "kimi": "kimi", "update": "update", "tip": "tip"}


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
                outline=ICON_INK, width=max(2, int(n * 0.09)))
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
        d.arc([n * 0.08, n * 0.08, n * 0.92, n * 0.92], start=150, end=330, fill=ICON_INK, width=w)
        d.line([(n * 0.22, n * 0.9), (n * 0.9, n * 0.1)], fill=ICON_INK, width=w)
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
    elif kind == "tip":                    # 초록 동그라미에 더하기 (확장 추가)
        d.ellipse([0, 0, n - 1, n - 1], fill=GREEN)
        d.rectangle([n * 0.22, c - n * 0.08, n * 0.78, c + n * 0.08], fill="#1b1c20")
        d.rectangle([c - n * 0.08, n * 0.22, c + n * 0.08, n * 0.78], fill="#1b1c20")
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
FONT = FONTS.get(LANG, "Segoe UI")   # 한국어 맑은 고딕, 일본어·중국어는 그 글자용 Windows 글꼴
REPLY_FONT = (FONT, 10)   # 로봇 입력칸 글씨: Claude 글 칸과 같은 글씨체·크기


class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", ctypes.c_long), ("lfWidth", ctypes.c_long), ("lfEscapement", ctypes.c_long),
                ("lfOrientation", ctypes.c_long), ("lfWeight", ctypes.c_long), ("lfItalic", ctypes.c_ubyte),
                ("lfUnderline", ctypes.c_ubyte), ("lfStrikeOut", ctypes.c_ubyte), ("lfCharSet", ctypes.c_ubyte),
                ("lfOutPrecision", ctypes.c_ubyte), ("lfClipPrecision", ctypes.c_ubyte),
                ("lfQuality", ctypes.c_ubyte), ("lfPitchAndFamily", ctypes.c_ubyte),
                ("lfFaceName", ctypes.c_wchar * 32)]


def ime_font(widget):
    """한글을 조합하는 동안 입력기(IME)가 따로 그리는 글자를 이 칸과 같은 글씨체·크기로.
    (안 하면 Windows 기본 글씨로 그려서 쓰는 중인 글자만 크게 보임)"""
    try:
        f = tkfont.Font(root=widget, font=widget.cget("font"))
        size = f.actual("size")
        lf = LOGFONTW()
        lf.lfHeight = size if size < 0 else -round(size * widget.winfo_fpixels("1i") / 72)
        lf.lfWeight = 400
        lf.lfCharSet = 1                         # DEFAULT_CHARSET
        lf.lfFaceName = f.actual("family")[:31]
        imm = ctypes.windll.imm32
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = [ctypes.c_void_p]
        imm.ImmSetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.POINTER(LOGFONTW)]
        imm.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        hwnd = widget.winfo_id()
        himc = imm.ImmGetContext(hwnd)
        if himc:
            imm.ImmSetCompositionFontW(himc, ctypes.byref(lf))
            imm.ImmReleaseContext(hwnd, himc)
    except Exception:
        pass


class InlineIME:
    """브라우저·구글 검색창처럼 한글을 글 칸 안에서 바로 조합해 보여 준다 (ㅎ → 하 → 한 이 칠 때마다 칸에).
    Tk 8.6 은 조합 중인 글자를 입력기가 띄운 작은 따로 창에 맡겨서, 한 글자가 완성돼야 칸에 들어갔다.
    키보드 포커스는 Tk 창 본체(Toplevel)가 받으므로 그 창의 입력기 신호를 가로채, 지금 커서가 있는
    로봇 입력칸(attach 한 칸)에 조합 중인 글자를 밑줄 친 채로 넣었다가 완성되면 진짜 글로 바꾼다.
    주의: 창 신호 안에서 Tk 를 부르면 파이썬·Tk 상태가 꼬여 프로그램이 죽는다(실제로 죽었음) →
    신호 안에서는 글자만 받아 쌓아 두고, 칸에 넣는 건 Tk 타이머(15ms)와 키 바인딩에서 flush() 로."""
    WM_IME_SETCONTEXT, WM_IME_STARTCOMPOSITION = 0x0281, 0x010D
    WM_IME_ENDCOMPOSITION, WM_IME_COMPOSITION = 0x010E, 0x010F
    GCS_COMPSTR, GCS_RESULTSTR = 0x0008, 0x0800
    ISC_SHOWUICOMPOSITIONWINDOW = 0x80000000
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint,
                                 ctypes.c_size_t, ctypes.c_ssize_t)

    def __init__(self, toplevel, on_input=None):
        self.top, self.on_input = toplevel, on_input
        u, imm = ctypes.windll.user32, ctypes.windll.imm32
        u.SetWindowLongPtrW.restype = ctypes.c_void_p
        u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        u.CallWindowProcW.restype = ctypes.c_ssize_t
        u.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                      ctypes.c_size_t, ctypes.c_ssize_t]
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = [ctypes.c_void_p]
        imm.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        imm.ImmGetCompositionStringW.restype = ctypes.c_long
        imm.ImmGetCompositionStringW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        self.u, self.imm = u, imm
        self.target = None                       # 조합을 받을 글 칸 (그 칸의 FocusIn/FocusOut 이 정함)
        self.queue = []                          # 창 신호에서 받아 둔 (완성 글 | None, 조합 중 글)
        self._job = None
        self.proc = self.WNDPROC(self.wndproc)   # (들고 있어야 사라지지 않음)
        self.hwnd = toplevel.winfo_id()
        self.old = u.SetWindowLongPtrW(self.hwnd, -4, ctypes.cast(self.proc, ctypes.c_void_p))   # GWLP_WNDPROC

    def attach(self, w):
        self.target = w
        if self._job is None:
            self.poll()

    def detach(self, w):
        if self.target is w:
            self.flush()
            self.target = None

    def poll(self):
        self.flush()
        self._job = self.top.after(15, self.poll) if self.target is not None else None

    def wndproc(self, hwnd, msg, wp, lp):
        # (여기서는 Tk 를 부르지 않는다 — 위 주의)
        try:
            if msg == self.WM_IME_SETCONTEXT:    # 입력기의 조합 창은 띄우지 말라고 (글 칸에 직접 그림)
                lp &= ~self.ISC_SHOWUICOMPOSITIONWINDOW
            elif self.target is not None and msg in (self.WM_IME_STARTCOMPOSITION, self.WM_IME_COMPOSITION,
                                                     self.WM_IME_ENDCOMPOSITION):
                if msg == self.WM_IME_COMPOSITION:
                    done = self.text(hwnd, self.GCS_RESULTSTR) if lp & self.GCS_RESULTSTR else None
                    comp = self.text(hwnd, self.GCS_COMPSTR) if lp & self.GCS_COMPSTR else ""
                    self.queue.append((done, comp))
                elif msg == self.WM_IME_ENDCOMPOSITION:
                    self.queue.append((None, ""))
                return 0
        except Exception:
            pass
        return self.u.CallWindowProcW(self.old, hwnd, msg, wp, lp)

    def flush(self, *_):
        """받아 둔 조합 글자를 칸에 넣는다 (Tk 타이머·키 바인딩에서 — 칠 키보다 먼저 처리되게)."""
        w, got = self.target, bool(self.queue)
        while self.queue:
            done, comp = self.queue.pop(0)
            if w is None:
                continue
            try:
                self.preedit(w, "")
                if done:
                    w.insert("insert", done)
                self.preedit(w, comp)
                w.see("insert")
            except tk.TclError:
                pass
        if got and self.on_input:
            self.on_input()

    def text(self, hwnd, flag):
        himc = self.imm.ImmGetContext(hwnd)
        if not himc:
            return ""
        try:
            n = self.imm.ImmGetCompositionStringW(himc, flag, None, 0)
            if n <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(n // 2 + 1)
            self.imm.ImmGetCompositionStringW(himc, flag, buf, n)
            return buf.value[:n // 2]
        finally:
            self.imm.ImmReleaseContext(hwnd, himc)

    @staticmethod
    def preedit(w, s):
        """조합 중인 글자: 커서 자리에 밑줄 친 채로 (다음 조합이 오면 바꿔 끼움)."""
        if w.tag_ranges("ime"):
            w.delete("ime.first", "ime.last")
        if s:
            w.insert("insert", s, ("ime",))

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
# (위 도트 그림은 아이콘·스토어 그림을 만드는 도구들이 쓴다. 화면의 로봇은 아래 robot_image 로 매끈하게 그림)

# ---- 화면 로봇: 4배로 크게 그린 뒤 줄여서 매끈하게 ----
BOT_O = "#f7952c"        # 몸 주황
BOT_O2 = "#e27f1d"       # 귀·발 (조금 진한 주황)
BOT_LINE = "#9c4a0c"     # 테두리
BOT_FACE = "#ffc78f"     # 얼굴판·배 (연한 주황)
BOT_EYE = "#3b2416"      # LED 눈 (둥근 사각형)
# 상태 색: 안테나 공과 가슴 체크 마크
BOT_STATE = {"idle": "#ffc98a", "work": "#ffd84d", "happy": "#6fe39a", "alert": "#ff5c5c"}


def robot_image(mode, w, h, blink=False, arm_up=0, hard=True):
    """귀여운 주황 로봇 (RGBA). mode: idle·work·happy·alert, arm_up: 0 내림 / 1 왼팔 / 2 오른팔 (일할 때 번갈아).
    hard: 가장자리를 딱 끊기 (화면 로봇용). 아이콘처럼 진짜 투명 배경이면 False 로 부드럽게."""
    k = 4
    W, H = w * k, h * k
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sx, sy = W / 150, H / 160                       # 150 x 160 칸 기준으로 그린다

    def box(x0, y0, x1, y1):
        return [x0 * sx, y0 * sy, x1 * sx, y1 * sy]
    lw = max(1, int(4 * sx))
    state = BOT_STATE.get(mode, BOT_STATE["idle"])

    # 안테나
    d.line([75 * sx, 10 * sy, 75 * sx, 26 * sy], fill=BOT_LINE, width=lw + int(2 * sx))
    d.ellipse(box(65, 1, 85, 21), fill=state, outline=BOT_LINE, width=lw)
    d.ellipse(box(70, 5, 76, 11), fill="#ffffff")
    # 팔 (몸 뒤)
    for side, x0 in ((1, 24), (2, 110)):
        up = arm_up == side
        d.rounded_rectangle(box(x0, 92 if up else 102, x0 + 16, 120 if up else 130),
                            radius=8 * sx, fill=BOT_O, outline=BOT_LINE, width=lw)
    # 발
    d.rounded_rectangle(box(44, 136, 70, 154), radius=7 * sx, fill=BOT_O2, outline=BOT_LINE, width=lw)
    d.rounded_rectangle(box(80, 136, 106, 154), radius=7 * sx, fill=BOT_O2, outline=BOT_LINE, width=lw)
    # 몸통·배
    d.rounded_rectangle(box(38, 96, 112, 142), radius=18 * sx, fill=BOT_O, outline=BOT_LINE, width=lw)
    d.rounded_rectangle(box(55, 104, 95, 132), radius=10 * sx, fill=BOT_FACE)
    # 가슴: 할 일(Task)을 끝내 주는 로봇이라 체크 마크 (상태 색 동그라미 위)
    d.ellipse(box(64, 107, 86, 129), fill=state, outline=BOT_LINE, width=max(1, lw // 2))
    d.line([(68.5 * sx, 118 * sy), (73.5 * sx, 123 * sy), (81.5 * sx, 112.5 * sy)],
           fill=BOT_LINE, width=lw, joint="curve")
    # 귀
    d.rounded_rectangle(box(4, 48, 18, 74), radius=6 * sx, fill=BOT_O2, outline=BOT_LINE, width=lw)
    d.rounded_rectangle(box(132, 48, 146, 74), radius=6 * sx, fill=BOT_O2, outline=BOT_LINE, width=lw)
    # 머리·얼굴판
    d.rounded_rectangle(box(13, 24, 137, 98), radius=32 * sx, fill=BOT_O, outline=BOT_LINE, width=lw)
    d.rounded_rectangle(box(27, 36, 123, 88), radius=24 * sx, fill=BOT_FACE)
    d.rounded_rectangle(box(30, 28, 70, 34), radius=3 * sx, fill="#ffb867")   # 머리 윗부분 반짝
    # 눈
    for ex in (55, 95):
        if mode == "happy":                         # ^ ^
            d.arc(box(ex - 10, 52, ex + 10, 70), 200, 340, fill=BOT_EYE, width=lw + int(sx))
        elif blink:
            d.rounded_rectangle(box(ex - 9, 59, ex + 9, 64), radius=2 * sx, fill=BOT_EYE)
        else:                                       # 로봇다운 둥근 사각형 LED 눈
            big = 2 if mode == "alert" else 0
            d.rounded_rectangle(box(ex - 8 - big, 50 - big, ex + 8 + big, 70 + big),
                                radius=5 * sx, fill=BOT_EYE)
            d.rounded_rectangle(box(ex - 5, 53, ex - 1, 58), radius=1.5 * sx, fill="#ffffff")   # 반짝
    # 입
    if mode == "alert":
        d.ellipse(box(70, 72, 80, 82), fill=BOT_EYE)
    elif mode == "happy":
        d.chord(box(64, 68, 86, 84), 0, 180, fill=BOT_EYE)
    else:
        d.arc(box(66, 66, 84, 80), 20, 160, fill=BOT_EYE, width=lw)
    small = img.resize((w, h), Image.LANCZOS)
    if hard:
        # 투명색 화면 위라 가장자리를 반투명으로 두면 검은 테가 생긴다 → 반 이상 칠해진 점만 남긴다
        small.putalpha(small.getchannel("A").point(lambda v: 255 if v >= 110 else 0))
    return small


def fmt_dur(sec):
    """3분 5초 / 3m 5s / 3分5秒 …"""
    sec = max(0, int(sec))
    s_, m_, h_, a, b = UNITS.get(ui_lang(), UNITS["en"])
    if sec < 60:
        return f"{sec}{a}{s_}"
    if sec < 3600:
        return f"{sec // 60}{a}{m_}{b}{sec % 60}{a}{s_}"
    return f"{sec // 3600}{a}{h_}{b}{sec % 3600 // 60}{a}{m_}"


def fmt_short(sec):
    """목록용 짧은 시간: 35초 / 3분 / 2시간."""
    sec = max(0, int(sec))
    s_, m_, h_, a, _ = UNITS.get(ui_lang(), UNITS["en"])
    return (f"{sec}{a}{s_}" if sec < 60 else f"{sec // 60}{a}{m_}" if sec < 3600
            else f"{sec // 3600}{a}{h_}")


def answer_lines(text):
    """답변(마크다운)을 (종류, 글) 줄 목록으로: h 소제목 / li 목록 / gap 빈 줄 다음 문단 / p 보통.
    굵게(**)·코드(`) 표시와 표의 세로줄은 걷어 낸다."""
    out, gap = [], False
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            gap = True
            continue
        if set(s) <= set("|-: "):                 # 표 구분선
            continue
        s = s.replace("**", "").replace("`", "")
        if s.startswith("|"):
            s = " · ".join(c.strip() for c in s.strip("|").split("|") if c.strip())
        if s.startswith("#"):
            out.append(("h", s.lstrip("#").strip()))
        elif s[:2] in ("- ", "* ", "• "):
            out.append(("li", "• " + s[2:].strip()))
        elif len(s) > 2 and s[0].isdigit() and s[1:3] in (". ", ") "):
            out.append(("li", s))
        else:
            out.append(("gap" if gap and out else "p", s))
        gap = False
    return out


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


def make_sounds(missing_only=False):
    rate = 44100
    for name, notes in SOUNDS.items():
        path = os.path.join(APP_DIR, f"{name}.wav")
        if missing_only and os.path.exists(path):
            continue
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


IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def image_dir():
    """답장에 붙인 이미지를 두는 곳: 사진\\TaskPet (Claude 앱 안의 Claude Code도 읽을 수 있는 곳 —
    %LOCALAPPDATA% 는 앱 가상화로 다르게 보일 수 있어 피한다)."""
    base = os.path.join(HOME, "Pictures")
    try:
        import uuid
        guid = (ctypes.c_byte * 16).from_buffer_copy(
            uuid.UUID("33E28130-4E1E-4676-835A-98395C3BC3BB").bytes_le)   # FOLDERID_Pictures
        buf = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0:
            base = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
    except Exception:
        pass
    path = os.path.join(base, APP)
    os.makedirs(path, exist_ok=True)
    return path


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
    """실행 중이던 옛 TaskPet이 완전히 꺼질 때까지 잠깐(최대 2초) 기다리며 덮어쓴다."""
    for _ in range(10):
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


def remove_old_extracts():
    """한 파일(onefile) 시절 TaskPet 이 켤 때마다 임시 폴더에 풀고 못 지운 _MEI 폴더(하나에 70MB쯤)를 치운다.
    TaskPet 훅 프로그램이 든 폴더만 지운다 (다른 프로그램의 _MEI 는 건드리지 않음)."""
    me = os.path.normcase(getattr(sys, "_MEIPASS", ""))
    for d in glob.glob(os.path.join(tempfile.gettempdir(), "_MEI*")):
        if os.path.normcase(d) != me and os.path.isfile(os.path.join(d, HOOK_EXE)):
            shutil.rmtree(d, ignore_errors=True)


def remove_old_copies(folder):
    for p in glob.glob(os.path.join(folder, "**", "*.old"), recursive=True):
        try:
            os.remove(p)
        except OSError:
            pass


def install():
    try:
        _install()
    except Exception as ex:
        msgbox(t("install_failed") + f"{type(ex).__name__}: {ex}", 0x10)


def _install():
    os.makedirs(INSTALL_DIR, exist_ok=True)
    stop_running_widget(INSTALL_DIR)
    exe = os.path.join(INSTALL_DIR, "TaskPet.exe")
    updating = os.path.exists(exe)
    remove_old_copies(INSTALL_DIR)
    subprocess.run(["taskkill", "/f", "/im", NATIVE_EXE], capture_output=True, creationflags=NO_WINDOW)
    # 폴더판: 풀린 폴더(TaskPet.exe + _internal + 훅·감시·연결 프로그램 + 브라우저 확장 압축 해제본)를 통째로 복사.
    # 예전 버전의 파이썬 부품은 먼저 지워 섞이지 않게 (못 지운 파일은 copy_retry 가 비켜 두고 덮음)
    shutil.rmtree(os.path.join(INSTALL_DIR, "_internal"), ignore_errors=True)
    for base, _, files in os.walk(APP_DIR):
        dst = os.path.normpath(os.path.join(INSTALL_DIR, os.path.relpath(base, APP_DIR)))
        os.makedirs(dst, exist_ok=True)
        for name in files:
            copy_retry(os.path.join(base, name), os.path.join(dst, name))
    # 예전에 Claude 데스크톱 앱(MSIX) 안에서 설치한 적이 있으면 그 앱의 가상 공간에 옛 사본이 남아,
    # 앱 안에서 도는 Claude Code(앱 터미널 포함)는 계속 옛 훅을 쓴다 → 남아 있는 도우미만 새것으로 덮어쓴다
    for d in glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Packages", "*", "LocalCache", "Local", APP)):
        for name in (HOOK_EXE, GPT_EXE, NATIVE_EXE, TERM_EXE):
            if os.path.exists(os.path.join(d, name)):
                try:
                    copy_retry(os.path.join(INSTALL_DIR, name), os.path.join(d, name))
                except OSError:
                    pass
    for p in glob.glob(os.path.join(INSTALL_DIR, "*.wav")):   # 알림 소리는 새 버전이 켜질 때 다시 만든다
        try:
            os.remove(p)
        except OSError:
            pass
    hook = os.path.join(INSTALL_DIR, HOOK_EXE)
    register_native_host()

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
    pat = re.compile(rb"Mapping internal session (local_[A-Za-z0-9-]+) to CLI session "
                     + re.escape(sid.encode("utf-8")))
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")):
        for name in ("main.log.old", "main.log"):
            p = os.path.join(base, "Claude", "logs", name)
            try:
                size = os.path.getsize(p)
                with open(p, "rb") as f:
                    f.seek(max(0, size - 8_000_000))
                    for line in f:               # 한 줄씩 (8MB 로그를 통째로 글자로 바꾸지 않게)
                        m = pat.search(line) if b"Mapping internal session" in line else None
                        if m:
                            found = m.group(1).decode("ascii")
            except OSError:
                pass
    return found


class _MemCounters(ctypes.Structure):     # PROCESS_MEMORY_COUNTERS_EX
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                                       "PrivateUsage")]


def proc_private_bytes(pid):
    """그 프로세스만 쓰는 메모리 (작업 관리자의 '메모리'와 비슷). 모르면 0."""
    k = ctypes.WinDLL("kernel32")
    k.OpenProcess.restype = ctypes.c_void_p
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MemCounters), ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return 0
    try:
        m = _MemCounters()
        m.cb = ctypes.sizeof(m)
        return m.PrivateUsage if k.K32GetProcessMemoryInfo(h, ctypes.byref(m), m.cb) else 0
    finally:
        k.CloseHandle(h)


class ChatGptWatcher:
    """taskpet-chatgpt.exe를 띄워 두고, ChatGPT 창에서 '작업 중'인 대화 제목 목록을 받는다.
    일반 채팅은 컴퓨터에 기록이 남지 않아 창을 화면 읽기 기능으로 읽는 수밖에 없다."""

    MEM_LIMIT = 150 * 2**20   # 감시 프로그램이 이보다 커지면 새로 띄운다 (보통 20~30MB)

    def __init__(self):
        self.report = None        # 가장 최근 {"ok", "hwnd", "working"}
        self.fresh = False
        self.proc = None
        self.sent_at = 0.0        # 답 보내기·카드 명령을 보낸 시각 (결과가 오면 0)
        self.exe = next((p for p in (os.path.join(APP_DIR, GPT_EXE),
                                     os.path.join(APP_DIR, "..", "build", GPT_EXE))
                         if os.path.exists(p)), None)
        self.launch()

    def launch(self):
        if not self.exe:
            return
        try:
            self.proc = subprocess.Popen(
                [self.exe, str(os.getpid())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        except OSError:
            self.proc = None
            return
        import threading
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        for line in proc.stdout:
            try:
                obj = json.loads(line.decode("utf-8", "ignore"))
            except Exception:
                continue
            if "reply" in obj:            # 답 보내기 결과
                self.reply_result = obj["reply"]
                self.sent_at = 0.0
            elif "gptchat" in obj:        # ChatGPT 앱 대화 글 (로봇에서 그 줄을 펼쳐 볼 때만 물어봄)
                self.chat_result = obj["gptchat"]
                self.chat_seq = getattr(self, "chat_seq", 0) + 1
            else:
                self.report = obj
                self.fresh = True

    def check_memory(self):
        """만일을 위한 안전장치: 감시 프로그램이 한도를 넘으면 하던 명령이 없을 때 새로 띄운다.
        (1.6.2까지는 .NET 화면 읽기가 2초마다 윈도우 쪽 메모리를 조금씩 흘려 1분에 약 1.2MB씩 늘었다.
        1.6.3부터 COM 화면 읽기로 바꿔 평평하므로 보통은 여기까지 오지 않는다.)"""
        p = self.proc
        if not (p and p.poll() is None) or (self.sent_at and time.time() - self.sent_at < 120):
            return False
        if proc_private_bytes(p.pid) < self.MEM_LIMIT:
            return False
        try:
            p.kill()
            p.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.launch()
        return True

    def reply(self, title, text, vscode=False, images=(), restore=0):
        """Claude 앱(또는 VS Code)의 그 세션에 글을 넣어 보낸다 (창은 앞으로 가져오지 않음). 결과는 take_reply().
        images 가 있으면 감시 프로그램이 잠깐 포커스를 받아 진짜로 붙여넣고, 포커스는 restore 창으로 돌려놓는다."""
        self.reply_result = None
        if not (self.proc and self.proc.poll() is None):
            self.reply_result = t("reply_nohelper")
            return
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        try:
            cmd = "replyvscode" if vscode else "replyclaude"
            imgs = base64.b64encode("\n".join(images).encode("utf-8")).decode("ascii")
            # 감시 프로그램이 창에 포커스를 줄 수 있게 허락 (지금은 로봇을 막 누른 참이라 로봇이 맨 앞)
            ctypes.windll.user32.AllowSetForegroundWindow(self.proc.pid)
            self.proc.stdin.write(f"{cmd}\t{title}\t{b64}\t{imgs}\t{int(restore or 0)}\n".encode("utf-8"))
            self.proc.stdin.flush()
            self.sent_at = time.time()
        except OSError:
            self.reply_result = t("reply_nohelper")

    def ask_chat(self, title):
        """ChatGPT 앱에 지금 열린 대화가 그 제목이면 메시지를 읽어 달라고 한다. 결과는 chat_result."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(f"gptchat\t{title}\n".encode("utf-8"))
                self.proc.stdin.flush()
            except OSError:
                pass

    def reply_gpt(self, title, text):
        """ChatGPT 앱 그 대화에 글을 넣어 보낸다 (창은 앞으로 가져오지 않음). 결과는 take_reply()."""
        self.reply_result = None
        if not (self.proc and self.proc.poll() is None):
            self.reply_result = t("reply_nohelper")
            return
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        try:
            self.proc.stdin.write(f"replygpt\t{title}\t{b64}\n".encode("utf-8"))
            self.proc.stdin.flush()
            self.sent_at = time.time()
        except OSError:
            self.reply_result = t("reply_nohelper")

    def card(self, title, label, other="", vscode=False):
        """질문 카드(AskUserQuestion)에서 선택지(또는 '기타' + 글)를 골라 제출한다. 결과는 take_reply()."""
        self.reply_result = None
        if not (self.proc and self.proc.poll() is None):
            self.reply_result = t("reply_nohelper")
            return
        enc = lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii")
        try:
            cmd = "cardvscode" if vscode else "cardclaude"
            self.proc.stdin.write(f"{cmd}\t{title}\t{enc(label)}\t{enc(other)}\n".encode("utf-8"))
            self.proc.stdin.flush()
            self.sent_at = time.time()
        except OSError:
            self.reply_result = t("reply_nohelper")

    def take_reply(self):
        r, self.reply_result = getattr(self, "reply_result", None), None
        return r

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


def browser_extension_state():
    """(지원 브라우저가 있는지, 우리 확장이 어느 브라우저에든 설치돼 있는지).
    스토어판은 프로필의 Extensions 안 ID 폴더로, 직접 불러온 개발판은 프로필 설정 파일에 적힌 ID로 안다."""
    local = os.environ.get("LOCALAPPDATA", "")
    found_browser = False
    for sub in (r"Google\Chrome", r"BraveSoftware\Brave-Browser", r"Microsoft\Edge", "Chromium"):
        data = os.path.join(local, sub, "User Data")
        if not os.path.isdir(data):
            continue
        found_browser = True
        for prof in [os.path.join(data, "Default")] + glob.glob(os.path.join(data, "Profile *")):
            if any(os.path.isdir(os.path.join(prof, "Extensions", i)) for i in EXT_IDS):
                return True, True
            for name in ("Secure Preferences", "Preferences"):
                try:
                    with open(os.path.join(prof, name), "rb") as f:
                        text = f.read()
                except OSError:
                    continue
                if any(i.encode() in text for i in EXT_IDS):
                    return True, True
    return found_browser, False


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


def term_exe():
    return next((p for p in (os.path.join(APP_DIR, TERM_EXE), os.path.join(APP_DIR, "..", "build", TERM_EXE))
                 if os.path.exists(p)), None)


def term_run(cmd, e, text=""):
    """터미널 도우미 실행 → 결과 이름 (ok / gone / no_console / no_helper / error)."""
    exe = term_exe()
    if not exe:
        return "no_helper"
    args = [exe, cmd, str(e.get("cc_pid", 0)), str(e.get("cc_start", 0))]
    if cmd == "send":
        args.append(base64.b64encode(text.encode("utf-8")).decode("ascii"))
    try:
        r = subprocess.run(args, capture_output=True, timeout=15, creationflags=NO_WINDOW)
        return r.stdout.decode("utf-8", "ignore").strip() or "error"
    except (OSError, subprocess.TimeoutExpired):
        return "error"


def is_term(e):
    """터미널(cli)에서 도는 Claude Code 세션이고, 그 프로세스를 훅이 알려 줬는지."""
    return e.get("src") == "claude" and e.get("entry") == "cli" and bool(e.get("cc_pid"))


def web_command(obj):
    """로봇 → 브라우저 확장 명령 한 줄 (연결 프로그램이 읽어 그 브라우저 확장에게 넘김)."""
    try:
        with open(WEB_CMD, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except OSError:
        pass


def web_chat_file(e):
    return os.path.join(WEB_CHAT_DIR, f"{e.get('browser') or 'web'}-{e.get('tab')}.json")


def web_turns(msgs):
    """확장이 보낸 [['me'|'ai', 글], ...] → 대화 기록창의 턴 목록 (Claude Code 기록과 같은 모양)."""
    turns = []
    for m in msgs:
        if not isinstance(m, (list, tuple)) or len(m) < 2:
            continue
        role, text = m[0], str(m[1])
        if role == "me" or not turns:
            turns.append({"me": text if role == "me" else "", "t0": 0, "imgs": [], "parts": [], "open": None})
            if role == "me":
                continue
        turns[-1]["parts"].append(("text", text))
    return turns


def open_task(key, e):
    if e.get("src") == "update":
        Updater.install(e)
        return
    if e.get("src") == "tip":
        try:
            os.startfile(STORE_URL)
        except OSError:
            pass
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
            web_command({"cmd": "open", "tab": e.get("tab"), "conv": e.get("conv", ""),
                         "url": url, "browser": browser})
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
    if is_term(e):
        try:                                      # 도우미가 창을 앞으로 가져올 수 있게 허락
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        threading.Thread(target=term_run, args=("focus", e), daemon=True).start()
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
    return p[:80] if p else t("img_tag")


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
    이때는 Claude Code가 승인 대기 신호를 보내지 않으므로 기록을 직접 읽는다.
    질문이 있으면 {"ask": 질문, "choices": [{"label", "message"}, ...]}, 없으면 None.
    choices 는 글로 답하는 버튼만 (커밋·PR 같은 앱 동작 버튼은 로봇에서 누를 수 없어 뺀다)."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as f:
            f.seek(max(0, size - 600_000))
            tail = f.read()
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        if b'"mcp__ccd_turn__wrap_up"' not in line:
            continue
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ts < since - 2:
            return None           # 이번 턴 전에 한 것
        for part in (rec.get("message") or {}).get("content") or []:
            inp = part.get("input") if isinstance(part, dict) else None
            if (part.get("name") == "mcp__ccd_turn__wrap_up" and isinstance(inp, dict)
                    and str(inp.get("ask") or "").strip()):
                acts = inp.get("actions")
                if isinstance(acts, str):          # 버튼 목록이 글(JSON)로 들어오기도 함
                    try:
                        acts = json.loads(acts)
                    except ValueError:
                        acts = []
                choices = []
                for a in acts if isinstance(acts, list) else []:
                    if isinstance(a, dict) and not a.get("action") and a.get("label"):
                        choices.append({"label": str(a["label"])[:24],
                                        "message": str(a.get("message") or a["label"])})
                return {"ask": str(inp["ask"]).strip()[:120], "choices": choices}
        return None
    return None


def claude_last_answer(transcript):
    """이번 턴의 마지막 답변 글 (마지막 도구 사용 뒤에 Claude가 쓴 글), 세션을 연 곳, 자동으로 붙은 세션 제목,
    그리고 내가 마지막으로 보낸 메시지.
    돌려주는 값: (답변 글, "claude-desktop" | "claude-vscode" | "cli" | "", 제목, 내 메시지)
    VS Code 패널은 이 자동 제목을 세션 이름으로 보여 준다."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as f:
            f.seek(max(0, size - 600_000))
            tail = f.read()
    except OSError:
        return "", "", "", ""
    texts, entry, ai_title, question = [], "", "", ""
    for line in tail.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        entry = rec.get("entrypoint") or entry
        if rec.get("type") == "ai-title":
            ai_title = str(rec.get("aiTitle") or "") or ai_title
        said = user_said(rec)                    # 내가 보낸 글 (일하는 중에 끼워 보낸 글도)
        if said:
            question = said
        msg = rec.get("message")
        if rec.get("type") not in ("user", "assistant") or not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind in ("tool_use", "tool_result") or (rec["type"] == "user" and kind == "text"
                                                        and not rec.get("isMeta")):
                texts = []                       # 도구를 쓰거나 새 질문이 오면 그 앞 글은 중간 설명
            elif rec["type"] == "assistant" and kind == "text":
                texts.append(str(part.get("text") or ""))
    answer = "\n\n".join(x.strip() for x in texts if x.strip())
    # 원래 글 그대로 둔다 (보여 줄 때 answer_lines 로 소제목·목록을 다듬음)
    return answer.strip()[:4000], entry, ai_title.strip()[:60], question.strip()[:1000]


PASTED_TAG = re.compile(r"</?pasted_content[^>]*>")


def user_said(rec):
    """기록 한 줄이 내가 보낸 메시지면 그 글, 아니면 None.
    Claude가 일하는 중에 끼워 보낸 글(queued_command)도 내 메시지. 붙여 넣은 글은 꼬리표만 걷고,
    시스템이 넣은 글(<...>, 요약, 중단 표시, 첨부 설명)은 빼고, 이미지는 (이미지)로."""
    if not isinstance(rec, dict) or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    if rec.get("type") == "user" and not rec.get("isCompactSummary"):
        msg = rec.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
    elif rec.get("type") == "attachment":
        att = rec.get("attachment")
        if not (isinstance(att, dict) and att.get("type") == "queued_command"
                and att.get("commandMode", "prompt") == "prompt"):
            return None
        content = att.get("prompt")
    else:
        return None
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return None
    said = [PASTED_TAG.sub("", str(p.get("text") or "")).strip() for p in content
            if isinstance(p, dict) and p.get("type") == "text"]
    said = [x for x in said if x and not x.startswith(("<", "[Image", "[Request interrupted"))]
    if any(isinstance(p, dict) and p.get("type") == "image" for p in content):
        said.append(t("img_tag"))
    return "\n".join(said) if said else None


def images_in(content):
    """메시지·도구 결과 안의 그림들 (base64 글자들)."""
    out = []
    for p in content if isinstance(content, list) else []:
        src = p.get("source") if isinstance(p, dict) and p.get("type") == "image" else None
        if isinstance(src, dict) and src.get("type") == "base64" and src.get("data"):
            out.append(str(src["data"]))
    return out


def rec_images(rec):
    """내가 보낸 메시지(끼워 보낸 글 포함)에 붙인 그림들."""
    if rec.get("type") == "attachment":
        return images_in((rec.get("attachment") or {}).get("prompt"))
    msg = rec.get("message")
    return images_in(msg.get("content") if isinstance(msg, dict) else None)


def result_images(rec):
    """도구 결과(예: 그림 파일 읽기)가 돌려준 그림들."""
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for part in (content if isinstance(content, list) else [])
            if isinstance(part, dict) and part.get("type") == "tool_result"
            for b in images_in(part.get("content"))]


def claude_image(transcript, ref):
    """claude_turns 가 남긴 그림 자리 → base64 글자 (없으면 None).
    자리 = "줄 위치:u번호"(내가 붙인 그림) 또는 "줄 위치:r번호"(도구 결과 그림) — 그 한 줄만 다시 읽는다."""
    try:
        off, which = ref.split(":")
        with open(transcript, "rb") as f:
            f.seek(int(off))
            rec = json.loads(f.readline())
        return (rec_images(rec) if which[0] == "u" else result_images(rec))[int(which[1:])]
    except (OSError, ValueError, IndexError, AttributeError, TypeError):
        return None


def claude_turns(transcript, tail_bytes=1_500_000, state=None):
    """대화를 차례대로 (끝에서 tail_bytes 만큼만 읽음). 위로 스크롤하면 tail_bytes 를 늘려 다시 부른다.
    state(dict)를 넘기면 읽은 자리를 거기 기억했다가, 다음에 같은 파일·같은 tail_bytes 로 부를 때
    새로 붙은 줄만 읽어 이어 붙인다 (일하는 동안 1초마다 수십 MB 를 다시 읽지 않게).
    파일은 한 줄씩 읽어서 큰 기록도 한꺼번에 메모리에 올리지 않는다.
    돌려주는 값: (대화 목록, 앞에 더 있는지). 대화 하나 =
      {"me": 내 메시지, "imgs": 내가 붙인 그림 자리들, "t0": 보낸 시각, "ai": [Claude 글들],
       "parts": [("text", 글) | ("tools", [(종류, 대상)…]) | ("image", 그림 자리)…] (나온 차례대로),
       "open": 결과가 아직 안 온 마지막 도구 (종류, 대상) 또는 None}
    그림은 base64 글자(그림 하나에 수백 KB)를 들고 있지 않고 자리만 — 보여 줄 때 claude_image 로 꺼낸다."""
    st = state if state is not None else {}
    try:
        size = os.path.getsize(transcript)
    except OSError:
        return [], False
    # 다른 파일·다른 양이거나, 파일이 줄었거나, 너무 길게 이어 붙었으면 끝에서부터 새로
    if (st.get("path") != transcript or st.get("tail") != tail_bytes or size < st.get("off", 0)
            or size - st.get("start", 0) > tail_bytes * 2):
        start = max(0, size - tail_bytes)
        st.clear()
        st.update(path=transcript, tail=tail_bytes, start=start, off=start, skip=start > 0,
                  turns=[], cur=None, results=set(), last_tool=None, open_turn=None)
    turns, results = st["turns"], st["results"]     # results = 결과가 온 도구들
    cur, last_tool = st["cur"], st["last_tool"]     # last_tool = 마지막으로 부른 도구

    def new_turn(me, ts, imgs=()):
        turn = {"me": me, "t0": ts, "imgs": list(imgs), "ai": [], "parts": [], "open": None}
        turns.append(turn)
        return turn

    try:
        with open(transcript, "rb") as f:
            f.seek(st["off"])
            if st["skip"]:                       # 잘린 첫 줄
                st["off"] += len(f.readline())
                st["skip"] = False
            for line in f:
                if not line.endswith(b"\n"):     # 아직 쓰는 중인 마지막 줄은 다음에
                    break
                at = st["off"]
                st["off"] += len(line)
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                said = user_said(rec)
                if said:
                    cur = new_turn(said, rec_time(rec), [f"{at}:u{i}" for i in range(len(rec_images(rec)))])
                    continue
                if not isinstance(rec, dict) or rec.get("isSidechain"):
                    continue
                msg = rec.get("message")
                content = (msg.get("content") if isinstance(msg, dict) else None) or []
                if rec.get("type") == "user":
                    n = 0
                    for part in content if isinstance(content, list) else []:
                        if isinstance(part, dict) and part.get("type") == "tool_result":
                            results.add(part.get("tool_use_id"))
                            k = len(images_in(part.get("content")))
                            if cur is not None:  # 도구가 돌려준 그림 (예: 이미지 파일 읽기) → 그 자리에 작게
                                cur["parts"] += [("image", f"{at}:r{i}") for i in range(n, n + k)]
                            n += k
                    continue
                if rec.get("type") != "assistant" or not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    kind = part.get("type")
                    if kind not in ("text", "tool_use", "thinking"):
                        continue
                    # 긴 작업 중 Claude 앱이 보여 주는 진행 안내 글은 '생각' 칸(thinking)에 글로 남는 일이 많다
                    # (내용 없는 thinking 은 숨긴 생각이라 건너뜀)
                    text = str(part.get("text" if kind == "text" else "thinking") or "").strip()
                    if kind == "thinking":
                        if not text:
                            continue
                        kind = "text"
                    if kind == "text" and not text:
                        continue
                    if cur is None:              # 잘린 앞부분의 답
                        cur = new_turn("", rec_time(rec))
                    if kind == "text":
                        cur["ai"].append(text)
                        if cur["parts"] and cur["parts"][-1][0] == "text":
                            cur["parts"][-1] = ("text", cur["parts"][-1][1] + "\n\n" + text)
                        else:
                            cur["parts"].append(("text", text))
                        last_tool = None
                        continue
                    name, inp = str(part.get("name") or ""), part.get("input")
                    what = tool_kind(name, inp if isinstance(inp, dict) else {})
                    last_tool = (what, part.get("id"))
                    if what[0] is None:
                        continue
                    if cur["parts"] and cur["parts"][-1][0] == "tools":
                        cur["parts"][-1][1].append(what)
                    else:
                        cur["parts"].append(("tools", [what]))
    except OSError:
        pass
    st["cur"], st["last_tool"] = cur, last_tool
    if st["open_turn"] is not None:              # 지난번 '지금 하는 일'은 지우고 다시 정한다
        st["open_turn"]["open"] = None
        st["open_turn"] = None
    if cur is not None and last_tool and last_tool[0][0] and last_tool[1] not in results:
        cur["open"] = last_tool[0]               # 지금 하고 있는 일 (결과가 아직 안 옴)
        st["open_turn"] = cur
    return turns, st["start"] > 0


_PLAN_CACHE = {}   # 기록 파일 → (읽은 위치, 계획 목록, 계획이 마지막으로 바뀐 시각)


def claude_plan(transcript):
    """지금 계획 목록과 마지막으로 바뀐 시각: (계획 | None, 시각).
    계획은 한참 전에 만들어졌을 수 있어 기록 파일 전체에서 계획 도구만 골라 차례로 적용한다.
    처음 한 번만 끝까지 읽고, 그다음부터는 새로 붙은 부분만 읽는다.
    한 줄씩 읽는다 — 수십 MB 기록을 한꺼번에 읽어 나누면 잠깐이지만 그 두세 배 메모리를 쓴다."""
    off, plan, changed = _PLAN_CACHE.get(transcript, (0, None, 0.0))
    try:
        if os.path.getsize(transcript) < off:    # 파일이 줄었으면 처음부터
            off, plan, changed = 0, None, 0.0
        with open(transcript, "rb") as f:
            f.seek(off)
            for line in f:
                if not line.endswith(b"\n"):     # 아직 쓰는 중인 마지막 줄은 다음에
                    break
                off += len(line)
                if b"update_plan" not in line and b"TodoWrite" not in line and b"wrap_up" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or rec.get("type") != "assistant" or rec.get("isSidechain"):
                    continue
                for part in (rec.get("message") or {}).get("content") or []:
                    if isinstance(part, dict) and part.get("type") == "tool_use":
                        inp = part.get("input")
                        new = plan_step(plan, str(part.get("name") or ""), inp if isinstance(inp, dict) else {})
                        if new is not None:
                            plan, changed = new, rec_time(rec)
    except OSError:
        pass
    _PLAN_CACHE[transcript] = (off, plan, changed)
    return plan, changed


def rec_time(rec):
    """기록 한 줄의 시각 (초). 없으면 0."""
    try:
        return datetime.fromisoformat(str(rec.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def tool_kind(name, inp):
    """도구 이름·입력 → (종류, 대상). 종류 None 은 보여 주지 않는 도구 (계획·도구 찾기·마무리 등)."""
    def base(p):
        return os.path.basename(str(p).replace("/", "\\").rstrip("\\")) if p else ""
    if name in ("Read", "NotebookRead"):
        return "read", base(inp.get("file_path") or inp.get("notebook_path"))
    if name in ("Edit", "MultiEdit", "NotebookEdit"):
        return "edit", base(inp.get("file_path") or inp.get("notebook_path"))
    if name == "Write":
        return "write", base(inp.get("file_path"))
    if name in ("Grep", "Glob"):
        return "search", str(inp.get("pattern") or "")[:30]
    if name in ("Bash", "PowerShell"):
        return "run", str(inp.get("description") or "")[:40]
    if name == "WebSearch":
        return "web", str(inp.get("query") or "")[:30]
    if name == "WebFetch":
        return "web", re.sub(r"^https?://(www\.)?", "", str(inp.get("url") or "")).split("/")[0][:30]
    if name in ("Agent", "Task"):
        return "agent", str(inp.get("description") or "")[:30]
    if name == "AskUserQuestion":
        return "ask", ""
    if "claude-in-chrome" in name or "Claude_Browser" in name:
        return "browser", ""
    short = name.split("__")[-1]
    if (short in ("update_plan", "wrap_up", "TodoWrite", "ToolSearch")
            or name.startswith(("mcp__ccd_", "Task"))):
        return None, ""
    return "tool", short[:24]


# 도구 종류 → (하는 중, 한 뒤) 글. Claude 앱처럼 '읽는 중 taskpet.py' / '읽음 taskpet.py · 편집함 2개'
TOOL_WORDS = {
    "read": (("읽는 중", "읽음"), ("Reading", "Read")),
    "edit": (("편집 중", "편집함"), ("Editing", "Edited")),
    "write": (("만드는 중", "만듦"), ("Writing", "Wrote")),
    "search": (("검색 중", "검색함"), ("Searching", "Searched")),
    "run": (("명령 실행 중", "명령 실행"), ("Running", "Ran")),
    "web": (("웹 보는 중", "웹 봄"), ("Browsing web", "Web")),
    "agent": (("에이전트 실행 중", "에이전트"), ("Running agent", "Agent")),
    "ask": (("질문하는 중", "질문함"), ("Asking", "Asked")),
    "browser": (("브라우저 쓰는 중", "브라우저"), ("Using browser", "Browser")),
    "tool": (("도구 쓰는 중", "도구"), ("Using tool", "Tool")),
}


def tool_words(kind):
    """(하는 중, 한 뒤) 글을 화면 언어로."""
    if kind not in TOOL_WORDS:
        kind = "tool"
    if KO:
        return TOOL_WORDS[kind][0]
    return TOOL_TR.get(ui_lang(), {}).get(kind) or TOOL_WORDS[kind][1]


def tool_doing(what):
    """지금 하는 일 한 줄: '읽는 중 taskpet.py'."""
    kind, target = what
    word = tool_words(kind)[0]
    return f"{word} {target}".strip()


def tools_summary(tools):
    """한 묶음의 도구들을 한 줄로: '읽음 taskpet.py · 편집함 2개 · 명령 실행 3개' (나온 차례대로)."""
    groups = {}
    for kind, target in tools:
        groups.setdefault(kind, []).append(target)
    out = []
    for kind, targets in groups.items():
        word = tool_words(kind)[1]
        uniq = list(dict.fromkeys(x for x in targets if x))
        if kind in ("read", "edit", "write") and len(uniq) == 1:
            out.append(f"{word} {uniq[0]}")       # 파일 하나면 이름 (같은 파일을 여러 번이어도)
        else:
            out.append(f"{word} {t('n_items', n=len(targets))}")
    return " · ".join(out)


def plan_step(plan, name, inp):
    """계획 도구(update_plan·TodoWrite·wrap_up)면 바뀐 계획 목록 [{"content","status"}…], 아니면 None."""
    short = name.split("__")[-1]
    if short == "TodoWrite":
        items = inp.get("todos")
    elif short == "update_plan":
        items = inp.get("items")
    elif short == "wrap_up":                     # 마무리하면 남은 단계도 모두 끝남
        return [dict(x, status="completed") for x in plan] if plan else None
    else:
        return None
    if isinstance(items, list):
        return [{"content": str(x.get("content") or "")[:80], "status": str(x.get("status") or "pending")}
                for x in items if isinstance(x, dict)]
    if not plan:
        return None
    plan = [dict(x) for x in plan]
    if inp.get("advance"):                       # 하던 단계 끝, 다음 단계 시작
        for i, x in enumerate(plan):
            if x["status"] == "in_progress":
                x["status"] = "completed"
                nxt = next((y for y in plan[i + 1:] if y["status"] == "pending"), None)
                if nxt:
                    nxt["status"] = "in_progress"
                break
        else:
            nxt = next((y for y in plan if y["status"] == "pending"), None)
            if nxt:
                nxt["status"] = "in_progress"
    for n in inp.get("done") or []:
        if isinstance(n, int) and 1 <= n <= len(plan):
            plan[n - 1]["status"] = "completed"
    n = inp.get("start")
    if isinstance(n, int) and 1 <= n <= len(plan):
        for x in plan:
            if x["status"] == "in_progress":
                x["status"] = "completed"
        plan[n - 1]["status"] = "in_progress"
    return plan


def claude_pending_card(transcript):
    """아직 답하지 않은 질문 카드(AskUserQuestion)가 있으면 {"ask", "choices", "card": True}, 없으면 None.
    질문 하나·하나만 고르는 카드만 선택지를 꺼낸다 (나머지는 질문만 보여 주고 앱에서 답하게)."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as f:
            f.seek(max(0, size - 600_000))
            tail = f.read()
    except OSError:
        return None
    answered = set()
    for line in reversed(tail.splitlines()):
        if b"tool_result" not in line and b'"AskUserQuestion"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for part in (rec.get("message") or {}).get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_result":
                answered.add(part.get("tool_use_id"))
            elif part.get("name") == "AskUserQuestion":
                if part.get("id") in answered:
                    return None           # 마지막 카드는 이미 답함
                qs = (part.get("input") or {}).get("questions") or []
                if not qs or not isinstance(qs[0], dict):
                    return None
                q = qs[0]
                choices = []
                if len(qs) == 1 and not q.get("multiSelect"):
                    for o in q.get("options") or []:
                        if isinstance(o, dict) and o.get("label"):
                            choices.append({"label": str(o["label"])[:24],
                                            "message": str(o["label"])})
                return {"ask": str(q.get("question") or "").strip()[:120],
                        "choices": choices, "card": True}
    return None


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
        self.tasks = {k: v for k, v in saved.get("tasks", {}).items() if not k.startswith(("u:", "t:"))}
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
        self.web_sent = []                # 웹 탭에 보낸 답의 결과 (키, 됐는지, 오류 이름) — 화면 쪽이 가져감
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
            if e.get("recent"):                  # 켤 때 띄운 최근 대화는 지우거나 새 일이 올 때까지 둔다
                continue
            if (now - e.get("start", now) > 12 * 3600
                    or (e.get("status") == "done" and now - e.get("end", now) > 3600)):
                del self.tasks[k]
                self.dirty = True

    def add_recent_claude(self):
        """켜자마자 가장 최근 Claude Code 대화 1개를 '완료' 줄로 띄운다 — 컴퓨터를 다시 켠 뒤에도
        로봇에서 바로 대화를 보고 이어서 보낼 수 있게. 이미 Claude 줄이 있으면(로봇만 다시 켬) 그대로 둔다."""
        for k in [k for k, e in self.tasks.items() if e.get("recent")]:
            del self.tasks[k]                    # 지난번에 띄운 것은 치우고 지금 가장 최근 것으로
        if any(e.get("src") == "claude" for e in self.tasks.values()):
            return
        files = [p for p in glob.glob(os.path.join(CLAUDE_DIR, "projects", "*", "*.jsonl"))
                 if not os.path.basename(p).startswith("agent-")]   # 에이전트(곁가지) 기록은 빼고
        try:
            tp = max(files, key=os.path.getmtime)
            mtime = os.path.getmtime(tp)
        except (ValueError, OSError):
            return
        sid = os.path.splitext(os.path.basename(tp))[0]
        key = "c:" + sid
        if self.dismissed.get(key, 0) >= mtime:  # 지운 뒤로 새 일이 없으면 다시 띄우지 않음
            return
        cwd = ""
        try:
            with open(tp, "rb") as f:
                f.seek(max(0, os.path.getsize(tp) - 200_000))
                for line in reversed(f.read().splitlines()):
                    if b'"cwd"' in line:
                        cwd = str(json.loads(line).get("cwd") or "")
                        break
        except (OSError, ValueError):
            pass
        turns, _ = claude_turns(tp, 600_000)
        t0 = turns[-1]["t0"] if turns and turns[-1]["t0"] else mtime
        e = {"src": "claude", "id": sid, "prompt": "", "transcript": tp,
             "title": claude_title({"transcript_path": tp, "session_id": sid}),
             "folder": os.path.basename(cwd) or "Claude",
             "start": min(t0, mtime), "end": mtime, "status": "done", "recent": True}
        self.note_answer(e, tp)
        if not e["title"]:                       # 이름 없는 세션은 내 마지막 메시지 앞부분으로
            e["prompt"] = (e.get("asked") or "").split("\n")[0][:40]
        self.tasks[key] = e
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
        if d.get("type") == "sent":              # 로봇에서 보낸 답이 그 탭에 들어갔는지
            if live:
                self.web_sent.append((key, bool(d.get("ok")), str(d.get("error") or ""), d.get("id")))
            return
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
        d = rec.get("d") or {}
        key = "c:" + str(d.get("session_id")) if d.get("session_id") else None
        old = self.tasks.get(key) if key else None
        self._claude_event(rec)
        e = self.tasks.get(key) if key else None
        if e is not None and e is not old and old and old.get("entry") and not e.get("entry"):
            e["entry"] = old["entry"]            # 새 턴으로 줄을 새로 만들어도 어디서 도는 세션인지는 그대로
        if e is not None and d.get("cc_pid"):
            e["cc_pid"], e["cc_start"] = d["cc_pid"], d.get("cc_start", 0)
        elif e is not None and old and old.get("cc_pid") and not e.get("cc_pid"):
            e["cc_pid"], e["cc_start"] = old["cc_pid"], old.get("cc_start", 0)

    def _claude_event(self, rec):
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
                # 질문 카드(AskUserQuestion)로 멈췄으면 질문·선택지를 꺼내 둔다 (로봇에서 바로 고를 수 있게)
                card = claude_pending_card(d.get("transcript_path") or e.get("transcript", "")) if live else None
                if card:
                    e["ask"], e["choices"], e["card"] = card["ask"], card["choices"], True
                if live:
                    self.note_answer(e, d.get("transcript_path") or e.get("transcript", ""))
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
                for k in ("wait_start", "ask", "choices", "card", "sending"):
                    e.pop(k, None)
        elif ev == "stop":
            if e and e.get("status") in ("working", "waiting"):
                for k in ("wait_start", "ask", "choices", "card", "sending"):
                    e.pop(k, None)
                e["title"] = claude_title(d) or e.get("title", "")
                tp = d.get("transcript_path") or e.get("transcript", "")
                bg = claude_bg_pending(tp) if live else 0
                asks = claude_turn_asks(tp, e.get("start", ts)) if live else None
                if live:            # 줄 아래에 보여 줄 마지막 답변, 로봇에서 답장할 수 있는 세션인지
                    self.note_answer(e, tp)
                if asks:
                    e["status"] = "waiting"   # 답을 기다리며 멈춤
                    e["wait_start"] = ts
                    e["ask"], e["choices"] = asks["ask"], asks["choices"]
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

    @staticmethod
    def note_answer(e, transcript):
        e["answer"], e["entry"], ai_title, e["asked"] = claude_last_answer(transcript)
        # VS Code 세션은 따로 붙인 이름이 없으면 자동 제목이 패널의 세션 이름이다 (로봇에서 답할 때 이걸로 찾음)
        if e["entry"] == "claude-vscode" and ai_title and not claude_title(
                {"transcript_path": transcript, "session_id": e.get("id", "")}):
            e["title"] = ai_title

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

    def apply_ext_tip(self, show):
        """브라우저는 있는데 확장이 없으면 '확장 설치' 줄을 하나 둔다 (✕로 지우면 다시 안 뜸)."""
        key = "t:ext"
        if show and key not in self.tasks:
            self.tasks[key] = {"src": "tip", "id": "ext", "prompt": "", "folder": APP,
                               "title": t("ext_tip_title"), "start": time.time(), "status": "tip"}
            self.dirty = True
        elif not show and key in self.tasks:
            del self.tasks[key]
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
            # 답변·세션을 연 곳을 아직 안 꺼내 둔 줄(새로 시작한 줄, 로봇을 다시 켰을 때 등)은 한 번 꺼내 둔다
            if e.get("src") == "claude" and not e.get("entry") and e.get("transcript"):
                self.note_answer(e, e["transcript"])
                self.dirty = True
            # '백그라운드 기다리는 중'이 실제로는 끝나 있고 질문으로 멈춘 상태면 바로잡는다
            if e.get("src") == "claude" and e.get("bg") and e.get("transcript"):
                bg = claude_bg_pending(e["transcript"])
                if bg != e["bg"]:
                    self.dirty = True
                    if bg:
                        e["bg"] = bg
                    else:
                        e.pop("bg", None)
                        asks = claude_turn_asks(e["transcript"], e.get("start", 0))
                        if asks:
                            e["status"] = "waiting"
                            e["wait_start"] = time.time()
                            e["ask"], e["choices"] = asks["ask"], asks["choices"]
                            self.on_event("wait", key)
            # 질문 카드로 멈춰 있는데 선택지를 아직 못 꺼냈으면(로봇을 다시 켰을 때 등) 꺼내 둔다
            if (e.get("src") == "claude" and e.get("status") == "waiting" and not e.get("ask")
                    and e.get("transcript")):
                card = claude_pending_card(e["transcript"])
                if card:
                    e["ask"], e["choices"], e["card"] = card["ask"], card["choices"], True
                    self.dirty = True
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
        self._last_click = ("", 0.0, 0)   # 마지막으로 누른 줄, 그때 시각, 클릭 신호 번호
        self._bub_sig = None
        self._pos_sig = None
        self._infos = []
        self._icons = {}
        self._bot = {}                # 로봇 그림 (표정·팔 모양별로 한 번만 그림)
        self._hist = {}               # 대화 기록창 상태 (어느 세션·몇 개·읽던 자리)
        self._chat = None             # 지금 그려진 대화 기록창 (칸들)
        self._typed_at = 0.0          # 입력칸에 마지막으로 글자를 친 때
        self._rounds = {}             # 둥근 바탕 그림 (크기·색별로 한 번만 그림)
        self.detail = None            # › 로 펼친 상세 카드의 줄 (없으면 목록)
        self.reply_imgs = []          # 답장에 붙인 이미지 파일들
        self.prev_fg = 0              # 로봇 입력칸을 열기 전에 쓰던 창
        self.reply_key = None         # 답을 보내는 중인 줄
        self.reply_var = tk.StringVar(self.root)
        # 쓰던 글은 세션마다 기억해 파일에도 둔다 (밖을 눌러 카드가 닫히거나 로봇을 다시 켜도 그대로)
        self.drafts = read_json(DRAFTS, {})
        self._draft_key = None        # 지금 입력칸이 어느 세션 글인지
        self._want_focus = False      # 사용자가 카드를 열었으니 입력칸에 커서를 줄지
        self._refocus = None          # 카드를 다시 만들기 전 입력칸 커서 자리 (커서가 있었을 때만)
        self._input_extra = 0         # 입력칸이 한 줄보다 늘어난 높이 (그만큼 기록창을 줄임)
        self._thumb_cache = {}        # 대화 속 그림 작은 사진 (그림 이름 → 사진)
        self._img_src = None          # 지금 기록창 그림을 꺼낼 기록 파일 (그림은 자리만 들고 있음)
        self.reply_var.trace_add("write", lambda *a: self.save_draft())
        # 화면에 보이는 앱("claude"·"code"·"chatgpt")들, Claude 앱에 띄워 둔 세션 제목, ChatGPT 앱에 띄워 둔 대화 제목
        self.seen = ((), "", "")
        self.shown_at = time.time()   # 말풍선이 (다시) 보이기 시작한 때 — 자동 숨김 기준
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
        self.bubble.bind("<MouseWheel>", self.chat_wheel)   # 말풍선 어디서든 휠 → 대화 기록창
        try:                          # 한글을 입력칸 안에서 바로 조합 (안 되면 Tk 기본 방식)
            self.ime = InlineIME(self.bubble, lambda: setattr(self, "_typed_at", time.time()))
        except Exception:
            self.ime = None
        self.bubble.bind("<Button-1>", self.bubble_click, add="+")
        self.bubble.withdraw()

        self.tracker = Tracker(self.on_event)
        self.updater = Updater()
        self.ext_tip = None               # 확장 설치 권유 줄을 둘지 (검사 결과, 다른 스레드가 채움)
        self.next_ext_check = time.time() + 30

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
        # 로봇부터 화면에 띄우고, 나머지 준비(최근 대화 읽기·감시 프로그램·소리 파일)는 그 뒤에
        self.draw()
        self.root.update()
        self.root.after(10, self.late_init)
        self.root.mainloop()

    def late_init(self):
        self.tracker.add_recent_claude()          # 켜자마자 가장 최근 대화 1개
        global GPT
        GPT = ChatGptWatcher()
        make_sounds(missing_only=True)
        for f in glob.glob(os.path.join(WEB_CHAT_DIR, "*")):
            try:
                os.remove(f)
            except OSError:
                pass
        if FROZEN:
            threading.Thread(target=remove_old_extracts, daemon=True).start()
        self.tick()

    # ---- 신호 ----
    def on_event(self, kind, key):
        e = self.tracker.tasks.get(key)
        if e and self.viewed(e):
            return                    # 그 세션을 지금 보고 있으면 알리지 않는다
        if self.hidden:
            self.shown_at = time.time()
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
                self.shown_at = time.time()
            self.update_bubble(force=True)

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=INNER, fg=FG,
                    activebackground=ACCENT, activeforeground="#1b1c20")
        m.add_command(label=f"{APP} {VERSION}", state="disabled")
        m.add_separator()
        m.add_command(label=t("clear"), command=self.clear_done)
        m.add_cascade(label=t("settings"), menu=self.settings_menu(m))
        m.add_command(label=t("ext_menu"), command=self.get_extension)
        m.add_separator()
        m.add_command(label=t("uninstall"), command=self.do_uninstall)
        m.add_command(label=t("quit"), command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    # ---- 보고 있는 창은 알리지 않기 · 말풍선 자동 숨김 ----
    def viewed(self, e):
        """그 줄의 세션을 지금 화면에서 보고 있는지 (맨 앞이 아니어도 창이 화면에 보이면 보는 중).
        VS Code는 패널에 세션이 다 보이므로 VS Code 창이 보이면 VS Code 세션 모두,
        Claude 앱·ChatGPT 앱(일반 채팅·Codex)은 띄워 둔 그 대화만."""
        if not self.settings.get("hide_viewed", True):
            return False
        apps, session, gpt = self.seen
        if e.get("src") in ("chatgpt", "codex"):
            return "chatgpt" in apps and bool(gpt) and e.get("title") == gpt
        if e.get("src") != "claude":
            return False
        if e.get("entry") == "claude-vscode":
            return "code" in apps
        return "claude" in apps and bool(session) and e.get("title") == session

    def shown_tasks(self):
        return {k: e for k, e in self.tracker.tasks.items() if not self.viewed(e)}

    def auto_hide(self):
        # 숨겨 둔 사이 새 줄이 생기면(신호 없이 생기는 줄도 있음) 다시 보인다
        keys = set(self.shown_tasks())
        if keys - getattr(self, "_known_keys", keys) and self.hidden:
            self.hidden = False
            self.shown_at = time.time()
            self.update_bubble(force=True)
        self._known_keys = keys
        sec = self.settings.get("autohide", 0)
        if not sec or self.hidden or self.detail:
            return
        if any(e.get("sending") for e in self.tracker.tasks.values()):
            return
        try:                          # 말풍선 위에 마우스를 올려 두면 읽는 중이니 기다린다
            px, py = self.root.winfo_pointerxy()
            b = self.bubble
            if (b.state() != "withdrawn" and b.winfo_rootx() <= px <= b.winfo_rootx() + b.winfo_width()
                    and b.winfo_rooty() <= py <= b.winfo_rooty() + b.winfo_height()):
                self.shown_at = time.time()
                return
        except tk.TclError:
            pass
        if time.time() - self.shown_at > sec:
            self.hidden = True
            self.update_bubble(force=True)

    def follow_progress(self):
        """펼친 카드의 대화 기록이 바뀌면(새 글·새 답) 1초 안에 기록창만 고쳐 그린다 — 일하는 중 글도 실시간으로.
        카드 전체를 다시 만들지 않으므로 입력칸에 쓰던 글이 끊기지 않는다."""
        ch = self._chat
        e = self.tracker.tasks.get(self.detail) if self.detail else None
        if not ch or not e or not self.has_chat(e):
            return
        if time.time() - getattr(self, "_live_at", 0) < 1:
            return
        self._live_at = time.time()
        self.tick_status()
        try:
            if self.read_chat(e) or (e.get("status") == "working") != ch["working"]:
                self.fill_chat(e)
                self.position_bubble()
        except tk.TclError:                      # 그사이 카드가 닫혔으면 그만
            self._chat = None

    def set_setting(self, key, value):
        self.save_setting(key, value)
        self.shown_at = time.time()
        self.update_bubble(force=True)

    def settings_menu(self, parent):
        sm = tk.Menu(parent, tearoff=0, bg=INNER, fg=FG,
                     activebackground=ACCENT, activeforeground="#1b1c20")
        hide = tk.Menu(sm, tearoff=0, bg=INNER, fg=FG,
                       activebackground=ACCENT, activeforeground="#1b1c20")
        cur = self.settings.get("autohide", 0)
        presets = ((0, t("autohide_off")), (10, t("sec", n=10)), (30, t("sec", n=30)), (60, t("min1")))
        for sec, label in presets:
            hide.add_command(label=("● " if cur == sec else "○ ") + label,
                             command=lambda v=sec: self.set_setting("autohide", v))
        custom = cur not in [p[0] for p in presets]
        hide.add_separator()
        hide.add_command(label=("● " + t("autohide_mine", d=fmt_dur(cur))) if custom else "○ " + t("autohide_ask"),
                         command=self.ask_autohide)
        sm.add_cascade(label=t("autohide"), menu=hide)
        flags = (("hide_viewed", True, t("hide_viewed")), ("answer_preview", True, t("answer_preview")))
        for key, default, label in flags:
            on = self.settings.get(key, default)
            sm.add_command(label=("✓ " if on else "   ") + label,
                           command=lambda k=key, v=not on: self.set_setting(k, v))
        sm.add_command(label=("✓ " if MUTED else "   ") + t("mute"), command=self.toggle_mute)
        # 언어: 어느 언어 화면에서도 찾을 수 있게 이름에 늘 'Language' 를 붙이고, 각 언어는 그 언어 글자로
        lm = tk.Menu(sm, tearoff=0, bg=INNER, fg=FG,
                     activebackground=ACCENT, activeforeground="#1b1c20")
        cur = self.settings.get("lang") or ""
        for code, name in [("", t("lang_auto"))] + LANG_NAMES:
            lm.add_command(label=("● " if cur == code else "○ ") + name,
                           command=lambda c=code: self.set_lang(c))
            if not code:
                lm.add_separator()
        sm.add_separator()
        sm.add_cascade(label=t("lang_menu"), menu=lm)
        return sm

    def set_lang(self, code):
        """언어를 바꾸면 글자·글꼴이 여러 곳에 박혀 있으니 로봇을 새로 띄운다."""
        if code == (self.settings.get("lang") or ""):
            return
        self.save_setting("lang", code)
        args = [sys.executable, "--restart"] if FROZEN else [sys.executable, os.path.abspath(__file__), "--restart"]
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        # 작업 묶음(job)에서 빠져나와 따로 돌게 (안 되면 그냥 따로)
        for flags in (0x01000000 | 0x00000008 | 0x00000200, 0x00000008 | 0x00000200):
            try:
                subprocess.Popen(args, cwd=APP_DIR, env=env, creationflags=flags)
                break
            except OSError:
                continue
        self.quit()

    def ask_autohide(self):
        """말풍선 자동 숨김 시간을 직접 정한다 (초, 3초~1시간)."""
        from tkinter import simpledialog
        cur = self.settings.get("autohide", 0) or 20
        v = simpledialog.askinteger(APP, t("autohide_prompt"), parent=self.root,
                                    initialvalue=cur, minvalue=3, maxvalue=3600)
        if v:
            self.set_setting("autohide", int(v))

    def get_extension(self):
        # Chrome 웹 스토어 페이지를 기본 브라우저로 연다 (Chrome·Brave·Edge 모두 여기서 설치)
        try:
            os.startfile(STORE_URL)
        except OSError:
            pass

    def check_ext_tip(self):
        # 켠 지 30초 뒤, 그다음 10분마다 확장이 설치됐는지 본다 (✕로 끈 뒤에는 안 봄)
        if self.ext_tip is not None:
            self.tracker.apply_ext_tip(self.ext_tip and not self.settings.get("ext_tip_off"))
            self.ext_tip = None
        if time.time() < self.next_ext_check or self.settings.get("ext_tip_off"):
            return
        self.next_ext_check = time.time() + 10 * 60

        def work():
            has_browser, installed = browser_extension_state()
            self.ext_tip = has_browser and not installed
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
            self.quit()
            uninstall(ask=False, from_widget=True)

    def clear_done(self):
        tasks = self.tracker.tasks
        for k in [k for k, e in tasks.items() if e.get("status") == "done"]:
            self.tracker.dismissed[k] = time.time()
            del tasks[k]
        self.tracker.dirty = True
        self.update_bubble(force=True)

    def dismiss(self, key):
        if key == "t:ext":
            self.save_setting("ext_tip_off", True)
        self.tracker.tasks.pop(key, None)
        self.tracker.dismissed[key] = time.time()
        self.tracker.dirty = True
        self.update_bubble(force=True)

    CLICK_WAIT_MS = 400      # 한 번 클릭인지 더블 클릭인지 기다리는 시간 (사용자 지정: 보통 0.5초보다 조금 짧게)

    def row_click(self, key, ev=None):
        """한 번 클릭 = 펼치기(› 와 같음), 더블 클릭 = 그 대화 창 열기 (펼치지 않고).
        첫 클릭 뒤 잠깐(0.26초) 두 번째 클릭을 기다렸다가 펼친다. 느린 더블 클릭이라 이미 펼쳐졌으면
        두 번째 클릭(펼친 카드 위)은 bubble_click 이 받아 창을 열고 목록으로 되돌린다."""
        now = time.time()
        last, when, _ = self._last_click
        e = self.tracker.tasks.get(key)
        if getattr(self, "_click_job", None):
            self.root.after_cancel(self._click_job)
            self._click_job = None
        if key == last and now - when < self.dbl_sec():
            self._last_click = ("", 0.0, 0)
            if e:
                open_task(key, e)
            return
        self._last_click = (key, now, getattr(ev, "time", 0))
        if e and self.has_detail(e):
            self._click_job = self.root.after(self.CLICK_WAIT_MS, lambda: self.click_open(key))

    def click_open(self, key):
        self._click_job = None
        if self.detail is None and key in self.tracker.tasks:
            self.open_detail(key)

    def title_open(self, key, e):
        self._last_click = ("", 0.0, 0)          # bubble_click 이 한 번 더 열지 않게
        open_task(key, e)

    def bubble_click(self, ev):
        """줄을 눌러 펼친 직후 같은 자리를 한 번 더 눌렀으면(= 더블 클릭) 그 대화 창을 연다."""
        key, when, stamp = self._last_click
        if (key and self.detail == key and ev.time != stamp
                and time.time() - when < self.dbl_sec()):
            self._last_click = ("", 0.0, 0)
            e = self.tracker.tasks.get(key)
            if e:
                open_task(key, e)
            self.root.after(10, self.close_detail)   # 창을 열려던 것이니 펼친 카드는 접는다

    @staticmethod
    def dbl_sec():
        """윈도우 더블 클릭 시간 (초)."""
        try:
            return max(200, min(900, int(ctypes.windll.user32.GetDoubleClickTime()))) / 1000
        except Exception:
            return 0.5

    # ---- 반복 ----
    def tick(self):
        if os.path.exists(QUIT_FLAG):
            self.quit()
            return
        self.tick_n += 1
        if self.tick_n % 2 == 1:
            rep = GPT.take() if GPT else None
            if rep:
                self.tracker.apply_chatgpt(rep)
                seen = (tuple(rep.get("seen") or ()), rep.get("seen_session", ""), rep.get("seen_gpt", ""))
                if seen != self.seen:
                    self.seen = seen
                    # 펼친 카드는 보이는 창과 상관없으니 통째로 다시 만들지 않는다 (입력칸이 끊기지 않게)
                    self.update_bubble(force=not self.detail)
            self.auto_hide()
            self.follow_progress()
            res = GPT.take_reply() if GPT else None
            if res:
                self.reply_done(res)
            self.web_results()
            self.sync_web_watch()
            res, self._term_result = getattr(self, "_term_result", None), None
            if res:
                self.reply_done(res if res == "ok" else
                                (t("term_err_" + res) if T.get("term_err_" + res) else res))
            self.tracker.poll()
            self.updater.tick()
            found = self.updater.take()
            if found:
                self.tracker.apply_update(*found)
            self.check_ext_tip()
            if self.tick_n % 10 == 1:
                self.tracker.refresh_claude_titles()
            if self.tick_n % 150 == 1 and GPT:   # 1분마다: 감시 프로그램이 너무 커졌으면 새로
                GPT.check_memory()
            self.update_bubble()
        self.draw()
        self.root.after(400, self.tick)

    def mode(self):
        st = [e.get("status") for e in self.shown_tasks().values()]
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
        blink = mode == "idle" and random.random() < 0.12
        arm = (1 if self.tick_n % 2 == 0 else 2) if mode == "work" else 0     # 일할 때 팔을 번갈아
        bounce = -S(2) if (mode != "idle" and self.tick_n % 2 == 0) else 0
        key = (mode, blink, arm)
        if key not in self._bot:
            w, h = 15 * self.px, 16 * self.px
            im = robot_image(mode, w, h, blink=blink, arm_up=arm)
            bg = Image.new("RGB", im.size, KEY)              # 투명색 위에 붙여 창에서 빠지게
            bg.paste(im, mask=im.getchannel("A"))
            self._bot[key] = ImageTk.PhotoImage(bg)
        c.create_image(self.pad_x, self.pad_y + bounce, image=self._bot[key], anchor="nw")

        st = [e.get("status") for e in self.shown_tasks().values()]
        n = st.count("working")
        badge = None
        if "waiting" in st:
            badge = (RED, "!")
        elif n:
            srcs = {e.get("src") for e in self.shown_tasks().values()
                    if e.get("status") == "working"}
            # 진행 중인 것이 모두 같은 색이면 그 색, 섞여 있으면 기본 주황
            colors = {SRC_COLOR.get(s, ACCENT) for s in srcs}
            badge = (colors.pop() if len(colors) == 1 else ACCENT, str(n))
        elif "done" in st:                       # 다 끝났으면 초록 ✓
            badge = (GREEN, "✓")
        if badge:                                # 머리 오른쪽 위 모서리에 붙여 단다
            d = S(16)
            x = self.pad_x + int(15 * self.px * 0.84)
            y = self.pad_y + int(16 * self.px * 0.10)
            c.create_oval(x, y, x + d, y + d, fill=badge[0], width=0)
            c.create_text(x + d / 2, y + d / 2, text=badge[1], fill="#1b1c20",
                          font=(FONT, 8, "bold"))

    # ---- 말풍선 ----
    @staticmethod
    def info_text(e, now, short=False):
        """줄의 상태 글. short=True 는 목록용 짧은 글 (마우스를 올리면 자세한 글로)."""
        st = e.get("status")
        if st == "update":
            phase = e.get("phase")
            body = (t("update_dl", p=e.get("pct", 0)) if phase == "dl" else
                    t("update_run") if phase == "run" else
                    t("update_fail") if phase == "fail" else t("update_ready"))
        elif st == "tip":
            body = t("ext_tip_body")
        elif st == "done":
            if short:
                body = t("done_short", d=fmt_short(now - e.get("end", now)))
            else:
                when = time.strftime("%H:%M", time.localtime(e.get("end", now)))
                body = t("done", w=when, d=fmt_dur(e.get("end", now) - e.get("start", now)))
        elif st == "waiting":
            d = now - e.get("wait_start", now)
            body = t("waiting_short", d=fmt_short(d)) if short else t("waiting", d=fmt_dur(d))
        elif e.get("bg"):
            body = (t("bg_short", n=e["bg"]) if short
                    else t("bg", n=e["bg"], d=fmt_dur(now - e.get("start", now))))
        else:
            d = now - e.get("start", now)
            body = t("working_short", d=fmt_short(d)) if short else t("working", d=fmt_dur(d))
        return body

    @staticmethod
    def info_color(e):
        st = e.get("status")
        return TXT_RED if st == "waiting" else WORKING if st == "working" else DONE_FG if st == "done" else SUB

    @staticmethod
    def is_web(e):
        """브라우저 확장이 알려 준 웹 채팅 줄 (탭 번호가 있음)."""
        return e.get("src") in WEB_SRCS and e.get("tab") is not None

    @staticmethod
    def is_gpt(e):
        """ChatGPT 데스크톱 앱의 일반 채팅 줄 (제목으로 찾음)."""
        return e.get("src") == "chatgpt" and bool(e.get("title"))

    @staticmethod
    def term_menu(e):
        """터미널 세션이 선택 메뉴(권한 확인 등)로 멈춘 상태 — 글자를 넣으면 Enter 가 메뉴의 기본 선택을 눌러 버림."""
        return is_term(e) and e.get("status") == "waiting" and not e.get("ask")

    def can_send(self, e):
        """로봇에서 글을 보낼 수 있는 줄 (Claude 앱·VS Code 세션은 답하는 중에도, 웹 탭, ChatGPT 앱)."""
        if self.is_web(e) or self.is_gpt(e):
            return True
        if is_term(e):
            return e.get("status") in ("done", "working", "waiting")
        return (e.get("src") == "claude" and bool(e.get("title"))
                and e.get("entry") in ("claude-desktop", "claude-vscode")
                and e.get("status") in ("done", "working", "waiting"))

    def has_chat(self, e):
        """펼친 카드에 대화 기록창을 그릴 줄."""
        return (e.get("src") == "claude" and bool(e.get("transcript"))) or self.is_web(e) or self.is_gpt(e)

    def has_detail(self, e):
        """› 로 펼칠 내용이 있는 줄 (대화 기록·질문·보내기)."""
        if self.is_web(e) or self.is_gpt(e):
            return True
        if e.get("src") != "claude":
            return False
        return bool(e.get("transcript") or (e.get("answer") and self.settings.get("answer_preview", True))
                    or e.get("ask") or self.can_send(e))

    # ---- 둥근 모양 (Tk 칸은 네모라서, 매끈한 둥근 바탕 그림을 깔고 그 위에 글자를 올린다) ----
    def round_photo(self, w, h, fill, outline=None, ow=0, r=None, under=INNER, keep=True):
        """둥근 바탕 그림. keep=False 면 모아 두지 않는다 (크기가 매번 다른 대화 칸 — 부른 쪽이 들고 있어야 함)."""
        key = (w, h, fill, outline, ow, r, under)
        if key in self._rounds:
            return self._rounds[key]
        k = 4
        r = r if r is not None else h // 2
        cap = r + 2                              # 위·아래 둥근 부분 높이
        hh = h if h <= cap * 2 + 2 else cap * 2 + 2
        img = Image.new("RGB", (w * k, hh * k), under)
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, w * k - 1, hh * k - 1], radius=r * k, fill=fill, outline=outline, width=ow * k)
        img = img.resize((w, hh), Image.LANCZOS)
        if hh < h:
            # 긴 칸(긴 답변)은 4배 그림이 너무 커지므로 위·아래 둥근 부분만 그리고 가운데는 곧은 줄을 늘인다
            full = Image.new("RGB", (w, h), under)
            full.paste(img.crop((0, 0, w, cap)), (0, 0))
            full.paste(img.crop((0, cap, w, cap + 1)).resize((w, h - cap * 2)), (0, cap))
            full.paste(img.crop((0, hh - cap, w, hh)), (0, h - cap))
            img = full
        photo = ImageTk.PhotoImage(img)
        if keep:
            self.keep_round(key, photo)
        return photo

    def keep_round(self, key, value):
        """둥근 그림 모아 두기 (오래된 것부터 버림 — 쓰고 있는 칸은 그림을 직접 들고 있어서 안 사라짐)."""
        if len(self._rounds) >= 300:
            self._rounds.pop(next(iter(self._rounds)))
        self._rounds[key] = value

    def round_bg(self, cv, w, h, fill, outline=None, ow=0, r=None, under=INNER):
        """캔버스 cv 에 둥근 바탕을 깐다 (그림은 cv.imgs 가 들고 있음).
        긴 칸은 위·아래 둥근 부분만 그림으로 (같은 폭이면 다시 씀) 하고 가운데 곧은 부분은 캔버스 사각형으로 —
        칸 높이만 한 그림을 만들면 긴 답변 칸 하나가 1~2MB 라, 이전 대화를 많이 불러오면 수백 MB 가 된다."""
        r = r if r is not None else h // 2
        cap = r + 2                              # 위·아래 둥근 부분 높이
        if h <= cap * 2 + 2:                     # 짧은 칸은 그림 하나
            cv.imgs = [self.round_photo(w, h, fill, outline, ow, r, under, keep=False)]
            cv.create_image(0, 0, image=cv.imgs[0], anchor="nw")
            return
        key = ("caps", w, fill, outline, ow, r, under)
        if key not in self._rounds:
            k, hh = 4, cap * 2 + 2
            img = Image.new("RGB", (w * k, hh * k), under)
            ImageDraw.Draw(img).rounded_rectangle(
                [0, 0, w * k - 1, hh * k - 1], radius=r * k, fill=fill, outline=outline, width=ow * k)
            img = img.resize((w, hh), Image.LANCZOS)
            row = [img.getpixel((x, cap)) for x in range(w)]
            runs, x0 = [], 0                     # 가운데 곧은 줄 = 같은 색 구간들 (테두리·바탕)
            for x in range(1, w + 1):
                if x == w or row[x] != row[x0]:
                    runs.append((x0, x, "#%02x%02x%02x" % row[x0]))
                    x0 = x
            self.keep_round(key, (ImageTk.PhotoImage(img.crop((0, 0, w, cap))),
                                  ImageTk.PhotoImage(img.crop((0, hh - cap, w, hh))), runs))
        top, bottom, runs = self._rounds[key]
        cv.imgs = [top, bottom]
        cv.create_image(0, 0, image=top, anchor="nw")
        cv.create_image(0, h - cap, image=bottom, anchor="nw")
        for x0, x1, color in runs:
            cv.create_rectangle(x0, cap, x1, h - cap, fill=color, width=0)

    def round_label(self, parent, text, fill, fg, size=8, padx=7, pady=3, width=None, hover=None, under=INNER):
        """알약 모양 글자 칸. hover=(바탕, 글자) 면 마우스를 올렸을 때 그 색으로. under = 둘레 바탕색."""
        font = (FONT, size, "bold")
        f = tkfont.Font(root=self.root, font=font)
        w = width or f.measure(text) + S(padx) * 2
        h = f.metrics("linespace") + S(pady) * 2
        img = self.round_photo(w, h, fill, under=under)
        lb = tk.Label(parent, text=text, image=img, compound="center", bg=under, fg=fg, font=font,
                      bd=0, padx=0, pady=0, highlightthickness=0)
        lb.pill = True                           # 줄에 마우스를 올려도 바탕 그대로
        lb.imgs = [img]                          # 모아 둔 그림이 버려져도 이 칸에선 안 사라지게
        if hover:
            on = self.round_photo(w, h, hover[0], under=under)
            lb.imgs.append(on)
            lb.bind("<Enter>", lambda ev: lb.configure(image=on, fg=hover[1]), add="+")
            lb.bind("<Leave>", lambda ev: lb.configure(image=img, fg=fg), add="+")
            lb.configure(cursor="hand2")
        return lb

    def pill_label(self, parent, e):
        src = e.get("src")
        label = t("src_" + src) if src in ("claudeweb", "claudechat", "chatweb") else SRC_LABEL.get(src, "Claude")
        if e.get("entry") == "claude-vscode":
            label += " · VS Code"
        if e.get("browser"):                     # 웹 줄은 어느 브라우저인지도
            label += " · " + BROWSER_NAME.get(e["browser"], e["browser"].capitalize())
        bg, fg = PILL.get(e.get("src"), PILL["claude"])
        return self.round_label(parent, label, bg, fg, size=7, padx=6, pady=1)

    def update_bubble(self, force=False):
        order = {"waiting": 0, "working": 1, "done": 2}
        items = sorted(self.shown_tasks().items(),
                       key=lambda kv: (order.get(kv[1].get("status"), 3),
                                       -kv[1].get("start", 0)))
        if self.detail and self.detail not in self.tracker.tasks:
            self.detail = None
        if not items or self.hidden:
            self.bubble.withdraw()
            self._bub_sig = None
            return
        now = time.time()
        if self.detail:
            e = self.tracker.tasks[self.detail]
            # (마지막 답변 글은 넣지 않는다: 대화는 기록창이 따로 읽고, 보낸 직후 답변 칸이 비었다가 다시 채워지며
            #  카드가 두 번 다시 만들어져 그사이 쓰던 한글이 끊겼음)
            sig = ("detail", self.detail, e.get("status"), e.get("title", ""), e.get("ask", ""),
                   tuple(c["label"] for c in e.get("choices") or []),
                   bool(e.get("sending")), tuple(self.reply_imgs), self.can_send(e), e.get("entry"))
        else:
            sig = ("list", len(items) > 8, tuple(
                (k, e.get("status"), e.get("title", ""), e.get("prompt", ""), self.has_detail(e),
                 bool(self.drafts.get(k)))
                for k, e in items[:8]))
        if not force and self.detail and sig != self._bub_sig and self.typing():
            self.ui_log("다시 만들기 미룸", sig, self._bub_sig)
            sig = self._bub_sig      # 입력칸에 글을 쓰는 중이면 카드를 다시 만들지 않는다 (한글 조합이 끊기지 않게)
        if not force and sig == self._bub_sig:
            for k, lbl in self._infos:     # 시간 글자만 바꿔 깜빡임 방지
                e = self.tracker.tasks.get(k)
                if e:
                    lbl.configure(text=self.info_text(e, now, short=lbl.short))
            self.show_bubble()
            return
        if self.detail and self.entry_focused():
            self.ui_log("입력 중 다시 만듦", "force" if force else "", sig, self._bub_sig)
        self._bub_sig = sig
        self._infos = []
        self.save_chat_state()
        # 입력칸에 커서가 있었으면 새 입력칸에 그 자리 그대로 돌려준다 (아니면 포커스를 뺏지 않음)
        ent = self.entry_focused()
        self._refocus = ent.index("insert") if ent else None
        # 새 내용은 아직 화면에 안 붙인 칸에 다 만든 뒤, 말풍선 크기·모양을 맞추고 한 번에 바꿔 끼운다
        # (만드는 도중의 모습 — 펼칠 때 제목 한 줄만 있는 말풍선 — 이 잠깐 보이지 않게)
        old, self.bub_box = self.bub_box, tk.Frame(self.bub_c, bg=INNER)
        if self.detail:
            self.build_detail(self.detail, self.tracker.tasks[self.detail], now)
        else:
            self.build_list(items, now)
        # 목록과 펼친 카드의 폭을 같게 → 펼치고 접을 때 위아래로만 바뀌고 가로로 움찔하지 않음
        tk.Frame(self.bub_box, bg=INNER, width=self.content_w(), height=1).pack()
        self.position_bubble()                   # (크기 계산은 이 안에서 한 번)
        self.bub_c.itemconfigure("boxwin", window=self.bub_box)
        self.bub_c.tag_raise("boxwin")
        old.destroy()
        self.show_bubble()

    def content_w(self):
        """말풍선 안쪽 폭 — 목록·펼친 카드 모두 이 폭 (사용자: 펼칠 때 가로로 움찔하지 않게).
        보통 목록 줄(약 350px)이 시간 글자 여유까지 두고 들어가는 폭."""
        return S(368)

    def fit_titles(self, rows):
        """줄이 말풍선 폭을 넘으면 제목을 실제 글자 폭에 맞춰 '…'로 줄인다 (글자 수가 아니라 폭으로)."""
        self.bub_box.update_idletasks()
        f = tkfont.Font(root=self.root, font=(FONT, 9, "bold"))
        # (시간 글자가 '9분'→'10분'처럼 늘어나도 넘지 않게 조금 여유)
        room_all = self.content_w() - S(4) - S(16)
        for row, head, name in rows:
            excess = row.winfo_reqwidth() - room_all
            if excess <= 0:
                continue
            room = f.measure(" " + name) - excess
            lo, hi = 0, len(name)
            while lo < hi:                       # 들어가는 가장 긴 앞부분
                mid = (lo + hi + 1) // 2
                if f.measure(" " + name[:mid] + "…") <= room:
                    lo = mid
                else:
                    hi = mid - 1
            head.configure(text=" " + name[:lo].rstrip() + "…")

    # ---- 목록: 줄마다 한 줄 (아이콘 · 제목 · 이름표 · 짧은 상태 · › · ✕) ----
    def build_list(self, items, now):
        rows = []
        for i, (key, e) in enumerate(items[:8]):
            status = e.get("status")
            if i:                                # 줄 사이 얇은 구분선
                tk.Frame(self.bub_box, bg=LINE, height=1).pack(fill="x", padx=S(2))
            row = tk.Frame(self.bub_box, bg=INNER)
            row.pack(fill="x", padx=S(2), pady=S(3))
            # 맨 앞 칸: 답을 기다리면 빨간 ●, 끝났으면 초록 ✓ (끝난 줄은 제목·상태도 초록)
            mark, mark_fg = {"waiting": ("●", TXT_RED), "done": ("✓", DONE_FG)}.get(status, (" ", FG))
            bar = tk.Label(row, text=mark, bg=INNER, fg=mark_fg,
                           font=(FONT, 8 if status == "done" else 7, "bold"), width=1)
            bar.pack(side="left", padx=(0, S(2)))
            name = e.get("title") or e.get("prompt") or e.get("folder", "?")
            if len(name) > 24:
                name = name[:23] + "…"
            head = tk.Label(row, text=" " + name, image=self.icon(e.get("src")), compound="left",
                            bg=INNER, fg=DONE_FG if status == "done" else FG, font=(FONT, 9, "bold"))
            head.hl = True                       # 마우스를 올리면 이 글자 색이 바뀜
            head.base = DONE_FG if status == "done" else FG
            head.pack(side="left")
            rows.append((row, head, name.rstrip("…")))
            pill = self.pill_label(row, e)
            pill.pack(side="left", padx=(S(6), 0))
            marks = [pill]                       # 이름표·✎ 위도 같은 줄 (올리면 제목 색이 바뀌고, 누르면 펼침)
            if self.drafts.get(key):             # 로봇에서 쓰다 만 글이 있으면 ✎
                pen = tk.Label(row, text="✎", bg=INNER, fg=WORKING, font=(FONT, 9, "bold"))
                pen.pack(side="left", padx=(S(4), 0))
                marks.append(pen)
            info = tk.Label(row, text=self.info_text(e, now, short=True), bg=INNER,
                            fg=self.info_color(e),
                            font=(FONT, 8, "bold" if status == "waiting" else "normal"))
            info.short = True
            info.pack(side="left", padx=(S(6), 0))
            self._infos.append((key, info))
            # (자세한 시각·걸린 시간은 상세 카드에. 여기서 글을 길게 바꾸면 줄이 넓어져 말풍선 밖으로 밀려남)
            x = tk.Label(row, text=" ✕", bg=INNER, fg=SUB, font=(FONT, 9), cursor="hand2")
            x.pack(side="right")
            x.bind("<Button-1>", lambda ev, k=key: self.dismiss(k))
            parts = [row, bar, head, *marks, info, x]
            if self.has_detail(e):
                more = tk.Label(row, text=" ›", bg=INNER, fg=FG, font=(FONT, 12, "bold"),
                                cursor="hand2")
                more.pack(side="right")
                more.bind("<Button-1>", lambda ev, k=key: self.open_detail(k))
                parts.append(more)
            for w in (row, bar, head, *marks, info):
                w.bind("<Button-1>", lambda ev, k=key: self.row_click(k, ev))
                w.configure(cursor="hand2")
            # 마우스를 올린 줄은 배경을 살짝 밝게 (더블 클릭할 줄이 어느 것인지 보이게)
            for w in parts:
                w.bind("<Enter>", lambda ev, ps=parts: self.hover(ps, True), add="+")
                w.bind("<Leave>", lambda ev, ps=parts: self.hover(ps, False, ev), add="+")
        if len(items) > 8:
            tk.Label(self.bub_box, text=t("more", n=len(items) - 8), bg=INNER,
                     fg=SUB, font=(FONT, 8)).pack(anchor="w", padx=S(2))
        self.fit_titles(rows)

    # ---- 상세 카드: › 를 누른 줄 하나만 (답변 · 질문 · 보내기) ----
    def build_detail(self, key, e, now):
        status = e.get("status")
        self._input_extra = 0                    # (입력칸을 만들 때 다시 정해짐)
        card = tk.Frame(self.bub_box, bg=INNER)
        card.pack(fill="x", padx=S(2), pady=S(1))
        top = tk.Frame(card, bg=INNER)
        top.pack(fill="x")
        back = tk.Label(top, text="‹ " + t("back"), bg=INNER, fg=SUB, font=(FONT, 8), cursor="hand2")
        back.pack(side="left")
        back.bind("<Button-1>", lambda ev: self.close_detail())
        x = tk.Label(top, text="✕", bg=INNER, fg=SUB, font=(FONT, 9), cursor="hand2")
        x.pack(side="right")
        x.bind("<Button-1>", lambda ev: self.close_detail())
        self.pill_label(top, e).pack(side="right", padx=(0, S(8)))
        title = tk.Label(card, text=" " + (e.get("title") or e.get("prompt") or "?"),
                         image=self.icon(e.get("src")), compound="left", bg=INNER,
                         fg=DONE_FG if status == "done" else FG,
                         font=(FONT, 10, "bold"), wraplength=self.content_w() - S(40), justify="left", anchor="w",
                         cursor="hand2")
        title.pack(fill="x", pady=(S(6), 0))
        title.bind("<Double-Button-1>", lambda ev: self.title_open(key, e))
        info = tk.Label(card, text=self.info_text(e, now), bg=INNER, fg=self.info_color(e),
                        font=(FONT, 8), anchor="w")
        info.short = False
        info.pack(fill="x")
        self._infos.append((key, info))
        if self.has_chat(e):
            self.chat_area(card, key, e)         # 대화 기록 (내 메시지 오른쪽 · AI 왼쪽)
        term = is_term(e)
        # 여러 문항 카드는 앱에서 답하게 · 터미널 질문은 터미널에서 (터미널 화면의 선택지는 로봇이 못 누름)
        card_only = ((e.get("card") and not e.get("choices"))
                     or (term and (e.get("card") or self.term_menu(e))))
        if status == "waiting" and e.get("ask"):
            tk.Label(card, text=e["ask"], bg=INNER, fg=FG, font=(FONT, 9, "bold"), anchor="w",
                     justify="left", wraplength=self.content_w() - S(40)).pack(fill="x", pady=(S(8), S(2)))
            if card_only:
                tk.Label(card, text=t("answer_in_term" if term else "answer_in_app"), bg=INNER, fg=SUB, font=(FONT, 8),
                         anchor="w").pack(fill="x")
            elif not e.get("sending"):
                for c in e.get("choices") or []:
                    self.big_button(card, c["label"], lambda m=c["message"]: self.send_reply(key, m))
        if self.term_menu(e):                    # 터미널이 선택 메뉴로 멈춤: 입력칸이 왜 없는지 알려 준다
            tk.Label(card, text=t("answer_in_term"), bg=INNER, fg=SUB, font=(FONT, 8),
                     anchor="w").pack(fill="x", pady=(S(8), 0))
        if e.get("sending"):
            tk.Label(card, text=t("reply_sending"), bg=INNER, fg=SUB, font=(FONT, 8),
                     anchor="w").pack(fill="x", pady=(S(6), 0))
        elif (self.can_send(e) or (status == "waiting" and e.get("ask"))) and not card_only:
            # 글은 언제든 여기서 (질문 카드면 '기타'로 들어감). 이미지는 Claude 앱 세션만
            self.reply_entry(card, key, allow_img=not e.get("card") and e.get("entry") != "claude-vscode"
                             and not self.is_web(e) and not term and not self.is_gpt(e))

    # ---- 대화 기록창 (채팅): 내 메시지는 오른쪽 주황 말풍선, Claude 글은 왼쪽 흰 칸 ----
    # 맨 아래(최신)부터 보이고, 맨 위에서 휠을 더 올리면 이전 대화를 6개씩 더 불러온다.
    # 새 글이 오면 이 칸 안에서 달라진 곳만 고쳐 그린다 → 카드 전체(입력칸)는 그대로라
    # 로봇에서 글을 쓰는 중에 Claude가 일해도 쓰던 글·한글 조합·커서가 끊기지 않는다.
    CHAT_STEP = 6            # 한 번에 더 보여 줄 대화 수
    CHAT_TEXT_MAX = 4000     # Claude 글 한 칸은 끝에서 이만큼만 (아주 긴 글도 가볍게)
    CHAT_PARTS = 14          # 한 대화에서 보여 줄 글·도구 줄 수 (넘으면 앞을 생략)

    def chat_area(self, parent, key, e):
        h = self._hist
        if h.get("key") != key:                  # 다른 세션을 펼치면 처음부터 (최근 6개, 맨 아래)
            h.clear()
            h.update(key=key, bytes=1_500_000, show=self.CHAT_STEP, at_bottom=True)
        cv = tk.Canvas(parent, bg=INNER, highlightthickness=0, bd=0, yscrollincrement=S(14))
        inner = tk.Frame(cv, bg=INNER)
        cv.create_window(0, 0, window=inner, anchor="nw", tags="inner")
        cv.pack(fill="x", pady=(S(4), 0))
        self._chat = {"cv": cv, "inner": inner, "rows": [], "H": 0, "working": None}
        self.read_chat(e)
        self.fill_chat(e)

    def read_chat(self, e, force=False):
        """기록 파일이 바뀌었으면 다시 읽는다 (바뀌었으면 True)."""
        h = self._hist
        if self.is_gpt(e):                       # ChatGPT 앱: 감시 프로그램이 그 창을 읽어 줌 (열려 있는 대화일 때만)
            now = time.time()
            if GPT and now - h.get("asked", 0) > 1.5:
                h["asked"] = now
                GPT.ask_chat(e["title"])
            res = getattr(GPT, "chat_result", None) if GPT else None
            if not res or res.get("title") != e["title"]:
                if "turns" in h and not force:
                    return False
                # 아직 답이 안 왔으면 빈 기록창 (안내는 '그 대화가 안 열려 있음'이라는 답이 왔을 때만)
                h["turns"], h["gpt_ok"], h["sig"] = [], True, None
                h["more"], h["plan"], h["plan_at"] = False, None, 0
                return True
            sig = json.dumps([res.get("ok"), res.get("msgs")], ensure_ascii=False)
            if not force and "turns" in h and sig == h.get("sig"):
                return False
            msgs = [[r, x or (t("img_tag") if r == "me" else x)] for r, x in res.get("msgs") or []]
            h["turns"], h["sig"], h["gpt_ok"] = web_turns(msgs), sig, bool(res.get("ok"))
            h["more"], h["plan"], h["plan_at"] = False, None, 0
            return True
        if self.is_web(e):                       # 웹 탭: 확장이 보내 준 대화 글 파일
            path = web_chat_file(e)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = 0
            if not force and "turns" in h and mtime == h.get("mtime"):
                return False
            data = read_json(path, {}) if mtime else {}
            h["turns"] = web_turns(data.get("msgs") or [])
            h["more"], h["plan"], h["plan_at"], h["mtime"] = False, None, 0, mtime
            return True
        try:
            mtime = os.path.getmtime(e["transcript"])
        except OSError:
            mtime = 0
        if not force and "turns" in h and mtime == h.get("mtime"):
            return False
        # 읽던 자리(state)를 넘겨서 일하는 동안엔 새로 붙은 줄만 읽는다
        h["turns"], h["more"] = claude_turns(e["transcript"], h["bytes"], h.setdefault("state", {}))
        h["plan"], h["plan_at"] = claude_plan(e["transcript"])
        h["mtime"] = mtime
        return True

    def chat_blocks(self, e):
        """기록창에 위에서부터 그릴 것: 이전 대화 안내 · (내 메시지 · Claude 글 · 도구 줄 · 계획)… ·
        일하는 중이면 맨 아래 '읽는 중 taskpet.py' 같은 지금 하는 일 (없으면 '생각 중…')."""
        h = self._hist
        turns = h.get("turns") or []
        shown = turns[-h["show"]:]
        out = []
        if len(turns) > len(shown) or h.get("more"):
            out.append(("older", ""))
        if self.is_gpt(e) and not h.get("gpt_ok"):    # ChatGPT 앱에서 다른 대화를 보고 있으면 읽을 수 없음
            out.append(("omit", t("gpt_open_hint")))
        show_ai = self.settings.get("answer_preview", True)
        self._img_src = e.get("transcript")      # 그림은 자리만 있고, 그릴 때 이 파일에서 꺼낸다
        for turn in shown:
            me, imgs = turn["me"], turn.get("imgs") or []
            if imgs:                             # 그림은 아래에 작게 보이므로 '(이미지)' 글자는 뺀다
                me = "\n".join(x for x in me.split("\n") if x != t("img_tag"))
            if me:
                out.append(("me", me))
            out += [("myimg", ref) for ref in imgs[:4]]
            parts = turn.get("parts") or []
            if not show_ai:
                parts = [p for p in parts if p[0] != "text"]
            if len(parts) > self.CHAT_PARTS:     # 아주 긴 턴은 끝부분만 (7개 단위로 잘라 자주 다시 그리지 않게)
                cut = (len(parts) - self.CHAT_PARTS + 6) // 7 * 7
                out.append(("omit", t("omitted", n=cut)))
                parts = parts[cut:]
            for kind, val in parts:
                if kind == "text":
                    if len(val) > self.CHAT_TEXT_MAX:
                        val = "…" + val[-self.CHAT_TEXT_MAX:]
                    out.append(("ai", val))
                elif kind == "image":
                    out.append(("image", val))
                else:
                    out.append(("tools", tools_summary(val)))
        # 계획은 Claude 앱처럼 최근 메시지 아래에 하나: 아직 남은 단계가 있거나, 이번 대화에서 고친 것
        plan, plan_at = h.get("plan"), h.get("plan_at", 0)
        last = turns[-1] if turns else {}
        if plan and (any(x["status"] != "completed" for x in plan) or plan_at >= last.get("t0", 0)):
            out.append(("plan", tuple((x["status"], x["content"]) for x in plan)))
        if e.get("status") == "working":
            now_doing = tool_doing(last["open"]) if last.get("open") else t("thinking")
            out.append(("status", now_doing))
        return out

    def chat_view_max(self):
        """기록창 높이 한도: 화면이 낮으면 줄여서 입력칸·선택지가 화면 밖으로 밀리지 않게."""
        l, t_, r, b = work_area()
        # 입력칸이 여러 줄로 늘어난 만큼(_input_extra) 줄여서 말풍선 전체 크기는 그대로
        return max(S(120), min(S(380), (b - t_) - S(340)) - getattr(self, "_input_extra", 0))

    def relayout_chat(self):
        """기록창 높이만 다시 맞춘다 (입력칸이 늘거나 줄었을 때). 맨 아래를 보던 중이면 계속 맨 아래."""
        ch = self._chat
        if not ch or not ch["H"]:
            return
        cv = ch["cv"]
        try:
            at_bottom = cv.yview()[1] >= 0.999
            cv.configure(height=min(ch["H"], self.chat_view_max()))
            if at_bottom:
                cv.yview_moveto(1.0)
        except tk.TclError:
            pass

    def fill_chat(self, e, older=False):
        """기록창을 채운다. 이미 그려 둔 칸은 그대로 두고, 달라진 곳부터 아래만 새로 그린다."""
        ch = self._chat
        cv, inner, rows = ch["cv"], ch["inner"], ch["rows"]
        if ch["H"]:                              # 지금 보던 자리
            a, b = cv.yview()
            pos = {"at_bottom": b >= 0.999, "top_px": a * ch["H"], "from_bottom": ch["H"] * (1 - a)}
        else:                                    # 카드를 다시 만들기 전에 저장해 둔 자리
            pos = self._hist
        blocks = self.chat_blocks(e)
        same = 0
        while same < min(len(rows), len(blocks)) and rows[same][0] == blocks[same]:
            same += 1
        for _, w in rows[same:]:
            w.destroy()
        del rows[same:]
        for kind, text in blocks[same:]:
            if kind in ("older", "omit"):
                w = tk.Label(inner, text=t("older_hint") if kind == "older" else text,
                             bg=INNER, fg=SUB, font=(FONT, 8))
                w.pack(pady=(S(2), 0))
            elif kind == "me":
                w = self.my_message(inner, text)
            elif kind == "ai":
                w = self.answer_box(inner, text)
            elif kind == "tools":                # 도구를 쓴 묶음: 작은 회색 한 줄
                w = tk.Label(inner, text="· " + text, bg=INNER, fg=SUB, font=(FONT, 8), anchor="w",
                             justify="left", wraplength=S(320))
                w.pack(fill="x", padx=(S(6), 0), pady=(S(5), 0))
            elif kind == "plan":
                w = self.plan_box(inner, text)
            elif kind in ("image", "myimg"):
                w = self.image_block(inner, text, right=kind == "myimg")
            else:                                # 지금 하는 일 + 걸린 시간 (시간은 follow_progress 가 1초마다)
                w = tk.Frame(inner, bg=INNER)
                w.pack(fill="x", padx=(S(6), 0), pady=(S(6), 0))
                # 길면 말풍선이 넓어지므로 짧게 자른다 (시간 글자까지 기록창 폭 안에)
                tk.Label(w, text="● " + (text if len(text) <= 24 else text[:23] + "…"), bg=INNER,
                         fg=WORKING, font=(FONT, 8, "bold"), anchor="w").pack(side="left")
                w.clock = tk.Label(w, text="", bg=INNER, fg=SUB, font=(FONT, 8))
                w.clock.pack(side="left", padx=(S(6), 0))
            rows.append(((kind, text), w))
        ch["working"] = e.get("status") == "working"
        turns = self._hist.get("turns") or []
        ch["t0"] = turns[-1].get("t0", 0) if turns else 0
        self.tick_status()
        inner.update_idletasks()
        W = max(inner.winfo_reqwidth(), self.content_w() - S(4))   # 말풍선 폭에 맞춤
        H = max(inner.winfo_reqheight(), 1)
        view = min(H, self.chat_view_max())
        cv.itemconfigure("inner", width=W)        # 폭을 채워야 내 메시지가 오른쪽 끝에 붙음
        cv.configure(width=W, height=view, scrollregion=(0, 0, W, H))
        ch["H"] = H
        # 읽던 자리: 이전 대화를 불러왔으면 보던 글이 그 자리에, 맨 아래였으면 계속 최신으로,
        # 위로 올려 읽던 중이면 새 글이 와도 그 위치 그대로
        if older:
            cv.yview_moveto(max(0.0, H - pos.get("from_bottom", H)) / H)
        elif pos.get("at_bottom", True) or H <= view:
            cv.yview_moveto(1.0)
        else:
            cv.yview_moveto(pos.get("top_px", 0) / H)

    def tick_status(self):
        """맨 아래 '지금 하는 일' 줄 옆에 이번 대화가 걸린 시간 (Claude 앱처럼 '읽는 중 a.py  3분 12초')."""
        ch = self._chat
        if not ch or not ch["rows"] or ch["rows"][-1][0][0] != "status":
            return
        w = ch["rows"][-1][1]
        try:
            w.clock.configure(text=fmt_dur(time.time() - ch["t0"]) if ch.get("t0") else "")
        except tk.TclError:
            pass

    def image_block(self, parent, sig, right=False):
        """대화 속 그림을 작게 (둥근 모서리, 내가 붙인 것은 오른쪽). 누르면 크게 열기.
        sig = 기록 파일 안 그림 자리 — 그림 글자는 여기서 그 한 줄만 다시 읽어 꺼낸다."""
        src, cache = self._img_src, self._thumb_cache
        ph = cache.get((src, sig))
        if ph is None:
            try:
                im = Image.open(io.BytesIO(base64.b64decode(claude_image(src, sig))))
                im = im.convert("RGB")
            except Exception:
                w = tk.Label(parent, text=t("img_broken"), bg=INNER, fg=SUB, font=(FONT, 8))
                w.pack(anchor="e" if right else "w")
                return w
            im.thumbnail((S(220), S(150)), Image.LANCZOS)
            w, h = im.size
            k, r = 4, S(10)
            mask = Image.new("L", (w * k, h * k), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r * k, fill=255)
            out = Image.new("RGB", (w, h), INNER)
            out.paste(im, mask=mask.resize((w, h), Image.LANCZOS))
            ph = ImageTk.PhotoImage(out)
            if len(cache) >= 24:                 # 오래된 것부터 버림 (작은 사진 하나 약 0.1MB, 칸이 들고 있는 건 그대로)
                cache.pop(next(iter(cache)))
            cache[(src, sig)] = ph
        lb = tk.Label(parent, image=ph, bg=INNER, bd=0, cursor="hand2")
        lb.img = ph
        lb.pack(anchor="e" if right else "w", padx=(0, 0) if right else (S(6), 0), pady=(S(6), 0))
        lb.bind("<Button-1>", lambda ev: self.open_image(src, sig))
        return lb

    def open_image(self, src, sig):
        """그림을 임시 파일로 저장해 사진 앱으로 크게 연다."""
        try:
            raw = base64.b64decode(claude_image(src, sig))
            ext = (".png" if raw[:4] == b"\x89PNG" else ".jpg" if raw[:2] == b"\xff\xd8" else
                   ".webp" if raw[8:12] == b"WEBP" else ".gif" if raw[:4] == b"GIF8" else ".png")
            folder = os.path.join(tempfile.gettempdir(), "TaskPet-images")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "img-" + hashlib.sha1(raw).hexdigest()[:12] + ext)
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(raw)
            os.startfile(path)
        except Exception:
            pass

    def plan_box(self, parent, items):
        """계획(할 일 목록): 둥근 칸 안에 ✓ 끝남 · ● 하는 중 · ○ 남음."""
        cv = tk.Canvas(parent, bg=INNER, highlightthickness=0, bd=0)
        box = tk.Frame(cv, bg=ANS_BG)
        tk.Label(box, text=t("plan"), bg=ANS_BG, fg=SUB, font=(FONT, 8, "bold"), anchor="w").pack(fill="x")
        for status, content in items:
            mark, mark_fg = {"completed": ("✓", DONE_FG), "in_progress": ("●", WORKING)}.get(status, ("○", SUB))
            row = tk.Frame(box, bg=ANS_BG)
            row.pack(fill="x", pady=(S(2), 0))
            tk.Label(row, text=mark, bg=ANS_BG, fg=mark_fg, font=(FONT, 9, "bold"), width=2,
                     anchor="n").pack(side="left", anchor="n")
            tk.Label(row, text=content, bg=ANS_BG, fg=SUB if status == "completed" else ANS_FG,
                     font=(FONT, 9, "bold" if status == "in_progress" else "normal"),
                     justify="left", anchor="w", wraplength=S(270)).pack(side="left", fill="x")
        box.update_idletasks()
        pad = S(10)
        w, h = max(box.winfo_reqwidth() + pad * 2, S(300)), box.winfo_reqheight() + pad * 2
        cv.configure(width=w, height=h)
        self.round_bg(cv, w, h, ANS_BG, outline=ENTRY_LINE, ow=S(1), r=S(14))
        cv.create_window(pad, pad, window=box, anchor="nw")
        cv.pack(anchor="w", pady=(S(8), 0))
        return cv

    def save_chat_state(self):
        """카드를 통째로 다시 만들기 전에 기록창에서 보던 자리를 기억해 둔다."""
        ch, self._chat = self._chat, None
        if not ch or not ch["H"]:
            return
        try:
            a, b = ch["cv"].yview()
        except tk.TclError:
            return
        H = ch["H"]
        self._hist.update(at_bottom=b >= 0.999, top_px=a * H, from_bottom=H * (1 - a))

    def chat_wheel(self, ev):
        """기록창 위에서 휠: 위아래로 굴리고, 맨 위에서 더 올리면 이전 대화를 불러온다.
        (말풍선 창 전체에 걸어 둠 — 입력칸에 커서가 있어도 휠은 기록창이 받게)"""
        ch = self._chat
        if not ch:
            return None
        cv = ch["cv"]
        try:
            w = cv.winfo_containing(ev.x_root, ev.y_root)
        except (tk.TclError, KeyError):
            w = None
        if w is None or not (w == cv or str(w).startswith(str(cv) + ".")):
            return None
        up = ev.delta > 0
        if up and cv.yview()[0] <= 0.0:
            self.load_older()
        else:
            cv.yview_scroll(-3 if up else 3, "units")
        return "break"

    def load_older(self):
        """이전 대화 6개를 더 (보여 줄 게 모자라면 기록 파일을 더 앞에서부터 읽음)."""
        if time.time() - getattr(self, "_older_at", 0) < 0.6:
            return
        h = self._hist
        e = self.tracker.tasks.get(self.detail) if self.detail else None
        if not e or not self._chat:
            return
        if h.get("show", 0) < len(h.get("turns") or []):
            h["show"] += self.CHAT_STEP
        elif h.get("more"):
            h["bytes"] *= 3
            h["show"] += self.CHAT_STEP
            self.read_chat(e, force=True)
        else:
            return
        self._older_at = time.time()
        self.fill_chat(e, older=True)
        self.position_bubble()

    def my_message(self, parent, text):
        """내가 보낸 메시지: 오른쪽에 붙인 주황 말풍선 (길면 앞부분만)."""
        if len(text) > 300:
            text = text[:299] + "…"
        cv = tk.Canvas(parent, bg=INNER, highlightthickness=0, bd=0)
        lb = tk.Label(cv, text=text, bg=MY_BG, fg=MY_FG, font=(FONT, 10), justify="left",
                      wraplength=S(250), padx=0, pady=0)
        padx, pady = S(12), S(7)                 # (글자 칸 크기는 만들 때 바로 정해져서 따로 기다리지 않음)
        w, h = lb.winfo_reqwidth() + padx * 2, lb.winfo_reqheight() + pady * 2
        cv.configure(width=w, height=h)
        # 크기가 제각각이라 그림을 모아 두지 않고 이 칸이 들고 있다 (칸이 지워지면 같이 사라짐)
        self.round_bg(cv, w, h, MY_BG, r=min(S(16), h // 2))
        cv.create_window(padx, pady, window=lb, anchor="nw")
        cv.pack(anchor="e", pady=(S(8), 0))
        return cv

    def answer_box(self, parent, text):
        """Claude 글을 읽기 좋게: 소제목은 굵게, 목록은 •, 문단 사이는 띄운 둥근 흰 칸 (높이는 글에 딱 맞게)."""
        lines = answer_lines(text)
        cv = tk.Canvas(parent, bg=INNER, highlightthickness=0, bd=0)   # 둥근 바탕을 깔 자리
        tw = self.answer_text(cv)
        self.fill_answer(tw, lines)
        tw.configure(state="disabled")           # 읽기만 (끌어서 복사는 됨)
        th = self.text_px(lines) + S(2) * 2      # 글 높이 + 위아래 pady
        pad = S(9)
        w, h = tw.winfo_reqwidth() + pad * 2, th + pad * 2
        cv.configure(width=w, height=h)
        self.round_bg(cv, w, h, ANS_BG, r=S(16))
        cv.create_window(pad, pad, window=tw, anchor="nw", height=th)
        cv.pack(anchor="w", pady=(S(8), 0))
        # 글 칸이 휠을 먹으면 기록창이 안 굴러가므로 기록창으로 넘긴다
        tw.bind("<MouseWheel>", lambda ev: self.chat_wheel(ev) or "break")
        return cv

    def answer_text(self, parent):
        """Claude 글 칸. 보이는 칸과 높이를 재는 칸이 똑같아야 해서 한곳에서 만든다."""
        # 실수로 끌어도 파랗게 선택되지 않게 (줄 끝 빈 곳까지 파랗게 칠해져 보기 싫었음): 선택 색을 바탕과 같게,
        # 끌기·두세 번 클릭 선택은 막음
        tw = tk.Text(parent, bg=ANS_BG, fg=ANS_FG, font=(FONT, 10), wrap="word", relief="flat",
                     width=40, padx=S(4), pady=S(2), highlightthickness=0, bd=0, cursor="arrow",
                     spacing1=S(3), spacing2=S(3), spacing3=S(4), exportselection=False,
                     selectbackground=ANS_BG, selectforeground=ANS_FG, inactiveselectbackground=ANS_BG)
        for seq in ("<B1-Motion>", "<Double-Button-1>", "<Triple-Button-1>", "<Shift-Button-1>"):
            tw.bind(seq, lambda ev: "break")
        tw.tag_configure("h", font=(FONT, 10, "bold"), foreground=ANS_HEAD, spacing1=S(7))
        tw.tag_configure("li", lmargin1=S(4), lmargin2=S(16))
        tw.tag_configure("gap", spacing1=S(3))
        return tw

    @staticmethod
    def fill_answer(tw, lines):
        for kind, s in lines:
            tw.insert("end", s + "\n", kind)
        tw.delete("end-2c", "end-1c")            # 마지막 빈 줄

    def text_px(self, lines):
        """글이 실제로 차지할 높이(px). 화면 밖에 둔 같은 모양의 칸에 넣어 Tk가 접은 그대로 잰다
        (글자 폭으로 어림하면 아래가 비거나 잘려서)."""
        m = getattr(self, "_measure", None)
        if m is None:
            # 이미 떠 있는 로봇 창 안, 보이는 곳 바깥(왼쪽 멀리)에 둔다 — 화면에 붙어 있어야 폭이 정해져서 잴 수 있음
            m = self._measure = self.answer_text(self.root)
            m.place(x=-S(3000), y=0)
        if m.winfo_width() <= 1:
            self.root.update_idletasks()
        m.delete("1.0", "end")
        self.fill_answer(m, lines)
        r = m.count("1.0", "end", "update", "ypixels")
        return int((r[0] if isinstance(r, tuple) else r) or 0)

    def chip(self, parent, text, command, sub=False, under=INNER, pack=True):
        """작은 버튼 (말풍선이 투명 창이라 Label로 만들고 누르면 command). under = 버튼 둘레 바탕색."""
        base, fg = (CHIP_SUB_BG, CHIP_SUB_FG) if sub else (CHIP_BG, CHIP_FG)
        b = self.round_label(parent, text, base, fg, size=8, padx=10, pady=4,
                             hover=(CHIP_HOVER, CHIP_FG), under=under)
        if pack:
            b.pack(side="left", padx=(0, S(4)))
        b.bind("<Button-1>", lambda ev: command())
        return b

    def big_button(self, parent, text, command):
        """선택지: 폭 가득한 큰 알약 버튼 (Claude 앱 질문 카드처럼 세로로)."""
        b = self.round_label(parent, text, CHIP_BG, CHIP_FG, size=9, pady=6, width=self.content_w() - S(4),
                             hover=(CHIP_HOVER, CHIP_FG))
        b.pack(anchor="w", pady=(S(4), 0))
        b.bind("<Button-1>", lambda ev: command())
        return b

    def reply_entry(self, box, key, allow_img=True):
        # Claude·ChatGPT 앱의 입력창처럼: 폭 가득한 둥근 상자 안에 여러 줄 글 칸(길어지면 6줄까지 늘어나고
        # 그 뒤로는 칸 안에서 스크롤), 상자 아래쪽 안에 '이미지'(왼쪽)·'➤'(오른쪽) 버튼.
        # Enter = 보내기, Shift+Enter = 줄바꿈, 글씨는 Claude 글과 같은 글씨체·크기, 비어 있으면 흐린 안내 글.
        ew = self.content_w() - S(4)             # 말풍선 폭 가득
        padx, pady, gap, bot = S(12), S(9), S(4), S(6)
        tw_px = ew - padx * 2
        cv = tk.Canvas(box, width=ew, bg=INNER, highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(S(8), 0))
        ent = tk.Text(cv, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG, relief="flat", bd=0,
                      font=REPLY_FONT, wrap="word", width=1, height=1, padx=0, pady=0,
                      spacing2=S(2), highlightthickness=0,
                      # Tk 가 그리는 선택 표시는 보이지 않게 (아래 'mysel' 이 대신 칠함)
                      selectbackground=ENTRY_BG, selectforeground=ENTRY_FG, inactiveselectbackground=ENTRY_BG)
        ent.tag_configure("ime", underline=True)   # 조합 중인 한글 (InlineIME)
        ent.tag_configure("mysel", background=SELECT_BG)   # 고른 글 (줄바꿈 빼고 글자에만, 옅은 주황)
        ent.is_reply = True                      # entry_focused()·InlineIME 가 알아보게
        ent.insert("1.0", self.reply_var.get())
        ent.edit_modified(False)
        ent.edit_reset()
        hint = tk.Label(ent, text=t("reply_hint"), bg=ENTRY_BG, fg=HINT_FG, font=REPLY_FONT,
                        padx=0, pady=0, bd=0, cursor="xterm")
        hint.bind("<Button-1>", lambda ev: self.focus_entry(ent, "end"))
        bg = cv.create_image(0, 0, anchor="nw")
        win = cv.create_window(padx, pady, window=ent, anchor="nw", width=tw_px)
        send = self.chip(cv, t("reply_send"), lambda: self.send_reply(key, ent.get("1.0", "end-1c"), other=True),
                         under=ENTRY_BG, pack=False)
        send_id = cv.create_window(0, 0, window=send, anchor="se")
        pick_id = None
        if allow_img:
            ent.bind("<Control-v>", lambda ev: self.paste_image())
            ent.bind("<Control-V>", lambda ev: self.paste_image())
            pick = self.chip(cv, t("img_pick"), self.pick_image, sub=True, under=ENTRY_BG, pack=False)
            pick_id = cv.create_window(0, 0, window=pick, anchor="sw")
        bar_h = send.winfo_reqheight()

        def fit(th):
            """글 칸 높이 th(px)에 맞춰 둥근 상자·버튼 자리를 바꾼다."""
            eh = pady + th + gap + bar_h + bot
            cv.configure(height=eh)
            cv.img = self.round_photo(ew, eh, ENTRY_BG, outline=ENTRY_LINE, ow=S(1), r=S(16))
            cv.itemconfigure(bg, image=cv.img)
            cv.itemconfigure(win, height=th)
            cv.coords(send_id, ew - padx + S(4), eh - bot)
            if pick_id:
                cv.coords(pick_id, padx - S(4), eh - bot)
            cv.th = th
            # 늘어난 만큼 위의 대화 기록창을 줄여 말풍선 크기는 그대로
            self._input_extra = th - self.reply_lh()
            self.relayout_chat()

        def show_hint():
            if ent.get("1.0", "end-1c"):
                hint.place_forget()
            else:                                # 커서(맨 왼쪽)를 덮지 않게 조금 오른쪽에
                hint.place(x=S(8), y=0)

        def paint_sel(ev=None, show=True):
            # Tk 는 고른 줄바꿈을 줄 오른쪽 끝까지 칠해서, 끌 때마다 빈 여백이 칠해졌다 사라졌다.
            # 진짜 선택(sel)은 그대로 두고(복사는 줄바꿈까지 정상) 보이지 않게 한 뒤,
            # 줄마다 글자 부분에만 'mysel' 을 칠한다 → 여백은 처음부터 칠해질 일이 없음
            try:
                ent.tag_remove("mysel", "1.0", "end")
                r = ent.tag_ranges("sel") if show else ()
                for a, b in zip(r[::2], r[1::2]):
                    first, last = int(str(a).split(".")[0]), int(str(b).split(".")[0])
                    for n in range(first, last + 1):
                        s = str(a) if n == first else f"{n}.0"
                        e = ent.index(f"{n}.0 lineend")
                        if n == last and ent.compare(b, "<", e):
                            e = str(b)
                        if ent.compare(s, "<", e):
                            ent.tag_add("mysel", s, e)
                ent.tag_raise("mysel")
            except tk.TclError:
                pass
        ent.bind("<<Selection>>", paint_sel, add="+")
        fit(self.input_px(self.reply_var.get(), tw_px))
        show_hint()

        def changed(ev=None):
            if not ent.edit_modified():
                return
            ent.edit_modified(False)
            text = ent.get("1.0", "end-1c")
            if text != self.reply_var.get():
                self.reply_var.set(text)         # → 세션마다 저장
            show_hint()
            th = self.input_px(text, tw_px)
            if th != cv.th:                      # 줄 수가 바뀌면 칸을 늘이거나 줄인다
                fit(th)
                ent.see("insert")
                self.position_bubble()

        ime = self.ime

        def on_return(ev):
            if ime:
                ime.flush()                      # 막 완성된 한글이 먼저 칸에 들어가게
            if ev.state & 0x0001:                # Shift+Enter → 줄바꿈 (기본 동작)
                return None
            self.send_reply(key, ent.get("1.0", "end-1c"), other=True)
            return "break"

        def on_key(ev):
            if ime:
                ime.flush()                      # (스페이스 등은 완성된 한글 뒤에 들어가야 함)
            self._typed_at = time.time()

        def on_focus(ev):
            ime_font(ent)
            paint_sel()                          # 다시 오면 고른 글 표시도 다시
            if ime:
                ime.attach(ent)

        def on_blur(ev):
            paint_sel(show=False)                # 다른 데로 가면 고른 글 표시는 숨김
            if ime:
                ime.detach(ent)
        ent.bind("<<Modified>>", changed)
        ent.bind("<Return>", on_return)
        ent.bind("<KP_Enter>", on_return)
        ent.bind("<FocusIn>", on_focus, add="+")
        ent.bind("<FocusOut>", on_blur, add="+")
        ent.bind("<Escape>", lambda ev: self.close_detail())
        ent.bind("<Key>", on_key, add="+")
        # 다른 곳을 눌렀다가 다시 입력칸을 누르면 키보드를 받게 (커서는 누른 자리에)
        # (다른 프로그램을 눌러도 카드는 닫지 않는다 — 보통 프로그램처럼. 닫기는 ‹ 목록·✕·Esc)
        ent.bind("<Button-1>", lambda ev: self.focus_entry(ent, None), add="+")
        self._draft_key = key
        if allow_img and self.reply_imgs:   # 붙인 이미지 미리보기 (누르면 그 이미지 빼기)
            row = tk.Frame(box, bg=INNER)
            row.pack(anchor="w", pady=(S(3), 0))
            self._thumbs = []
            for path in list(self.reply_imgs):
                try:
                    im = Image.open(path)
                    im.thumbnail((S(44), S(44)))
                    ph = ImageTk.PhotoImage(im)
                except Exception:
                    continue
                self._thumbs.append(ph)
                lb = tk.Label(row, image=ph, bg=ANS_BG, padx=S(2), pady=S(2), cursor="hand2")
                lb.pack(side="left", padx=(0, S(4)))
                lb.bind("<Button-1>", lambda ev, p=path: self.drop_image(p))
            tk.Label(row, text=t("img_hint"), bg=INNER, fg=SUB, font=(FONT, 7)).pack(side="left")
        # 커서는 사용자가 카드를 열었을 때나, 다시 만들기 전에 입력칸에 있었을 때만 준다
        # (Claude가 일하는 동안 카드가 바뀌어도 다른 창에서 쓰던 키보드를 뺏지 않게)
        if self._want_focus or self._refocus is not None:
            pos = "end" if self._refocus is None else self._refocus
            self.root.after(60, lambda: self.focus_entry(ent, pos))
        self._want_focus, self._refocus = False, None

    def reply_lh(self):
        if not getattr(self, "_reply_lh", 0):
            self._reply_lh = tkfont.Font(root=self.root, font=REPLY_FONT).metrics("linespace")
        return self._reply_lh

    def input_px(self, text, px):
        """입력칸 글 높이(px): 1줄 ~ 6줄 (넘으면 칸 안에서 스크롤). 화면 밖 같은 모양 칸에 넣어 잰다."""
        m = getattr(self, "_measure_in", None)
        if m is None:
            m = self._measure_in = tk.Text(self.root, font=REPLY_FONT, wrap="word", width=1, height=1,
                                           padx=0, pady=0, bd=0, spacing2=S(2), highlightthickness=0)
        if getattr(m, "px", None) != px:
            m.place(x=-S(3000), y=0, width=px)
            m.px = px
            self.root.update_idletasks()
        m.delete("1.0", "end")
        m.insert("1.0", text)
        r = m.count("1.0", "end", "update", "ypixels")
        h = int((r[0] if isinstance(r, tuple) else r) or 0)
        lh = self.reply_lh()
        return max(lh, min(h, lh * 6))

    # ---- 답장에 이미지 붙이기 ----
    # 붙인 이미지는 사진 폴더에 파일로 두었다가, 보낼 때 감시 프로그램이 잠깐 포커스를 받아 입력창에 진짜로 붙여넣는다.
    def paste_image(self):
        try:
            from PIL import ImageGrab
            got = ImageGrab.grabclipboard()
        except Exception:
            got = None
        if isinstance(got, Image.Image):
            path = os.path.join(image_dir(), time.strftime("paste-%Y%m%d-%H%M%S.png"))
            try:
                got.save(path)
            except OSError:
                return None
            self.reply_imgs.append(path)
        elif isinstance(got, list) and any(p.lower().endswith(IMG_EXTS) for p in got):
            self.reply_imgs += [p for p in got if p.lower().endswith(IMG_EXTS)]
        else:
            return None               # 이미지가 아니면 보통 글 붙여넣기
        self.save_draft()
        self._want_focus = True
        self.update_bubble(force=True)
        return "break"

    def pick_image(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            parent=self.bubble, title=t("img_pick"),
            filetypes=[(t("img_pick"), " ".join("*" + x for x in IMG_EXTS))])
        self.reply_imgs += [p.replace("/", "\\") for p in paths]
        self.save_draft()
        self._want_focus = True
        self.update_bubble(force=True)

    def drop_image(self, path):
        if path in self.reply_imgs:
            self.reply_imgs.remove(path)
        self.save_draft()
        self._want_focus = True
        self.update_bubble(force=True)

    def focus_entry(self, ent, pos="end"):
        # 투명 창은 그냥은 키보드를 못 받아서, 말풍선 창을 앞으로 올린 뒤 입력칸에 커서를 둔다
        # pos: 커서 자리 ("end" 끝, 숫자·"줄.칸" 그 자리, None 그대로 — 누른 자리에 두기)
        try:
            hwnd = ctypes.windll.user32.GetParent(self.bubble.winfo_id())
            fg = ctypes.windll.user32.GetForegroundWindow()
            if fg and fg != hwnd:     # 그 전에 쓰던 창 (이미지를 붙인 뒤 포커스를 여기로 돌려놓는다)
                self.prev_fg = fg
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                self.bubble.focus_force()
            ent.focus_set()
            if pos is not None:
                ent.mark_set("insert", pos)
                ent.see("insert")
            ime_font(ent)
        except tk.TclError:
            pass

    def entry_focused(self):
        """키보드 커서가 있는 로봇 입력칸 (없으면 None)."""
        try:
            w = self.bubble.focus_get()
        except (tk.TclError, KeyError):
            return None
        return w if getattr(w, "is_reply", False) else None

    def typing(self):
        """입력칸에 글을 쓰는 중인지: 2.5초 안에 글자를 쳤거나, 커서가 입력칸에 있고 쓰던 글이 있으면."""
        return (time.time() - self._typed_at < 2.5
                or (self.entry_focused() is not None and bool(self.reply_var.get().strip())))

    def ui_log(self, what, *sigs):
        """입력하다 카드가 다시 만들어지는 일을 남긴다 (글자가 빠진다는 제보를 따라가려고). 무엇이 바뀌었는지만."""
        new = sigs[-2] if len(sigs) >= 2 else None
        old = sigs[-1] if sigs else None
        diff = []
        if isinstance(new, tuple) and isinstance(old, tuple):
            diff = [f"{i}:{str(b)[:40]}→{str(a)[:40]}" for i, (a, b) in enumerate(zip(new, old)) if a != b]
        line = f"{what} {' '.join(str(x) for x in sigs[:-2])} {diff}"
        if line == getattr(self, "_ui_last", None):
            return
        self._ui_last = line
        try:
            p = os.path.join(APP_DIR, "ui.log")
            if os.path.exists(p) and os.path.getsize(p) > 100_000:
                os.remove(p)
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("%m-%d %H:%M:%S ") + line + "\n")
        except OSError:
            pass

    # ---- 쓰던 글 저장 (세션마다, 파일에도) ----
    def load_draft(self, key):
        self._draft_key = None                   # 바꾸는 동안은 저장하지 않게
        d = self.drafts.get(key) or {}
        self.reply_imgs = [p for p in d.get("imgs", []) if os.path.exists(p)]
        self.reply_var.set(d.get("text", ""))
        self._draft_key = key

    def save_draft(self):
        key = self._draft_key
        if not key:
            return
        text = self.reply_var.get()
        if text.strip() or self.reply_imgs:
            self.drafts[key] = {"text": text, "imgs": list(self.reply_imgs), "t": time.time()}
        elif self.drafts.pop(key, None) is None:
            return
        if getattr(self, "_draft_job", None):
            self.root.after_cancel(self._draft_job)
        self._draft_job = self.root.after(800, self.write_drafts)   # 칠 때마다 쓰지 않고 잠깐 모아서

    def write_drafts(self):
        self._draft_job = None
        if len(self.drafts) > 30:                # 오래된 것부터 정리
            for k in sorted(self.drafts, key=lambda k: self.drafts[k].get("t", 0))[:-30]:
                del self.drafts[k]
        try:
            write_json(DRAFTS, self.drafts)
        except OSError:
            pass

    def open_detail(self, key):
        self.load_draft(key)
        self.detail = key
        self.shown_at = time.time()
        self._want_focus = True
        self.update_bubble(force=True)

    def close_detail(self):
        self.detail = None
        self._draft_key = None                   # 닫힌 뒤 입력칸 글이 바뀌어도 저장된 글은 그대로
        self._hist.clear()                       # 읽어 둔 대화 목록도 버린다 (다시 펼치면 최근 것부터 새로 읽음)
        self._img_src = None
        self.update_bubble(force=True)

    def send_reply(self, key, text, other=False):
        e = self.tracker.tasks.get(key)
        text = (text or "").strip()
        if e and is_term(e):                     # 터미널 Claude Code: 도우미가 그 콘솔 입력에 넣고 Enter
            # 질문 카드·선택 메뉴는 터미널에서 (다른 경로로 새지 않게 여기서 끝)
            if not text or e.get("sending") or e.get("card") or self.term_menu(e):
                return
            e["sending"] = True
            self.reply_key = key
            self.reply_imgs = []
            self.reply_var.set("")

            def work(ent=dict(e), msg=text):
                self._term_result = term_run("send", ent, msg)
            threading.Thread(target=work, daemon=True).start()
            self.update_bubble(force=True)
            return
        if e and self.is_gpt(e) and GPT:         # ChatGPT 앱: 감시 프로그램이 그 대화 입력창에 넣고 Enter
            if not text or e.get("sending"):
                return
            e["sending"] = True
            self.reply_key = key
            self.reply_imgs = []
            self.reply_var.set("")
            GPT.reply_gpt(e["title"], text)
            self.update_bubble(force=True)
            return
        if e and self.is_web(e):                 # 웹 탭: 확장이 그 탭 입력창에 넣고 보내기를 누름
            if not text or e.get("sending"):
                return
            self._web_send_id = getattr(self, "_web_send_id", 0) + 1
            e.update(sending=True, sent_at=time.time(), send_id=self._web_send_id)
            self.reply_key = key
            self.reply_imgs = []
            self.reply_var.set("")
            web_command({"cmd": "send", "tab": e["tab"], "browser": e.get("browser", ""),
                         "text": text, "id": self._web_send_id})
            self.update_bubble(force=True)
            return
        images = (list(self.reply_imgs) if other and e and not e.get("card")
                  and e.get("entry") != "claude-vscode" else [])
        if images and not text:           # 이미지만 보내면 짧은 글을 같이
            text = t("img_default")
        if not e or not text or not GPT:
            return
        if not e.get("title"):
            threading.Thread(target=msgbox, args=(t("reply_notitle"),), daemon=True).start()
            return
        e["sending"] = True
        self.reply_key = key
        self.reply_imgs = []                     # (이미지를 먼저 비워야 쓰던 글 저장에서도 같이 지워짐)
        self.reply_var.set("")
        vs = e.get("entry") == "claude-vscode"
        if e.get("card"):            # 질문 카드: 고르고 제출 (기타면 글을 넣어서)
            GPT.card(e["title"], "" if other else text, text if other else "", vscode=vs)
        else:                        # 다음 단계 상자·끝난 세션: 입력창에 글을 넣어 보내기
            GPT.reply(e["title"], text, vscode=vs, images=images, restore=self.prev_fg)
        self.update_bubble(force=True)

    def web_results(self):
        """웹 탭에 보낸 답의 결과를 받고, 15초 넘게 답이 없으면 실패로 (확장이 옛 버전일 때)."""
        res = self.tracker.web_sent
        while res:
            key, ok, err, sid = res.pop(0)
            e = self.tracker.tasks.get(key)
            if e and e.get("sending") and e.get("send_id") == sid:
                self.web_reply_done(key, ok, err)
        for key, e in list(self.tracker.tasks.items()):
            if e.get("sending") and self.is_web(e) and time.time() - e.get("sent_at", 0) > 15:
                self.web_reply_done(key, False, "timeout")

    def web_reply_done(self, key, ok, err):
        e = self.tracker.tasks.get(key)
        if e and e.pop("sending", None):
            self.update_bubble(force=True)
        if not ok:
            msg = T.get("web_err_" + err) and t("web_err_" + err) or err
            threading.Thread(target=msgbox, args=(t("reply_fail", e=msg), 0x30), daemon=True).start()

    def sync_web_watch(self):
        """펼친 카드가 웹 탭이면 확장에게 그 탭 대화 글을 보내 달라고 하고(20초마다 다시), 닫으면 그만 보내게.
        다 본 대화 글 파일은 지운다 (대화 내용이 컴퓨터에 남지 않게)."""
        e = self.tracker.tasks.get(self.detail) if self.detail else None
        want = self.detail if e and self.is_web(e) else None
        cur = getattr(self, "_watch", None)
        now = time.time()
        if want == cur:
            if want and now - self._watch_at > 20:
                web_command({"cmd": "watch", "tab": e["tab"], "browser": e.get("browser", "")})
                self._watch_at = now
            return
        if cur:
            self.unwatch(self._watch_e)
        if want:
            web_command({"cmd": "watch", "tab": e["tab"], "browser": e.get("browser", "")})
        self._watch, self._watch_e, self._watch_at = want, e, now

    def unwatch(self, e):
        """확장에게 그 탭 대화 글을 그만 보내게 하고, 받아 둔 파일을 지운다 (그사이 온 글도 2.5초 뒤 한 번 더)."""
        web_command({"cmd": "unwatch", "tab": e["tab"], "browser": e.get("browser", "")})
        path = web_chat_file(e)

        def drop():
            try:
                os.remove(path)
            except OSError:
                pass
        drop()
        try:
            self.root.after(2500, drop)
        except tk.TclError:
            pass

    def quit(self):
        """로봇 끄기 (메뉴·언어 바꾸기·제거·quit.flag 모두 여기로): 펼쳐 둔 웹 카드가 있으면 먼저 unwatch."""
        e = getattr(self, "_watch_e", None)
        if getattr(self, "_watch", None) and e:
            web_command({"cmd": "unwatch", "tab": e["tab"], "browser": e.get("browser", "")})
            try:
                os.remove(web_chat_file(e))
            except OSError:
                pass
        self.root.destroy()

    def reply_done(self, result):
        # 성공하면 곧 Claude Code가 새 턴을 시작해(훅 신호) 줄이 '진행 중'으로 바뀐다
        # 답하는 중에 보낸 글은 새 턴 신호 없이 대기열로 들어가므로, 성공하면 '보내는 중' 표시를 바로 거둔다
        e = self.tracker.tasks.get(self.reply_key)
        if e and (result != "ok" or e.get("status") == "working" or self.is_gpt(e)):
            e.pop("sending", None)
            self.update_bubble(force=True)
        if result != "ok":
            threading.Thread(target=msgbox, args=(t("reply_fail", e=result), 0x30),
                             daemon=True).start()

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
        # 네모 띠 대신 제목 글자 색만 바꿔 어느 줄인지 보이게 (말풍선 안은 둥근 모양만)
        for w in parts:
            if getattr(w, "hl", False):
                try:
                    w.configure(fg=HOVER if on else getattr(w, "base", FG))
                except tk.TclError:
                    pass

    def show_bubble(self):
        if self.bubble.state() == "withdrawn":
            self.bubble.deiconify()
        self.position_bubble()

    def bubble_image(self, bw, bh, rect_w, rect_h, ty):
        """크게 그린 뒤 줄여서 모서리를 매끈하게. 가장자리는 어차피 딱 끊으므로
        펼친 카드처럼 큰 말풍선은 2배로만 (4배면 그리는 데 오래 걸려 펼칠 때 굼뜸)."""
        k = 4 if bh < S(160) else 2
        img = Image.new("RGBA", (bw * k, bh * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        o = S(2)
        radius = getattr(self, "_radius", min(S(26), rect_h // 2))
        d.rounded_rectangle([o * k, o * k, (o + rect_w) * k, (o + rect_h) * k],
                            radius=radius * k, fill=INNER, outline=BORDER, width=S(2) * k)
        bx = (o + rect_w) * k - S(2) * k
        tw = S(13)
        d.polygon([(bx, ty * k), ((rect_w + o + tw) * k, (ty + S(8)) * k),
                   (bx, (ty + S(16)) * k)], fill=BORDER)
        d.polygon([(bx - k, (ty + S(3)) * k), ((rect_w + o + tw - S(5)) * k, (ty + S(8)) * k),
                   (bx - k, (ty + S(13)) * k)], fill=INNER)
        # 줄인 뒤 가장자리를 반투명 없이 딱 끊는다: 반투명 점은 투명색(검정)과 섞여
        # 밝은 배경에서 가장자리에 거무스름한 점(구멍처럼 보임)이 생기기 때문
        small = img.resize((bw, bh), Image.LANCZOS)
        small.putalpha(small.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        bg = Image.new("RGB", small.size, KEY)
        bg.paste(small, mask=small.getchannel("A"))
        return ImageTk.PhotoImage(bg)

    def position_bubble(self):
        if self.hidden or self.bubble.state() == "withdrawn":
            return
        self.bub_box.update_idletasks()
        # 캡슐형: 모서리 반지름을 크게(한 줄이면 반원, 펼친 카드도 큰 곡선) 하고,
        # 둥근 모서리에 글이 닿지 않게 반지름의 약 0.3배만큼 여백을 둔다
        bw0, bh0 = self.bub_box.winfo_reqwidth(), self.bub_box.winfo_reqheight()
        radius = min(S(60), (bh0 + S(22)) // 2)
        padx = max(S(20), int(radius * 0.32))
        pady = max(S(11), int(radius * 0.32))
        rect_w = bw0 + padx * 2
        rect_h = bh0 + pady * 2
        self._radius = min(radius, rect_h // 2)
        bw = rect_w + S(16)
        bh = max(rect_h + S(4), S(44))
        l, t_, r, b = work_area()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        x = max(l + 4, rx - bw - S(2))
        y = max(t_ + 4, min(ry + self.ch - bh - S(24), b - bh - 4))
        ty = max(S(12), min(ry + S(30) - y, bh - S(28)))
        # 꼬리는 캡슐의 곧은 옆면에 붙인다 (둥근 모서리에 붙으면 떠 보임). 곧은 면이 없으면 가운데
        lo, hi = int(self._radius * 0.75) - S(8), rect_h - int(self._radius * 0.75) - S(8)
        ty = rect_h // 2 - S(8) if lo > hi else max(lo, min(ty, hi))
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
        c.coords("boxwin", S(2) + padx, S(2) + pady)
        c.tag_raise("boxwin")
        self.bubble.geometry(f"{bw}x{bh}+{x}+{y}")


def main():
    if "--uninstall" in sys.argv:
        uninstall()
        return
    if FROZEN and os.path.normcase(APP_DIR) != os.path.normcase(INSTALL_DIR):
        install()
        return
    # 이미 실행 중이면 끝 (언어를 바꿔 다시 켤 때는 옛 로봇이 꺼질 때까지 5초까지 기다린다)
    for _ in range(50 if "--restart" in sys.argv else 1):
        h = ctypes.windll.kernel32.CreateMutexW(None, False, "TaskPetWidget")
        if ctypes.windll.kernel32.GetLastError() != 183:
            break
        ctypes.windll.kernel32.CloseHandle(h)
        if "--restart" in sys.argv:
            time.sleep(0.1)
    else:
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
    Pet()


if __name__ == "__main__":
    main()
