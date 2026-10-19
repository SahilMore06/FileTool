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
if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/pyinstaller" ]]; then
    PYINSTALLER="${CONDA_PREFIX}/bin/pyinstaller"
elif [[ -x ".venv/bin/pyinstaller" ]]; then
    PYINSTALLER=".venv/bin/pyinstaller"
elif [[ -x "/Users/sahil/miniforge3/envs/filetool/bin/pyinstaller" ]]; then
    PYINSTALLER="/Users/sahil/miniforge3/envs/filetool/bin/pyinstaller"
elif command -v pyinstaller >/dev/null 2>&1; then
    PYINSTALLER="$(command -v pyinstaller)"
else
    echo "Error: pyinstaller not found. Run: pip install pyinstaller"
    exit 1
fi

echo "Using PyInstaller: ${PYINSTALLER}"

echo "Cleaning previous build artifacts..."
rm -rf build dist FileTool.spec

ICON_ARG=()
if [[ -f "resources/FileTool.icns" ]]; then
    ICON_ARG=(--icon "resources/FileTool.icns")
fi

echo "Running PyInstaller..."
"${PYINSTALLER}" \
    --name "FileTool" \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier "com.filetool.macos" \
    "${ICON_ARG[@]}" \
    --collect-all "filetool" \
    --collect-all "PySide6" \
    --collect-all "PIL" \
    --collect-all "pillow_heif" \
    --collect-all "pypdf" \
    --collect-all "pdf2docx" \
    --collect-all "pptx" \
    --collect-all "openpyxl" \
    --collect-all "pandas" \
    --hidden-import "objc" \
    --hidden-import "AppKit" \
    --hidden-import "Quartz" \
    --hidden-import "filetool.platform.mac_drag_monitor" \
    --hidden-import "filetool.platform.mac_actions" \
    --hidden-import "filetool.platform.mac_window" \
    --hidden-import "filetool.ui.wheel.wheel_window" \
    --hidden-import "filetool.ui.wheel.wheel_painter" \
    --hidden-import "filetool.ui.wheel.geometry" \
    --hidden-import "filetool.ui.wheel.animations" \
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

    /usr/libexec/PlistBuddy -c "Set :CFBundleName FileTool" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleName string FileTool" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 1.0.0" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string 1.0.0" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion 1.0.0" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string 1.0.0" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :NSAppleEventsUsageDescription 'FileTool uses Apple Events to reveal converted files in Finder.'" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string 'FileTool uses Apple Events to reveal converted files in Finder.'" "${INFO_PLIST}" 2>/dev/null || true
fi

echo ""
echo "Cleaning Qt auxiliary bundles and signing application..."
rm -rf dist/FileTool.app/Contents/Frameworks/PySide6/*__dot__app 2>/dev/null || true
codesign -f -s - --deep "dist/FileTool.app" 2>/dev/null || true

echo ""
echo "Creating downloadable distribution packages (ZIP and DMG)..."
(
    cd dist
    echo "Creating FileTool.app.zip..."
    ditto -c -k --keepParent "FileTool.app" "FileTool.app.zip"

    if command -v hdiutil >/dev/null 2>&1; then
        echo "Creating FileTool.dmg..."
        rm -f "FileTool.dmg"
        hdiutil create -volname "FileTool" -srcfolder "FileTool.app" -ov -format UDZO "FileTool.dmg"
    fi
)

echo ""
echo "============================================================"
echo "✔ Successfully Built: dist/FileTool.app"
echo "✔ Downloadable ZIP:   dist/FileTool.app.zip"
[[ -f "dist/FileTool.dmg" ]] && echo "✔ Downloadable DMG:   dist/FileTool.dmg"
echo "============================================================"
