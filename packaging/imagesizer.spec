# PyInstaller spec: `pyinstaller packaging/imagesizer.spec` builds dist/ImageSizer for the current OS.
# The Upscayl engine is not bundled; the app downloads it on first use.
import os
import sys

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[os.path.join(SPECPATH, "..", "src")],
    excludes=["tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ImageSizer", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ImageSizer")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="ImageSizer.app", bundle_identifier="io.github.imagesizer")
