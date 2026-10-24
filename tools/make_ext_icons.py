# 확장 아이콘(16·32·48·128px)을 로봇 도트로 만든다.  python tools\make_ext_icons.py
import os

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
src = open(os.path.join(ROOT, "src", "taskpet.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("IDLE = ["):src.index("]", src.index("IDLE = [")) + 1], ns)
GRID = ns["IDLE"]
COLORS = {"O": "#f5942b", "D": "#a85a0e", "F": "#2a2230", "M": "#ffb15e", "E": "#4ea1ff"}  # 눈은 파랑(GPT 쪽)

out = os.path.join(ROOT, "extension", "icons")
os.makedirs(out, exist_ok=True)
n = 16
big = Image.new("RGBA", (n * 16, n * 16), (0, 0, 0, 0))
d = ImageDraw.Draw(big)
ox = (n - len(GRID[0])) // 2
for y, row in enumerate(GRID):
    for x, ch in enumerate(row):
        if ch != ".":
            d.rectangle([(x + ox) * 16, y * 16, (x + ox + 1) * 16 - 1, (y + 1) * 16 - 1], fill=COLORS[ch])
for size in (16, 32, 48, 128):
    big.resize((size, size), Image.NEAREST).save(os.path.join(out, f"{size}.png"))
print("완료", sorted(os.listdir(out)))
