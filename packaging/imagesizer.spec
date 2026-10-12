# PyInstaller spec: `pyinstaller packaging/imagesizer.spec` builds dist/ImageSizer for the current OS.
# The Upscayl engine is not bundled; the app downloads it on first use.
import os
import sys
import tomllib

from PyInstaller.utils.hooks import copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
    VERSION = tomllib.load(f)["project"]["version"]

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=[(os.path.join(ROOT, "src", "imagesizer", "resources"), "imagesizer/resources")]
    + copy_metadata("imagesizer"),  # lets importlib.metadata report the version when frozen
    excludes=["tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ImageSizer",
    console=False,
    icon=os.path.join(SPECPATH, "icon.icns" if sys.platform == "darwin" else "icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="ImageSizer")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ImageSizer.app",
        icon=os.path.join(SPECPATH, "icon.icns"),
        bundle_identifier="io.github.hembone.imagesizer",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "ImageSizer",
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
        },
    )
