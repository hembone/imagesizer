from importlib.metadata import PackageNotFoundError, version

try:
    # Release builds write the tag's version here (e.g. 0.1.0-rc1); see .github/workflows/release.yml
    from ._build_version import VERSION as __version__
except ImportError:
    try:
        __version__ = version("imagesizer")
    except PackageNotFoundError:  # running from a source tree without installing
        __version__ = "dev"
