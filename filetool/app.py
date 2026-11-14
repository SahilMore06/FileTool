"""GUI and Background Menu-Bar entry point for FileTool."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_filetool_dir = str(Path(__file__).resolve().parent)
_project_root = str(Path(__file__).resolve().parent.parent)
if _filetool_dir in sys.path:
    sys.path.remove(_filetool_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtCore import QEasingCurve, QObject, QSettings, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from filetool.core.deps import TOOLS_METADATA, resolver
from filetool.core.utils import setup_logging
from filetool.platform.mac_drag_monitor import MacDragMonitor
from filetool.platform.mac_window import mac_screen_to_qt_coords
from filetool.ui.components import create_brand_icon, create_brand_pixmap
from filetool.ui.main_window import MainWindow
from filetool.ui.styles import ACCENT_PRESETS
from filetool.ui.tray_popover import TrayPopover
from filetool.ui.wheel.animations import should_reduce_motion
from filetool.ui.wheel.wheel_window import WheelWindow

logger = logging.getLogger("filetool.app")


def create_tray_icon(
    accent_color: str = "#F28A32",
    rotation_deg: float = 0.0,
    progress: int | None = None,
    done_t: float = 0.0,
) -> QIcon:
    """Create a Retina 2x radial wheel emblem icon for the macOS menu bar."""
    pix = create_brand_pixmap(
        size=20,
        accent_color=accent_color,
        dpr=2.0,
        rotation_deg=rotation_deg,
        progress=progress,
        done_t=done_t,
    )
    icon = QIcon(pix)
    icon.setIsMask(False)
    return icon


class TrayAnimator(QObject):
    """Drives zero-idle-CPU menu-bar emblem animations on spin, drag, and conversion progress."""

    def __init__(self, tray: QSystemTrayIcon, accent_color: str = "#F28A32", parent=None):
        super().__init__(parent)
        self._tray = tray
        self._accent = accent_color
        self._rotation_deg: float = 0.0
        self._progress: int | None = None
        self._done_t: float = 0.0
        self._converting = False
        self._wheel_open = False

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(33)  # ~30fps only while actively converting or wheel open
        self._spin_timer.timeout.connect(self._tick)

        self._detent_anim = QVariantAnimation(self)
        self._detent_anim.setDuration(420)
        self._detent_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._detent_anim.valueChanged.connect(self._on_detent)

        self._done_anim = QVariantAnimation(self)
        self._done_anim.setDuration(900)
        self._done_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._done_anim.valueChanged.connect(self._on_done)

        self._apply_icon()

    def _apply_icon(self) -> None:
        self._tray.setIcon(
            create_tray_icon(
                accent_color=self._accent,
                rotation_deg=self._rotation_deg,
                progress=self._progress,
                done_t=self._done_t,
            )
        )

    def _on_detent(self, val) -> None:
        self._rotation_deg = float(val) % 360.0
        self._apply_icon()

    def _on_done(self, val) -> None:
        self._done_t = float(val)
        self._apply_icon()

    def _sync_timer(self) -> None:
        active = (self._converting or self._wheel_open) and not should_reduce_motion()
        if active:
            if not self._spin_timer.isActive():
                self._spin_timer.start()
        else:
            self._spin_timer.stop()

    def _tick(self) -> None:
        if not (self._converting or self._wheel_open):
            self._spin_timer.stop()
            return
        step = 6.0 if self._converting else 3.2
        self._rotation_deg = (self._rotation_deg + step) % 360.0
        self._apply_icon()

    def set_accent(self, hex_color: str) -> None:
        self._accent = hex_color
        self._apply_icon()

    def pulse_turn(self, delta_deg: float = 60.0, duration_ms: int = 380) -> None:
        if should_reduce_motion() or self._converting:
            return
        self._detent_anim.stop()
        self._detent_anim.setDuration(duration_ms)
        self._detent_anim.setStartValue(self._rotation_deg)
        self._detent_anim.setEndValue(self._rotation_deg + delta_deg)
        self._detent_anim.start()

    def set_wheel_open(self, is_open: bool) -> None:
        self._wheel_open = is_open
        self._sync_timer()
        if not is_open:
            self._apply_icon()

    def set_queue_state(self, active_jobs: int, progress_pct: int, just_finished: bool) -> None:
        if active_jobs > 0:
            self._converting = True
            self._progress = progress_pct
            self._done_t = 0.0
            self._sync_timer()
            self._apply_icon()
            return

        self._converting = False
        self._progress = None
        self._sync_timer()
        if just_finished and not should_reduce_motion():
            self._done_anim.stop()
            self._done_anim.setStartValue(1.0)
            self._done_anim.setEndValue(0.0)
            self._done_anim.start()
        else:
            self._done_t = 0.0
            self._apply_icon()


def _activate_for_popover() -> None:
    """Bring Accessory NSApp forward briefly so Qt.Popup receives clicks and Esc cleanly."""
    if QGuiApplication.platformName() != "cocoa":
        return
    try:
        from AppKit import NSApp

        NSApp.activateIgnoringOtherApps_(True)
    except Exception as exc:
        logger.debug("NSApp activation for tray popover skipped: %s", exc)


def _installed_tools_summary() -> str:
    found = sum(1 for name in TOOLS_METADATA if resolver.resolve(name))
    total = len(TOOLS_METADATA)
    return f"{found} of {total} local tools ready"


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

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FileTool")
    app.setApplicationDisplayName("FileTool")
    app.setQuitOnLastWindowClosed(False)

    qsettings = QSettings("FileTool", "FileTool")
    accessory_mode = qsettings.value("accessory_mode", True, type=bool)
    set_macos_accessory_mode(accessory_mode)

    window = MainWindow()
    accent_hex = ACCENT_PRESETS[window.accent_key]["accent"]
    app.setWindowIcon(create_brand_icon(accent_hex))

    wheel_window = WheelWindow(runner=window.runner)

    key_mappings = {
        qsettings.value("trigger_convert", "Shift", type=str).lower(): "convert",
        qsettings.value("trigger_tools", "Command", type=str).lower(): "tools",
        qsettings.value("trigger_actions", "Control", type=str).lower(): "actions",
    }
    monitor = MacDragMonitor(key_mappings=key_mappings)

    tray = QSystemTrayIcon(create_tray_icon(accent_hex), app)
    tray_animator = TrayAnimator(tray, accent_color=accent_hex, parent=app)
    popover = TrayPopover(dark_mode=window.dark_mode, accent_key=window.accent_key)
    popover.update_state(
        wheel_enabled=qsettings.value("wheel_enabled", True, type=bool),
        key_mappings=key_mappings,
        tools_summary=_installed_tools_summary(),
    )

    def on_trigger(wheel_type: str, x: float, y: float, files: list):
        if qsettings.value("wheel_enabled", True, type=bool):
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.show_wheel(wheel_type, qt_x, qt_y, files)
            tray_animator.set_wheel_open(True)

    def on_move(x: float, y: float):
        if wheel_window.isVisible():
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.update_cursor_pos(qt_x, qt_y)

    def on_drop(wheel_type: str, x: float, y: float, files: list):
        if wheel_window.isVisible():
            qt_x, qt_y = mac_screen_to_qt_coords(x, y)
            wheel_window.trigger_drop_at(qt_x, qt_y)
        tray_animator.set_wheel_open(False)

    def on_cancel():
        wheel_window.cancel_wheel()
        tray_animator.set_wheel_open(False)

    monitor.wheel_triggered.connect(on_trigger)
    monitor.wheel_switched.connect(lambda w: (wheel_window.switch_wheel(w), tray_animator.pulse_turn(60.0, 260)))
    monitor.wheel_moved.connect(on_move)
    monitor.wheel_dropped.connect(on_drop)
    monitor.wheel_cancelled.connect(on_cancel)
    monitor.wheel_navigated.connect(wheel_window.navigate_key)

    def on_settings_saved(s: dict):
        nonlocal key_mappings
        if "key_mappings" in s:
            key_mappings = dict(s["key_mappings"])
            monitor.set_key_mappings(key_mappings)
        if "accessory_mode" in s:
            set_macos_accessory_mode(s["accessory_mode"])
        wheel_window.set_theme(window.dark_mode, window.accent_key)
        popover.update_state(
            wheel_enabled=bool(s.get("wheel_enabled", qsettings.value("wheel_enabled", True, type=bool))),
            key_mappings=key_mappings,
            tools_summary=_installed_tools_summary(),
        )

    def on_theme_updated(is_dark: bool, accent_key: str):
        new_hex = ACCENT_PRESETS.get(accent_key, ACCENT_PRESETS["amber"])["accent"]
        app.setWindowIcon(create_brand_icon(new_hex))
        tray_animator.set_accent(new_hex)
        popover.set_theme(is_dark, accent_key)

    def on_queue_progress(active_jobs: int, pct: int, just_finished: bool):
        tray_animator.set_queue_state(active_jobs, pct, just_finished)
        popover.update_state(
            wheel_enabled=qsettings.value("wheel_enabled", True, type=bool),
            key_mappings=key_mappings,
            active_jobs=active_jobs,
            progress_pct=pct if active_jobs > 0 else None,
        )
        if active_jobs > 0:
            tray.setToolTip(f"FileTool — Converting {active_jobs} file(s) ({pct}%)")
        else:
            tray.setToolTip("FileTool — Drag files & tap Shift / Cmd / Ctrl for Drag Wheel")

    window.settings_updated.connect(on_settings_saved)
    window.theme_updated.connect(on_theme_updated)
    window.queue_progress_changed.connect(on_queue_progress)
    monitor.start()

    def show_main_window():
        _activate_for_popover()
        window.show()
        window.raise_()
        window.activateWindow()
        window.logo.spin_once(60.0, 300)

    def open_prefs():
        show_main_window()
        window._open_settings()

    def open_deps():
        show_main_window()
        window._show_dep_report()

    def on_wheel_toggled(enabled: bool):
        qsettings.setValue("wheel_enabled", enabled)
        window.settings_page.sw_wheel.setChecked(enabled)
        tray_animator.pulse_turn(60.0 if enabled else -60.0, 260)

    def on_popover_files_dropped(paths: list):
        window._on_files_dropped(paths)
        show_main_window()

    popover.open_requested.connect(show_main_window)
    popover.preferences_requested.connect(open_prefs)
    popover.dependencies_requested.connect(open_deps)
    popover.quit_requested.connect(app.quit)
    popover.wheel_toggled.connect(on_wheel_toggled)
    popover.files_dropped.connect(on_popover_files_dropped)

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.Context, QSystemTrayIcon.DoubleClick):
            if popover.isVisible():
                popover.hide()
                return
            if popover.was_just_hidden():
                return
            tray_animator.pulse_turn(60.0, 300)
            popover.update_state(
                wheel_enabled=qsettings.value("wheel_enabled", True, type=bool),
                key_mappings=key_mappings,
                tools_summary=_installed_tools_summary(),
            )
            _activate_for_popover()
            popover.show_at(tray.geometry())

    tray.activated.connect(on_tray_activated)
    tray.setToolTip("FileTool — Drag files & tap Shift / Cmd / Ctrl for Drag Wheel")
    tray.show()
    QTimer.singleShot(150, lambda: tray_animator.pulse_turn(180.0, 520))

    # Load any files passed on launch (e.g. Finder Quick Action)
    cli_files = [
        Path(arg)
        for arg in unknown
        if arg and not arg.startswith("-") and Path(arg).exists()
    ]
    if cli_files:
        window._on_files_dropped(cli_files)

    # Show main window unless started with --daemon
    if not args.daemon:
        show_main_window()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
