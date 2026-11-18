#!/bin/sh
# Builds dist/pdfbud.app and registers it as a PDF opener. Run from anywhere.
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)  # PyInstaller reads relative paths from the spec folder, so give it absolute ones
uv run python packaging/icon.py
uv run pyinstaller --noconfirm --windowed --name pdfbud --icon "$ROOT/packaging/pdfbud.icns" --specpath build \
  --osx-bundle-identifier io.github.hfmsio.pdfbud \
  --paths "$ROOT/src" --add-data "$ROOT/src/pdfbud/web:pdfbud/web" packaging/entry.py
uv run python - <<'PY'
import plistlib
from pdfbud import __version__
f = "dist/pdfbud.app/Contents/Info.plist"
p = plistlib.load(open(f, "rb"))
p["CFBundleDocumentTypes"] = [{"CFBundleTypeName": "PDF", "CFBundleTypeExtensions": ["pdf"], "CFBundleTypeRole": "Editor"}]
p["CFBundleShortVersionString"] = p["CFBundleVersion"] = __version__
p["LSMinimumSystemVersion"] = "11.0"  # the oldest macOS the bundled Python and PyMuPDF binaries accept
plistlib.dump(p, open(f, "wb"))
PY
codesign --force --deep --sign - dist/pdfbud.app  # editing the plist broke PyInstaller's seal; ad hoc until there is a Developer ID
codesign --verify --deep --strict dist/pdfbud.app
