"""Aspect ratio parsing and presets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import gcd

PRESETS = ["1:1", "4:5", "5:4", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9"]

_RATIO_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[:x/]\s*(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Ratio:
    w: float
    h: float

    @classmethod
    def parse(cls, text: str) -> "Ratio":
        m = _RATIO_RE.match(text)
        if not m:
            raise ValueError(f"Invalid aspect ratio: {text!r} (expected e.g. 16:9)")
        w, h = float(m.group(1)), float(m.group(2))
        if w <= 0 or h <= 0:
            raise ValueError(f"Aspect ratio parts must be positive: {text!r}")
        return cls(w, h)

    @classmethod
    def from_size(cls, width: int, height: int) -> "Ratio":
        g = gcd(width, height) or 1
        return cls(width // g, height // g)

    @property
    def value(self) -> float:
        return self.w / self.h

    @property
    def label(self) -> str:
        return f"{_fmt(self.w)}:{_fmt(self.h)}"

    @property
    def slug(self) -> str:
        """Filename-safe form, e.g. ``16x9``."""
        return f"{_fmt(self.w)}x{_fmt(self.h)}".replace(".", "_")


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else f"{n:g}"
