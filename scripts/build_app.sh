#!/usr/bin/env bash
# Package Fluxora as a standalone macOS .app bundle via PyInstaller.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

APP_VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' filetool/__init__.py | head -n 1)"
APP_VERSION="${APP_VERSION:-1.1.0}"

echo "============================================================"
echo "     Building Fluxora v${APP_VERSION} (.app) for macOS      "
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
rm -rf build dist FileTool.spec Fluxora.spec

ICON_ARG=()
if [[ -f "resources/Fluxora.icns" ]]; then
    ICON_ARG=(--icon "resources/Fluxora.icns")
fi

echo "Running PyInstaller..."
"${PYINSTALLER}" \
    --name "Fluxora" \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier "com.fluxora.macos" \
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
    --hidden-import "filetool.core.legal" \
    --hidden-import "filetool.ui.onboarding" \
    --hidden-import "filetool.ui.tray_popover" \
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
INFO_PLIST="dist/Fluxora.app/Contents/Info.plist"

if [[ -f "${INFO_PLIST}" ]]; then
    # Add NSHighResolutionCapable if missing
    /usr/libexec/PlistBuddy -c "Set :NSHighResolutionCapable true" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName Fluxora" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string Fluxora" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleName Fluxora" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleName string Fluxora" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${APP_VERSION}" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string ${APP_VERSION}" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${APP_VERSION}" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string ${APP_VERSION}" "${INFO_PLIST}" 2>/dev/null || true

    /usr/libexec/PlistBuddy -c "Set :NSAppleEventsUsageDescription 'Fluxora uses Apple Events to reveal converted files in Finder.'" "${INFO_PLIST}" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string 'Fluxora uses Apple Events to reveal converted files in Finder.'" "${INFO_PLIST}" 2>/dev/null || true
fi

echo ""
echo "Cleaning Qt auxiliary bundles and signing application..."
rm -rf dist/Fluxora.app/Contents/Frameworks/PySide6/*__dot__app 2>/dev/null || true
codesign -f -s - --deep "dist/Fluxora.app" 2>/dev/null || true

echo ""
echo "Creating downloadable distribution packages (ZIP and DMG)..."
(
    cd dist
    echo "Creating Fluxora.app.zip..."
    ditto -c -k --keepParent "Fluxora.app" "Fluxora.app.zip"

    if command -v hdiutil >/dev/null 2>&1; then
        echo "Creating Fluxora.dmg..."
        rm -f "Fluxora.dmg"
        hdiutil create -volname "Fluxora" -srcfolder "Fluxora.app" -ov -format UDZO "Fluxora.dmg"
    fi

    if command -v shasum >/dev/null 2>&1; then
        echo "Generating SHA256SUMS.txt..."
        rm -f "SHA256SUMS.txt"
        for pkg in Fluxora.dmg Fluxora.app.zip; do
            [[ -f "${pkg}" ]] && shasum -a 256 "${pkg}" >> "SHA256SUMS.txt"
        done
    fi
)

echo ""
echo "============================================================"
echo "✔ Successfully Built: dist/Fluxora.app (v${APP_VERSION})"
echo "✔ Downloadable ZIP:   dist/Fluxora.app.zip"
[[ -f "dist/Fluxora.dmg" ]] && echo "✔ Downloadable DMG:   dist/Fluxora.dmg"
[[ -f "dist/SHA256SUMS.txt" ]] && echo "✔ Checksums:          dist/SHA256SUMS.txt"
echo "============================================================"
