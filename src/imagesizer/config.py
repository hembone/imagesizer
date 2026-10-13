"""Settings and presets, persisted as JSON in the user config dir."""

from __future__ import annotations

import json
import shutil
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
        return (0, 0, 0, 0) if self.pad_transparent else self.fill_rgba()

    def fill_rgba(self) -> tuple[int, int, int, int]:
        """The pad color, opaque even when padding is transparent: the fill for formats without alpha (JPEG)."""
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
    engine_prompt_dismissed: bool = False  # user chose "Later" on the first-run download offer

    def __post_init__(self):
        if not self.current.output.directory:
            self.current.output.directory = str(Path(user_pictures_dir()) / "ImageSizer")


_SCALARS = (bool, int, float, str)


def _from_dict(cls, data: Any, problems: list[str] | None = None, where: str = ""):
    """Build a dataclass from JSON data, ignoring unknown keys and keeping defaults for missing ones.

    A field whose value can't be used keeps its default, and a bad list item or dict entry is dropped, so one
    broken value doesn't cost the rest of the settings. Each such repair is noted in ``problems``.
    """
    problems = problems if problems is not None else []
    if not isinstance(data, dict):
        problems.append(f"{where or cls.__name__}: expected an object")
        return cls()
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        try:
            kwargs[f.name] = _convert(hints[f.name], data[f.name], problems, f"{where}.{f.name}".lstrip("."))
        except (TypeError, ValueError, AttributeError) as e:
            problems.append(f"{where}.{f.name}".lstrip(".") + f": {e}")
    return cls(**kwargs)


def _convert(tp, value, problems: list[str], where: str):
    origin = get_origin(tp)
    if is_dataclass(tp):
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        return _from_dict(tp, value, problems, where)
    if origin is list:
        if not isinstance(value, list):
            raise TypeError("expected a list")
        (item,) = get_args(tp)
        return [v for v in (_convert_item(item, v, problems, f"{where}[{i}]") for i, v in enumerate(value))
                if v is not _DROP]
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        _, item = get_args(tp)
        converted = {k: _convert_item(item, v, problems, f"{where}[{k!r}]") for k, v in value.items()}
        return {k: v for k, v in converted.items() if v is not _DROP}
    if tp in _SCALARS and not _scalar_ok(tp, value):
        raise TypeError(f"expected {tp.__name__}, got {type(value).__name__}")
    return value


def _scalar_ok(tp, value) -> bool:
    if isinstance(value, bool):  # bool is an int subclass; only accept it where a bool is expected
        return tp is bool
    if tp is float:
        return isinstance(value, (int, float))
    return isinstance(value, tp)


_DROP = object()


def _convert_item(tp, value, problems: list[str], where: str):
    try:
        return _convert(tp, value, problems, where)
    except (TypeError, ValueError, AttributeError) as e:
        problems.append(f"{where}: {e}")
        return _DROP


def config_path() -> Path:
    return Path(user_config_dir("imagesizer", appauthor=False)) / "settings.json"


def load(path: Path | None = None) -> Settings:
    """Read settings. A broken file is copied to ``settings.json.bad`` first, since the next save replaces it."""
    path = path or config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Settings()
    problems: list[str] = []
    try:
        settings = _from_dict(Settings, json.loads(text), problems)
    except (ValueError, TypeError, AttributeError) as e:
        problems.append(str(e))
        settings = Settings()
    if problems:
        try:
            shutil.copyfile(path, path.with_name(path.name + ".bad"))
        except OSError:
            pass
    return settings


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
