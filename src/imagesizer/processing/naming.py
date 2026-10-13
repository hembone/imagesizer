"""Folder/file name templates, sanitizing and collision handling."""

from __future__ import annotations

import re
import string
from enum import Enum
from pathlib import Path

FOLDER_TOKENS = ("name", "date", "index", "scale", "model")
FILE_TOKENS = FOLDER_TOKENS + ("ratio", "w", "h")

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


class TemplateError(ValueError):
    pass


class FileCollision(str, Enum):
    RENAME = "rename"
    OVERWRITE = "overwrite"
    SKIP = "skip"


class FolderCollision(str, Enum):
    REUSE = "reuse"
    RENAME = "rename"
    SKIP = "skip"


def sanitize(name: str) -> str:
    """Make ``name`` a valid file/folder name on Windows, macOS and Linux."""
    name = _ILLEGAL.sub("", name).strip().rstrip(". ")
    if not name:
        return "untitled"
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name[:200]


def validate(template: str, allowed: tuple[str, ...]) -> None:
    """Raise TemplateError if ``template`` is malformed or uses unknown tokens."""
    if not template.strip():
        raise TemplateError("Template is empty")
    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(template) if f is not None]
    except ValueError as e:
        raise TemplateError(f"Malformed template: {e}") from None
    for f in fields:
        if f not in allowed:
            raise TemplateError(f"Unknown token {{{f}}}; available: " + ", ".join(f"{{{t}}}" for t in allowed))


def render(template: str, allowed: tuple[str, ...], **tokens: object) -> str:
    validate(template, allowed)
    return sanitize(template.format(**tokens))


def _numbered(path: Path, is_dir: bool) -> Path:
    stem, suffix = (path.name, "") if is_dir else (path.stem, path.suffix)
    i = 1
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def resolve_file(path: Path, policy: FileCollision, claimed: set[Path] | None = None) -> Path | None:
    """Apply the collision policy. ``claimed`` holds paths already used in this run. None means skip."""
    claimed = claimed if claimed is not None else set()
    taken = path.exists() or path in claimed
    if not taken or policy is FileCollision.OVERWRITE:
        return path
    if policy is FileCollision.SKIP:
        return None
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not candidate.exists() and candidate not in claimed:
            return candidate
        i += 1


def resolve_folder(path: Path, policy: FolderCollision, claimed: set[Path] | None = None) -> Path | None:
    """Apply the collision policy. A folder in ``claimed`` belongs to another image of this run, so it is never
    reused or skipped: that image gets the next numbered folder instead."""
    if claimed and path in claimed:
        i = 1
        while True:
            candidate = path.with_name(f"{path.name}_{i}")
            if not candidate.exists() and candidate not in claimed:
                return candidate
            i += 1
    if not path.exists() or policy is FolderCollision.REUSE:
        return path
    if policy is FolderCollision.SKIP:
        return None
    return _numbered(path, is_dir=True)
