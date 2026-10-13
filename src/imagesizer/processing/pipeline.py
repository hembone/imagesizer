"""Per-image job: optional upscale, then fit/resize to every selected ratio and save into the image's own folder."""

from __future__ import annotations

import datetime as _dt
import io
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageCms, ImageOps

from ..config import Preset, RatioSpec
from ..engine.upscayl import Cancelled, Engine
from . import naming
from .resize import ANCHORS, FitMode, crop_box, fit_image, has_alpha, pad_layout, target_size, to_8bit

# Outputs of a 4x upscale routinely exceed Pillow's decompression-bomb limit; we produce them ourselves.
Image.MAX_IMAGE_PIXELS = None

INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
_UPSCAYL_NATIVE = {".png", ".jpg", ".jpeg", ".webp"}
FORMATS = {"png": ("PNG", ".png"), "jpg": ("JPEG", ".jpg"), "webp": ("WEBP", ".webp")}

ProgressFn = Callable[[str, float], None]


@dataclass
class ImageResult:
    source: Path
    folder: Path | None = None
    outputs: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: str | None = None


def planned_size(src_w: int, src_h: int, spec: RatioSpec, fit_mode: str, scale: int = 1) -> tuple[int, int]:
    """Output dimensions for one ratio without touching pixels (for name previews)."""
    w, h = src_w * scale, src_h * scale
    size = spec.size()
    ratio = size.effective_ratio(spec.parsed())
    if fit_mode == FitMode.PAD.value:
        fw, fh, _, _ = pad_layout(w, h, ratio)
    else:
        left, top, right, bottom = crop_box(w, h, ratio)
        fw, fh = right - left, bottom - top
    return target_size(fw, fh, ratio, size)


def collect_inputs(paths: Iterable[str | Path], recursive: bool = True) -> list[Path]:
    """Expand files and folders into a sorted, de-duplicated list of supported images."""
    found: dict[Path, None] = {}
    for p in map(Path, paths):
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for f in sorted(it):
                if f.is_file() and f.suffix.lower() in INPUT_EXTENSIONS:
                    found[f.resolve()] = None
        elif p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS:
            found[p.resolve()] = None
    return list(found)


class Pipeline:
    def __init__(self, preset: Preset, engine: Engine | None = None, cancel: threading.Event | None = None):
        self.preset = preset
        self.engine = engine
        self.cancel = cancel or threading.Event()
        self.date = _dt.date.today().isoformat()
        self._used_folders: set[Path] = set()  # folders already given to an image in this run

    # --- validation -------------------------------------------------------

    def validate(self) -> list[str]:
        p = self.preset
        errors = []
        enabled = [r for r in p.ratios if r.enabled]
        if not enabled:
            errors.append("Select at least one aspect ratio.")
        for r in enabled:
            try:
                r.parsed()
                r.size()
            except ValueError as e:
                errors.append(str(e))
            if (r.size_mode == "long_edge" and r.long_edge < 1) or (r.size_mode == "exact" and min(r.width, r.height) < 1):
                errors.append(f"{r.ratio}: output size must be positive.")
        for tpl, tokens in ((p.output.folder_template, naming.FOLDER_TOKENS), (p.output.file_template, naming.FILE_TOKENS)):
            try:
                naming.validate(tpl, tokens)
            except naming.TemplateError as e:
                errors.append(f"Template {tpl!r}: {e}")
        if not p.output.directory:
            errors.append("Choose an output folder.")
        if p.output.format not in FORMATS:
            errors.append(f"Unknown output format {p.output.format!r}.")
        if p.fit.anchor not in ANCHORS:
            errors.append(f"Unknown anchor {p.fit.anchor!r}.")
        if p.upscale.enabled:
            if self.engine is None or not self.engine.has_binary:
                errors.append("Upscayl engine is not installed. Download it, or turn off upscaling.")
            elif p.upscale.model not in self.engine.installed_models():
                errors.append(f"Upscale model {p.upscale.model!r} is not installed.")
        return errors

    # --- processing -------------------------------------------------------

    def _tokens(self, src: Path, index: int) -> dict:
        up = self.preset.upscale
        return {
            "name": src.stem,
            "date": self.date,
            "index": index,
            "scale": up.scale if up.enabled else 1,
            "model": up.model if up.enabled else "none",
        }

    def preview_names(self, src: Path, index: int = 1, sizes: dict[int, tuple[int, int]] | None = None) -> tuple[str, list[str]]:
        """Folder name and file names this preset would produce for ``src`` (no I/O). Raises TemplateError.

        ``sizes`` maps an index into ``preset.ratios`` to that row's output size."""
        out = self.preset.output
        tokens = self._tokens(src, index)
        folder = naming.render(out.folder_template, naming.FOLDER_TOKENS, **tokens)
        ext = FORMATS.get(out.format, ("", ".png"))[1]
        files = []
        for i, r in enumerate(self.preset.ratios):
            if not r.enabled:
                continue
            try:
                ratio = r.size().effective_ratio(r.parsed())
            except ValueError:
                continue
            w, h = (sizes or {}).get(i, ("W", "H"))
            files.append(naming.render(out.file_template, naming.FILE_TOKENS, **tokens, ratio=ratio.slug, w=w, h=h) + ext)
        return folder, files

    def process(self, src: Path, index: int = 1, progress: ProgressFn | None = None) -> ImageResult:
        progress = progress or (lambda m, f: None)
        result = ImageResult(src)
        p = self.preset
        out_dir = Path(p.output.directory)
        tokens = self._tokens(src, index)
        created_folder = False
        try:
            folder_name = naming.render(p.output.folder_template, naming.FOLDER_TOKENS, **tokens)
            folder = naming.resolve_folder(out_dir / folder_name, naming.FolderCollision(p.output.folder_collision),
                                           self._used_folders)
            if folder is None:
                result.skipped.append(f"folder {folder_name!r} already exists")
                return result
            self._used_folders.add(folder)
            result.folder = folder

            progress("Loading", 0.0)
            with Image.open(src) as im:
                im.load()
                icc = im.info.get("icc_profile")
                exif = im.getexif()
                orientation = exif.get(0x0112, 1)
                base = to_8bit(ImageOps.exif_transpose(im))
            if base.mode == "CMYK":
                base, icc = _cmyk_to_rgb(base, icc), None
            if 0x0112 in exif:
                exif[0x0112] = 1
            meta = {"icc": icc, "exif": exif} if p.output.keep_metadata else {}

            ratios = [r for r in p.ratios if r.enabled]
            up_share = 0.7 if p.upscale.enabled else 0.0

            with tempfile.TemporaryDirectory(prefix="imagesizer-") as tmp:
                work = base
                if p.upscale.enabled:
                    work = self._upscale(src, base, orientation, Path(tmp),
                                         lambda f: progress("Upscaling", f * up_share))
                self._check_cancel()

                if not folder.exists():
                    folder.mkdir(parents=True)
                    created_folder = True
                claimed: set[Path] = set()
                fmt, ext = FORMATS[p.output.format]
                file_policy = naming.FileCollision(p.output.file_collision)

                if p.upscale.enabled and p.output.keep_upscaled:
                    self._write(work, folder, {**tokens, "ratio": "upscaled", "w": work.width, "h": work.height},
                                fmt, ext, file_policy, claimed, meta, result)

                for i, spec in enumerate(ratios):
                    self._check_cancel()
                    ratio = spec.size().effective_ratio(spec.parsed())
                    progress(f"Resizing {ratio.label}", up_share + (1 - up_share) * i / len(ratios))
                    fitted = fit_image(work, spec.parsed(), FitMode(p.fit.mode), p.fit.anchor,
                                       spec.size(), p.fit.pad_rgba())
                    self._write(fitted, folder, {**tokens, "ratio": ratio.slug, "w": fitted.width, "h": fitted.height},
                                fmt, ext, file_policy, claimed, meta, result)
            progress("Done", 1.0)
        except Cancelled:
            result.error = "Cancelled"
        except Exception as e:  # report per-image failures and keep the batch going
            result.error = f"{type(e).__name__}: {e}"
        if result.error and created_folder and result.folder and not any(result.folder.iterdir()):
            result.folder.rmdir()
        return result

    def _check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()

    def _upscale(self, src: Path, base: Image.Image, orientation: int, tmp: Path,
                 progress: Callable[[float], None]) -> Image.Image:
        assert self.engine is not None
        up = self.preset.upscale
        # upscayl-bin ignores EXIF orientation and only reads png/jpg/webp, so hand it an upright PNG when needed.
        needs_copy = (orientation not in (None, 1) or src.suffix.lower() not in _UPSCAYL_NATIVE
                      or base.mode not in ("RGB", "RGBA", "L"))
        if needs_copy:
            src_for_engine = tmp / "input.png"
            normalized = base if base.mode in ("RGB", "RGBA") else base.convert(
                "RGBA" if "A" in base.getbands() or "transparency" in base.info else "RGB")
            normalized.save(src_for_engine, "PNG")
        else:
            src_for_engine = src
        dst = tmp / "upscaled.png"
        self.engine.upscale(src_for_engine, dst, up.model, up.scale, up.gpu_id, up.tile_size,
                            progress=progress, cancel=self.cancel)
        with Image.open(dst) as im:
            im.load()
            return im.copy()

    def _write(self, img: Image.Image, folder: Path, tokens: dict, fmt: str, ext: str,
               policy: naming.FileCollision, claimed: set[Path], meta: dict, result: ImageResult) -> None:
        name = naming.render(self.preset.output.file_template, naming.FILE_TOKENS, **tokens)
        path = naming.resolve_file(folder / (name + ext), policy, claimed)
        if path is None:
            result.skipped.append(f"{name + ext} already exists")
            return
        claimed.add(path)
        save_image(img, path, fmt, self.preset.output.quality, self.preset.fit.fill_rgba(), **meta)
        result.outputs.append(path)


def _cmyk_to_rgb(img: Image.Image, icc: bytes | None) -> Image.Image:
    """Color-manage CMYK through its embedded profile to sRGB; a naive convert gives washed-out colors."""
    if icc:
        try:
            return ImageCms.profileToProfile(img, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                             ImageCms.createProfile("sRGB"), outputMode="RGB")
        except (ImageCms.PyCMSError, OSError):
            pass
    return img.convert("RGB")


def _icc_matches(icc: bytes, mode: str) -> bool:
    """Whether an ICC profile's color space fits the image mode (GRAY for L/LA, RGB otherwise)."""
    try:
        space = ImageCms.ImageCmsProfile(io.BytesIO(icc)).profile.xcolor_space.strip()
    except (ImageCms.PyCMSError, OSError, AttributeError):
        return False
    return space == ("GRAY" if mode in ("L", "LA") else "RGB")


def save_image(img: Image.Image, path: Path, fmt: str, quality: int = 92,
               background: tuple[int, ...] = (255, 255, 255, 255), icc: bytes | None = None,
               exif: Image.Exif | None = None) -> None:
    """Convert to a mode the format supports and write atomically (temp file + rename)."""
    alpha = has_alpha(img)
    if fmt == "JPEG":
        if alpha:
            bg = Image.new("RGB", img.size, background[:3])
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
            img = bg
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L", "LA") or (fmt == "WEBP" and img.mode in ("L", "LA")):
        img = img.convert("RGBA" if alpha else "RGB")

    kwargs: dict = {}
    if fmt in ("JPEG", "WEBP"):
        kwargs["quality"] = quality
    if fmt == "JPEG":
        kwargs["subsampling"] = 0 if quality >= 90 else 2
        kwargs["optimize"] = True
    if fmt == "PNG":
        kwargs["compress_level"] = 6
    if icc and _icc_matches(icc, img.mode):
        kwargs["icc_profile"] = icc
    if exif is not None and len(exif):
        kwargs["exif"] = exif.tobytes()

    part = path.with_name(path.name + ".part")
    try:
        img.save(part, fmt, **kwargs)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)

