# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "ui"), "ui"),
    (str(ROOT / "scripts"), "scripts"),
    (str(ROOT / "assets"), "assets"),
]
hiddenimports = collect_submodules("backend") + [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CosmicOptimizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest=str(ROOT / "app.manifest"),
    uac_admin=True,
    uac_uiaccess=False,
    icon=str(ROOT / "icon.ico"),
)

