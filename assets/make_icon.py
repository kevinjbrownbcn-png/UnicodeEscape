"""Regenerates the app icon: assets/icon.ico (multi-size) and assets/icon.png (512 px logo/favicon).

Run:  python assets/make_icon.py
Requires Pillow. The design is a navy rounded tile with a teal outline and a teal `\\u` glyph
(the escape sequence this tool produces), using the app's palette (see theme.py).
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\consolab.ttf"
SIZE = 1024  # master canvas; downsampled for the smaller sizes
NAVY, TEAL = "#0f172a", "#2dd4bf"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

def build_master():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((24, 24, SIZE - 24, SIZE - 24), radius=230, fill=NAVY, outline=TEAL, width=22)
    font = ImageFont.truetype(FONT, 600)
    # Centre on the glyphs' real bounding box (not the font's line box).
    left, top, right, bottom = d.textbbox((0, 0), "\\u", font=font)
    d.text((SIZE / 2 - (left + right) / 2, SIZE / 2 + 10 - (top + bottom) / 2), "\\u", font=font, fill=TEAL)
    return img

if __name__ == "__main__":
    master = build_master()
    master.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))
    master.save(os.path.join(OUT, "icon.ico"), sizes=ICO_SIZES)
    print("Wrote assets/icon.ico and assets/icon.png")
