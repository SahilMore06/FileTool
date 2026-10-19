"""macOS Native Actions, AirDrop, Float Window, Haptics, and Notifications."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("filetool.platform.mac_actions")

LAUNCH_AGENT_LABEL = "com.filetool.app"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def trigger_haptic_tick() -> None:
    """Trigger a subtle macOS trackpad haptic tick on completion."""
    try:
        from AppKit import (
            NSHapticFeedbackManager,
            NSHapticFeedbackPatternGeneric,
            NSHapticFeedbackPerformanceTimeNow,
        )
        performer = NSHapticFeedbackManager.defaultPerformer()
        if performer:
            performer.performFeedbackPattern_performanceTime_(
                NSHapticFeedbackPatternGeneric,
                NSHapticFeedbackPerformanceTimeNow,
            )
    except Exception as exc:
        logger.debug("Haptic feedback error: %s", exc)


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
            clean_title = title.replace('"', '\\"')
            clean_msg = message.replace('"', '\\"')
            script = f'display notification "{clean_msg}" with title "{clean_title}"'
            subprocess.run(["osascript", "-e", script], check=False)
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
            return posix_paths
        end tell
        '''
        res = subprocess.run(["osascript", "-e", ascript], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            # osascript returns comma-delimited strings
            return [p.strip() for p in res.stdout.strip().split(", ") if p.strip()]
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
    moved: List[str] = []

    for p in paths:
        src = Path(p)
        if src.exists():
            dest = dest_dir / src.name
            # Avoid overwrite collision
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
            shutil.move(str(src), str(dest))
            moved.append(str(dest))

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # Header with file name and close button
        header = QHBoxLayout()
        header.setSpacing(6)

        name_lbl = QLabel(Path(self.file_path).name)
        name_lbl.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 12px;")
        header.addWidget(name_lbl, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                color: #DDD;
                border: none;
                border-radius: 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #FF5F56;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # Thumbnail display
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("background: rgba(0, 0, 0, 0.3); border-radius: 8px;")
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
                from AppKit import NSWorkspace, NSBitmapImageRep, NSPNGFileType
                icon = NSWorkspace.sharedWorkspace().iconForFile_(str(p))
                icon.setSize_((128, 128))
                tiff_data = icon.TIFFRepresentation()
                rep = NSBitmapImageRep.imageRepsWithData_(tiff_data)[0]
                png_data = rep.representationUsingType_properties_(NSPNGFileType, None)
                pix = QPixmap()
                pix.loadFromData(bytes(png_data))
            except Exception:
                pass

        if pix and not pix.isNull():
            scaled = pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)

        # Frosted dark translucent glass
        painter.fillPath(path, QColor(28, 30, 36, 230))
        painter.setPen(QColor(255, 255, 255, 45))
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


_active_float_windows: List[FloatWindow] = []


def action_float(file_path: str) -> FloatWindow:
    """Open an always-on-top floating inspection window."""
    w = FloatWindow(file_path)
    _active_float_windows.append(w)
    w.show()
    return w


# --- Launch at Login (macOS LaunchAgent plist) ---

def is_launch_at_login_enabled() -> bool:
    """Check if LaunchAgent plist is installed and configured."""
    return LAUNCH_AGENT_PATH.exists()


def set_launch_at_login(enabled: bool) -> bool:
    """Enable or disable launch at login via ~/Library/LaunchAgents/com.filetool.app.plist."""
    try:
        if not enabled:
            if LAUNCH_AGENT_PATH.exists():
                subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_PATH)], check=False)
                LAUNCH_AGENT_PATH.unlink()
            return True

        # Generate plist
        LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        py_exe = sys.executable
        app_entry = str(Path(__file__).resolve().parent.parent / "app.py")

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exe}</string>
        <string>{app_entry}</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
        LAUNCH_AGENT_PATH.write_text(plist_content, encoding="utf-8")
        subprocess.run(["launchctl", "load", str(LAUNCH_AGENT_PATH)], check=False)
        return True
    except Exception as exc:
        logger.error("Failed toggling launch at login: %s", exc)
        return False
