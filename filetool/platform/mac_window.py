"""macOS Native Window Configuration via PyObjC.

Sets window level (NSStatusWindowLevel / always-on-top), collection behaviors
(all spaces and full-screen auxiliary), and ensures window display without
stealing focus or activating the app.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

logger = logging.getLogger("filetool.platform.mac_window")

# Native constants
NS_STATUS_WINDOW_LEVEL = 25  # Floats above normal windows and status items
NS_FLOATING_WINDOW_LEVEL = 3

# NSWindowCollectionBehavior
NS_COLLECTION_CAN_JOIN_ALL_SPACES = 1 << 0
NS_COLLECTION_MOVE_TO_ACTIVE_SPACE = 1 << 1
NS_COLLECTION_FULL_SCREEN_AUXILIARY = 1 << 8


def get_ns_window(widget: QWidget):
    """Retrieve PyObjC NSWindow pointer from a QWidget's native winId."""
    try:
        import objc
        view_ptr = int(widget.winId())
        ns_view = objc.objc_object(c_void_p=view_ptr)
        return ns_view.window()
    except Exception as exc:
        logger.debug("Failed getting native NSWindow: %s", exc)
        return None


def configure_overlay_window(widget: QWidget) -> bool:
    """
    Configure QWidget to behave as a seamless, non-activating macOS overlay window:
    - Joins all Spaces and full-screen apps
    - Stays on top at NSStatusWindowLevel
    - Does not hide on app deactivation
    """
    ns_win = get_ns_window(widget)
    if not ns_win:
        return False

    try:
        # 1. Window Level: Above standard windows and spaces
        ns_win.setLevel_(NS_STATUS_WINDOW_LEVEL)

        # 2. Collection Behavior: Visible on all desktops, spaces, and over fullscreen apps
        behavior = NS_COLLECTION_CAN_JOIN_ALL_SPACES | NS_COLLECTION_FULL_SCREEN_AUXILIARY
        ns_win.setCollectionBehavior_(behavior)

        # 3. Do not hide when another application is active
        ns_win.setHidesOnDeactivate_(False)

        # 4. Accept mouse tracking and events
        ns_win.setIgnoresMouseEvents_(False)
        ns_win.setAcceptsMouseMovedEvents_(True)

        return True
    except Exception as exc:
        logger.warning("Error configuring native NSWindow: %s", exc)
        return False


def show_without_activating(widget: QWidget) -> None:
    """
    Display window without focus stealing or activating FileTool.
    Preserves active focus in Finder, Desktop, etc.
    """
    widget.setAttribute(Qt.WA_ShowWithoutActivating, True)
    widget.show()
    widget.raise_()
    ns_win = get_ns_window(widget)
    if ns_win:
        try:
            ns_win.orderFrontRegardless()
        except Exception as exc:
            logger.debug("orderFrontRegardless failed: %s", exc)


def clamp_window_to_screen(
    center_x: float,
    center_y: float,
    window_width: int,
    window_height: int,
) -> Tuple[int, int]:
    """
    Given cursor position (center_x, center_y), clamp top-left position
    so that the window is fully inside the screen bounds.
    """
    cursor_pt = QPoint(int(center_x), int(center_y))
    screen = QGuiApplication.screenAt(cursor_pt) or QGuiApplication.primaryScreen()
    if not screen:
        return (int(center_x - window_width // 2), int(center_y - window_height // 2))

    geom = screen.availableGeometry()

    desired_x = int(center_x - window_width // 2)
    desired_y = int(center_y - window_height // 2)

    clamped_x = max(geom.left(), min(desired_x, geom.right() - window_width))
    clamped_y = max(geom.top(), min(desired_y, geom.bottom() - window_height))

    return (clamped_x, clamped_y)


def mac_screen_to_qt_coords(ns_x: float, ns_y: float) -> Tuple[float, float]:
    """
    Convert macOS NSEvent screen coordinates (origin bottom-left of primary screen)
    to Qt desktop coordinates (origin top-left of primary screen).
    """
    primary = QGuiApplication.primaryScreen()
    if not primary:
        return (ns_x, ns_y)
    screen_h = primary.geometry().height()
    return (ns_x, screen_h - ns_y)
