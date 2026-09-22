# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for a standalone Plotea.

    pip install pyinstaller
    pyinstaller plotea.spec

Produces dist/Plotea/ on Windows and Linux, dist/Plotea.app on macOS. Users
never need Python: the interpreter, Qt and the scientific stack are bundled.
"""
import glob
import os
import sys

import PyQt6
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.getcwd())
ICON_DIR = os.path.join(ROOT, "plotea", "resources")


def icon_for_platform():
    if sys.platform.startswith("win"):
        candidate = os.path.join(ICON_DIR, "plotea.ico")
    elif sys.platform == "darwin":
        candidate = os.path.join(ICON_DIR, "plotea.icns")
    else:
        candidate = os.path.join(ICON_DIR, "plotea.png")
    return candidate if os.path.exists(candidate) else None


datas = [(os.path.join("plotea", "resources"),
          os.path.join("plotea", "resources"))]
datas += collect_data_files("matplotlib", subdir="mpl-data")
# Qt's French translations: without them the standard dialog buttons fall
# back to English inside the bundle.
datas += [(path, os.path.join("PyQt6", "Qt6", "translations"))
          for path in glob.glob(os.path.join(
              os.path.dirname(PyQt6.__file__), "Qt6", "translations",
              "qt*_fr.qm"))]

# Qt modules Plotea never touches; dropping them roughly halves the bundle.
excludes = [
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtQml",
    "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth", "PyQt6.QtNetworkAuth", "PyQt6.QtPositioning",
    "PyQt6.QtSensors", "PyQt6.QtSerialPort", "PyQt6.QtTest",
    "PyQt6.QtDesigner", "PyQt6.Qt3DCore", "PyQt6.QtCharts",
    "tkinter", "PySide6", "PyQt5", "IPython", "jupyter", "notebook",
    "pytest", "sphinx", "wx",
]

hiddenimports = [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_svg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_ps",
    "openpyxl",
    "scipy.special._cdflib",
]

a = Analysis(
    ["run_plotea.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Plotea",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # PLOTEA_CONSOLE=1 keeps a terminal attached, to read a startup
    # traceback that the windowed build can only show in a dialog.
    console=bool(os.environ.get("PLOTEA_CONSOLE")),
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_for_platform(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Plotea",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Plotea.app",
        icon=icon_for_platform(),
        bundle_identifier="org.plotea.app",
        info_plist={
            "CFBundleName": "Plotea",
            "CFBundleDisplayName": "Plotea",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Projet Plotea",
                "CFBundleTypeExtensions": ["plotea"],
                "CFBundleTypeRole": "Editor",
            }],
        },
    )
