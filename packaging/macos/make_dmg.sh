#!/usr/bin/env bash
# Wrap ImageSizer.app in a drag-to-Applications disk image.
# Usage: packaging/macos/make_dmg.sh VERSION ARCH [APP_PATH] [OUTPUT_DIR]
set -euo pipefail

VERSION="$1"
ARCH="$2"  # arm64 | x86_64
APP="${3:-dist/ImageSizer.app}"
OUT="${4:-dist}"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

mkdir -p "$OUT"
TARGET="$OUT/ImageSizer-$VERSION-macOS-$ARCH.dmg"
rm -f "$TARGET"
hdiutil create -volname "ImageSizer $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$TARGET"
echo "Built $TARGET"
