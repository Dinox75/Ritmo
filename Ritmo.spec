# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

web_data, web_bins, web_hidden = collect_all('webview')
face_data, face_bins, face_hidden = collect_all('mediapipe')
cvzone_data, cvzone_bins, cvzone_hidden = collect_all('cvzone')

a = Analysis(
    ['desktop.py'],
    pathex=['.'],
    binaries=web_bins + face_bins + cvzone_bins,
    datas=web_data + face_data + cvzone_data + [('web', 'web'), ('tutor/guide.md', 'tutor'), ('local_ai/models.json', 'local_ai'), ('local_ai/knowledge.json', 'local_ai'), ('config/config.json', 'config'), ('config/classificacao_apps.json', 'config'), ('assets/ritmo.ico', 'assets')],
    hiddenimports=web_hidden + face_hidden + cvzone_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Ritmo',
    console=False,
    icon='assets/ritmo.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Ritmo')
