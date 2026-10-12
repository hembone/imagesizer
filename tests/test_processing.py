import pytest
from PIL import Image

from imagesizer.processing import naming
from imagesizer.processing.ratios import Ratio
from imagesizer.processing.resize import (
    ANCHORS,
    FitMode,
    SizeMode,
    SizeSpec,
    crop_box,
    fit_image,
    pad_layout,
    target_size,
)


# --- ratios ---------------------------------------------------------------

@pytest.mark.parametrize("text,w,h", [("16:9", 16, 9), ("4x5", 4, 5), (" 1 : 1 ", 1, 1), ("2.39:1", 2.39, 1)])
def test_parse(text, w, h):
    r = Ratio.parse(text)
    assert (r.w, r.h) == (w, h)


@pytest.mark.parametrize("text", ["", "16", "0:9", "a:b", "16:9:1"])
def test_parse_invalid(text):
    with pytest.raises(ValueError):
        Ratio.parse(text)


def test_labels():
    assert Ratio.parse("16:9").label == "16:9"
    assert Ratio.parse("16:9").slug == "16x9"
    assert Ratio.parse("2.39:1").slug == "2_39x1"
    assert Ratio.from_size(1080, 1350).label == "4:5"


# --- crop / pad math ------------------------------------------------------

@pytest.mark.parametrize("ratio", ["1:1", "4:5", "16:9", "9:16", "21:9", "3:2"])
@pytest.mark.parametrize("size", [(4000, 3000), (3000, 4000), (1000, 1000), (1921, 1081)])
@pytest.mark.parametrize("anchor", list(ANCHORS))
def test_crop_box_fits_and_matches_ratio(ratio, size, anchor):
    r = Ratio.parse(ratio)
    left, top, right, bottom = crop_box(*size, r, anchor)
    w, h = right - left, bottom - top
    assert 0 <= left and 0 <= top and right <= size[0] and bottom <= size[1]
    assert abs(w / h - r.value) < 2 / min(w, h)
    assert w == size[0] or h == size[1]  # largest possible box


def test_crop_box_anchors():
    r = Ratio.parse("1:1")
    assert crop_box(400, 200, r, "left") == (0, 0, 200, 200)
    assert crop_box(400, 200, r, "center") == (100, 0, 300, 200)
    assert crop_box(400, 200, r, "right") == (200, 0, 400, 200)
    assert crop_box(200, 400, r, "top") == (0, 0, 200, 200)
    assert crop_box(200, 400, r, "bottom") == (0, 200, 200, 400)


def test_pad_layout():
    assert pad_layout(400, 200, Ratio.parse("1:1")) == (400, 400, 0, 100)
    assert pad_layout(400, 200, Ratio.parse("1:1"), "top") == (400, 400, 0, 0)
    assert pad_layout(100, 100, Ratio.parse("16:9")) == (178, 100, 39, 0)


def test_target_size():
    r = Ratio.parse("4:5")
    assert target_size(800, 1000, r, SizeSpec(SizeMode.MAX)) == (800, 1000)
    assert target_size(800, 1000, r, SizeSpec(SizeMode.LONG_EDGE, long_edge=2000)) == (1600, 2000)
    assert target_size(800, 1000, Ratio.parse("16:9"), SizeSpec(SizeMode.LONG_EDGE, long_edge=1920)) == (1920, 1080)
    assert target_size(800, 1000, r, SizeSpec(SizeMode.EXACT, width=1080, height=1350)) == (1080, 1350)


def test_fit_image_crop_and_pad():
    img = Image.new("RGB", (400, 200), "red")
    out = fit_image(img, Ratio.parse("1:1"), FitMode.CROP)
    assert out.size == (200, 200)
    out = fit_image(img, Ratio.parse("1:1"), FitMode.PAD, pad_color=(0, 0, 255, 255))
    assert out.size == (400, 400) and out.getpixel((0, 0)) == (0, 0, 255) and out.getpixel((200, 200)) == (255, 0, 0)
    out = fit_image(img, Ratio.parse("1:1"), FitMode.PAD, pad_color=(0, 0, 0, 0))
    assert out.mode == "RGBA" and out.getpixel((0, 0))[3] == 0


def test_fit_image_exact_uses_its_own_ratio():
    img = Image.new("RGB", (1000, 1000))
    out = fit_image(img, Ratio.parse("1:1"), size=SizeSpec(SizeMode.EXACT, width=1080, height=1350))
    assert out.size == (1080, 1350)


# --- naming ---------------------------------------------------------------

def test_sanitize():
    assert naming.sanitize('a<b>:c"d/e\\f|g?h*') == "abcdefgh"
    assert naming.sanitize("  trailing. ") == "trailing"
    assert naming.sanitize("CON") == "_CON"
    assert naming.sanitize("???") == "untitled"


def test_render_and_validate():
    assert naming.render("{name}_{ratio}_{w}x{h}", naming.FILE_TOKENS, name="beach", ratio="16x9", w=1920, h=1080,
                         date="", index=1, scale=4, model="m") == "beach_16x9_1920x1080"
    with pytest.raises(naming.TemplateError):
        naming.validate("{name}_{ratio}", naming.FOLDER_TOKENS)
    with pytest.raises(naming.TemplateError):
        naming.validate("{name", naming.FILE_TOKENS)
    with pytest.raises(naming.TemplateError):
        naming.validate("  ", naming.FILE_TOKENS)


def test_resolve_file(tmp_path):
    p = tmp_path / "a.png"
    assert naming.resolve_file(p, naming.FileCollision.SKIP) == p
    p.touch()
    assert naming.resolve_file(p, naming.FileCollision.SKIP) is None
    assert naming.resolve_file(p, naming.FileCollision.OVERWRITE) == p
    assert naming.resolve_file(p, naming.FileCollision.RENAME) == tmp_path / "a_1.png"
    assert naming.resolve_file(p, naming.FileCollision.RENAME, {tmp_path / "a_1.png"}) == tmp_path / "a_2.png"


def test_resolve_folder(tmp_path):
    d = tmp_path / "beach"
    d.mkdir()
    assert naming.resolve_folder(d, naming.FolderCollision.REUSE) == d
    assert naming.resolve_folder(d, naming.FolderCollision.SKIP) is None
    assert naming.resolve_folder(d, naming.FolderCollision.RENAME) == tmp_path / "beach_1"
