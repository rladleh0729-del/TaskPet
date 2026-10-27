# 확장 아이콘(16·32·48·128px)을 TaskPet 로봇 그림으로 만든다.  python tools\make_ext_icons.py
# (프로그램 아이콘과 같은 robot_image — 정사각형 가운데에 둔다)
import os
import sys

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from taskpet import robot_image  # noqa: E402

out = os.path.join(ROOT, "extension", "icons")
os.makedirs(out, exist_ok=True)
bot = robot_image("idle", 240, 256, hard=False)
big = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
big.paste(bot, (8, 0), bot)
for size in (16, 32, 48, 128):
    big.resize((size, size), Image.LANCZOS).save(os.path.join(out, f"{size}.png"))
print("완료", sorted(os.listdir(out)))
