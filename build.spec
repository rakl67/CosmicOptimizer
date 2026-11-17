# -*- mode: python ; coding: utf-8 -*-
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
OUT = Path(DISTPATH) / "CosmicOptimizer"

datas = [(str(ROOT / "ui"), "ui")]
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
    [],
    exclude_binaries=True,
    name="CosmicOptimizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CosmicOptimizer",
)

shutil.copytree(ROOT / "scripts", OUT / "scripts", dirs_exist_ok=True)
shutil.copy2(ROOT / "README.md", OUT / "README.md")

