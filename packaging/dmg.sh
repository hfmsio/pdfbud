#!/bin/sh
# Packs dist/pdfbud.app into dist/pdfbud-<version>-arm64.dmg with a checksum file. Run build.sh first.
set -e
cd "$(dirname "$0")/.."
NAME="pdfbud-$(uv run python -c 'import pdfbud; print(pdfbud.__version__)')-arm64"
STAGE=$(mktemp -d)
ditto dist/pdfbud.app "$STAGE/pdfbud.app"  # ditto keeps the signature and links intact
ln -s /Applications "$STAGE/Applications"
rm -f "dist/$NAME.dmg"
hdiutil create -quiet -volname pdfbud -srcfolder "$STAGE" -fs HFS+ -format UDZO -imagekey zlib-level=9 "dist/$NAME.dmg"
rm -rf "$STAGE"
(cd dist && shasum -a 256 "$NAME.dmg" > "$NAME.dmg.sha256" && cat "$NAME.dmg.sha256")
