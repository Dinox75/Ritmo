"""Empacota o ícone vetorial renderizado do Ritmo para o Windows."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
image = Image.open(ROOT / "web" / "icon-512.png").convert("RGBA")
target = ROOT / "assets" / "ritmo.ico"
image.save(target, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)
