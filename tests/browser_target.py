"""Use an explicit Chromium for QA, or the installed Windows Edge by default."""
import os
from pathlib import Path

CUSTOM_BROWSER = os.environ.get("RITMO_QA_BROWSER")
EDGE_LOCATIONS = [
    Path(os.environ.get(root, fallback)) / "Microsoft/Edge/Application/msedge.exe"
    for root, fallback in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                           ("ProgramFiles", r"C:\Program Files"))
]
BROWSER = Path(CUSTOM_BROWSER) if CUSTOM_BROWSER else next(
    (path for path in EDGE_LOCATIONS if path.is_file()), None)
if CUSTOM_BROWSER and not BROWSER.is_file():
    raise ValueError("RITMO_QA_BROWSER deve apontar para um executável existente")
