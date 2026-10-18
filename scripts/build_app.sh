#!/usr/bin/env bash
# ==============================================================================
# FileTool - macOS Application Bundle (.app) Packaging Script
# Uses PyInstaller to build a standalone, double-clickable FileTool.app bundle.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "============================================================"
echo "          Building FileTool.app for macOS (Apple Silicon)   "
echo "============================================================"

# Ensure pyinstaller is available
if [[ -f ".venv/bin/pyinstaller" ]]; then
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYINSTALLER="$(command -v pyinstaller)"
fi

echo "Cleaning previous build artifacts..."
rm -rf build dist FileTool.spec

echo "Running PyInstaller..."
"${PYINSTALLER}" \
    --name "FileTool" \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier "com.filetool.macos" \
    --collect-all "filetool" \
    --collect-all "pyside6" \
    --collect-all "PIL" \
    --collect-all "pillow_heif" \
    --collect-all "pypdf" \
    --collect-all "pdf2docx" \
    --collect-all "pptx" \
    --collect-all "openpyxl" \
    --hidden-import "filetool.core.engines.archives" \
    --hidden-import "filetool.core.engines.images" \
    --hidden-import "filetool.core.engines.media" \
    --hidden-import "filetool.core.engines.office" \
    --hidden-import "filetool.core.engines.pandoc_docs" \
    --hidden-import "filetool.core.engines.pdf" \
    --hidden-import "filetool.core.engines.spreadsheets" \
    --hidden-import "filetool.core.engines.subtitles" \
    --hidden-import "filetool.core.tools.compress" \
    --hidden-import "filetool.core.tools.crop" \
    --hidden-import "filetool.core.tools.merge" \
    --hidden-import "filetool.core.tools.metadata" \
    --hidden-import "filetool.core.tools.resize" \
    --hidden-import "filetool.core.tools.split" \
    --hidden-import "filetool.core.tools.trim" \
    app.py

echo ""
echo "Patching Info.plist for high DPI and permissions..."
INFO_PLIST="dist/FileTool.app/Contents/Info.plist"

if [[ -f "${INFO_PLIST}" ]]; then
    # Add NSHighResolutionCapable if missing
    /usr/libexec/PlistBuddy -c "Set :NSHighResolutionCapable true" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName FileTool" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string FileTool" "${INFO_PLIST}" 2>/dev/null || true
fi

echo ""
echo "============================================================"
echo "✔ Successfully Built: dist/FileTool.app"
echo "You can move it to /Applications or double-click to launch."
echo "============================================================"
