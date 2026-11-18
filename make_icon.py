"""Erzeugt icon.ico (Briefumschlag). Nur nötig, wenn man das Icon neu bauen will.

    pip install pillow
    python make_icon.py
"""

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# runder blauer Hintergrund
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=48, fill=(32, 110, 200, 255))

# Briefumschlag
x0, y0, x1, y1 = 44, 74, S - 44, S - 74
d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(255, 255, 255, 255))
w = 10
d.line((x0 + 6, y0 + 8, S // 2, S // 2 + 6, x1 - 6, y0 + 8), fill=(32, 110, 200, 255), width=w, joint="curve")

# oranger "Senden"-Punkt
d.ellipse((S - 92, S - 92, S - 24, S - 24), fill=(255, 150, 30, 255), outline=(255, 255, 255, 255), width=8)
d.polygon([(S - 74, S - 58), (S - 46, S - 72), (S - 52, S - 44)], fill=(255, 255, 255, 255))

img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save("icon.png")
print("icon.ico / icon.png erstellt")
