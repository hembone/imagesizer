"""Headless command line: ``imagesizer-cli INPUT... -o OUT --ratio 1:1 --ratio 16:9=1920x1080``."""

from __future__ import annotations

import argparse
import re
import sys

from . import config
from .config import Preset, RatioSpec
from .engine.upscayl import MODELS, Engine, EngineError
from .processing.pipeline import Pipeline, collect_inputs
from .processing.resize import ANCHORS

_RATIO_ARG = re.compile(r"^(?P<ratio>[^=@]+?)(?:=(?P<w>\d+)x(?P<h>\d+)|@(?P<edge>\d+))?$")


def parse_ratio_arg(text: str) -> RatioSpec:
    """``4:5`` (max size), ``4:5@2048`` (long edge) or ``4:5=1080x1350`` (exact)."""
    m = _RATIO_ARG.match(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"bad --ratio {text!r}")
    spec = RatioSpec(m["ratio"].strip())
    try:
        spec.parsed()
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
    if m["w"]:
        spec.size_mode, spec.width, spec.height = "exact", int(m["w"]), int(m["h"])
    elif m["edge"]:
        spec.size_mode, spec.long_edge = "long_edge", int(m["edge"])
    return spec


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="imagesizer-cli", description=__doc__)
    ap.add_argument("inputs", nargs="*", help="image files or folders")
    ap.add_argument("-o", "--output", help="output folder")
    ap.add_argument("-r", "--ratio", action="append", type=parse_ratio_arg, default=[],
                    help="aspect ratio, repeatable: 4:5 | 4:5@2048 | 4:5=1080x1350")
    ap.add_argument("--preset", help="use a preset saved from the GUI")
    ap.add_argument("--no-upscale", action="store_true")
    ap.add_argument("--model", choices=list(MODELS))
    ap.add_argument("--scale", type=int, choices=[2, 3, 4])
    ap.add_argument("--gpu", help="GPU id (default auto)")
    ap.add_argument("--fit", choices=["crop", "pad"])
    ap.add_argument("--anchor", choices=list(ANCHORS))
    ap.add_argument("--pad-color", help="hex color, or 'transparent'")
    ap.add_argument("--format", choices=["png", "jpg", "webp"])
    ap.add_argument("--quality", type=int)
    ap.add_argument("--folder-template")
    ap.add_argument("--file-template")
    ap.add_argument("--keep-upscaled", action="store_true")
    ap.add_argument("--download-engine", action="store_true", help="download upscayl-bin and all models, then exit")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = config.load()
    engine = Engine.locate(settings.engine_binary or None, settings.engine_models_dir or None)

    if args.download_engine:
        def show(msg: str, frac: float) -> None:
            print(f"\r{msg} {frac:6.1%}".ljust(80), end="", flush=True)
        try:
            engine.download(progress=show)
        except (EngineError, OSError) as e:
            print(f"\nDownload failed: {e}", file=sys.stderr)
            return 1
        print(f"\nInstalled to {engine.binary.parent}")
        return 0

    if not args.inputs:
        build_parser().error("no inputs given")

    if args.preset:
        if args.preset not in settings.presets:
            print(f"Unknown preset {args.preset!r}. Saved: {', '.join(settings.presets) or 'none'}", file=sys.stderr)
            return 2
        preset = config.preset_from_json(config.preset_to_json(settings.presets[args.preset]))
    else:
        preset = Preset()
    if args.ratio:
        preset.ratios = args.ratio
    if args.output:
        preset.output.directory = args.output
    if args.no_upscale:
        preset.upscale.enabled = False
    for attr, target, key in [("model", preset.upscale, "model"), ("scale", preset.upscale, "scale"),
                              ("gpu", preset.upscale, "gpu_id"), ("fit", preset.fit, "mode"),
                              ("anchor", preset.fit, "anchor"), ("format", preset.output, "format"),
                              ("quality", preset.output, "quality"),
                              ("folder_template", preset.output, "folder_template"),
                              ("file_template", preset.output, "file_template")]:
        if getattr(args, attr) is not None:
            setattr(target, key, getattr(args, attr))
    if args.pad_color:
        if args.pad_color.lower() == "transparent":
            preset.fit.pad_transparent = True
        else:
            preset.fit.pad_color = args.pad_color
    if args.keep_upscaled:
        preset.output.keep_upscaled = True
    if not preset.output.directory:
        preset.output.directory = settings.current.output.directory

    pipeline = Pipeline(preset, engine)
    errors = pipeline.validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    files = collect_inputs(args.inputs)
    if not files:
        print("No supported images found.", file=sys.stderr)
        return 2

    failed = 0
    for i, src in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {src.name}", flush=True)
        res = pipeline.process(src, i, lambda m, f: print(f"\r    {m} {f:4.0%}".ljust(60), end="", flush=True))
        print("\r".ljust(60), end="\r")
        for out in res.outputs:
            print(f"    -> {out}")
        for s in res.skipped:
            print(f"    skipped: {s}")
        if res.error:
            failed += 1
            print(f"    ERROR: {res.error}", file=sys.stderr)
    print(f"Done: {len(files) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
