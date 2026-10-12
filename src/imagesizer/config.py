"""Settings and presets, persisted as JSON in the user config dir."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from platformdirs import user_config_dir, user_pictures_dir

from .engine.upscayl import DEFAULT_MODEL
from .processing.ratios import Ratio
from .processing.resize import SizeMode, SizeSpec


@dataclass
class RatioSpec:
    ratio: str = "1:1"
    enabled: bool = True
    size_mode: str = SizeMode.MAX.value
    long_edge: int = 2048
    width: int = 1080
    height: int = 1080

    def parsed(self) -> Ratio:
        return Ratio.parse(self.ratio)

    def size(self) -> SizeSpec:
        return SizeSpec(SizeMode(self.size_mode), self.long_edge, self.width, self.height)


@dataclass
class UpscaleSettings:
    enabled: bool = True
    model: str = DEFAULT_MODEL
    scale: int = 4
    gpu_id: str = "auto"
    tile_size: int = 0


@dataclass
class FitSettings:
    mode: str = "crop"  # crop | pad
    anchor: str = "center"
    pad_color: str = "#ffffff"
    pad_transparent: bool = False

    def pad_rgba(self) -> tuple[int, int, int, int]:
        if self.pad_transparent:
            return (0, 0, 0, 0)
        c = self.pad_color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255


@dataclass
class OutputSettings:
    directory: str = ""
    format: str = "png"  # png | jpg | webp
    quality: int = 92
    folder_template: str = "{name}"
    file_template: str = "{name}_{ratio}_{w}x{h}"
    folder_collision: str = "reuse"
    file_collision: str = "rename"
    keep_upscaled: bool = False
    keep_metadata: bool = True


def _default_ratios() -> list[RatioSpec]:
    return [RatioSpec("1:1"), RatioSpec("4:5"), RatioSpec("16:9")]


@dataclass
class Preset:
    ratios: list[RatioSpec] = field(default_factory=_default_ratios)
    upscale: UpscaleSettings = field(default_factory=UpscaleSettings)
    fit: FitSettings = field(default_factory=FitSettings)
    output: OutputSettings = field(default_factory=OutputSettings)


@dataclass
class Settings:
    current: Preset = field(default_factory=Preset)
    presets: dict[str, Preset] = field(default_factory=dict)
    engine_binary: str = ""  # override; empty = default download location
    engine_models_dir: str = ""

    def __post_init__(self):
        if not self.current.output.directory:
            self.current.output.directory = str(Path(user_pictures_dir()) / "ImageSizer")


def _from_dict(cls, data: Any):
    """Build a dataclass from JSON data, ignoring unknown keys and keeping defaults for missing ones."""
    if not isinstance(data, dict):
        return cls()
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        kwargs[f.name] = _convert(hints[f.name], data[f.name])
    return cls(**kwargs)


def _convert(tp, value):
    origin = get_origin(tp)
    if is_dataclass(tp):
        return _from_dict(tp, value)
    if origin is list:
        (item,) = get_args(tp)
        return [_convert(item, v) for v in value]
    if origin is dict:
        _, item = get_args(tp)
        return {k: _convert(item, v) for k, v in value.items()}
    return value


def config_path() -> Path:
    return Path(user_config_dir("imagesizer", appauthor=False)) / "settings.json"


def load(path: Path | None = None) -> Settings:
    path = path or config_path()
    try:
        return _from_dict(Settings, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    tmp.replace(path)


def preset_to_json(preset: Preset) -> str:
    return json.dumps(asdict(preset), indent=2)


def preset_from_json(text: str) -> Preset:
    return _from_dict(Preset, json.loads(text))
