"""Locate, download and run the upscayl-bin (Real-ESRGAN ncnn-vulkan) engine."""

from __future__ import annotations

import json
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from platformdirs import user_data_dir

from . import platform

RELEASE_API = "https://api.github.com/repos/upscayl/upscayl-ncnn/releases/latest"
MODELS_URL = "https://raw.githubusercontent.com/upscayl/upscayl/main/resources/models/{name}.{ext}"

# Models shipped with Upscayl. All are 4x models; upscayl-bin can still output 2x or 3x.
MODELS: dict[str, str] = {
    "upscayl-standard-4x": "Upscayl Standard",
    "upscayl-lite-4x": "Upscayl Lite (fast)",
    "high-fidelity-4x": "High Fidelity",
    "digital-art-4x": "Digital Art",
    "remacri-4x": "Remacri (non-commercial)",
    "ultramix-balanced-4x": "Ultramix Balanced (non-commercial)",
    "ultrasharp-4x": "Ultrasharp (non-commercial)",
}
DEFAULT_MODEL = "upscayl-standard-4x"
MODEL_SCALE = 4

ProgressFn = Callable[[str, float], None]  # (message, fraction 0..1)

_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)%")


class EngineError(RuntimeError):
    pass


class Cancelled(Exception):
    pass


def default_engine_dir() -> Path:
    return Path(user_data_dir("imagesizer", appauthor=False)) / "engine"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _urlopen(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "imagesizer"})
    return urllib.request.urlopen(req, context=_ssl_context(), timeout=60)


def _download(url: str, dest: Path, on_bytes: Callable[[int, int], None] | None = None,
              cancel: threading.Event | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with _urlopen(url) as resp, open(part, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 16):
            if cancel is not None and cancel.is_set():
                f.close()
                part.unlink(missing_ok=True)
                raise Cancelled()
            f.write(chunk)
            done += len(chunk)
            if on_bytes:
                on_bytes(done, total)
    part.replace(dest)


@dataclass
class Engine:
    binary: Path
    models_dir: Path

    @classmethod
    def locate(cls, binary: str | Path | None = None, models_dir: str | Path | None = None) -> "Engine":
        """Engine from explicit paths (settings overrides) or the default download location."""
        base = default_engine_dir()
        return cls(Path(binary) if binary else base / platform.exe_name(),
                   Path(models_dir) if models_dir else base / "models")

    @property
    def has_binary(self) -> bool:
        return self.binary.is_file()

    def installed_models(self) -> list[str]:
        if not self.models_dir.is_dir():
            return []
        return sorted(p.stem for p in self.models_dir.glob("*.param") if p.with_suffix(".bin").is_file())

    @property
    def ready(self) -> bool:
        return self.has_binary and bool(self.installed_models())

    # --- installation -----------------------------------------------------

    def download(self, models: list[str] | None = None, progress: ProgressFn | None = None,
                 cancel: threading.Event | None = None) -> None:
        """Fetch the latest upscayl-bin for this OS plus the given models (default: all)."""
        progress = progress or (lambda m, f: None)
        models = list(MODELS) if models is None else models
        steps = 1 + 2 * len(models)

        def reporter(step: int, label: str):
            return lambda done, total: progress(label, (step + (done / total if total else 0)) / steps)

        if not self.has_binary:
            progress("Looking up latest engine release…", 0)
            with _urlopen(RELEASE_API) as resp:
                release = json.load(resp)
            suffix = f"-{platform.os_key()}.zip"
            asset = next((a for a in release.get("assets", []) if a["name"].endswith(suffix)), None)
            if asset is None:
                raise EngineError(f"No upscayl-bin release asset for {platform.os_key()}")
            with tempfile.TemporaryDirectory() as tmp:
                zpath = Path(tmp) / asset["name"]
                _download(asset["browser_download_url"], zpath, reporter(0, f"Downloading {asset['name']}"), cancel)
                with zipfile.ZipFile(zpath) as z:
                    member = next((n for n in z.namelist() if Path(n).name == platform.exe_name()), None)
                    if member is None:
                        raise EngineError(f"{platform.exe_name()} not found in {asset['name']}")
                    self.binary.parent.mkdir(parents=True, exist_ok=True)
                    # extract beside the target and rename at the end, so a half-written binary never looks installed
                    part = self.binary.with_name(self.binary.name + ".part")
                    try:
                        with z.open(member) as src, open(part, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        platform.make_executable(part)
                        part.replace(self.binary)
                    finally:
                        part.unlink(missing_ok=True)

        for i, name in enumerate(models):
            for j, ext in enumerate(("param", "bin")):
                dest = self.models_dir / f"{name}.{ext}"
                if not dest.is_file():
                    _download(MODELS_URL.format(name=name, ext=ext), dest,
                              reporter(1 + 2 * i + j, f"Downloading model {MODELS.get(name, name)}"), cancel)
        progress("Engine ready", 1.0)

    # --- running ----------------------------------------------------------

    def command(self, src: Path, dst: Path, model: str, scale: int = 4,
                gpu_id: str = "auto", tile_size: int = 0) -> list[str]:
        cmd = [str(self.binary), "-i", str(src), "-o", str(dst),
               "-m", str(self.models_dir), "-n", model,
               "-z", str(MODEL_SCALE), "-s", str(scale), "-f", "png"]
        if gpu_id and gpu_id != "auto":
            cmd += ["-g", str(gpu_id)]
        if tile_size:
            cmd += ["-t", str(tile_size)]
        return cmd

    def upscale(self, src: Path, dst: Path, model: str, scale: int = 4, gpu_id: str = "auto",
                tile_size: int = 0, progress: Callable[[float], None] | None = None,
                cancel: threading.Event | None = None) -> None:
        if not self.has_binary:
            raise EngineError("Upscayl engine is not installed")
        if model not in self.installed_models():
            raise EngineError(f"Model {model!r} is not installed in {self.models_dir}")
        proc = subprocess.Popen(
            self.command(src, dst, model, scale, gpu_id, tile_size),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", **platform.subprocess_flags(),
        )
        stop_watch = threading.Event()
        if cancel is not None:
            def watch():
                while not stop_watch.wait(0.2):
                    if cancel.is_set():
                        proc.terminate()
                        return
            threading.Thread(target=watch, daemon=True).start()
        log: list[str] = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                m = _PERCENT_RE.search(line)
                if m and progress:
                    progress(min(1.0, float(m.group(1).replace(",", ".")) / 100))
                elif not m:
                    log.append(line)
            code = proc.wait()
        finally:
            stop_watch.set()
        if cancel is not None and cancel.is_set():
            dst.unlink(missing_ok=True)
            raise Cancelled()
        if code != 0 or not dst.is_file():
            hint = ""
            text = "\n".join(log[-15:])
            if "vulkan" in text.lower() or "gpu" in text.lower():
                hint = "\nNo usable Vulkan GPU was found. Update GPU drivers, or disable upscaling to resize only."
            raise EngineError(f"upscayl-bin failed (exit {code}):\n{text}{hint}")
