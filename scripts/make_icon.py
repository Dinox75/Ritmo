"""Gera o ícone Windows a partir das cores e da letra do ícone web."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SIZE = 256
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=62, fill="#12373e")
font_path = Path("C:/Windows/Fonts/georgiab.ttf")
font = ImageFont.truetype(str(font_path), 188) if font_path.exists() else ImageFont.load_default()
box = draw.textbbox((0, 0), "R", font=font)
x = (SIZE - (box[2] - box[0])) / 2 - box[0] - 7
y = (SIZE - (box[3] - box[1])) / 2 - box[1] - 7
draw.text((x, y), "R", font=font, fill="#e4bb7d")
target = ROOT / "assets" / "ritmo.ico"
image.save(target, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)
