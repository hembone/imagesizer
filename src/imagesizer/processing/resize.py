"""Fitting an image to an aspect ratio (crop or pad) and resizing to a target size."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PIL import Image

from .ratios import Ratio

ANCHORS: dict[str, tuple[float, float]] = {
    "top-left": (0.0, 0.0),
    "top": (0.5, 0.0),
    "top-right": (1.0, 0.0),
    "left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "right": (1.0, 0.5),
    "bottom-left": (0.0, 1.0),
    "bottom": (0.5, 1.0),
    "bottom-right": (1.0, 1.0),
}


class FitMode(str, Enum):
    CROP = "crop"
    PAD = "pad"


class SizeMode(str, Enum):
    MAX = "max"  # keep full resolution, only crop/pad
    LONG_EDGE = "long_edge"
    EXACT = "exact"


@dataclass(frozen=True)
class SizeSpec:
    mode: SizeMode = SizeMode.MAX
    long_edge: int = 2048
    width: int = 1080
    height: int = 1080

    def effective_ratio(self, ratio: Ratio) -> Ratio:
        """An exact WxH target defines its own ratio; otherwise use the given one."""
        if self.mode is SizeMode.EXACT:
            return Ratio.from_size(self.width, self.height)
        return ratio


def _anchor(name: str) -> tuple[float, float]:
    try:
        return ANCHORS[name]
    except KeyError:
        raise ValueError(f"Unknown anchor {name!r}") from None


def crop_box(img_w: int, img_h: int, ratio: Ratio, anchor: str = "center") -> tuple[int, int, int, int]:
    """Largest box with ``ratio`` inside the image, placed by ``anchor``. Returns (left, top, right, bottom)."""
    ax, ay = _anchor(anchor)
    if img_w / img_h > ratio.value:  # image too wide: trim width
        h = img_h
        w = max(1, min(img_w, round(img_h * ratio.value)))
    else:  # image too tall: trim height
        w = img_w
        h = max(1, min(img_h, round(img_w / ratio.value)))
    left = round((img_w - w) * ax)
    top = round((img_h - h) * ay)
    return left, top, left + w, top + h


def pad_layout(img_w: int, img_h: int, ratio: Ratio, anchor: str = "center") -> tuple[int, int, int, int]:
    """Smallest canvas with ``ratio`` that contains the image. Returns (canvas_w, canvas_h, offset_x, offset_y)."""
    ax, ay = _anchor(anchor)
    if img_w / img_h > ratio.value:  # image too wide: grow height
        cw = img_w
        ch = max(img_h, round(img_w / ratio.value))
    else:
        ch = img_h
        cw = max(img_w, round(img_h * ratio.value))
    return cw, ch, round((cw - img_w) * ax), round((ch - img_h) * ay)


def target_size(w: int, h: int, ratio: Ratio, size: SizeSpec) -> tuple[int, int]:
    """Final output dimensions for a fitted image of size ``w``x``h``."""
    if size.mode is SizeMode.EXACT:
        return size.width, size.height
    if size.mode is SizeMode.LONG_EDGE:
        edge = size.long_edge
        if ratio.value >= 1:
            return edge, max(1, round(edge / ratio.value))
        return max(1, round(edge * ratio.value)), edge
    return w, h


def has_alpha(img: Image.Image) -> bool:
    """True for alpha modes and for palette/L/RGB images with a transparent color key."""
    return img.mode in ("RGBA", "LA", "PA") or (img.mode in ("P", "L", "RGB") and "transparency" in img.info)


def to_8bit(img: Image.Image) -> Image.Image:
    """Bring 16/32-bit grayscale down to 8-bit L; Pillow's own conversion just clips everything above 255."""
    if img.mode.startswith("I;16"):
        return img.convert("I").point(lambda v: v / 256).convert("L")
    if img.mode in ("I", "F"):
        lo, hi = img.getextrema()
        if hi <= lo:
            return Image.new("L", img.size, 0 if hi <= 0 else 255)
        f = img.convert("F")
        return f.point(lambda v: (v - lo) * 255 / (hi - lo)).convert("L")
    return img


def fit_image(
    img: Image.Image,
    ratio: Ratio,
    fit: FitMode = FitMode.CROP,
    anchor: str = "center",
    size: SizeSpec = SizeSpec(),
    pad_color: tuple[int, ...] = (255, 255, 255, 255),
) -> Image.Image:
    """Crop or pad ``img`` to ``ratio`` (or the exact size's ratio), then resize per ``size``."""
    ratio = size.effective_ratio(ratio)
    if fit is FitMode.CROP:
        fitted = img.crop(crop_box(img.width, img.height, ratio, anchor))
    else:
        cw, ch, ox, oy = pad_layout(img.width, img.height, ratio, anchor)
        alpha = has_alpha(img)
        mode = "RGBA" if (img.mode in ("RGBA", "LA", "PA") or len(pad_color) == 4 and pad_color[3] < 255) else "RGB"
        color = pad_color if mode == "RGBA" else pad_color[:3]
        fitted = Image.new(mode, (cw, ch), color)
        if mode == "RGBA":  # composite, so semi-transparent pixels keep their alpha over a transparent canvas
            fitted.alpha_composite(img if img.mode == "RGBA" else img.convert("RGBA"), (ox, oy))
        elif alpha:  # paste through the alpha so transparent pixels take the pad color, not their palette color
            src = img.convert("RGBA")
            fitted.paste(src.convert("RGB"), (ox, oy), src.getchannel("A"))
        else:
            fitted.paste(img.convert(mode) if img.mode != mode else img, (ox, oy))
    out_size = target_size(fitted.width, fitted.height, ratio, size)
    if out_size != fitted.size:
        fitted = fitted.resize(out_size, Image.Resampling.LANCZOS)
    return fitted
