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
PYTHON_BIN="$(dirname "${PYINSTALLER}")/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(command -v python3)"
fi

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
        echo "Creating Fluxora.dmg (with Drag-to-Applications shortcut)..."
        rm -f "Fluxora.dmg"
        if QT_QPA_PLATFORM=offscreen "${PYTHON_BIN}" -c "import dmgbuild, PySide6, PIL" >/dev/null 2>&1; then
            QT_QPA_PLATFORM=offscreen "${PYTHON_BIN}" - "${ROOT_DIR}" <<'PYEOF'
import sys
import tempfile
from pathlib import Path
import dmgbuild
from PIL import Image
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import (
    QImage,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QLinearGradient,
    QRadialGradient,
    QFont,
    QPolygonF,
)

root_dir = Path(sys.argv[1]).resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
from filetool.ui.components import create_brand_pixmap

app = QApplication.instance() or QApplication([])

def render_dmg_bg(scale: int, out_path: Path) -> None:
    CW, CH = 900, 600
    W, H = CW * scale, CH * scale
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)

    p.fillRect(QRectF(0, 0, CW, CH), QColor("#171819"))

    p.save()
    p.setPen(QPen(QColor(255, 255, 255, 7), 1.0))
    for x in range(66, CW, 66):
        p.drawLine(QPointF(x, 0), QPointF(x, CH))
    for y in range(66, CH, 66):
        p.drawLine(QPointF(0, y), QPointF(CW, y))
    p.restore()

    glow = QRadialGradient(330, 168, 250)
    glow.setColorAt(0.0, QColor(242, 138, 50, 42))
    glow.setColorAt(0.6, QColor(242, 138, 50, 14))
    glow.setColorAt(1.0, QColor(242, 138, 50, 0))
    p.fillRect(QRectF(0, 0, CW, CH), glow)

    for cx in (180, 480):
        zone = QRectF(cx - 78, 94, 156, 158)
        zp = QPainterPath()
        zp.addRoundedRect(zone, 24, 24)
        p.fillPath(zp, QColor(255, 255, 255, 8))
        pen_style = Qt.DashLine if cx == 480 else Qt.SolidLine
        p.setPen(QPen(QColor(242, 138, 50, 65 if cx == 480 else 38), 1.3, pen_style))
        p.drawPath(zp)

        # High-contrast warm Tangerine/Amber badge pill behind Finder's black icon label
        lbl_rect = QRectF(cx - 58, 212, 116, 26)
        lp = QPainterPath()
        lp.addRoundedRect(lbl_rect, 13, 13)
        lgrad = QLinearGradient(lbl_rect.topLeft(), lbl_rect.bottomLeft())
        lgrad.setColorAt(0.0, QColor("#F5A352"))
        lgrad.setColorAt(1.0, QColor("#E88428"))
        p.fillPath(lp, lgrad)
        p.setPen(QPen(QColor(255, 232, 204, 160), 1.0))
        p.drawPath(lp)

    p.save()
    grad = QLinearGradient(280, 162, 380, 162)
    grad.setColorAt(0.0, QColor(242, 138, 50, 95))
    grad.setColorAt(1.0, QColor("#F28A32"))
    p.setPen(QPen(grad, 3.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(282, 162), QPointF(372, 162))

    head = QPolygonF([
        QPointF(364, 151),
        QPointF(378, 162),
        QPointF(364, 173),
    ])
    p.setPen(QPen(QColor("#F28A32"), 3.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline(head)
    p.restore()

    pix = create_brand_pixmap(size=24, accent_color="#F28A32", dpr=float(scale * 2))
    p.drawPixmap(QRectF(252, 32, 24, 24), pix, QRectF(pix.rect()))
    f_title = QFont(".AppleSystemUIFont")
    f_title.setPixelSize(16)
    f_title.setWeight(QFont.Weight.Bold)
    p.setFont(f_title)
    p.setPen(QColor("#F1EFEA"))
    p.drawText(QRectF(284, 32, 160, 24), Qt.AlignVCenter | Qt.AlignLeft, "Fluxora Installer")

    pill = QRectF(190, 276, 280, 34)
    pp = QPainterPath()
    pp.addRoundedRect(pill, 17, 17)
    p.fillPath(pp, QColor(34, 35, 38, 240))
    p.setPen(QPen(QColor(242, 138, 50, 120), 1.2))
    p.drawPath(pp)

    f_sub = QFont(".AppleSystemUIFont")
    f_sub.setPixelSize(13)
    f_sub.setWeight(QFont.Weight.DemiBold)
    p.setFont(f_sub)
    p.setPen(QColor("#F1EFEA"))
    p.drawText(pill, Qt.AlignCenter, "Drag Fluxora into Applications")

    p.end()
    tmp_png = out_path.with_suffix(".raw.png")
    img.save(str(tmp_png))
    pil_img = Image.open(tmp_png)
    dpi_val = 72 * scale
    pil_img.save(out_path, dpi=(dpi_val, dpi_val))
    tmp_png.unlink(missing_ok=True)

with tempfile.TemporaryDirectory() as td:
    td_p = Path(td)
    bg1 = td_p / "dmg_bg.png"
    bg2 = td_p / "dmg_bg@2x.png"
    render_dmg_bg(1, bg1)
    render_dmg_bg(2, bg2)
    icns_path = root_dir / "resources" / "Fluxora.icns"
    settings = {
        "format": "UDZO",
        "size": None,
        "files": ["Fluxora.app"],
        "symlinks": {"Applications": "/Applications"},
        "icon_locations": {
            "Fluxora.app": (180, 162),
            "Applications": (480, 162),
        },
        "background": str(bg1),
        "window_rect": ((200, 120), (660, 468)),
        "icon_size": 92,
        "text_size": 13,
        "show_status_bar": False,
        "show_tab_view": False,
        "show_toolbar": False,
        "show_pathbar": False,
        "show_sidebar": False,
    }
    if icns_path.is_file():
        settings["icon"] = str(icns_path)
    dmgbuild.build_dmg("Fluxora.dmg", "Fluxora", settings=settings)
PYEOF
        else
            rm -rf dmg_stage
            mkdir -p dmg_stage
            cp -R "Fluxora.app" dmg_stage/
            ln -s /Applications dmg_stage/Applications
            hdiutil create -volname "Fluxora" -srcfolder "dmg_stage" -ov -format UDZO "Fluxora.dmg"
            rm -rf dmg_stage
        fi
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
