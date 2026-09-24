# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import os

root = Path(os.getcwd()).resolve()
logo = root / "assets" / "subaja-logo.png"

datas = [
    (str(root / "assets" / "models" / "segmentation" / "model.int8.onnx"), "assets/models/segmentation"),
    (str(root / "assets" / "models" / "nemo_en_titanet_small.onnx"), "assets/models"),
    (str(logo), "assets"),
]
binaries = []
hiddenimports = []

for package in ("sherpa_onnx", "imageio_ffmpeg", "google.genai"):
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

# ONEDIR portable build:
# SubAja.exe stays at the folder root, while runtime/DLL/resources live in _internal.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubAja",
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
    icon=str(logo),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SubAja",
)
