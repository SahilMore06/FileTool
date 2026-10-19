"""macOS Drag Detection without Accessibility Permissions.

Uses CGEventSourceButtonState, CGEventSourceFlagsState, NSEvent.mouseLocation,
and NSDragPboard. Features a pure, testable state machine for deterministic unit tests.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger("filetool.platform.drag_monitor")

# Quartz modifier bitmasks
MASK_SHIFT = 0x20000
MASK_CONTROL = 0x40000
MASK_COMMAND = 0x100000
MASK_OPTION = 0x80000

# Virtual key codes
VK_ESCAPE = 53
VK_RETURN = 36
VK_LEFT = 123
VK_RIGHT = 124
VK_DOWN = 125
VK_UP = 126

# Polling intervals
INTERVAL_IDLE_MS = 100    # 10 Hz when left mouse button is UP
INTERVAL_ACTIVE_MS = 16   # 60 Hz when left mouse button is DOWN


@dataclass
class DragEvent:
    event_type: str  # "trigger", "switch", "move", "drop", "cancel", "nav"
    wheel_type: Optional[str] = None  # "convert", "tools", "actions"
    position: Tuple[float, float] = (0.0, 0.0)
    files: List[str] = field(default_factory=list)
    direction: Optional[str] = None  # "left", "right", "up", "down", "apply", "cancel"


class DragStateMachine:
    """
    Pure state machine tracking mouse button, file drag activation,
    modifier quick-taps (<= 400ms), and wheel trigger/switch/drop lifecycle.
    """

    def __init__(
        self,
        key_mappings: Optional[Dict[str, str]] = None,
        tap_timeout: float = 0.400,
        drag_threshold_px: float = 4.0,
    ) -> None:
        # Key -> Wheel Type mapping
        self.key_mappings = key_mappings or {
            "shift": "convert",
            "command": "tools",
            "control": "actions",
        }
        self.tap_timeout = tap_timeout
        self.drag_threshold_px = drag_threshold_px

        # Button & drag state
        self.is_button_down: bool = False
        self.mouse_down_pos: Tuple[float, float] = (0.0, 0.0)
        self.mouse_down_change_count: int = -1
        self.last_idle_change_count: int = -1
        self.is_file_drag: bool = False
        self.dragged_files: List[str] = []

        # Modifier tap tracking
        self.modifier_down_key: Optional[str] = None
        self.modifier_down_time: float = 0.0
        self.modifier_multi_pressed: bool = False

        # Wheel state
        self.wheel_open: bool = False
        self.active_wheel_type: Optional[str] = None
        self.last_mouse_pos: Tuple[float, float] = (0.0, 0.0)

    def update(
        self,
        timestamp: float,
        left_down: bool,
        flags: int,
        mouse_pos: Tuple[float, float],
        pasteboard_change_count: int,
        get_files_fn: Callable[[], List[str]],
        key_states: Optional[Dict[int, bool]] = None,
    ) -> List[DragEvent]:
        """
        Evaluate one tick of the state machine.
        Returns list of emitted DragEvents.
        """
        events: List[DragEvent] = []

        # Check key states (Escape, Arrow keys, Return) while wheel is open
        if self.wheel_open and key_states:
            if key_states.get(VK_ESCAPE):
                self.wheel_open = False
                self.active_wheel_type = None
                events.append(DragEvent(event_type="cancel", position=mouse_pos))
                return events
            if key_states.get(VK_RETURN):
                events.append(DragEvent(event_type="nav", direction="apply", position=mouse_pos))
            elif key_states.get(VK_LEFT):
                events.append(DragEvent(event_type="nav", direction="left", position=mouse_pos))
            elif key_states.get(VK_RIGHT):
                events.append(DragEvent(event_type="nav", direction="right", position=mouse_pos))
            elif key_states.get(VK_UP):
                events.append(DragEvent(event_type="nav", direction="up", position=mouse_pos))
            elif key_states.get(VK_DOWN):
                events.append(DragEvent(event_type="nav", direction="down", position=mouse_pos))

        # 1. Handle Mouse Down / Up transitions
        if left_down and not self.is_button_down:
            # Mouse down started
            self.is_button_down = True
            self.mouse_down_pos = mouse_pos
            self.mouse_down_change_count = pasteboard_change_count
            self.is_file_drag = False
            self.dragged_files = []
            self.modifier_down_key = None
            self.modifier_multi_pressed = False

        elif not left_down:
            # Mouse is up (idle or released)
            self.last_idle_change_count = pasteboard_change_count
            if self.is_button_down:
                # Mouse button released
                self.is_button_down = False
                if self.wheel_open:
                    # Dropped on wheel!
                    events.append(
                        DragEvent(
                            event_type="drop",
                            wheel_type=self.active_wheel_type,
                            position=mouse_pos,
                            files=list(self.dragged_files),
                        )
                    )
                    self.wheel_open = False
                    self.active_wheel_type = None
                self.is_file_drag = False
                self.dragged_files = []
                self.modifier_down_key = None
                self.modifier_multi_pressed = False
                return events

        cursor_moved = (mouse_pos != self.last_mouse_pos)

        # 2. While mouse button is held, detect if active file drag
        if self.is_button_down:
            if not self.is_file_drag:
                dx = mouse_pos[0] - self.mouse_down_pos[0]
                dy = mouse_pos[1] - self.mouse_down_pos[1]
                dist = math.hypot(dx, dy)
                pb_changed = (
                    (pasteboard_change_count != self.mouse_down_change_count)
                    or (self.last_idle_change_count != -1 and pasteboard_change_count != self.last_idle_change_count)
                )
                if dist > self.drag_threshold_px and pb_changed:
                    files = get_files_fn()
                    if files:
                        self.is_file_drag = True
                        self.dragged_files = files

            # If wheel is open and cursor moved, emit move event
            if self.wheel_open and cursor_moved:
                events.append(
                    DragEvent(
                        event_type="move",
                        wheel_type=self.active_wheel_type,
                        position=mouse_pos,
                        files=list(self.dragged_files),
                    )
                )

        # 3. Track modifier keys (immediate trigger on press, stays open)
        active_keys = set()
        if flags & MASK_SHIFT:
            active_keys.add("shift")
        if flags & MASK_CONTROL:
            active_keys.add("control")
        if flags & MASK_COMMAND:
            active_keys.add("command")
        if flags & MASK_OPTION:
            active_keys.add("option")

        if len(active_keys) > 1:
            # Multiple modifiers held: invalidate tap candidate
            self.modifier_multi_pressed = True
            self.modifier_down_key = None
        elif len(active_keys) == 1:
            key = next(iter(active_keys))
            if self.modifier_down_key is None and not self.modifier_multi_pressed:
                # Key pressed down: trigger immediately on press!
                self.modifier_down_key = key
                self.modifier_down_time = timestamp
                trigger_events = self._handle_modifier_action(
                    key,
                    mouse_pos,
                    get_files_fn=get_files_fn,
                    pasteboard_change_count=pasteboard_change_count,
                )
                events.extend(trigger_events)
            elif self.modifier_down_key != key:
                self.modifier_multi_pressed = True
                self.modifier_down_key = None
        elif len(active_keys) == 0:
            if self.modifier_down_key is not None and not self.modifier_multi_pressed:
                # Key was released: if wheel is not open yet, check tap timeout
                press_duration = timestamp - self.modifier_down_time
                released_key = self.modifier_down_key
                self.modifier_down_key = None
                if not self.wheel_open and press_duration <= self.tap_timeout:
                    tap_events = self._handle_modifier_action(
                        released_key,
                        mouse_pos,
                        get_files_fn=get_files_fn,
                        pasteboard_change_count=pasteboard_change_count,
                    )
                    events.extend(tap_events)
            self.modifier_multi_pressed = False
            self.modifier_down_key = None

        self.last_mouse_pos = mouse_pos
        return events

    def _handle_modifier_action(
        self,
        key: str,
        mouse_pos: Tuple[float, float],
        get_files_fn: Optional[Callable[[], List[str]]] = None,
        pasteboard_change_count: int = -1,
    ) -> List[DragEvent]:
        events: List[DragEvent] = []
        # Modifier triggers radial wheel during an active file drag
        if not self.is_button_down:
            return events

        target_wheel = self.key_mappings.get(key.lower())
        if not target_wheel:
            return events

        # Query dragged files if not yet loaded
        if not self.dragged_files and get_files_fn:
            files = get_files_fn()
            if files:
                self.is_file_drag = True
                self.dragged_files = files

        # Only trigger or switch if file drag is active
        if not self.is_file_drag or not self.dragged_files:
            return events

        if not self.wheel_open:
            self.wheel_open = True
            self.active_wheel_type = target_wheel
            events.append(
                DragEvent(
                    event_type="trigger",
                    wheel_type=target_wheel,
                    position=mouse_pos,
                    files=list(self.dragged_files),
                )
            )
        else:
            # Tapping another trigger switches wheels
            if self.active_wheel_type != target_wheel:
                self.active_wheel_type = target_wheel
                events.append(
                    DragEvent(
                        event_type="switch",
                        wheel_type=target_wheel,
                        position=mouse_pos,
                        files=list(self.dragged_files),
                    )
                )

        return events

    # Backwards compatibility alias
    _handle_modifier_tap = _handle_modifier_action

    def cancel_wheel(self) -> None:
        """Manually close the wheel."""
        self.wheel_open = False
        self.active_wheel_type = None


class MacDragMonitor(QObject):
    """
    Live monitor running on Qt event loop.
    Polls at 60 Hz when button is down, 10 Hz when idle.
    """

    wheel_triggered = Signal(str, float, float, list)  # wheel_type, mouse_x, mouse_y, files
    wheel_switched = Signal(str)                        # wheel_type
    wheel_moved = Signal(float, float)                  # mouse_x, mouse_y
    wheel_dropped = Signal(str, float, float, list)     # wheel_type, mouse_x, mouse_y, files
    wheel_cancelled = Signal()
    wheel_navigated = Signal(str)                       # "left", "right", "up", "down", "apply"

    def __init__(self, key_mappings: Optional[Dict[str, str]] = None, parent=None):
        super().__init__(parent)
        self.state_machine = DragStateMachine(key_mappings=key_mappings)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_tick)
        self._current_interval_ms = INTERVAL_IDLE_MS
        self.finder_enter_enabled: bool = True
        self._last_return_down: bool = False

        # PyObjC / Quartz imports
        self._quartz_available = False
        self._init_pyobjc()

    def _init_pyobjc(self) -> None:
        try:
            import Quartz
            from AppKit import NSDragPboard, NSEvent, NSPasteboard, NSURL, NSPasteboardURLReadingFileURLsOnlyKey
            self._Quartz = Quartz
            self._NSEvent = NSEvent
            self._NSPasteboard = NSPasteboard
            self._NSURL = NSURL
            self._NSDragPboard = NSDragPboard
            self._URLReadingOptions = {NSPasteboardURLReadingFileURLsOnlyKey: True}
            self._drag_pb = NSPasteboard.pasteboardWithName_(NSDragPboard)
            self._quartz_available = True
            logger.info("MacDragMonitor initialized successfully with PyObjC Quartz/AppKit.")
        except Exception as exc:
            logger.warning("MacDragMonitor PyObjC initialization failed: %s", exc)
            self._quartz_available = False

    def start(self) -> None:
        if not self._quartz_available:
            logger.warning("Cannot start drag monitor: Quartz/AppKit unavailable.")
            return

        # Register instant flags-changed monitor for 0ms latency modifier response
        try:
            from AppKit import NSEventMaskFlagsChanged
            self._flags_monitor = self._NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged,
                self._on_flags_changed,
            )
        except Exception as exc:
            logger.debug("Failed registering global flags monitor: %s", exc)
            self._flags_monitor = None

        self._timer.start(INTERVAL_IDLE_MS)
        logger.info("MacDragMonitor polling started (10 Hz idle, 60 Hz active).")

    def _on_flags_changed(self, event) -> None:
        """Called by macOS the instant any modifier key changes state globally."""
        self._poll_tick()

    def stop(self) -> None:
        if hasattr(self, "_flags_monitor") and self._flags_monitor:
            try:
                self._NSEvent.removeMonitor_(self._flags_monitor)
                self._flags_monitor = None
            except Exception:
                pass
        self._timer.stop()
        logger.info("MacDragMonitor polling stopped.")

    def set_key_mappings(self, mappings: Dict[str, str]) -> None:
        self.state_machine.key_mappings = mappings

    def _read_drag_files(self) -> List[str]:
        """Read and validate file paths from NSDragPboard using multi-level fallback."""
        import os
        import urllib.parse
        files: List[str] = []

        def _clean_path(raw: str) -> Optional[str]:
            if not raw or not isinstance(raw, str):
                return None
            p = str(raw).strip()
            if p.startswith("file://localhost/"):
                p = p[16:]
            elif p.startswith("file://"):
                p = p[7:]
            p = urllib.parse.unquote(p)
            p = os.path.abspath(p)
            if os.path.exists(p):
                return p
            return None

        # Method 1: Check standard pasteboard string types (public.url, public.file-url, utf8)
        for t in ["public.file-url", "public.url", "Apple URL pasteboard type", "public.utf8-plain-text"]:
            try:
                val = self._drag_pb.stringForType_(t)
                if val:
                    for line in val.splitlines():
                        c = _clean_path(line)
                        if c and c not in files:
                            files.append(c)
            except Exception:
                pass

        if files:
            return files

        # Method 2: NSFilenamesPboardType (standard Finder drag type)
        try:
            plist = self._drag_pb.propertyListForType_("NSFilenamesPboardType")
            if plist and isinstance(plist, (list, tuple)):
                for item in plist:
                    clean = _clean_path(item)
                    if clean and clean not in files:
                        files.append(clean)
                if files:
                    return files
        except Exception as exc:
            logger.debug("propertyListForType_ failed: %s", exc)

        # Method 3: pasteboardItems inspection
        try:
            items = self._drag_pb.pasteboardItems()
            if items:
                for item in items:
                    for t in ["public.file-url", "public.url", "public.utf8-plain-text"]:
                        val = item.stringForType_(t)
                        if val:
                            for line in val.splitlines():
                                clean = _clean_path(line)
                                if clean and clean not in files:
                                    files.append(clean)
                if files:
                    return files
        except Exception as exc:
            logger.debug("pasteboardItems fallback failed: %s", exc)

        # Method 4: readObjectsForClasses_options_ using NSURL
        try:
            urls = self._drag_pb.readObjectsForClasses_options_([self._NSURL], None)
            if urls:
                for u in urls:
                    try:
                        p = u.path()
                        if p:
                            clean = _clean_path(p)
                            if clean and clean not in files:
                                files.append(clean)
                    except Exception:
                        pass
                if files:
                    return files
        except Exception as exc:
            logger.debug("readObjectsForClasses_options_ failed: %s", exc)

        # Method 5: Finder current frontmost selection fallback
        try:
            from filetool.platform.mac_actions import get_finder_selection
            sel = get_finder_selection()
            if sel:
                for s in sel:
                    clean = _clean_path(s)
                    if clean and clean not in files:
                        files.append(clean)
                if files:
                    return files
        except Exception as exc:
            logger.debug("get_finder_selection fallback failed: %s", exc)

        return files

    def _poll_tick(self) -> None:
        if not self._quartz_available:
            return

        now = time.monotonic()

        # 1. Query mouse button state: Combine Quartz and Cocoa
        left_down = bool(
            self._Quartz.CGEventSourceButtonState(
                self._Quartz.kCGEventSourceStateCombinedSessionState,
                self._Quartz.kCGMouseButtonLeft,
            )
            or self._Quartz.CGEventSourceButtonState(
                self._Quartz.kCGEventSourceStateHIDSystemState,
                self._Quartz.kCGMouseButtonLeft,
            )
            or (self._NSEvent.pressedMouseButtons() & 1)
        )

        # 2. Adjust polling interval dynamically
        needed_interval = INTERVAL_ACTIVE_MS if (left_down or self.state_machine.wheel_open) else INTERVAL_IDLE_MS
        if needed_interval != self._current_interval_ms:
            self._current_interval_ms = needed_interval
            self._timer.setInterval(needed_interval)

        # 3. Query modifier flags: Combine Quartz CombinedSession + HID + Cocoa
        flags = int(
            self._Quartz.CGEventSourceFlagsState(
                self._Quartz.kCGEventSourceStateCombinedSessionState
            )
            | self._Quartz.CGEventSourceFlagsState(
                self._Quartz.kCGEventSourceStateHIDSystemState
            )
            | self._NSEvent.modifierFlags()
        )

        # 4. Query mouse position
        loc = self._NSEvent.mouseLocation()
        mouse_pos = (float(loc.x), float(loc.y))

        # 5. Query pasteboard change count
        change_count = int(self._drag_pb.changeCount())

        # 6. Query key states if wheel is open (Escape, Return, Arrows)
        key_states: Optional[Dict[int, bool]] = None
        return_down = bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_RETURN))

        if self.state_machine.wheel_open:
            key_states = {
                VK_ESCAPE: bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_ESCAPE)),
                VK_RETURN: return_down,
                VK_LEFT: bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_LEFT)),
                VK_RIGHT: bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_RIGHT)),
                VK_UP: bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_UP)),
                VK_DOWN: bool(self._Quartz.CGEventSourceKeyState(self._Quartz.kCGEventSourceStateCombinedSessionState, VK_DOWN)),
            }
        elif self.finder_enter_enabled:
            # Stretch goal: Return pressed on Finder selection opens format wheel
            if self._last_return_down and not return_down:
                try:
                    from AppKit import NSWorkspace
                    front = NSWorkspace.sharedWorkspace().frontmostApplication()
                    if front and front.bundleIdentifier() == "com.apple.finder":
                        from filetool.platform.mac_actions import get_finder_selection
                        sel_files = get_finder_selection()
                        if sel_files:
                            self.wheel_triggered.emit("convert", mouse_pos[0], mouse_pos[1], sel_files)
                except Exception as exc:
                    logger.debug("Finder enter trigger check error: %s", exc)

        self._last_return_down = return_down

        # 7. Step state machine
        events = self.state_machine.update(
            timestamp=now,
            left_down=left_down,
            flags=flags,
            mouse_pos=mouse_pos,
            pasteboard_change_count=change_count,
            get_files_fn=self._read_drag_files,
            key_states=key_states,
        )

        # 8. Dispatch events
        for ev in events:
            if ev.event_type == "trigger" and ev.wheel_type:
                self.wheel_triggered.emit(ev.wheel_type, ev.position[0], ev.position[1], ev.files)
            elif ev.event_type == "switch" and ev.wheel_type:
                self.wheel_switched.emit(ev.wheel_type)
            elif ev.event_type == "move":
                self.wheel_moved.emit(ev.position[0], ev.position[1])
            elif ev.event_type == "drop" and ev.wheel_type:
                self.wheel_dropped.emit(ev.wheel_type, ev.position[0], ev.position[1], ev.files)
            elif ev.event_type == "cancel":
                self.wheel_cancelled.emit()
            elif ev.event_type == "nav" and ev.direction:
                self.wheel_navigated.emit(ev.direction)
