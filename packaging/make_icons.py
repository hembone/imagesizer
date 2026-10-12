"""Draw the app icon and write it in every format the installers need.

Run from the repo root after changing the design: ``python packaging/make_icons.py``.
Outputs are committed, so builds don't need to run this.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024
TOP, BOTTOM = (64, 132, 237), (124, 77, 214)  # blue -> violet


def draw(size: int = SIZE) -> Image.Image:
    s = size * 4  # supersample for smooth edges
    grad = Image.new("RGBA", (s, s))
    px = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / (s - 1)
        px.line([(0, y), (s, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)) + (255,))
    mask = Image.new("L", (s, s), 0)
    margin = s * 0.06
    ImageDraw.Draw(mask).rounded_rectangle((margin, margin, s - margin, s - margin), radius=s * 0.2, fill=255)
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(grad, mask=mask)

    # a smaller translucent "source" frame inside a larger "output" frame (composited so it blends)
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((s * 0.24, s * 0.40, s * 0.56, s * 0.72), radius=s * 0.03,
                                            fill=(255, 255, 255, 110))
    icon = Image.alpha_composite(icon, layer)

    d = ImageDraw.Draw(icon)
    white = (255, 255, 255, 255)
    w = round(s * 0.05)

    # crop marks at the corners of the output frame
    a, b, arm = s * 0.22, s * 0.78, s * 0.16
    for x, y, dx, dy in ((a, a, 1, 1), (b, a, -1, 1), (a, b, 1, -1), (b, b, -1, -1)):
        d.line([(x, y + dy * arm), (x, y), (x + dx * arm, y)], fill=white, width=w, joint="curve")

    # diagonal "scale up" arrow from the small frame toward the corner
    d.line([(s * 0.44, s * 0.56), (s * 0.66, s * 0.34)], fill=white, width=w)
    head = s * 0.12
    tip = (s * 0.69, s * 0.31)
    d.polygon([tip, (tip[0] - head, tip[1]), (tip[0], tip[1] + head)], fill=white)
    return icon.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    icon = draw()
    res = ROOT / "src" / "imagesizer" / "resources"
    res.mkdir(parents=True, exist_ok=True)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(res / "icon.png")
    icon.save(ROOT / "packaging" / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(ROOT / "packaging" / "icon.icns")
    print("wrote", res / "icon.png", ROOT / "packaging" / "icon.ico", ROOT / "packaging" / "icon.icns")


if __name__ == "__main__":
    main()
