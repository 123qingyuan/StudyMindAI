# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / 'frontend' / 'dist'), 'frontend/dist'),
    (str(ROOT / 'data' / 'question_bank_manifest.json'), 'data'),
    (str(ROOT / 'data' / 'builtin' / 'legacy-expansion-v1'), 'data/builtin/legacy-expansion-v1'),
    (str(ROOT / 'scripts' / 'seed_computer_library.py'), 'scripts'),
    (str(ROOT / 'scripts' / 'seed_multidisciplinary_library.py'), 'scripts'),
]
binaries = []
hiddenimports = collect_submodules('app') + [
    'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
    'sqlalchemy.dialects.sqlite', 'sqlalchemy.dialects.mysql.pymysql',
    'pydantic.deprecated.decorator', 'zoneinfo', 'tzdata',
]

for package in ('rapidocr_onnxruntime', 'onnxruntime', 'pymupdf', 'PIL', 'sklearn', 'scipy', 'numpy', 'cryptography', 'argon2'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(ROOT / 'scripts' / 'desktop_main.py')],
    pathex=[str(ROOT / 'backend'), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['playwright', 'pytest', 'pyarrow', 'fastembed', 'qdrant_client'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StudyMindAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)