# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import json
from pathlib import Path
import sys

profile = os.environ.get('RITMO_BUILD_PROFILE', 'preview')
if profile not in ('preview', 'full'):
    raise ValueError('RITMO_BUILD_PROFILE must be preview or full')

web_data, web_bins, web_hidden = collect_all('webview')
face_data, face_bins, face_hidden = collect_all('mediapipe') if profile == 'full' else ([], [], [])
boolean_data = [('tutor/boolean_sources.json', 'tutor')]
runtime_data = [('local_ai/runtime-integrity.json', 'local_ai')]
cvzone_data, cvzone_bins, cvzone_hidden = collect_all('cvzone') if profile == 'full' else ([], [], [])
profile_data = [(f'build_profiles/{profile}/capabilities.json', 'config')]
preview_excludes = [
    'cv2', 'mediapipe', 'cvzone', 'pygrabber', 'comtypes',
    'jax', 'jaxlib', 'numpy', 'scipy', 'matplotlib', 'google.protobuf',
    'PIL', 'Pythonwin', 'win32ui',
]

a = Analysis(
    ['desktop.py'],
    pathex=['.'],
    binaries=web_bins + face_bins + cvzone_bins,
    datas=web_data + face_data + cvzone_data + boolean_data + runtime_data + profile_data + [('web', 'web'), ('tutor/guide.md', 'tutor'), ('local_ai/models.json', 'local_ai'), ('local_ai/knowledge.json', 'local_ai'), ('config/config.json', 'config'), ('config/classificacao_apps.json', 'config'), ('assets/ritmo.ico', 'assets')],
    hiddenimports=web_hidden + face_hidden + cvzone_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=preview_excludes if profile == 'preview' else [],
    noarchive=False,
)
if profile == 'preview':
    # CPython 3.14 targets Windows 10+. Do not redistribute the runner's OS
    # API-set/UCRT DLLs. Record all omissions without asserting unknown origins.
    sys.path.insert(0, os.path.join(SPECPATH, 'scripts'))
    from preview_system_dlls import separate_os_prerequisites
    a.binaries, os_prerequisites = separate_os_prerequisites(a.binaries, os.environ['WINDIR'])
    report = Path(os.environ.get('RITMO_BUILD_ROOT', Path(SPECPATH) / 'build')) / 'preview-os-prerequisites.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'minimum_platform':'Updated Windows 10/11 x64 with WebView2',
                                  'not_redistributed':os_prerequisites}, indent=2), encoding='utf8')
    a.datas.append(('release/os-prerequisites.json', str(report), 'DATA'))
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
