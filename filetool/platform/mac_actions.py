"""macOS Native Actions, AirDrop, Float Window, Haptics, and Notifications."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as xml_escape

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("filetool.platform.mac_actions")

LAUNCH_AGENT_LABEL = "com.fluxora.app"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _escape_applescript_str(text: str) -> str:
    """Escape backslashes, quotes, and newlines for AppleScript literals."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


_HAPTIC_BRIDGE: Optional[tuple] = None
_HAPTIC_BRIDGE_MODULE: object = None


def _get_haptic_bridge() -> Optional[tuple]:
    """Lazily resolve and cache NSHapticFeedbackManager performer and enums."""
    global _HAPTIC_BRIDGE, _HAPTIC_BRIDGE_MODULE
    active_appkit = sys.modules.get("AppKit")
    if _HAPTIC_BRIDGE is not None and active_appkit is not None and active_appkit is _HAPTIC_BRIDGE_MODULE:
        return _HAPTIC_BRIDGE
    try:
        from AppKit import (
            NSHapticFeedbackManager,
            NSHapticFeedbackPatternAlignment,
            NSHapticFeedbackPatternGeneric,
            NSHapticFeedbackPatternLevelChange,
            NSHapticFeedbackPerformanceTimeDefault,
            NSHapticFeedbackPerformanceTimeDrawCompleted,
            NSHapticFeedbackPerformanceTimeNow,
        )

        performer = NSHapticFeedbackManager.defaultPerformer()
        if not performer:
            return None
        _HAPTIC_BRIDGE_MODULE = sys.modules.get("AppKit")
        _HAPTIC_BRIDGE = (
            performer,
            {
                "generic": NSHapticFeedbackPatternGeneric,
                "alignment": NSHapticFeedbackPatternAlignment,
                "level_change": NSHapticFeedbackPatternLevelChange,
            },
            {
                "now": NSHapticFeedbackPerformanceTimeNow,
                "draw_completed": NSHapticFeedbackPerformanceTimeDrawCompleted,
                "default": NSHapticFeedbackPerformanceTimeDefault,
            },
            NSHapticFeedbackPatternGeneric,
            NSHapticFeedbackPerformanceTimeNow,
        )
        return _HAPTIC_BRIDGE
    except Exception as exc:
        logger.debug("Haptic bridge unavailable: %s", exc)
        return None


def trigger_haptic_tick(pattern: str = "generic", when: str = "now") -> bool:
    """Trigger a macOS Force Touch trackpad haptic pulse.

    Args:
        pattern: One of ``"generic"``, ``"alignment"``, or ``"level_change"``.
        when: Performance timing hint (``"now"``, ``"draw_completed"``, ``"default"``).

    Returns:
        ``True`` if ``NSHapticFeedbackManager`` performed the pulse, else ``False``.
    """
    bridge = _get_haptic_bridge()
    if bridge is None:
        return False
    performer, pattern_map, timing_map, default_pattern, default_when = bridge
    try:
        chosen_pattern = pattern_map.get(pattern.lower(), default_pattern)
        chosen_when = timing_map.get(when.lower(), default_when)
        performer.performFeedbackPattern_performanceTime_(chosen_pattern, chosen_when)
        return True
    except Exception as exc:
        logger.debug("Haptic feedback error: %s", exc)
    return False


def play_tactile_feedback(pattern: str = "generic", sound_name: Optional[str] = None) -> bool:
    """Trigger trackpad haptic feedback paired with an optional subtle macOS system sound."""
    fired = trigger_haptic_tick(pattern=pattern)
    if sound_name and QGuiApplication.platformName() != "offscreen":
        play_sound(sound_name)
    return fired


def trigger_haptic_sequence(
    steps: Sequence[Tuple[int, str]],
    parent=None,
) -> List[QTimer]:
    """Schedule a rhythmic sequence of ``(delay_ms, pattern)`` trackpad haptic pulses."""
    timers: List[QTimer] = []
    for delay_ms, pattern in steps:
        delay = max(0, int(delay_ms))
        if delay == 0:
            trigger_haptic_tick(pattern=pattern)
            continue
        timer = QTimer(parent)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda p=pattern: trigger_haptic_tick(pattern=p))
        timer.start(delay)
        timers.append(timer)
    return timers


def play_sound(named: str = "Fuse") -> None:
    """Play a system sound effect.

    Args:
        named: Name of the system sound to play (e.g., "Fuse", "Pop", "Glass", "Hero", "Morse")
    """
    try:
        from AppKit import NSSound
        sound = NSSound.soundNamed_(named)
        if sound:
            sound.play()
    except Exception as exc:
        logger.debug("Sound playback error: %s", exc)


def reveal_in_finder(path: Path | str) -> bool:
    """Highlight and select a file in Finder."""
    target = Path(path)
    if not target.exists():
        logger.warning("Cannot reveal non-existent path: %s", target)
        return False

    try:
        from AppKit import NSWorkspace, NSURL
        url = NSURL.fileURLWithPath_(str(target.resolve()))
        ws = NSWorkspace.sharedWorkspace()
        ws.activateFileViewerSelectingURLs_([url])
        return True
    except Exception:
        # Fallback to subprocess
        try:
            subprocess.run(["open", "-R", str(target.resolve())], check=True)
            return True
        except Exception as exc:
            logger.warning("Finder reveal failed: %s", exc)
            return False


def send_completion_notification(title: str, message: str, file_path: Optional[str] = None) -> None:
    """
    Send a native macOS user notification with Reveal in Finder action.
    """
    try:
        from Foundation import NSUserNotification, NSUserNotificationCenter
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        notif = NSUserNotification.alloc().init()
        notif.setTitle_(title)
        notif.setInformativeText_(message)
        if file_path:
            notif.setUserInfo_({"path": file_path})
            notif.setHasActionButton_(True)
            notif.setActionButtonTitle_("Reveal")
        center.deliverNotification_(notif)
    except Exception:
        # Fallback to osascript
        try:
            clean_title = _escape_applescript_str(title)
            clean_msg = _escape_applescript_str(message)
            script = f'display notification "{clean_msg}" with title "{clean_title}"'
            subprocess.run(["osascript", "-e", script], capture_output=True, check=False)
        except Exception as exc:
            logger.debug("Notification error: %s", exc)


def get_finder_selection() -> List[str]:
    """Return list of selected POSIX paths in Finder via AppleScript."""
    try:
        ascript = '''
        tell application "Finder"
            set sel to selection as alias list
            set posix_paths to {}
            repeat with item_ref in sel
                set end of posix_paths to POSIX path of item_ref
            end repeat
            set AppleScript's text item delimiters to linefeed
            return posix_paths as text
        end tell
        '''
        res = subprocess.run(
            ["osascript", "-e", ascript],
            capture_output=True,
            text=True,
            check=False,
            timeout=0.4,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [p.rstrip("/") if len(p) > 1 else p for p in res.stdout.splitlines() if p.strip()]
    except Exception as exc:
        logger.debug("Failed getting Finder selection: %s", exc)
    return []


# --- File Actions ---

def action_airdrop(paths: List[str]) -> bool:
    """Send files via macOS AirDrop."""
    if not paths:
        return False
    try:
        from AppKit import NSSharingService, NSSharingServiceNameSendViaAirDrop, NSURL
        service = NSSharingService.sharingServiceNamed_(NSSharingServiceNameSendViaAirDrop)
        if service:
            urls = [NSURL.fileURLWithPath_(p) for p in paths if os.path.exists(p)]
            if urls:
                service.performWithItems_(urls)
                return True
    except Exception as exc:
        logger.warning("AirDrop action failed: %s", exc)
    return False


def action_copy_files(paths: List[str]) -> bool:
    """Copy file references to the macOS clipboard."""
    if not paths:
        return False
    try:
        from AppKit import NSPasteboard, NSURL
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        urls = [NSURL.fileURLWithPath_(p) for p in paths if os.path.exists(p)]
        if urls:
            pb.writeObjects_(urls)
            return True
    except Exception as exc:
        logger.warning("Copy files failed: %s", exc)
    return False


def action_copy_path(paths: List[str]) -> str:
    """Copy POSIX paths to the system clipboard."""
    if not paths:
        return ""
    joined = "\n".join(paths)
    clipboard = QGuiApplication.clipboard()
    if clipboard:
        clipboard.setText(joined)
    return joined


def action_open_in_terminal(paths: List[str]) -> bool:
    """Open Terminal.app at the containing directory."""
    if not paths:
        return False
    target = Path(paths[0])
    folder = target if target.is_dir() else target.parent
    try:
        subprocess.run(["open", "-a", "Terminal", str(folder)], check=True)
        return True
    except Exception as exc:
        logger.warning("Open in Terminal failed: %s", exc)
        return False


def action_move_files(paths: List[str], target_folder: Optional[str] = None) -> List[str]:
    """Move files to a chosen destination folder."""
    if not paths:
        return []

    if not target_folder:
        chosen = QFileDialog.getExistingDirectory(None, "Select Destination Folder", str(Path.home()))
        if not chosen:
            return []
        target_folder = chosen

    dest_dir = Path(target_folder)
    dest_dir.mkdir(parents=True, exist_ok=True)
    resolved_dest_dir = dest_dir.resolve()
    moved: List[str] = []

    for p in paths:
        src = Path(p)
        if not src.exists():
            continue
        if src.parent.resolve() == resolved_dest_dir:
            moved.append(str(src))
            continue
        dest = dest_dir / src.name
        # Avoid overwrite collision
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1
        try:
            shutil.move(str(src), str(dest))
            moved.append(str(dest))
        except OSError as exc:
            logger.warning("Failed moving %s to %s: %s", src, dest, exc)

    return moved


# --- Float Window ---

class FloatWindow(QWidget):
    """Small always-on-top floating thumbnail window for quick inspection."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._drag_pos = QPoint()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(220, 260)
        self._init_ui()

    def _init_ui(self) -> None:
        from filetool.ui.styles import get_tokens

        tokens = get_tokens(dark_mode=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # Header with file name and close button
        header = QHBoxLayout()
        header.setSpacing(6)

        name_lbl = QLabel(Path(self.file_path).name)
        name_lbl.setStyleSheet(
            f"color: {tokens['text_primary']}; font-weight: 600; font-size: 12px;"
        )
        header.addWidget(name_lbl, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Close preview (Esc)")
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {tokens['bg_surface2']};
                color: {tokens['text_secondary']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
                font-size: 11px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {tokens['error']};
                color: {tokens['text_primary']};
                border-color: {tokens['error']};
            }}
            QPushButton:focus {{
                border: 1.5px solid {tokens['border_focus']};
            }}
            """
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # Thumbnail display
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet(
            f"background: {tokens['bg_main']}; border: 1px solid {tokens['border']}; border-radius: 8px;"
        )
        layout.addWidget(self.img_lbl, stretch=1)

        self._load_thumbnail()

    def _load_thumbnail(self) -> None:
        p = Path(self.file_path)
        ext = p.suffix.lower().lstrip(".")
        pix: Optional[QPixmap] = None

        if ext in ("jpg", "jpeg", "png", "webp", "heic", "tiff", "bmp", "gif"):
            try:
                pix = QPixmap(str(p))
            except Exception:
                pass

        if not pix or pix.isNull():
            # Get native macOS icon
            try:
                from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace

                icon = NSWorkspace.sharedWorkspace().iconForFile_(str(p))
                icon.setSize_((128, 128))
                tiff_data = icon.TIFFRepresentation()
                reps = NSBitmapImageRep.imageRepsWithData_(tiff_data) if tiff_data else None
                if reps:
                    png_data = reps[0].representationUsingType_properties_(NSPNGFileType, None)
                    if png_data:
                        pix = QPixmap()
                        pix.loadFromData(bytes(png_data))
            except Exception:
                pass

        if pix and not pix.isNull():
            scaled = pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)

    def paintEvent(self, event) -> None:
        from filetool.ui.styles import get_tokens

        tokens = get_tokens(dark_mode=True)
        bg = QColor(tokens["bg_surface"])
        bg.setAlpha(235)
        border = QColor(tokens["border_strong"])

        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1.0, self.height() - 1.0, 14, 14)

        painter.fillPath(path, bg)
        painter.setPen(border)
        painter.drawPath(path)
        painter.end()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


_active_float_windows: List[FloatWindow] = []


def _discard_float_window(win: FloatWindow) -> None:
    try:
        _active_float_windows.remove(win)
    except ValueError:
        pass


def action_float(file_path: str) -> FloatWindow:
    """Open an always-on-top floating inspection window."""
    w = FloatWindow(file_path)
    w.setAttribute(Qt.WA_DeleteOnClose, True)
    _active_float_windows.append(w)
    w.destroyed.connect(lambda *_args, win=w: _discard_float_window(win))
    w.show()
    return w


# --- Launch at Login (macOS LaunchAgent plist) ---

def is_launch_at_login_enabled() -> bool:
    """Check if LaunchAgent plist is installed and configured."""
    return LAUNCH_AGENT_PATH.exists()


def set_launch_at_login(enabled: bool) -> bool:
    """Enable or disable launch at login via ~/Library/LaunchAgents/com.fluxora.app.plist."""
    try:
        domain = f"gui/{os.getuid()}" if hasattr(os, "getuid") else "gui/501"
        if not enabled:
            if LAUNCH_AGENT_PATH.exists():
                res = subprocess.run(
                    ["launchctl", "bootout", domain, str(LAUNCH_AGENT_PATH)],
                    capture_output=True,
                    check=False,
                )
                if res.returncode != 0:
                    subprocess.run(
                        ["launchctl", "unload", str(LAUNCH_AGENT_PATH)],
                        capture_output=True,
                        check=False,
                    )
                LAUNCH_AGENT_PATH.unlink()
            return True

        # Generate plist
        LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        py_exe = xml_escape(sys.executable)
        app_entry = xml_escape(str(Path(__file__).resolve().parent.parent / "app.py"))
        work_dir = xml_escape(str(Path(__file__).resolve().parent.parent.parent))
        label = xml_escape(LAUNCH_AGENT_LABEL)

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exe}</string>
        <string>{app_entry}</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{work_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
        LAUNCH_AGENT_PATH.write_text(plist_content, encoding="utf-8")
        subprocess.run(
            ["launchctl", "bootout", f"{domain}/{LAUNCH_AGENT_LABEL}"],
            capture_output=True,
            check=False,
        )
        res = subprocess.run(
            ["launchctl", "bootstrap", domain, str(LAUNCH_AGENT_PATH)],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            subprocess.run(
                ["launchctl", "load", str(LAUNCH_AGENT_PATH)],
                capture_output=True,
                check=False,
            )
        return True
    except Exception as exc:
        logger.error("Failed toggling launch at login: %s", exc)
        return False
