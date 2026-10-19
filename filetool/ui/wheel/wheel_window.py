"""macOS Drag Wheel Overlay Window.

Borderless, transparent, always-on-top, non-activating, joins all Spaces.
Handles drag events, angle hit-testing, 60fps animations, keyboard navigation,
and dispatches jobs to Runner and native actions.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from filetool.core.registry import registry
from filetool.core.runner import ConversionJob, JobRunner, JobStatus
from filetool.core.utils import get_unique_output_path
from filetool.platform.mac_actions import (
    action_airdrop,
    action_copy_files,
    action_copy_path,
    action_float,
    action_move_files,
    action_open_in_terminal,
    reveal_in_finder,
    send_completion_notification,
    trigger_haptic_tick,
)
from filetool.platform.mac_window import (
    clamp_window_to_screen,
    configure_overlay_window,
    show_without_activating,
)
from filetool.ui.wheel.animations import (
    CANCEL_DURATION_MS,
    CANCEL_END_SCALE,
    DONE_DURATION_MS,
    DROP_COLLAPSE_DURATION_MS,
    DROP_FLASH_DURATION_MS,
    ERROR_SHAKE_AMPLITUDE_PX,
    ERROR_SHAKE_DURATION_MS,
    HOVER_DURATION_MS,
    OPEN_DURATION_MS,
    OPEN_END_SCALE,
    OPEN_OVERSHOOT_SCALE,
    OPEN_START_SCALE,
    STAGGER_INTERVAL_MS,
    SWITCH_DURATION_MS,
    SWITCH_ROTATION_DEG,
    ease_out_back,
    ease_out_quad,
    shake_offset,
    should_reduce_motion,
)
from filetool.ui.wheel.geometry import (
    HitResult,
    SegmentArc,
    hit_test,
    layout_segments,
    navigate_direction,
)
from filetool.ui.wheel.wheel_painter import WheelPainter, WheelState

logger = logging.getLogger("filetool.ui.wheel.window")

WINDOW_SIZE = 520


def normalize_file_path(p: str) -> str:
    """Normalize file URLs and decode percent-encoded characters."""
    if not p:
        return ""
    if p.startswith("file://localhost/"):
        p = p[16:]
    elif p.startswith("file://"):
        p = p[7:]
    import urllib.parse
    p = urllib.parse.unquote(p)
    return os.path.abspath(p)


class WheelWindow(QWidget):
    """Radial overlay window centered at cursor during file drags."""

    closed = Signal()

    def __init__(self, runner: Optional[JobRunner] = None, parent=None):
        super().__init__(parent)
        self.runner = runner or JobRunner()
        self.painter = WheelPainter()

        # Window styling
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(WINDOW_SIZE, WINDOW_SIZE)

        # State
        self.wheel_type: str = "convert"  # "convert", "tools", "actions"
        self.dragged_files: List[str] = []
        self.primary_segments: List[SegmentArc] = []
        self.secondary_segments: Optional[List[SegmentArc]] = None
        self.hovered_index: int = -1
        self.hovered_ring: int = 1
        self.hover_progress: float = 0.0

        # Animation states
        self.open_scale: float = 1.0
        self.open_opacity: float = 1.0
        self.segment_stagger: List[float] = []
        self.switch_rotation: float = 0.0
        self.switch_opacity: float = 1.0

        self.drop_state: str = "none"
        self.drop_progress: float = 0.0
        self.job_progress: int = 0
        self.shake_offset_x: float = 0.0

        self.file_icon: Optional[QPixmap] = None
        self.is_dropping: bool = False
        self.current_job_id: Optional[str] = None

        # Animations
        self._open_anim: Optional[QVariantAnimation] = None
        self._hover_anim: Optional[QVariantAnimation] = None
        self._switch_anim: Optional[QVariantAnimation] = None
        self._drop_anim: Optional[QVariantAnimation] = None
        self._cancel_anim: Optional[QVariantAnimation] = None
        self._shake_anim: Optional[QVariantAnimation] = None

        # Connect runner signals
        self.runner.signals.progress.connect(self._on_job_progress)
        self.runner.signals.completed.connect(self._on_job_completed)
        self.runner.signals.failed.connect(self._on_job_failed)

        # Apply native macOS level & collection behavior
        configure_overlay_window(self)

    # --- Lifecycle & Opening ---

    def show_wheel(self, wheel_type: str, cursor_x: float, cursor_y: float, files: List[str]) -> None:
        """Open the wheel at the given cursor coordinates."""
        self.wheel_type = wheel_type
        clean_files = [normalize_file_path(f) for f in files]
        self.dragged_files = [f for f in clean_files if f and os.path.exists(f)]
        if not self.dragged_files:
            logger.debug("show_wheel called with no valid files: raw=%s clean=%s", files, clean_files)
            return

        # Stop any pending cancel animations
        if self._cancel_anim and self._cancel_anim.state() == QVariantAnimation.Running:
            self._cancel_anim.stop()

        self.is_dropping = False
        self.drop_state = "none"
        self.drop_progress = 0.0
        self.job_progress = 0
        self.hovered_index = -1
        self.hover_progress = 0.0
        self.open_opacity = 1.0
        self.open_scale = 1.0

        # Load file icon
        self._load_file_icon(self.dragged_files[0])

        # Populate segments
        self._populate_segments()

        # If coordinates are invalid or offscreen, fallback to current cursor
        if cursor_x <= 0 and cursor_y <= 0:
            cpos = QCursor.pos()
            cursor_x, cursor_y = float(cpos.x()), float(cpos.y())

        # Position clamped to screen
        pos_x, pos_y = clamp_window_to_screen(cursor_x, cursor_y, WINDOW_SIZE, WINDOW_SIZE)
        self.move(pos_x, pos_y)

        # Start open animation
        self._start_open_animation()

        # Show without stealing focus
        show_without_activating(self)

    def switch_wheel(self, new_type: str) -> None:
        """Smoothly switch between Convert, Tools, and Actions wheels."""
        if self.is_dropping or self.wheel_type == new_type:
            return

        self.wheel_type = new_type
        self._populate_segments()
        self.hovered_index = -1
        self.hover_progress = 0.0

        # Run switch animation
        if self._switch_anim and self._switch_anim.state() == QVariantAnimation.Running:
            self._switch_anim.stop()

        self._switch_anim = QVariantAnimation(self)
        self._switch_anim.setDuration(SWITCH_DURATION_MS)
        self._switch_anim.setStartValue(0.0)
        self._switch_anim.setEndValue(1.0)

        def _on_switch_step(val: float):
            # Rotation: swing from -SWITCH_ROTATION_DEG to 0
            self.switch_rotation = (1.0 - val) * -SWITCH_ROTATION_DEG
            # Crossfade
            self.switch_opacity = 0.4 + 0.6 * val
            self.update()

        self._switch_anim.valueChanged.connect(_on_switch_step)
        self._switch_anim.start()

    def cancel_wheel(self) -> None:
        """Cancel and close the wheel with shrink/fade animation."""
        if self.is_dropping:
            return

        if self._cancel_anim and self._cancel_anim.state() == QVariantAnimation.Running:
            return

        self._cancel_anim = QVariantAnimation(self)
        self._cancel_anim.setDuration(CANCEL_DURATION_MS)
        self._cancel_anim.setStartValue(0.0)
        self._cancel_anim.setEndValue(1.0)

        def _on_cancel_step(val: float):
            self.open_opacity = 1.0 - val
            self.open_scale = 1.0 - (1.0 - CANCEL_END_SCALE) * val
            self.update()

        def _on_cancel_done():
            self.hide()
            self.closed.emit()

        self._cancel_anim.valueChanged.connect(_on_cancel_step)
        self._cancel_anim.finished.connect(_on_cancel_done)
        self._cancel_anim.start()

    # --- Segments Population ---

    def _populate_segments(self) -> None:
        if not self.dragged_files:
            self.primary_segments = []
            self.secondary_segments = None
            return

        # Check if folder or mixed selections -> Force File Actions wheel only
        has_folder = any(os.path.isdir(p) for p in self.dragged_files)
        extensions = {Path(p).suffix.lower().lstrip(".") for p in self.dragged_files if not os.path.isdir(p)}
        is_mixed = len(extensions) > 1

        active_type = self.wheel_type
        if has_folder or is_mixed:
            active_type = "actions"

        items: List[dict] = []
        secondary_items: Optional[List[dict]] = None

        if active_type == "convert":
            ext = next(iter(extensions)) if extensions else ""
            available = registry.list_outputs(ext, available_only=False)

            if len(available) <= 8:
                for fmt in available:
                    items.append({
                        "label": fmt.upper(),
                        "icon": fmt.lower(),
                        "action_type": "convert",
                        "action_data": fmt.lower(),
                    })
            else:
                # Top 7 outputs + "More..." for second ring
                top_outputs = available[:7]
                remaining = available[7:]

                for fmt in top_outputs:
                    items.append({
                        "label": fmt.upper(),
                        "icon": fmt.lower(),
                        "action_type": "convert",
                        "action_data": fmt.lower(),
                    })

                more_sub_items = [
                    {
                        "label": fmt.upper(),
                        "icon": fmt.lower(),
                        "action_type": "convert",
                        "action_data": fmt.lower(),
                    }
                    for fmt in remaining
                ]

                items.append({
                    "label": "MORE…",
                    "icon": "convert",
                    "action_type": "more",
                    "action_data": None,
                    "sub_items": more_sub_items,
                })

        elif active_type == "tools":
            ext = next(iter(extensions)) if extensions else ""
            category = registry.get_category_for_ext(ext)

            if category == "Images":
                items = [
                    {"label": "COMPRESS", "icon": "compress", "action_type": "tool", "action_data": "compress_image"},
                    {"label": "RESIZE", "icon": "resize", "action_type": "tool", "action_data": "resize_image"},
                    {"label": "ROTATE", "icon": "rotate", "action_type": "tool", "action_data": "rotate_image"},
                    {"label": "CROP", "icon": "crop", "action_type": "tool", "action_data": "crop_image"},
                    {"label": "METADATA", "icon": "metadata", "action_type": "tool", "action_data": "strip_metadata"},
                    {"label": "TO PDF", "icon": "pdf", "action_type": "tool", "action_data": "to_pdf"},
                ]
            elif category == "Video":
                items = [
                    {"label": "COMPRESS", "icon": "compress", "action_type": "tool", "action_data": "compress_video"},
                    {"label": "TRIM", "icon": "trim", "action_type": "tool", "action_data": "trim_video"},
                    {"label": "SPLIT", "icon": "split", "action_type": "tool", "action_data": "split_video"},
                    {"label": "METADATA", "icon": "metadata", "action_type": "tool", "action_data": "strip_metadata"},
                ]
            elif category == "Audio":
                items = [
                    {"label": "TRIM", "icon": "trim", "action_type": "tool", "action_data": "trim_audio"},
                    {"label": "COMPRESS", "icon": "compress", "action_type": "tool", "action_data": "compress_audio"},
                ]
            elif category in ("Documents", "Other") and ext == "pdf":
                items = [
                    {"label": "COMPRESS", "icon": "compress", "action_type": "tool", "action_data": "compress_pdf"},
                    {"label": "ROTATE", "icon": "rotate", "action_type": "tool", "action_data": "rotate_pdf"},
                    {"label": "SPLIT", "icon": "split", "action_type": "tool", "action_data": "split_pdf"},
                    {"label": "MERGE", "icon": "merge", "action_type": "tool", "action_data": "merge_pdf"},
                    {"label": "METADATA", "icon": "metadata", "action_type": "tool", "action_data": "strip_metadata"},
                ]
            else:
                items = [
                    {"label": "COMPRESS", "icon": "compress", "action_type": "tool", "action_data": "compress_generic"},
                    {"label": "METADATA", "icon": "metadata", "action_type": "tool", "action_data": "strip_metadata"},
                ]

        elif active_type == "actions":
            items = [
                {"label": "AIRDROP", "icon": "airdrop", "action_type": "action", "action_data": "airdrop"},
                {"label": "FLOAT", "icon": "float", "action_type": "action", "action_data": "float"},
                {"label": "COPY", "icon": "copy", "action_type": "action", "action_data": "copy"},
                {"label": "MOVE", "icon": "move", "action_type": "action", "action_data": "move"},
                {"label": "PATH", "icon": "copy_path", "action_type": "action", "action_data": "copy_path"},
                {"label": "TERMINAL", "icon": "terminal", "action_type": "action", "action_data": "terminal"},
            ]

        self.primary_segments = layout_segments(items, ring=1)
        self.secondary_segments = None

    def _load_file_icon(self, file_path: str) -> None:
        try:
            from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
            icon = NSWorkspace.sharedWorkspace().iconForFile_(file_path)
            icon.setSize_((64, 64))
            tiff = icon.TIFFRepresentation()
            rep = NSBitmapImageRep.imageRepsWithData_(tiff)[0]
            png = rep.representationUsingType_properties_(NSPNGFileType, None)
            pix = QPixmap()
            pix.loadFromData(bytes(png))
            self.file_icon = pix
        except Exception:
            self.file_icon = None

    # --- Animations ---

    def _start_open_animation(self) -> None:
        reduce_motion = should_reduce_motion()

        if self._open_anim and self._open_anim.state() == QVariantAnimation.Running:
            self._open_anim.stop()

        n = len(self.primary_segments)
        total_duration = OPEN_DURATION_MS if reduce_motion else (OPEN_DURATION_MS + n * STAGGER_INTERVAL_MS)
        self.segment_stagger = [0.0] * n

        self._open_anim = QVariantAnimation(self)
        self._open_anim.setDuration(total_duration)
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)

        def _on_open_step(progress: float):
            if reduce_motion:
                self.open_opacity = progress
                self.open_scale = 1.0
                self.segment_stagger = [1.0] * n
            else:
                self.open_opacity = min(1.0, progress * 1.5)
                # Overshoot curve
                self.open_scale = OPEN_START_SCALE + (OPEN_END_SCALE - OPEN_START_SCALE) * ease_out_back(progress)

                # Segment stagger progress
                elapsed_ms = progress * total_duration
                for i in range(n):
                    start_ms = i * STAGGER_INTERVAL_MS
                    seg_prog = max(0.0, min(1.0, (elapsed_ms - start_ms) / float(OPEN_DURATION_MS)))
                    self.segment_stagger[i] = ease_out_quad(seg_prog)

            self.update()

        self._open_anim.valueChanged.connect(_on_open_step)
        self._open_anim.start()

    def _update_hover(self, index: int, ring: int) -> None:
        if self.hovered_index == index and self.hovered_ring == ring:
            return

        self.hovered_index = index
        self.hovered_ring = ring

        # Check if hovering "More..." segment to open secondary ring
        if ring == 1 and 0 <= index < len(self.primary_segments):
            seg = self.primary_segments[index]
            if seg.sub_items:
                self.secondary_segments = seg.sub_items
            else:
                self.secondary_segments = None
        elif ring == 0:
            self.secondary_segments = None

        # Hover animation
        if self._hover_anim and self._hover_anim.state() == QVariantAnimation.Running:
            self._hover_anim.stop()

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(HOVER_DURATION_MS)
        self._hover_anim.setStartValue(0.0)
        self._hover_anim.setEndValue(1.0)

        def _on_hover_step(val: float):
            self.hover_progress = val
            self.update()

        self._hover_anim.valueChanged.connect(_on_hover_step)
        self._hover_anim.start()

    # --- Mouse & Hit Testing ---

    def update_cursor_pos(self, global_x: float, global_y: float) -> None:
        """Called by MacDragMonitor during drag tracking."""
        if self.is_dropping:
            return

        # Convert global coordinates to window local
        local_x = global_x - self.x()
        local_y = global_y - self.y()

        cx = WINDOW_SIZE / 2.0
        cy = WINDOW_SIZE / 2.0
        dx = local_x - cx
        dy = local_y - cy

        res = hit_test(dx, dy, self.primary_segments, self.secondary_segments)
        if res.hit_type == "segment":
            self._update_hover(res.index, ring=1)
        elif res.hit_type == "secondary":
            self._update_hover(res.index, ring=2)
        elif res.hit_type == "hub":
            self._update_hover(-1, ring=0)
        else:
            self._update_hover(-1, ring=1)

    # --- Drag & Drop Handling ---

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            pos = event.position()
            self.update_cursor_pos(self.x() + pos.x(), self.y() + pos.y())

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            pos = event.position()
            self.update_cursor_pos(self.x() + pos.x(), self.y() + pos.y())

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._update_hover(-1, ring=1)

    def dropEvent(self, event: QDropEvent) -> None:
        event.acceptProposedAction()
        pos = event.position()
        self.trigger_drop_at(self.x() + pos.x(), self.y() + pos.y())

    def trigger_drop_at(self, global_x: float, global_y: float) -> None:
        """Execute action for segment under cursor at drop time."""
        if self.is_dropping:
            return

        local_x = global_x - self.x()
        local_y = global_y - self.y()
        cx = WINDOW_SIZE / 2.0
        cy = WINDOW_SIZE / 2.0
        dx = local_x - cx
        dy = local_y - cy

        res = hit_test(dx, dy, self.primary_segments, self.secondary_segments)

        if res.hit_type in ("hub", "outside"):
            # Center drop or outside drop = cancel!
            self.cancel_wheel()
            return

        chosen_seg: Optional[SegmentArc] = res.segment
        if not chosen_seg:
            self.cancel_wheel()
            return

        self._execute_segment(chosen_seg)

    # --- Keyboard Navigation ---

    def navigate_key(self, direction: str) -> None:
        """Handle directional navigation from monitor or keyboard."""
        if self.is_dropping or not self.primary_segments:
            return

        if direction == "apply":
            if self.hovered_index >= 0 and self.hovered_index < len(self.primary_segments):
                self._execute_segment(self.primary_segments[self.hovered_index])
            return

        if direction == "cancel":
            self.cancel_wheel()
            return

        new_idx = navigate_direction(self.hovered_index, direction, self.primary_segments)
        self._update_hover(new_idx, ring=1)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        if k == Qt.Key_Escape:
            self.cancel_wheel()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.navigate_key("apply")
        elif k == Qt.Key_Left:
            self.navigate_key("left")
        elif k == Qt.Key_Right:
            self.navigate_key("right")
        elif k == Qt.Key_Up:
            self.navigate_key("up")
        elif k == Qt.Key_Down:
            self.navigate_key("down")
        else:
            super().keyPressEvent(event)

    # --- Execution & Animation Pipeline ---

    def _execute_segment(self, seg: SegmentArc) -> None:
        self.is_dropping = True

        # Phase 1: Flash & Collapse ring into hub
        self.drop_state = "flash"
        self.drop_progress = 0.0

        if self._drop_anim and self._drop_anim.state() == QVariantAnimation.Running:
            self._drop_anim.stop()

        self._drop_anim = QVariantAnimation(self)
        self._drop_anim.setDuration(DROP_FLASH_DURATION_MS + DROP_COLLAPSE_DURATION_MS)
        self._drop_anim.setStartValue(0.0)
        self._drop_anim.setEndValue(1.0)

        flash_threshold = DROP_FLASH_DURATION_MS / float(DROP_FLASH_DURATION_MS + DROP_COLLAPSE_DURATION_MS)

        def _on_drop_step(val: float):
            if val < flash_threshold:
                self.drop_state = "flash"
                self.drop_progress = val / flash_threshold
            else:
                self.drop_state = "collapse"
                self.drop_progress = (val - flash_threshold) / (1.0 - flash_threshold)
            self.update()

        def _on_collapse_done():
            self._start_action_execution(seg)

        self._drop_anim.valueChanged.connect(_on_drop_step)
        self._drop_anim.finished.connect(_on_collapse_done)
        self._drop_anim.start()

    def _start_action_execution(self, seg: SegmentArc) -> None:
        self.drop_state = "progress"
        self.job_progress = 10
        self.update()

        action_type = seg.action_type
        action_data = seg.action_data
        files = list(self.dragged_files)

        if action_type == "convert":
            # Run via Runner
            target_ext = str(action_data)
            src_path = Path(files[0])
            job = ConversionJob(
                src_path=src_path,
                dest_ext=target_ext,
                target_dir=src_path.parent,
                overwrite=False,
            )
            self.current_job_id = job.id
            self.runner.add_job(job)
            self.runner.start_job(job.id)

        elif action_type == "tool":
            self._run_tool_action(str(action_data), files)

        elif action_type == "action":
            self._run_native_action(str(action_data), files)

    def _run_tool_action(self, tool_name: str, files: List[str]) -> None:
        src = Path(files[0])
        out_dir = src.parent

        def _worker():
            try:
                self.job_progress = 40
                self.update()

                out_path = src
                if tool_name == "compress_image":
                    from filetool.core.tools.compress import compress_image
                    cand = out_dir / f"{src.stem}_compressed{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = compress_image(src, dest, quality=60)
                elif tool_name == "compress_video":
                    from filetool.core.tools.compress import compress_video
                    cand = out_dir / f"{src.stem}_compressed{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = compress_video(src, dest, crf=28)
                elif tool_name == "compress_pdf":
                    from filetool.core.tools.compress import compress_pdf
                    cand = out_dir / f"{src.stem}_compressed{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = compress_pdf(src, dest, setting="/ebook")
                elif tool_name == "rotate_image":
                    from filetool.core.tools.resize import rotate_image
                    cand = out_dir / f"{src.stem}_rotated{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = rotate_image(src, dest, degrees=90)
                elif tool_name == "rotate_pdf":
                    from filetool.core.tools.resize import rotate_pdf
                    cand = out_dir / f"{src.stem}_rotated{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = rotate_pdf(src, dest, degrees=90)
                elif tool_name == "strip_metadata":
                    from filetool.core.tools.metadata import strip_image_metadata, strip_pdf_metadata
                    cand = out_dir / f"{src.stem}_clean{src.suffix}"
                    dest = get_unique_output_path(cand)
                    if src.suffix.lower() == ".pdf":
                        out_path = strip_pdf_metadata(src, dest)
                    else:
                        out_path = strip_image_metadata(src, dest)
                elif tool_name == "to_pdf":
                    from filetool.core.tools.merge import merge_images_to_pdf
                    cand = out_dir / f"{src.stem}.pdf"
                    dest = get_unique_output_path(cand)
                    out_path = merge_images_to_pdf([src], dest)
                else:
                    cand = out_dir / f"{src.stem}_processed{src.suffix}"
                    dest = get_unique_output_path(cand)
                    out_path = dest

                self._on_action_finished(str(out_path))
            except Exception as exc:
                logger.error("Tool execution error: %s", exc, exc_info=True)
                self._on_action_error(str(exc))

        QTimer.singleShot(50, _worker)

    def _run_native_action(self, action_name: str, files: List[str]) -> None:
        try:
            self.job_progress = 50
            self.update()

            success = False
            if action_name == "airdrop":
                success = action_airdrop(files)
            elif action_name == "float":
                w = action_float(files[0])
                success = w is not None
            elif action_name == "copy":
                success = action_copy_files(files)
            elif action_name == "move":
                moved = action_move_files(files)
                success = len(moved) > 0
            elif action_name == "copy_path":
                path_str = action_copy_path(files)
                success = bool(path_str)
            elif action_name == "terminal":
                success = action_open_in_terminal(files)

            if success:
                self._on_action_finished(files[0])
            else:
                raise RuntimeError(f"Native action '{action_name}' failed")
        except Exception as exc:
            logger.error("Action error: %s", exc)
            self._on_action_error(str(exc))

    # --- Runner Callbacks & Completion Animations ---

    def _on_job_progress(self, job_id: str, percent: int) -> None:
        if self.current_job_id == job_id:
            self.job_progress = percent
            self.update()

    def _on_job_completed(self, job_id: str, output_path: str) -> None:
        if self.current_job_id == job_id:
            self._on_action_finished(output_path)

    def _on_job_failed(self, job_id: str, err: str, tail: str) -> None:
        if self.current_job_id == job_id:
            self._on_action_error(err)

    def _on_action_finished(self, out_path: str) -> None:
        self.drop_state = "done"
        self.job_progress = 100
        self.update()

        # Trigger haptic tick
        trigger_haptic_tick()

        # Send notification
        send_completion_notification(
            title="FileTool Action Complete",
            message=f"Output saved: {Path(out_path).name}",
            file_path=out_path,
        )

        # Close after brief checkmark display
        QTimer.singleShot(DONE_DURATION_MS, self._finish_and_close)

    def _on_action_error(self, err_msg: str) -> None:
        self.drop_state = "error"
        self.update()

        # Error shake animation
        if self._shake_anim and self._shake_anim.state() == QVariantAnimation.Running:
            self._shake_anim.stop()

        self._shake_anim = QVariantAnimation(self)
        self._shake_anim.setDuration(ERROR_SHAKE_DURATION_MS)
        self._shake_anim.setStartValue(0.0)
        self._shake_anim.setEndValue(1.0)

        def _on_shake_step(val: float):
            self.shake_offset_x = shake_offset(val, ERROR_SHAKE_AMPLITUDE_PX)
            self.update()

        def _on_shake_done():
            self.shake_offset_x = 0.0
            QTimer.singleShot(600, self._finish_and_close)

        self._shake_anim.valueChanged.connect(_on_shake_step)
        self._shake_anim.finished.connect(_on_shake_done)
        self._shake_anim.start()

    def _finish_and_close(self) -> None:
        self.hide()
        self.is_dropping = False
        self.current_job_id = None
        self.closed.emit()

    # --- Paint Event ---

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        state = WheelState(
            wheel_type=self.wheel_type,
            primary_segments=self.primary_segments,
            secondary_segments=self.secondary_segments,
            hovered_index=self.hovered_index,
            hovered_ring=self.hovered_ring,
            hover_progress=self.hover_progress,
            open_scale=self.open_scale,
            open_opacity=self.open_opacity,
            segment_stagger_progress=self.segment_stagger,
            switch_rotation=self.switch_rotation,
            switch_opacity=self.switch_opacity,
            drop_state=self.drop_state,
            drop_progress=self.drop_progress,
            job_progress=self.job_progress,
            shake_offset_x=self.shake_offset_x,
            file_path=self.dragged_files[0] if self.dragged_files else None,
            file_name=Path(self.dragged_files[0]).name if self.dragged_files else "",
            file_icon=self.file_icon,
        )
        self.painter.paint(painter, self.width(), self.height(), state)
