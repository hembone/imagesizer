"""Per-OS details for the upscayl-bin engine."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def os_key() -> str:
    """The OS suffix used in upscayl-ncnn release asset names."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def exe_name() -> str:
    return "upscayl-bin.exe" if os_key() == "windows" else "upscayl-bin"


def make_executable(path: Path) -> None:
    """zipfile drops permission bits; restore +x and clear the macOS quarantine flag."""
    if os_key() == "windows":
        return
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if os_key() == "macos":
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(path)], capture_output=True, check=False)


def subprocess_flags() -> dict:
    """Keep a console window from flashing up for each upscale on Windows."""
    if os_key() == "windows":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def open_in_file_manager(path: Path) -> None:
    if os_key() == "windows":
        os.startfile(path)  # type: ignore[attr-defined]
    elif os_key() == "macos":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
