"""GUI and Background Menu-Bar entry point for FileTool."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is at sys.path[0] and filetool directory is not in sys.path
# to avoid shadowing the standard library 'platform' module
_filetool_dir = str(Path(__file__).resolve().parent)
_project_root = str(Path(__file__).resolve().parent.parent)
if _filetool_dir in sys.path:
    sys.path.remove(_filetool_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from filetool.core.utils import setup_logging
from filetool.platform.mac_drag_monitor import MacDragMonitor
from filetool.ui.main_window import MainWindow
from filetool.ui.wheel.wheel_window import WheelWindow

logger = logging.getLogger("filetool.app")


def create_tray_icon() -> QIcon:
    """Create a high-DPI template menu-bar icon (tangerine radial slice)."""
    pix = QPixmap(36, 36)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    # Stylized radial wheel / circle
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 149, 0))  # Tangerine orange
    painter.drawEllipse(4, 4, 28, 28)

    painter.setBrush(QColor(30, 30, 30))
    painter.drawEllipse(12, 12, 12, 12)

    painter.end()

    icon = QIcon(pix)
    icon.setIsMask(False)
    return icon


def set_macos_accessory_mode(enabled: bool) -> None:
    """Set macOS application activation policy to Accessory (no Dock icon)."""
    try:
        from AppKit import (
            NSApp,
            NSApplicationActivationPolicyAccessory,
            NSApplicationActivationPolicyRegular,
        )
        policy = NSApplicationActivationPolicyAccessory if enabled else NSApplicationActivationPolicyRegular
        NSApp.setActivationPolicy_(policy)
    except Exception as exc:
        logger.debug("Failed configuring NSApp activation policy: %s", exc)


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="FileTool - Native macOS file tool")
    parser.add_argument("--daemon", "--background", dest="daemon", action="store_true", help="Start minimized in menu-bar")
    args, unknown = parser.parse_known_args()

    # Enable native high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FileTool")
    app.setApplicationDisplayName("FileTool")
    app.setQuitOnLastWindowClosed(False)  # Keep running in background menu bar!

    qsettings = QSettings("FileTool", "FileTool")
    accessory_mode = qsettings.value("accessory_mode", True, type=bool)
    set_macos_accessory_mode(accessory_mode)

    # 1. Main Window
    window = MainWindow()

    # 2. Wheel Overlay Window sharing runner
    wheel_window = WheelWindow(runner=window.runner)

    # 3. Drag Monitor
    key_mappings = {
        qsettings.value("trigger_convert", "Shift", type=str).lower(): "convert",
        qsettings.value("trigger_tools", "Command", type=str).lower(): "tools",
        qsettings.value("trigger_actions", "Control", type=str).lower(): "actions",
    }
    monitor = MacDragMonitor(key_mappings=key_mappings)

    def on_trigger(wheel_type: str, x: float, y: float, files: list):
        if qsettings.value("wheel_enabled", True, type=bool):
            # Convert screen coordinates if needed
            from filetool.platform.mac_window import mac_screen_to_qt_coords
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.show_wheel(wheel_type, qt_x, qt_y, files)

    def on_move(x: float, y: float):
        if wheel_window.isVisible():
            from filetool.platform.mac_window import mac_screen_to_qt_coords
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.update_cursor_pos(qt_x, qt_y)

    def on_drop(wheel_type: str, x: float, y: float, files: list):
        if wheel_window.isVisible():
            from filetool.platform.mac_window import mac_screen_to_qt_coords
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.trigger_drop_at(qt_x, qt_y)

    monitor.wheel_triggered.connect(on_trigger)
    monitor.wheel_switched.connect(wheel_window.switch_wheel)
    monitor.wheel_moved.connect(on_move)
    monitor.wheel_dropped.connect(on_drop)
    monitor.wheel_cancelled.connect(wheel_window.cancel_wheel)
    monitor.wheel_navigated.connect(wheel_window.navigate_key)

    # Update monitor mappings when preferences change
    def on_settings_saved(s: dict):
        if "key_mappings" in s:
            monitor.set_key_mappings(s["key_mappings"])
        if "accessory_mode" in s:
            set_macos_accessory_mode(s["accessory_mode"])

    window.settings_updated.connect(on_settings_saved)

    # Start monitor
    monitor.start()

    # 4. System Tray Icon (Menu-bar app)
    tray = QSystemTrayIcon(create_tray_icon(), app)
    tray_menu = QMenu()

    def show_main_window():
        window.show()
        window.raise_()
        window.activateWindow()

    act_open = tray_menu.addAction("Open FileTool")
    act_open.triggered.connect(show_main_window)

    act_prefs = tray_menu.addAction("Preferences…")
    act_prefs.triggered.connect(window._open_settings)

    act_deps = tray_menu.addAction("Dependency Health…")
    act_deps.triggered.connect(window._show_dep_report)

    tray_menu.addSeparator()

    act_quit = tray_menu.addAction("Quit FileTool")
    act_quit.triggered.connect(app.quit)

    tray.setContextMenu(tray_menu)
    tray.setToolTip("FileTool — Drag files & tap Shift/Cmd/Ctrl for Drag Wheel")
    tray.show()

    # Show main window unless started with --daemon
    if not args.daemon:
        show_main_window()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
