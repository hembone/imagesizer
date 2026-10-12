import shutil
import threading
from pathlib import Path

import pytest
from PIL import Image

from imagesizer import config
from imagesizer.cli import parse_ratio_arg
from imagesizer.config import Preset, RatioSpec
from imagesizer.engine.upscayl import Engine
from imagesizer.processing.pipeline import Pipeline, collect_inputs


class FakeEngine(Engine):
    """Stands in for upscayl-bin: a plain Lanczos resize, recording the input it was given."""

    def __init__(self, tmp: Path):
        super().__init__(tmp / "upscayl-bin", tmp / "models")
        self.binary.touch()
        self.models_dir.mkdir()
        for ext in ("param", "bin"):
            (self.models_dir / f"upscayl-standard-4x.{ext}").touch()
        self.inputs: list[Path] = []

    def upscale(self, src, dst, model, scale=4, gpu_id="auto", tile_size=0, progress=None, cancel=None):
        self.inputs.append(src)
        with Image.open(src) as im:
            assert im.format in ("PNG", "JPEG", "WEBP")
            im.resize((im.width * scale, im.height * scale)).save(dst, "PNG")


def make_preset(out: Path, **output) -> Preset:
    p = Preset(ratios=[RatioSpec("1:1"), RatioSpec("4:5", size_mode="long_edge", long_edge=500),
                       RatioSpec("16:9", size_mode="exact", width=320, height=180)])
    p.output.directory = str(out)
    for k, v in output.items():
        setattr(p.output, k, v)
    return p


def test_each_image_gets_own_folder(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    Image.new("RGB", (300, 200), "red").save(src / "beach.jpg")
    Image.new("RGBA", (100, 250), (0, 0, 255, 128)).save(src / "portrait.png")
    pipe = Pipeline(make_preset(tmp_path / "out"), FakeEngine(tmp_path))
    assert pipe.validate() == []
    for i, f in enumerate(collect_inputs([src]), 1):
        res = pipe.process(f, i)
        assert res.error is None and len(res.outputs) == 3
    beach = sorted(p.name for p in (tmp_path / "out" / "beach").iterdir())
    assert beach == ["beach_16x9_320x180.png", "beach_1x1_800x800.png", "beach_4x5_400x500.png"]
    assert (tmp_path / "out" / "portrait").is_dir()
    with Image.open(tmp_path / "out" / "portrait" / "portrait_1x1_400x400.png") as im:
        assert im.mode == "RGBA"


def test_exif_rotation_applied_before_upscale(tmp_path):
    im = Image.new("RGB", (40, 20), "red")
    exif = im.getexif()
    exif[0x0112] = 6  # rotate 90 CW on display -> upright size 20x40
    im.save(tmp_path / "rot.jpg", exif=exif)
    engine = FakeEngine(tmp_path)
    p = make_preset(tmp_path / "out", keep_upscaled=True)
    p.ratios = [RatioSpec("1:2")]
    res = Pipeline(p, engine).process(tmp_path / "rot.jpg")
    assert res.error is None, res.error
    assert engine.inputs[0].name == "input.png"  # a pre-rotated copy was sent to the engine
    names = sorted(o.name for o in res.outputs)
    assert names == ["rot_1x2_80x160.png", "rot_upscaled_80x160.png"]
    with Image.open(res.outputs[0]) as out:
        assert out.getexif().get(0x0112, 1) == 1


def test_no_upscale_jpg_output_and_templates(tmp_path):
    Image.new("RGBA", (200, 100), (255, 0, 0, 0)).save(tmp_path / "a.png")
    p = make_preset(tmp_path / "out", format="jpg", folder_template="{name}-{scale}x", file_template="{index}_{ratio}")
    p.upscale.enabled = False
    p.ratios = [RatioSpec("1:1")]
    res = Pipeline(p).process(tmp_path / "a.png", index=7)
    assert res.error is None, res.error
    assert res.outputs == [tmp_path / "out" / "a-1x" / "7_1x1.jpg"]
    with Image.open(res.outputs[0]) as im:
        assert im.mode == "RGB" and im.size == (100, 100)


def test_collisions(tmp_path):
    Image.new("RGB", (50, 50)).save(tmp_path / "a.png")
    p = make_preset(tmp_path / "out")
    p.upscale.enabled = False
    p.ratios = [RatioSpec("1:1")]
    Pipeline(p).process(tmp_path / "a.png")
    res = Pipeline(p).process(tmp_path / "a.png")  # reuse folder, rename file
    assert res.outputs[0].name == "a_1x1_50x50_1.png"
    p.output.folder_collision = "rename"
    assert Pipeline(p).process(tmp_path / "a.png").folder.name == "a_1"
    p.output.folder_collision = "skip"
    res = Pipeline(p).process(tmp_path / "a.png")
    assert res.outputs == [] and res.skipped


def test_validation_errors(tmp_path):
    p = make_preset(tmp_path)
    p.ratios = [RatioSpec("nope")]
    p.output.file_template = "{bogus}"
    errors = Pipeline(p, None).validate()
    assert any("nope" in e for e in errors)
    assert any("bogus" in e for e in errors)
    assert any("engine" in e for e in errors)


def test_cancel_removes_empty_new_folder(tmp_path):
    Image.new("RGB", (50, 50)).save(tmp_path / "a.png")
    p = make_preset(tmp_path / "out")
    cancel = threading.Event()
    cancel.set()
    res = Pipeline(p, FakeEngine(tmp_path), cancel).process(tmp_path / "a.png")
    assert res.error == "Cancelled"
    assert not (tmp_path / "out" / "a").exists()


def test_bad_input_reports_error(tmp_path):
    (tmp_path / "broken.png").write_bytes(b"not an image")
    p = make_preset(tmp_path / "out")
    p.upscale.enabled = False
    res = Pipeline(p).process(tmp_path / "broken.png")
    assert res.error and not (tmp_path / "out" / "broken").exists()


def test_settings_roundtrip(tmp_path):
    s = config.Settings()
    s.current.ratios.append(RatioSpec("21:9", enabled=False))
    s.presets["web"] = make_preset(tmp_path)
    config.save(s, tmp_path / "s.json")
    loaded = config.load(tmp_path / "s.json")
    assert loaded == s
    assert isinstance(loaded.presets["web"].ratios[0], RatioSpec)
    assert config.load(tmp_path / "missing.json").current == config.Settings().current


@pytest.mark.parametrize("arg,mode,vals", [("4:5", "max", None), ("4:5@2048", "long_edge", 2048),
                                           ("16:9=1920x1080", "exact", (1920, 1080))])
def test_cli_ratio_arg(arg, mode, vals):
    spec = parse_ratio_arg(arg)
    assert spec.size_mode == mode
    if mode == "long_edge":
        assert spec.long_edge == vals
    if mode == "exact":
        assert (spec.width, spec.height) == vals


@pytest.mark.skipif(not Engine.locate().ready and not shutil.which("upscayl-bin"), reason="engine not installed")
def test_real_engine(tmp_path):
    Image.radial_gradient("L").convert("RGB").resize((64, 48)).save(tmp_path / "g.png")
    p = make_preset(tmp_path / "out")
    p.upscale.model = Engine.locate().installed_models()[0]
    res = Pipeline(p, Engine.locate()).process(tmp_path / "g.png")
    assert res.error is None, res.error
    assert any(o.name == "g_1x1_192x192.png" for o in res.outputs)


def test_planned_size_matches_actual(tmp_path):
    from imagesizer.processing.pipeline import planned_size
    Image.new("RGB", (300, 200)).save(tmp_path / "a.png")
    for fit in ("crop", "pad"):
        p = make_preset(tmp_path / fit)
        p.fit.mode = fit
        (tmp_path / fit).mkdir()
        res = Pipeline(p, FakeEngine(tmp_path / fit)).process(tmp_path / "a.png")
        actual = sorted(Image.open(o).size for o in res.outputs)
        assert actual == sorted(planned_size(300, 200, r, fit, 4) for r in p.ratios)


def _close(a, b, tol=12):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _padded(tmp_path, fmt, pad_color=None):
    Image.new("RGB", (200, 100), (0, 0, 255)).save(tmp_path / "wide.png")
    p = make_preset(tmp_path / f"out-{fmt}", format=fmt)
    p.upscale.enabled = False
    p.ratios = [RatioSpec("1:1")]
    p.fit.mode = "pad"
    p.fit.pad_transparent = True
    if pad_color:
        p.fit.pad_color = pad_color
    res = Pipeline(p).process(tmp_path / "wide.png")
    assert res.error is None, res.error
    return Image.open(res.outputs[0])


def test_transparent_pad_jpeg_uses_default_white_not_black(tmp_path):
    with _padded(tmp_path, "jpg") as im:
        assert im.size == (200, 200)
        assert _close(im.getpixel((100, 10)), (255, 255, 255))  # bar
        assert _close(im.getpixel((100, 100)), (0, 0, 255))  # image


def test_transparent_pad_jpeg_uses_chosen_color(tmp_path):
    with _padded(tmp_path, "jpg", "#ff0000") as im:
        assert _close(im.getpixel((100, 10)), (255, 0, 0))


def test_transparent_pad_png_keeps_alpha(tmp_path):
    with _padded(tmp_path, "png", "#ff0000") as im:
        assert im.mode == "RGBA" and im.getpixel((100, 10))[3] == 0


def test_rgba_source_to_jpeg_composites_over_pad_color(tmp_path):
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(tmp_path / "clear.png")
    p = make_preset(tmp_path / "out", format="jpg")
    p.upscale.enabled = False
    p.ratios = [RatioSpec("1:1")]
    p.fit.pad_color = "#00ff00"
    res = Pipeline(p).process(tmp_path / "clear.png")
    with Image.open(res.outputs[0]) as im:
        assert _close(im.getpixel((50, 50)), (0, 255, 0))


def test_fill_rgba_is_always_opaque():
    fit = config.FitSettings(pad_color="#123456")
    assert fit.fill_rgba() == (0x12, 0x34, 0x56, 255)
    fit.pad_transparent = True
    assert fit.fill_rgba() == (0x12, 0x34, 0x56, 255)
    assert fit.pad_rgba() == (0, 0, 0, 0)
