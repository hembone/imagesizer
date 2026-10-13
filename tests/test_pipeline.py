import json
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


@pytest.mark.parametrize("policy", ["rename", "overwrite"])
def test_same_name_in_two_subfolders_gets_two_folders(tmp_path, policy):
    for sub, color in (("x", "red"), ("y", "blue")):
        (tmp_path / "in" / sub).mkdir(parents=True)
        Image.new("RGB", (60, 40), color).save(tmp_path / "in" / sub / "photo.png")
    p = make_preset(tmp_path / "out", folder_collision="reuse", file_collision=policy)
    p.upscale.enabled = False
    pipe = Pipeline(p)
    folders = [pipe.process(f, i).folder for i, f in enumerate(collect_inputs([tmp_path / "in"]), 1)]
    assert [f.name for f in folders] == ["photo", "photo_1"]
    assert all(len(list(f.iterdir())) == 3 for f in folders)


def test_16bit_grey_input_is_not_blown_out(tmp_path):
    Image.new("I;16", (40, 40), 32768).save(tmp_path / "g.png")
    p = make_preset(tmp_path / "out")
    p.upscale.enabled = False
    res = Pipeline(p).process(tmp_path / "g.png")
    with Image.open(res.outputs[0]) as im:
        assert abs(im.convert("L").getpixel((0, 0)) - 128) <= 1


def test_icc_profile_dropped_when_color_space_mismatches(tmp_path):
    from PIL import ImageCms

    from imagesizer.processing.pipeline import save_image

    gray = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()  # not an RGB profile
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    save_image(Image.new("RGB", (4, 4)), tmp_path / "a.png", "PNG", icc=gray)
    save_image(Image.new("RGB", (4, 4)), tmp_path / "b.png", "PNG", icc=srgb)
    with Image.open(tmp_path / "a.png") as a, Image.open(tmp_path / "b.png") as b:
        assert "icc_profile" not in a.info and b.info.get("icc_profile")


def test_cmyk_source_saved_as_rgb(tmp_path):
    Image.new("CMYK", (40, 30), (0, 255, 255, 0)).save(tmp_path / "c.jpg")
    p = make_preset(tmp_path / "out", format="png")
    p.upscale.enabled = False
    res = Pipeline(p).process(tmp_path / "c.jpg")
    with Image.open(res.outputs[0]) as im:
        assert im.mode == "RGB" and "icc_profile" not in im.info


def test_preview_sizes_keyed_by_row(tmp_path):
    p = Preset(ratios=[RatioSpec("1:1", size_mode="long_edge", long_edge=100),
                       RatioSpec("1:1", size_mode="long_edge", long_edge=200)])
    _, files = Pipeline(p).preview_names(Path("a.jpg"), 1, {0: (100, 100), 1: (200, 200)})
    assert files == ["a_1x1_100x100.png", "a_1x1_200x200.png"]


def test_settings_keep_good_parts_and_back_up_bad_file(tmp_path):
    good = make_preset(tmp_path)
    s = config.Settings()
    s.presets["good"] = good
    config.save(s, tmp_path / "s.json")
    data = json.loads((tmp_path / "s.json").read_text())
    data["presets"]["broken"] = {"ratios": "nope"}
    data["current"]["upscale"]["scale"] = "four"
    (tmp_path / "s.json").write_text(json.dumps(data))
    loaded = config.load(tmp_path / "s.json")
    assert loaded.presets["good"] == good  # one bad preset doesn't cost the others
    assert loaded.presets["broken"].ratios == Preset().ratios  # bad field falls back to its default
    assert loaded.current.upscale.scale == 4
    assert (tmp_path / "s.json.bad").read_text() == json.dumps(data)


def test_unreadable_settings_backed_up(tmp_path):
    (tmp_path / "s.json").write_text("{not json")
    assert config.load(tmp_path / "s.json") == config.Settings()
    assert (tmp_path / "s.json.bad").read_text() == "{not json"
    config.save(config.Settings(), tmp_path / "ok.json")
    config.load(tmp_path / "ok.json")
    assert not (tmp_path / "ok.json.bad").exists()


def test_engine_install_leaves_no_partial_binary(tmp_path, monkeypatch):
    import io
    import zipfile

    from imagesizer.engine import upscayl

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"pkg/{upscayl.platform.exe_name()}", b"x" * 1000)

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(upscayl, "_urlopen", lambda url: Resp(json.dumps(
        {"assets": [{"name": f"bin-{upscayl.platform.os_key()}.zip", "browser_download_url": "z"}]}).encode()))
    monkeypatch.setattr(upscayl, "_download", lambda url, dest, *a: dest.write_bytes(buf.getvalue()))

    def boom(*a):
        raise OSError("disk full")

    monkeypatch.setattr(upscayl.shutil, "copyfileobj", boom)
    eng = Engine(tmp_path / "e" / upscayl.platform.exe_name(), tmp_path / "e" / "models")
    with pytest.raises(OSError):
        eng.download(models=[])
    assert not eng.has_binary and list((tmp_path / "e").iterdir()) == []
    monkeypatch.undo()
    monkeypatch.setattr(upscayl, "_urlopen", lambda url: Resp(json.dumps(
        {"assets": [{"name": f"bin-{upscayl.platform.os_key()}.zip", "browser_download_url": "z"}]}).encode()))
    monkeypatch.setattr(upscayl, "_download", lambda url, dest, *a: dest.write_bytes(buf.getvalue()))
    eng.download(models=[])
    assert eng.has_binary and eng.binary.read_bytes() == b"x" * 1000


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
