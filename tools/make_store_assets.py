# Chrome 웹 스토어에 올릴 것들을 만든다.  python tools\make_store_assets.py
#   dist\store\TaskPet-extension.zip  확장 묶음 ("key" 는 뺌 — 스토어가 ID를 따로 정함)
#   dist\store\screenshot(-en)-1280x800.png, promo(-en)-440x280.png  (한국어·영어)
# 그림은 실제 로봇 화면을 쓴다 → 먼저 python tools\make_scenes.py 로 dist\scenes 를 만들 것.
import json
import os
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EXT = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "dist", "store")
SCENES = os.path.join(ROOT, "dist", "scenes")
os.makedirs(OUT, exist_ok=True)

# ---- 확장 zip ----
manifest = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))
manifest.pop("key", None)
zpath = os.path.join(OUT, "TaskPet-extension.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    for base, _, files in os.walk(EXT):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, EXT).replace("\\", "/")
            if rel != "manifest.json":
                z.write(p, rel)
print("zip", zpath, sorted(zipfile.ZipFile(zpath).namelist()))

# ---- 사이트(querybot.kr/taskpet/)에서 받는 확장 zip ----
# 사용자가 '압축해제된 확장'으로 직접 불러오는 용도라 "key" 를 그대로 둔다
# (키가 있어야 확장 ID가 고정돼 TaskPet 연결 허용 목록과 맞음). 풀면 TaskPet-extension 폴더 하나가 나온다.
spath = os.path.join(ROOT, "site", "taskpet", "TaskPet-extension.zip")
os.makedirs(os.path.dirname(spath), exist_ok=True)
with zipfile.ZipFile(spath, "w", zipfile.ZIP_DEFLATED) as z:
    for base, _, files in os.walk(EXT):
        for f in files:
            p = os.path.join(base, f)
            z.write(p, "TaskPet-extension/" + os.path.relpath(p, EXT).replace("\\", "/"))
print("사이트 zip", spath, sorted(zipfile.ZipFile(spath).namelist()))

# ---- 그림 (로봇과 같은 옅은 주황 테마) ----
BG, CARD, BORDER = "#fff7ee", "#fff1e1", "#f39a3f"
INK, SUB, ORANGE = "#43260f", "#9a6b45", "#e07c1c"
FONTS = r"C:\Windows\Fonts"
K = 2   # 2배로 그려 줄여서 매끈하게


def font(size, bold=False):
    return ImageFont.truetype(os.path.join(FONTS, "malgunbd.ttf" if bold else "malgun.ttf"), size * K)


def paste(img, path, x, y, h):
    """장면 그림을 높이 h 로 맞춰 (x, y)에 붙인다 (2배 캔버스 기준 좌표는 1배로 줌)."""
    im = Image.open(path).convert("RGBA")
    w = round(im.width * h / im.height)
    im = im.resize((w * K, h * K), Image.LANCZOS)
    img.alpha_composite(im, (x * K, y * K))
    return w


# 언어별 글 (스토어 기본 언어는 영어, 한국어 등록정보에는 한국어 그림)
TEXT = {
    "ko": {"h1": "AI가 답을 다 쓰면", "h2": "로봇이 알려 줘요",
           "bullets": ["답하는 중 → 완료를 화면 오른쪽 아래 로봇이 표시",
                       "끝나면 짧은 '띠링' 소리와 초록 완료 표시",
                       "줄을 더블 클릭하면 그 대화 탭으로 바로 이동",
                       "대화 내용은 읽지 않고, 내 컴퓨터 안에서만 전달"],
           "foot": "Windows용 TaskPet 프로그램과 함께 쓰는 확장입니다",
           "promo": ["AI 답변이 끝나면", "로봇이 알려 줘요"], "suffix": ""},
    "en": {"h1": "When the AI is done,", "h2": "the robot tells you",
           "bullets": ["A robot at the bottom right shows answering → done",
                       "A short chime and green when it finishes",
                       "Double-click a row to jump to that chat tab",
                       "Never reads your chats; stays on your PC"],
           "foot": "Companion to the free TaskPet app for Windows",
           "promo": ["Know the moment", "your AI chat is done"], "suffix": "-en"},
}

for lang, tx in TEXT.items():
    # 스크린샷 1280x800: 왼쪽 글, 오른쪽 진짜 로봇 말풍선
    W, H = 1280, 800
    img = Image.new("RGBA", (W * K, H * K), BG)
    d = ImageDraw.Draw(img)
    d.text((80 * K, 110 * K), tx["h1"], font=font(54, True), fill=INK)
    d.text((80 * K, 180 * K), tx["h2"], font=font(54, True), fill=ORANGE)
    d.text((82 * K, 270 * K), "ChatGPT · Gemini · Claude · Grok · Kimi", font=font(26, True), fill=SUB)
    for i, line in enumerate(tx["bullets"]):
        yy = 350 + i * 52
        d.ellipse([84 * K, (yy + 10) * K, 98 * K, (yy + 24) * K], fill=BORDER)
        d.text((114 * K, yy * K), line, font=font(24), fill=INK)
    d.text((82 * K, 600 * K), tx["foot"], font=font(19), fill=SUB)
    paste(img, os.path.join(SCENES, f"ext_{lang}.png"), 664, 500, 250)   # (오른쪽 끝 1264 안에)
    img.convert("RGB").resize((W, H), Image.LANCZOS).save(
        os.path.join(OUT, f"screenshot{tx['suffix']}-1280x800.png"))

    # 작은 홍보 타일 440x280: 둥근 카드 + 로봇 + 이름
    W, H = 440, 280
    img = Image.new("RGBA", (W * K, H * K), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10 * K, 10 * K, (W - 10) * K, (H - 10) * K], radius=40 * K, fill=CARD,
                        outline=BORDER, width=4 * K)
    paste(img, os.path.join(SCENES, "robot.png"), 34, 62, 160)
    d.text((205 * K, 92 * K), "TaskPet", font=font(44, True), fill=ORANGE)
    d.text((207 * K, 160 * K), tx["promo"][0], font=font(20, True), fill=INK)
    d.text((207 * K, 190 * K), tx["promo"][1], font=font(20, True), fill=INK)
    img.convert("RGB").resize((W, H), Image.LANCZOS).save(os.path.join(OUT, f"promo{tx['suffix']}-440x280.png"))
print("그림 완료", sorted(os.listdir(OUT)))
