# -*- mode: python ; coding: utf-8 -*-
# Builds a single-file executable (streammark-publisher / streammark-publisher.exe):
# run it (with a .env alongside it, see .env.example) and it auto-detects the
# capture card and starts publishing. Primary target is Linux x86_64 (built by
# .github/workflows/build-publisher.yml on ubuntu-latest); also buildable on
# Windows via build_windows.ps1. Or directly:
#   pyinstaller --noconfirm streammark_publisher.spec
import sys

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# --collect-all equivalents: each of these ships a native lib (livekit's Rust
# ffi lib) or relies on dynamic imports PyInstaller's static analysis can't
# see on its own (cv2's backend plugins). comtypes/pygrabber only exist on
# Windows (DirectShow device enumeration) -- see pyproject.toml's
# sys_platform == 'win32' marker on the pygrabber dependency.
packages = ["livekit", "cv2"]
if sys.platform == "win32":
    packages += ["comtypes", "pygrabber"]

for pkg in packages:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["run_publisher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="streammark-publisher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
