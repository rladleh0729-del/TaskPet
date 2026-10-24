# Chrome 웹 스토어에 올릴 것들을 만든다.  python tools\make_store_assets.py
#   dist\store\TaskPet-extension.zip  확장 묶음 ("key" 는 뺌 — 스토어가 ID를 따로 정함)
#   dist\store\screenshot-1280x800.png, promo-440x280.png
import json
import os
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EXT = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "dist", "store")
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

# ---- 그림 ----
src = open(os.path.join(ROOT, "src", "taskpet.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("IDLE = ["):src.index("]", src.index("IDLE = [")) + 1], ns)
GRID = ns["IDLE"]
ROBOT = {"O": "#f5942b", "D": "#a85a0e", "F": "#2a2230", "M": "#ffb15e", "E": "#7fe0a0"}
INNER, BORDER, FG, SUB = "#221c28", "#f5942b", "#e8e8ec", "#9a9aa6"
GREEN, ORANGE, BLUE, PURPLE, SILVER, TEAL = ("#4cc46a", "#f5942b", "#4ea1ff", "#a98bff",
                                             "#cfd3dc", "#3dd6c6")
FONTS = r"C:\Windows\Fonts"
K = 2   # 2배로 그려 줄여서 매끈하게


def font(size, bold=False):
    return ImageFont.truetype(os.path.join(FONTS, "malgunbd.ttf" if bold else "malgun.ttf"), size * K)


def robot(d, x, y, cell):
    for ry, row in enumerate(GRID):
        for rx, ch in enumerate(row):
            if ch != ".":
                d.rectangle([(x + rx * cell) * K, (y + ry * cell) * K,
                             (x + (rx + 1) * cell) * K - 1, (y + (ry + 1) * cell) * K - 1],
                            fill=ROBOT[ch])


ROWS = [("work", "보고서 요약해 줘", "ChatGPT 웹", BLUE, "32초 진행 중"),
        ("done", "여행 계획 세우기", "Gemini", PURPLE, "완료 14:02 · 1분"),
        ("done", "코드 리뷰 부탁해", "Claude 웹", ORANGE, "완료 13:58 · 2분"),
        ("work", "오늘 뉴스 정리", "Grok", SILVER, "12초 진행 중"),
        ("done", "영어 문장 번역", "Kimi", TEAL, "완료 13:50 · 20초")]


def bubble(d, x, y, scale=1.0):
    """실제 로봇 말풍선처럼: 어두운 둥근 상자, 주황 테두리, 줄마다 상태·제목·이름표·시간."""
    fs = int(19 * scale)
    f, fb = font(fs), font(fs, True)
    row_h = int(40 * scale)
    pad = int(22 * scale)
    w = int(520 * scale)
    h = pad * 2 + row_h * len(ROWS)
    d.rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], radius=int(26 * scale) * K,
                        fill=INNER, outline=BORDER, width=int(3 * scale) * K)
    for i, (st, title, label, color, tail) in enumerate(ROWS):
        cy = y + pad + i * row_h + row_h // 2
        cx = x + pad
        r = int(8 * scale)
        if st == "done":
            d.rounded_rectangle([(cx) * K, (cy - r) * K, (cx + 2 * r) * K, (cy + r) * K],
                                radius=3 * K, outline=GREEN, width=2 * K)
            d.line([((cx + 4 * scale) * K, cy * K), ((cx + r) * K, (cy + 5 * scale) * K),
                    ((cx + 2 * r - 3 * scale) * K, (cy - 5 * scale) * K)], fill=GREEN, width=int(3 * scale) * K)
        else:
            d.ellipse([cx * K, (cy - r) * K, (cx + 2 * r) * K, (cy + r) * K], outline=color, width=int(3 * scale) * K)
            d.ellipse([(cx + r - 3 * scale) * K, (cy - 3 * scale) * K, (cx + r + 3 * scale) * K,
                       (cy + 3 * scale) * K], fill=color)
        tx = cx + 2 * r + int(12 * scale)
        d.text((tx * K, cy * K), title, font=fb, fill=GREEN if st == "done" else color, anchor="lm")
        tx += d.textlength(title, font=fb) / K + int(14 * scale)
        d.text((tx * K, cy * K), label, font=fb, fill=color, anchor="lm")
        tx += d.textlength(label, font=fb) / K + int(8 * scale)
        d.text((tx * K, cy * K), "· " + tail, font=f, fill=SUB, anchor="lm")
    return w, h


# 스크린샷 1280x800
W, H = 1280, 800
img = Image.new("RGB", (W * K, H * K), "#f3efe9")
d = ImageDraw.Draw(img)
d.text((80 * K, 110 * K), "AI가 답을 다 쓰면", font=font(54, True), fill="#2a2230")
d.text((80 * K, 180 * K), "로봇이 알려 줘요", font=font(54, True), fill=ORANGE)
d.text((82 * K, 270 * K), "ChatGPT · Gemini · Claude · Grok · Kimi", font=font(26, True), fill="#5b5266")
for i, line in enumerate(["답하는 중 → 완료를 화면 오른쪽 아래 로봇이 표시",
                          "끝나면 짧은 '띠링' 소리",
                          "줄을 더블 클릭하면 그 대화 탭으로 바로 이동",
                          "대화 내용은 읽지 않고, 내 컴퓨터 안에서만 전달"]):
    yy = 350 + i * 52
    d.ellipse([84 * K, (yy + 10) * K, 98 * K, (yy + 24) * K], fill=ORANGE)
    d.text((114 * K, yy * K), line, font=font(24), fill="#3b3442")
d.text((82 * K, 600 * K), "Windows용 TaskPet 프로그램과 함께 쓰는 확장입니다", font=font(19), fill="#8a8094")
bw, bh = bubble(d, 660, 552, 0.9)
robot(d, 1155, 630, 8)
img.resize((W, H), Image.LANCZOS).save(os.path.join(OUT, "screenshot-1280x800.png"))

# 작은 홍보 타일 440x280
W, H = 440, 280
img = Image.new("RGB", (W * K, H * K), INNER)
d = ImageDraw.Draw(img)
d.rounded_rectangle([10 * K, 10 * K, (W - 10) * K, (H - 10) * K], radius=24 * K, outline=BORDER, width=4 * K)
robot(d, 40, 70, 10)
d.text((205 * K, 92 * K), "TaskPet", font=font(44, True), fill=ORANGE)
d.text((207 * K, 160 * K), "AI 답변이 끝나면", font=font(20, True), fill=FG)
d.text((207 * K, 190 * K), "로봇이 알려 줘요", font=font(20, True), fill=FG)
img.resize((W, H), Image.LANCZOS).save(os.path.join(OUT, "promo-440x280.png"))
print("그림 완료", sorted(os.listdir(OUT)))
