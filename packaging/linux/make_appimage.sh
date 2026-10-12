#!/usr/bin/env bash
# Build ImageSizer-<version>-x86_64.AppImage from the PyInstaller output.
# Usage: packaging/linux/make_appimage.sh VERSION [PYINSTALLER_DIST_DIR] [OUTPUT_DIR]
set -euo pipefail

VERSION="$1"
DIST="$(realpath "${2:-dist/ImageSizer}")"
OUT="$(realpath -m "${3:-dist}")"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

APPDIR="$WORK/ImageSizer.AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -a "$DIST/." "$APPDIR/usr/bin/"
cp "$HERE/imagesizer.desktop" "$APPDIR/imagesizer.desktop"
cp "$HERE/imagesizer.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/src/imagesizer/resources/icon.png" "$APPDIR/imagesizer.png"
cp "$ROOT/src/imagesizer/resources/icon.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/imagesizer.png"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/ImageSizer" "$@"
RUN
chmod +x "$APPDIR/AppRun"

# appimagetool's current release embeds a static runtime, so users don't need libfuse2.
TOOL="${APPIMAGETOOL:-}"
if [ -z "$TOOL" ]; then
  TOOL="$WORK/appimagetool"
  curl -fsSL -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi

mkdir -p "$OUT"
TARGET="$OUT/ImageSizer-$VERSION-x86_64.AppImage"
# Extract-and-run avoids needing FUSE on build machines (CI containers don't have it).
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$TARGET"
echo "Built $TARGET"
