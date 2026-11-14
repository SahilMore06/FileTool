"""First-boot starter install animation, interactive haptic intro, and legal consent window."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from typing import Dict, List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from filetool.core.deps import TOOLS_METADATA, resolver
from filetool.core.legal import LEGAL_VERSION, render_legal_html
from filetool.platform.mac_actions import (
    play_tactile_feedback,
    trigger_haptic_sequence,
    trigger_haptic_tick,
)
from filetool.ui.components import (
    IOSSwitch,
    LogoWidget,
    ThemeToggle,
    _build_emblem_petal,
    draw_vector_icon,
)
from filetool.ui.styles import ACCENT_PRESETS, get_stylesheet, get_tokens
from filetool.ui.wheel.animations import ease_out_back, ease_out_quad, shake_offset, should_reduce_motion
from filetool.ui.wheel.geometry import hit_test_tangerine, layout_segments
from filetool.ui.wheel.wheel_painter import WheelPainter, WheelState

logger = logging.getLogger("filetool.ui.onboarding")

_SHADOW_MARGIN = 16

_SANDBOX_ITEMS: Dict[str, List[dict]] = {
    "convert": [
        {"label": ".JPG", "icon_name": "jpg", "action_type": "convert", "action_data": "jpg"},
        {"label": ".WEBP", "icon_name": "webp", "action_type": "convert", "action_data": "webp"},
        {"label": ".PNG", "icon_name": "png", "action_type": "convert", "action_data": "png"},
        {"label": ".AVIF", "icon_name": "avif", "action_type": "convert", "action_data": "avif"},
        {"label": ".TIFF", "icon_name": "tiff", "action_type": "convert", "action_data": "tiff"},
        {"label": ".PDF", "icon_name": "pdf", "action_type": "convert", "action_data": "pdf"},
    ],
    "tools": [
        {"label": "Compress", "icon_name": "compress", "action_type": "tool", "action_data": "compress_image"},
        {"label": "Resize", "icon_name": "resize", "action_type": "tool", "action_data": "resize_image"},
        {"label": "Rotate", "icon_name": "rotate", "action_type": "tool", "action_data": "rotate_image"},
        {"label": "Crop", "icon_name": "crop", "action_type": "tool", "action_data": "crop_image"},
        {"label": "No EXIF", "icon_name": "metadata", "action_type": "tool", "action_data": "strip_metadata"},
        {"label": "To PDF", "icon_name": "to_pdf", "action_type": "tool", "action_data": "to_pdf"},
    ],
    "actions": [
        {"label": "AirDrop", "icon_name": "airdrop", "action_type": "action", "action_data": "airdrop"},
        {"label": "Float", "icon_name": "float", "action_type": "action", "action_data": "float"},
        {"label": "Copy", "icon_name": "copy", "action_type": "action", "action_data": "copy"},
        {"label": "Move", "icon_name": "move", "action_type": "action", "action_data": "move"},
        {"label": "Path", "icon_name": "copy_path", "action_type": "action", "action_data": "copy_path"},
        {"label": "Terminal", "icon_name": "terminal", "action_type": "action", "action_data": "terminal"},
    ],
}


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    k = max(0.0, min(1.0, float(t)))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * k),
        int(c1.green() + (c2.green() - c1.green()) * k),
        int(c1.blue() + (c2.blue() - c1.blue()) * k),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * k),
    )


class _StarterInstallCanvas(QWidget):
    """60fps QPainter starter install choreography + interactive haptic aperture."""

    install_milestone = Signal(int)
    install_completed = Signal()

    def __init__(self, dark_mode: bool = False, accent_key: str = "amber", parent=None):
        super().__init__(parent)
        self.setFixedSize(296, 300)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip("Click or press Space to feel the starter aperture spring")

        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"

        self._install_t: float = 0.0
        self._done_t: float = 0.0
        self._spin_deg: float = 0.0
        self._press_scale: float = 1.0
        self._hover_t: float = 0.0
        self._cursor_offset = QPointF(0.0, 0.0)
        self._milestone_idx: int = -1
        self._has_played: bool = False

        self._install_anim = QVariantAnimation(self)
        self._install_anim.setDuration(1180)
        self._install_anim.setEasingCurve(QEasingCurve.Linear)
        self._install_anim.valueChanged.connect(self._on_install_step)
        self._install_anim.finished.connect(self._on_install_done)

        self._done_anim = QVariantAnimation(self)
        self._done_anim.setDuration(750)
        self._done_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._done_anim.valueChanged.connect(self._on_done_step)

        self._spin_anim = QVariantAnimation(self)
        self._spin_anim.setDuration(380)
        self._spin_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._spin_anim.valueChanged.connect(self._on_spin_step)

        self._recoil_anim = QVariantAnimation(self)
        self._recoil_anim.setDuration(240)
        self._recoil_anim.setEasingCurve(QEasingCurve.OutBack)
        self._recoil_anim.valueChanged.connect(self._on_recoil_step)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

    def set_theme(self, dark_mode: bool, accent_key: str) -> None:
        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self.update()

    def play_install_sequence(self, emit_haptics: bool = True) -> None:
        """Play the full orbital assembly & starter verification animation."""
        self._emit_haptics = emit_haptics
        self._install_anim.stop()
        self._done_anim.stop()
        self._milestone_idx = -1

        if should_reduce_motion():
            self._install_t = 1.0
            self._done_t = 0.0
            self._spin_deg = 0.0
            self.update()
            for idx in range(4):
                self.install_milestone.emit(idx)
            if emit_haptics:
                trigger_haptic_tick("level_change")
            self.install_completed.emit()
            return

        self._install_t = 0.0
        self._done_t = 0.0
        self._install_anim.setStartValue(0.0)
        self._install_anim.setEndValue(1.0)
        self._install_anim.start()

    def stop_animations(self) -> None:
        for anim in (self._install_anim, self._done_anim, self._spin_anim, self._recoil_anim, self._hover_anim):
            anim.stop()

    def _on_install_step(self, val) -> None:
        t = float(val)
        self._install_t = t
        thresholds = (0.20, 0.42, 0.65, 0.86)
        for idx, th in enumerate(thresholds):
            if t >= th and self._milestone_idx < idx:
                self._milestone_idx = idx
                self.install_milestone.emit(idx)
                if getattr(self, "_emit_haptics", False) and idx in (1, 3):
                    trigger_haptic_tick("alignment")
        self.update()

    def _on_install_done(self) -> None:
        self._install_anim.stop()
        self._has_played = True
        self._install_t = 1.0
        if getattr(self, "_emit_haptics", False):
            play_tactile_feedback("level_change", "Glass")
        self._done_anim.stop()
        self._done_anim.setStartValue(1.0)
        self._done_anim.setEndValue(0.0)
        self._done_anim.start()
        self.install_completed.emit()

    def _on_done_step(self, val) -> None:
        self._done_t = float(val)
        self.update()

    def _on_spin_step(self, val) -> None:
        self._spin_deg = float(val) % 360.0
        self.update()

    def _on_recoil_step(self, val) -> None:
        self._press_scale = float(val)
        self.update()

    def _on_hover_step(self, val) -> None:
        self._hover_t = float(val)
        self.update()

    def trigger_tactile_pulse(self) -> None:
        """Fire a crisp spin + spring recoil + haptic pulse on click/key press."""
        trigger_haptic_tick("alignment")
        if should_reduce_motion():
            return
        self._spin_anim.stop()
        self._spin_anim.setStartValue(self._spin_deg)
        self._spin_anim.setEndValue(self._spin_deg + 120.0)
        self._spin_anim.start()

        self._recoil_anim.stop()
        self._recoil_anim.setStartValue(0.90)
        self._recoil_anim.setEndValue(1.0)
        self._recoil_anim.start()

    def enterEvent(self, event) -> None:
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._cursor_offset = QPointF(0.0, 0.0)
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        cx, cy = self.width() / 2.0, self.height() / 2.0
        pos = event.position()
        self._cursor_offset = QPointF(
            max(-8.0, min(8.0, (pos.x() - cx) * 0.05)),
            max(-8.0, min(8.0, (pos.y() - cy) * 0.05)),
        )
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.trigger_tactile_pulse()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.trigger_tactile_pulse()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        t = get_tokens(self._dark_mode, self._accent_key)
        accent = QColor(t["accent"])
        success = QColor(t["success"])
        border = QColor(t["border_strong"])
        surface = QColor(t["bg_surface2"])
        fg = QColor(t["text_primary"])
        fg_sec = QColor(t["text_secondary"])

        cx = self.width() / 2.0 + self._cursor_offset.x() * 0.55
        cy = self.height() / 2.0 - 10.0 + self._cursor_offset.y() * 0.55

        prog = self._install_t
        halo_alpha = int((42 + 34 * max(self._hover_t, self._done_t)) * min(1.0, prog * 1.4))
        halo_col = _lerp_color(accent, success, self._done_t * 0.75)
        halo_r = 128.0 + 14.0 * self._done_t
        halo = QRadialGradient(QPointF(cx, cy), halo_r)
        halo.setColorAt(0.25, QColor(halo_col.red(), halo_col.green(), halo_col.blue(), halo_alpha))
        halo.setColorAt(1.0, QColor(halo_col.red(), halo_col.green(), halo_col.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        # Calibration dial ring + 12 tick notches
        ring_r = 104.0
        p.save()
        p.translate(cx, cy)
        p.scale(self._press_scale, self._press_scale)

        track_pen = QPen(border, 1.4)
        p.setPen(track_pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0.0, 0.0), ring_r, ring_r)

        sweep_deg = 360.0 * ease_out_quad(min(1.0, prog / 0.94))
        ring_col = _lerp_color(accent, success, self._done_t * 0.85)
        p.setPen(QPen(ring_col, 3.0, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(-ring_r, -ring_r, ring_r * 2.0, ring_r * 2.0), 90 * 16, int(-sweep_deg * 16))

        for tick_i in range(12):
            ang = math.radians(tick_i * 30.0 - 90.0)
            active_tick = prog >= (tick_i / 12.0) * 0.92
            t_col = ring_col if active_tick else border
            p.setPen(QPen(t_col, 1.6 if tick_i % 2 == 0 else 1.0, Qt.SolidLine, Qt.RoundCap))
            r_in = ring_r - (7.0 if tick_i % 2 == 0 else 4.0)
            r_out = ring_r - 1.5
            p.drawLine(
                QPointF(r_in * math.cos(ang), r_in * math.sin(ang)),
                QPointF(r_out * math.cos(ang), r_out * math.sin(ang)),
            )

        # Expanding shockwave ring on completion
        if self._done_t > 0.02:
            burst_prog = 1.0 - self._done_t
            burst_r = 46.0 + burst_prog * 74.0
            burst_c = QColor(success.red(), success.green(), success.blue(), int(150 * self._done_t))
            p.setPen(QPen(burst_c, 2.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(0.0, 0.0), burst_r, burst_r)

        # Staggered 6-petal orbital assembly
        outer_r = 76.0
        inner_r = 31.0
        gap_rad = 0.155
        grad_hi = ring_col.lighter(124)
        grad_mid = ring_col
        grad_lo = ring_col.darker(118)

        for idx in range(6):
            start_at = 0.08 + idx * 0.075
            local_t = max(0.0, min(1.0, (prog - start_at) / 0.44))
            eased = ease_out_back(local_t, overshoot=1.35)
            petal_opacity = max(0.0, min(1.0, local_t * 1.45))
            if petal_opacity <= 0.01:
                continue

            radial_fly = (1.0 - eased) * 34.0
            rot_deg = self._spin_deg + (1.0 - eased) * -76.0
            p.save()
            p.setOpacity(petal_opacity)
            petal_scale = 0.48 + 0.52 * eased
            p.scale(petal_scale, petal_scale)
            petal = _build_emblem_petal(
                0.0,
                0.0,
                idx,
                6,
                inner_r + radial_fly * 0.45,
                outer_r + radial_fly,
                gap_rad,
                math.radians(rot_deg),
            )
            fill = QRadialGradient(QPointF(0.0, 0.0), outer_r + radial_fly)
            if idx == 0:
                fill.setColorAt(0.25, grad_hi.lighter(115))
                fill.setColorAt(0.75, grad_hi)
                fill.setColorAt(1.0, grad_mid)
            else:
                fill.setColorAt(0.25, grad_hi if idx in (1, 5) else grad_mid)
                fill.setColorAt(0.78, grad_mid)
                fill.setColorAt(1.0, grad_lo)

            p.setPen(QPen(QColor(255, 255, 255, 70 if idx == 0 else 30), 1.0))
            p.setBrush(QBrush(fill))
            p.drawPath(petal)
            p.restore()

        # Center hub aperture lock-in
        core_t = max(0.0, min(1.0, (prog - 0.35) / 0.45))
        hub_r = 24.0 * ease_out_back(core_t, 1.2)
        if hub_r > 1.0:
            p.setPen(QPen(QColor(255, 255, 255, 55), 1.1))
            p.setBrush(QColor(0x1B, 0x1D, 0x22))
            p.drawEllipse(QPointF(0.0, 0.0), hub_r, hub_r)

            dot_r = hub_r * (0.44 + 0.08 * self._hover_t)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawEllipse(QPointF(0.0, 0.0), dot_r, dot_r)

        p.restore()

        # Bottom install status readout
        if prog < 0.99:
            pct = int(round(prog * 100))
            cap = f"Preparing local engines · {pct}%"
            cap_col = fg_sec
        else:
            cap = "Ready on macOS · Click wheel to pulse"
            cap_col = fg_sec

        badge_rect = QRectF(cx - 118.0, self.height() - 32.0, 236.0, 24.0)
        p.setPen(QPen(border, 1.0))
        p.setBrush(surface)
        p.drawRoundedRect(badge_rect, 12.0, 12.0)

        p.setFont(QFont(".AppleSystemUIFont", 11, QFont.Weight.DemiBold))
        p.setPen(cap_col if prog < 0.99 else fg)
        p.drawText(badge_rect, Qt.AlignCenter, cap)
        p.end()


class _HapticWheelSandbox(QWidget):
    """Interactive miniature Finder Drag Wheel using real WheelPainter & haptic detents."""

    wheel_switched = Signal(str)
    petal_clicked = Signal(str, str)

    def __init__(self, dark_mode: bool = False, accent_key: str = "amber", parent=None):
        super().__init__(parent)
        self.setFixedSize(296, 296)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self._wheel_type = "convert"
        self._wheel_painter = WheelPainter()
        self._hovered_idx = -1
        self._hover_progress = 0.0
        self._switch_rot = 0.0
        self._switch_op = 1.0
        self._drop_state = "none"
        self._drop_prog = 0.0
        self._segments = layout_segments(_SANDBOX_ITEMS[self._wheel_type], ring=1)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(90)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_val)

        self._switch_anim = QVariantAnimation(self)
        self._switch_anim.setDuration(170)
        self._switch_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._switch_anim.valueChanged.connect(self._on_switch_val)

        self._flash_anim = QVariantAnimation(self)
        self._flash_anim.setDuration(380)
        self._flash_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._flash_anim.valueChanged.connect(self._on_flash_val)
        self._flash_anim.finished.connect(self._on_flash_done)

    def set_theme(self, dark_mode: bool, accent_key: str) -> None:
        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self.update()

    def set_wheel_type(self, wheel_type: str, emit_haptic: bool = True) -> None:
        if wheel_type not in _SANDBOX_ITEMS or wheel_type == self._wheel_type:
            return
        self._wheel_type = wheel_type
        self._segments = layout_segments(_SANDBOX_ITEMS[wheel_type], ring=1)
        self._hovered_idx = -1
        self._hover_progress = 0.0
        self._drop_state = "none"

        if emit_haptic:
            play_tactile_feedback("alignment", "Tink")

        if should_reduce_motion():
            self._switch_rot = 0.0
            self._switch_op = 1.0
            self.update()
        else:
            self._switch_anim.stop()
            self._switch_anim.setStartValue(0.0)
            self._switch_anim.setEndValue(1.0)
            self._switch_anim.start()
        self.wheel_switched.emit(wheel_type)

    def stop_animations(self) -> None:
        for anim in (self._hover_anim, self._switch_anim, self._flash_anim):
            anim.stop()

    def _on_hover_val(self, val) -> None:
        self._hover_progress = float(val)
        self.update()

    def _on_switch_val(self, val) -> None:
        v = float(val)
        self._switch_rot = (1.0 - v) * -14.0
        self._switch_op = 0.45 + 0.55 * v
        self.update()

    def _on_flash_val(self, val) -> None:
        self._drop_prog = float(val)
        self.update()

    def _on_flash_done(self) -> None:
        self._drop_state = "none"
        self._drop_prog = 0.0
        self.update()

    def _update_hover(self, pos: QPointF) -> None:
        dx = pos.x() - self.width() / 2.0
        dy = pos.y() - self.height() / 2.0
        idx = hit_test_tangerine(dx, dy, len(self._segments))
        if idx != self._hovered_idx:
            self._hovered_idx = idx
            if idx >= 0:
                trigger_haptic_tick("alignment")
            if should_reduce_motion():
                self._hover_progress = 1.0 if idx >= 0 else 0.0
                self.update()
            else:
                self._hover_anim.stop()
                self._hover_anim.setStartValue(0.15 if idx >= 0 else self._hover_progress)
                self._hover_anim.setEndValue(1.0 if idx >= 0 else 0.0)
                self._hover_anim.start()

    def mouseMoveEvent(self, event) -> None:
        self._update_hover(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hovered_idx != -1:
            self._hovered_idx = -1
            self._hover_progress = 0.0
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._hovered_idx >= 0:
            seg = self._segments[self._hovered_idx]
            play_tactile_feedback("level_change", "Pop")
            self._drop_state = "done"
            self._drop_prog = 0.0
            if not should_reduce_motion():
                self._flash_anim.stop()
                self._flash_anim.setStartValue(0.0)
                self._flash_anim.setEndValue(1.0)
                self._flash_anim.start()
            self.petal_clicked.emit(self._wheel_type, seg.label)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        preset = ACCENT_PRESETS[self._accent_key]
        state = WheelState(
            wheel_type=self._wheel_type,
            primary_segments=self._segments,
            hovered_index=self._hovered_idx,
            hovered_ring=1,
            hover_progress=self._hover_progress,
            dark_mode=self._dark_mode,
            accent_color=preset["accent"],
            accent_hover=preset["accent_hover"],
            switch_rotation=self._switch_rot,
            switch_opacity=self._switch_op,
            drop_state=self._drop_state,
            drop_progress=self._drop_prog,
            file_name="sample.heic",
            file_count=1,
        )
        self._wheel_painter.paint(p, self.width(), self.height(), state)
        p.end()


class _ConsentCheckbox(QAbstractButton):
    """Tactile animated consent toggle with haptic feedback and invalid shake."""

    def __init__(self, text: str, dark_mode: bool = False, accent_key: str = "amber", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setText(text)
        self.setMinimumHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self._check_t: float = 0.0
        self._shake_x: float = 0.0
        self._invalid: bool = False

        self._check_anim = QVariantAnimation(self)
        self._check_anim.setDuration(190)
        self._check_anim.setEasingCurve(QEasingCurve.OutBack)
        self._check_anim.valueChanged.connect(self._on_check_val)

        self._shake_anim = QVariantAnimation(self)
        self._shake_anim.setDuration(260)
        self._shake_anim.setEasingCurve(QEasingCurve.Linear)
        self._shake_anim.valueChanged.connect(self._on_shake_val)
        self._shake_anim.finished.connect(self._on_shake_done)

        self.toggled.connect(self._on_toggled)
        self.clicked.connect(lambda c: trigger_haptic_tick("level_change" if c else "alignment"))

    def set_theme(self, dark_mode: bool, accent_key: str) -> None:
        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self.update()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._check_t = 1.0 if checked else 0.0
        if checked:
            self._invalid = False
        self.update()

    def trigger_shake(self) -> None:
        self._invalid = True
        trigger_haptic_tick("generic")
        if should_reduce_motion():
            self._shake_x = 0.0
            self.update()
            return
        self._shake_anim.stop()
        self._shake_anim.setStartValue(0.0)
        self._shake_anim.setEndValue(1.0)
        self._shake_anim.start()

    def stop_animations(self) -> None:
        self._check_anim.stop()
        self._shake_anim.stop()

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self._invalid = False
        target = 1.0 if checked else 0.0
        if should_reduce_motion():
            self._check_anim.stop()
            self._check_t = target
            self.update()
            return
        self._check_anim.stop()
        self._check_anim.setStartValue(self._check_t)
        self._check_anim.setEndValue(target)
        self._check_anim.start()

    def _on_check_val(self, val) -> None:
        self._check_t = float(val)
        self.update()

    def _on_shake_val(self, val) -> None:
        self._shake_x = shake_offset(float(val), amplitude=7.0)
        self.update()

    def _on_shake_done(self) -> None:
        self._shake_x = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        t = get_tokens(self._dark_mode, self._accent_key)
        bg = QColor(t["error_subtle"] if self._invalid else t["bg_surface2"])
        border = QColor(t["error"] if self._invalid else (t["border_focus"] if self.hasFocus() else t["border"]))

        row_rect = QRectF(8.0 + self._shake_x, 1.0, max(40.0, self.width() - 16.0), self.height() - 2.0)
        p.setPen(QPen(border, 1.4 if self.hasFocus() or self._invalid else 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(row_rect, 10.0, 10.0)

        box_sz = 20.0
        box_x = 22.0 + self._shake_x
        box_y = (self.height() - box_sz) / 2.0
        box_rect = QRectF(box_x, box_y, box_sz, box_sz)

        fill_t = max(0.0, min(1.0, self._check_t))
        idle_box = QColor(t["bg_surface"])
        active_box = QColor(t["accent"])
        box_fill = _lerp_color(idle_box, active_box, fill_t)
        box_border = _lerp_color(QColor(t["error"] if self._invalid else t["border_strong"]), active_box, fill_t)

        p.setPen(QPen(box_border, 1.4))
        p.setBrush(box_fill)
        p.drawRoundedRect(box_rect, 6.0, 6.0)

        if self._check_t > 0.05:
            ink = QColor(t["accent_fg"])
            p.setPen(QPen(ink, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            k = max(0.0, min(1.0, self._check_t))
            p1 = QPointF(box_x + 5.0, box_y + 10.5)
            p2 = QPointF(box_x + 8.8, box_y + 14.2)
            p3 = QPointF(box_x + 15.2, box_y + 6.4)
            if k <= 0.45:
                seg = k / 0.45
                mid = QPointF(p1.x() + (p2.x() - p1.x()) * seg, p1.y() + (p2.y() - p1.y()) * seg)
                p.drawLine(p1, mid)
            else:
                seg = (k - 0.45) / 0.55
                p.drawLine(p1, p2)
                end = QPointF(p2.x() + (p3.x() - p2.x()) * seg, p2.y() + (p3.y() - p2.y()) * seg)
                p.drawLine(p2, end)

        text_x = int(box_x + box_sz + 12.0)
        p.setFont(QFont(".AppleSystemUIFont", 12.5, QFont.Weight.DemiBold))
        p.setPen(QColor(t["text_primary"]))
        p.drawText(
            QRectF(text_x, 0.0, max(100.0, self.width() - text_x - 12.0), float(self.height())),
            Qt.AlignVCenter | Qt.TextWordWrap,
            self.text(),
        )
        p.end()


class OnboardingWindow(QWidget):
    """Animated first-boot onboarding, haptic drag-wheel playground, and Privacy & Terms consent."""

    onboarding_completed = Signal(dict)
    onboarding_declined = Signal()
    theme_preview_changed = Signal(bool, str)

    STEP_INTRO = 0
    STEP_SANDBOX = 1
    STEP_LEGAL = 2

    def __init__(
        self,
        dark_mode: bool = False,
        accent_key: str = "amber",
        first_boot: bool = True,
        qsettings: Optional[QSettings] = None,
        initial_step: int = 0,
        initial_legal_doc: str = "privacy",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("Welcome to FileTool")
        self.resize(860, 588)

        self.qsettings = qsettings or QSettings("FileTool", "FileTool")
        self._first_boot = bool(first_boot)
        self._dark_mode = bool(dark_mode)
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self._legal_doc = "terms" if initial_legal_doc == "terms" else "privacy"
        self._current_step = 0
        self._drag_origin: Optional[QPoint] = None
        self._closing_fade = False
        self._active_haptic_timers: List[QTimer] = []

        self._entrance_anim = QVariantAnimation(self)
        self._entrance_anim.setDuration(260)
        self._entrance_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._entrance_anim.valueChanged.connect(self._on_entrance_val)

        self._exit_anim = QVariantAnimation(self)
        self._exit_anim.setDuration(220)
        self._exit_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._exit_anim.valueChanged.connect(self._on_exit_val)
        self._exit_anim.finished.connect(self._on_exit_done)

        self._pending_result: Optional[dict] = None
        self._cap_labels: List[QLabel] = []
        self._accent_btns: Dict[str, QPushButton] = {}
        self._sandbox_mode_btns: Dict[str, QPushButton] = {}
        self._step_btns: List[QPushButton] = []

        self._init_ui()
        self._apply_theme()
        self.go_to_step(initial_step, emit_haptic=False)

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("onboardingCard")
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("onboardingHeader")
        header.setFixedHeight(54)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(18, 8, 18, 8)
        h_lay.setSpacing(10)

        accent_hex = ACCENT_PRESETS[self._accent_key]["accent"]
        self.header_logo = LogoWidget(size=24, accent_color=accent_hex)
        h_lay.addWidget(self.header_logo)

        title_lbl = QLabel("FileTool")
        title_lbl.setObjectName("appTitle")
        h_lay.addWidget(title_lbl)

        self.setup_badge = QLabel("First Launch" if self._first_boot else "Tour & Legal")
        self.setup_badge.setObjectName("pillTag")
        h_lay.addWidget(self.setup_badge)

        h_lay.addStretch(1)

        for idx, text in enumerate(("1. Install && Intro", "2. Wheel && Feel", "3. Privacy && Terms")):
            btn = QPushButton(text)
            btn.setObjectName("onboardingStepPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, s=idx: self.go_to_step(s))
            h_lay.addWidget(btn)
            self._step_btns.append(btn)

        h_lay.addStretch(1)

        self.theme_toggle = ThemeToggle(is_dark=self._dark_mode)
        self.theme_toggle.setToolTip("Switch Light / Dark appearance")
        self.theme_toggle.theme_changed.connect(self._on_theme_toggled)
        h_lay.addWidget(self.theme_toggle)

        card_lay.addWidget(header)

        # Body pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_intro_page())
        self.pages.addWidget(self._build_sandbox_page())
        self.pages.addWidget(self._build_legal_page())
        card_lay.addWidget(self.pages, stretch=1)

        # Footer action bar
        footer = QWidget()
        footer.setObjectName("onboardingFooter")
        footer.setFixedHeight(58)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(20, 10, 20, 10)
        f_lay.setSpacing(10)

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._on_back)
        f_lay.addWidget(self.back_btn)

        self.decline_btn = QPushButton("Decline && Quit" if self._first_boot else "Close")
        self.decline_btn.setObjectName("dangerSubtleButton" if self._first_boot else "secondaryButton")
        self.decline_btn.setCursor(Qt.PointingHandCursor)
        self.decline_btn.clicked.connect(self._on_decline)
        f_lay.addWidget(self.decline_btn)

        f_lay.addStretch(1)

        self.skip_to_legal_btn = QPushButton("Skip Intro → Terms")
        self.skip_to_legal_btn.setObjectName("subtleLinkButton")
        self.skip_to_legal_btn.setCursor(Qt.PointingHandCursor)
        self.skip_to_legal_btn.clicked.connect(lambda: self.go_to_step(self.STEP_LEGAL))
        f_lay.addWidget(self.skip_to_legal_btn)

        self.primary_btn = QPushButton("Get Started →")
        self.primary_btn.setObjectName("primaryButton")
        self.primary_btn.setMinimumWidth(168)
        self.primary_btn.setCursor(Qt.PointingHandCursor)
        self.primary_btn.clicked.connect(self._on_primary)
        f_lay.addWidget(self.primary_btn)

        card_lay.addWidget(footer)
        outer.addWidget(self.card)

    def _build_intro_page(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setAlignment(Qt.AlignCenter)
        self.hero_canvas = _StarterInstallCanvas(self._dark_mode, self._accent_key)
        self.hero_canvas.install_milestone.connect(self._on_install_milestone)
        left_col.addWidget(self.hero_canvas, alignment=Qt.AlignCenter)

        self.replay_anim_btn = QPushButton("Replay Install Animation")
        self.replay_anim_btn.setObjectName("subtleLinkButton")
        self.replay_anim_btn.setCursor(Qt.PointingHandCursor)
        self.replay_anim_btn.clicked.connect(lambda: self.hero_canvas.play_install_sequence(emit_haptics=True))
        left_col.addWidget(self.replay_anim_btn, alignment=Qt.AlignCenter)
        lay.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addStretch(1)

        headline = QLabel("Offline conversion,\ntuned to your cursor")
        headline.setObjectName("onboardingHeadline")
        headline.setWordWrap(True)
        right_col.addWidget(headline)

        lead = QLabel(
            "Batch convert images, audio, video, PDFs, and Office files on your Mac, "
            "or tap a modifier key mid-drag in Finder to open FileTool's radial wheel."
        )
        lead.setObjectName("onboardingLead")
        lead.setWordWrap(True)
        right_col.addWidget(lead)

        cap_card = QFrame()
        cap_card.setObjectName("cardPanel")
        cap_lay = QVBoxLayout(cap_card)
        cap_lay.setContentsMargins(14, 12, 14, 12)
        cap_lay.setSpacing(8)

        found_tools = sum(1 for name in TOOLS_METADATA if resolver.resolve(name))
        total_tools = len(TOOLS_METADATA)
        cap_title = QLabel(f"Local Starter Environment ({found_tools} of {total_tools} CLI engines detected)")
        cap_title.setObjectName("onboardingSectionTitle")
        cap_lay.addWidget(cap_title)

        grid_row_1 = QHBoxLayout()
        grid_row_1.setSpacing(8)
        grid_row_2 = QHBoxLayout()
        grid_row_2.setSpacing(8)

        caps = [
            "Images · 266 pairs",
            "Media · Video & Audio",
            "PDF & Office Docs",
            "Drag Wheel · Trackpad Haptics",
        ]
        for idx, text in enumerate(caps):
            pill = QLabel(text)
            pill.setObjectName("onboardingCapabilityPill")
            pill.setProperty("ready", False)
            pill.setAlignment(Qt.AlignCenter)
            self._cap_labels.append(pill)
            (grid_row_1 if idx < 2 else grid_row_2).addWidget(pill, stretch=1)

        cap_lay.addLayout(grid_row_1)
        cap_lay.addLayout(grid_row_2)
        right_col.addWidget(cap_card)
        right_col.addStretch(1)

        lay.addLayout(right_col, stretch=1)
        return page

    def _build_sandbox_page(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(28, 18, 28, 16)
        lay.setSpacing(24)

        # Left interactive haptic wheel
        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        left_col.setAlignment(Qt.AlignCenter)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        for key, label in (("convert", "⇧ Convert"), ("tools", "⌘ Tools"), ("actions", "⌃ Actions")):
            btn = QPushButton(label)
            btn.setObjectName("filterPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._pick_sandbox_wheel(k))
            mode_row.addWidget(btn)
            self._sandbox_mode_btns[key] = btn
        left_col.addLayout(mode_row)

        self.wheel_sandbox = _HapticWheelSandbox(self._dark_mode, self._accent_key)
        self.wheel_sandbox.wheel_switched.connect(self._sync_sandbox_pills)
        self.wheel_sandbox.petal_clicked.connect(self._on_sandbox_petal_clicked)
        left_col.addWidget(self.wheel_sandbox, alignment=Qt.AlignCenter)

        self.sandbox_status = QLabel("Sweep across petals to feel Force Touch detents, or click to test")
        self.sandbox_status.setObjectName("mutedMeta")
        self.sandbox_status.setAlignment(Qt.AlignCenter)
        self.sandbox_status.setWordWrap(True)
        self.sandbox_status.setFixedWidth(296)
        left_col.addWidget(self.sandbox_status)

        lay.addLayout(left_col)

        # Right theme + quick preferences
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        sec_head = QLabel("Feel the Drag Wheel & Choose Your Look")
        sec_head.setObjectName("onboardingHeadline")
        sec_head.setStyleSheet("font-size: 18px;")
        right_col.addWidget(sec_head)

        sec_sub = QLabel("Tap Shift, Command, or Control anytime here or in Finder to switch wheels instantly.")
        sec_sub.setObjectName("onboardingLead")
        sec_sub.setWordWrap(True)
        right_col.addWidget(sec_sub)

        look_card = QFrame()
        look_card.setObjectName("cardPanel")
        look_lay = QVBoxLayout(look_card)
        look_lay.setContentsMargins(14, 12, 14, 12)
        look_lay.setSpacing(10)

        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("Appearance"))
        t_row.addStretch()
        self.ob_light_btn = QPushButton("Light")
        self.ob_light_btn.setObjectName("filterPill")
        self.ob_light_btn.setCursor(Qt.PointingHandCursor)
        self.ob_light_btn.clicked.connect(lambda: self._on_theme_toggled(False, haptic=True))
        self.ob_dark_btn = QPushButton("Dark")
        self.ob_dark_btn.setObjectName("filterPill")
        self.ob_dark_btn.setCursor(Qt.PointingHandCursor)
        self.ob_dark_btn.clicked.connect(lambda: self._on_theme_toggled(True, haptic=True))
        t_row.addWidget(self.ob_light_btn)
        t_row.addWidget(self.ob_dark_btn)
        look_lay.addLayout(t_row)

        a_row = QHBoxLayout()
        a_row.addWidget(QLabel("Accent Color"))
        a_row.addStretch()
        for key, preset in ACCENT_PRESETS.items():
            btn = QPushButton(preset["label"])
            btn.setObjectName("filterPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._on_accent_picked(k))
            a_row.addWidget(btn)
            self._accent_btns[key] = btn
        look_lay.addLayout(a_row)
        right_col.addWidget(look_card)

        beh_card = QFrame()
        beh_card.setObjectName("cardPanel")
        beh_lay = QVBoxLayout(beh_card)
        beh_lay.setContentsMargins(14, 12, 14, 12)
        beh_lay.setSpacing(10)

        accent_hex = ACCENT_PRESETS[self._accent_key]["accent"]

        w_row = QHBoxLayout()
        w_text = QVBoxLayout()
        w_text.setSpacing(1)
        w_text.addWidget(QLabel("Enable Finder Drag Wheel"))
        w_sub = QLabel("Open radial wheel on Shift / Cmd / Ctrl tap while dragging files")
        w_sub.setObjectName("mutedMeta")
        w_sub.setWordWrap(True)
        w_text.addWidget(w_sub)
        w_row.addLayout(w_text, stretch=1)
        self.sw_wheel = IOSSwitch(
            checked=self.qsettings.value("wheel_enabled", True, type=bool),
            dark_mode=self._dark_mode,
            accent_color=accent_hex,
        )
        w_row.addWidget(self.sw_wheel)
        beh_lay.addLayout(w_row)

        m_row = QHBoxLayout()
        m_text = QVBoxLayout()
        m_text.setSpacing(1)
        m_text.addWidget(QLabel("Keep in Menu Bar Only"))
        m_sub = QLabel("Run quietly in the macOS menu bar without occupying the Dock")
        m_sub.setObjectName("mutedMeta")
        m_sub.setWordWrap(True)
        m_text.addWidget(m_sub)
        m_row.addLayout(m_text, stretch=1)
        self.sw_accessory = IOSSwitch(
            checked=self.qsettings.value("accessory_mode", True, type=bool),
            dark_mode=self._dark_mode,
            accent_color=accent_hex,
        )
        m_row.addWidget(self.sw_accessory)
        beh_lay.addLayout(m_row)

        right_col.addWidget(beh_card)
        right_col.addStretch(1)
        lay.addLayout(right_col, stretch=1)
        self._sync_sandbox_pills("convert")
        return page

    def _build_legal_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 16, 28, 14)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        legal_head = QLabel("Privacy Policy & Terms of Use")
        legal_head.setObjectName("onboardingHeadline")
        legal_head.setStyleSheet("font-size: 18px;")
        legal_sub = QLabel("Review how FileTool handles files locally before launching.")
        legal_sub.setObjectName("onboardingLead")
        text_col.addWidget(legal_head)
        text_col.addWidget(legal_sub)
        top_row.addLayout(text_col, stretch=1)

        tab_box = QFrame()
        tab_box.setObjectName("tabGroup")
        tab_lay = QHBoxLayout(tab_box)
        tab_lay.setContentsMargins(3, 3, 3, 3)
        tab_lay.setSpacing(3)

        self.tab_privacy_btn = QPushButton("Privacy Policy")
        self.tab_privacy_btn.setObjectName("tabButton")
        self.tab_privacy_btn.setCursor(Qt.PointingHandCursor)
        self.tab_privacy_btn.clicked.connect(lambda: self.select_legal_doc("privacy"))

        self.tab_terms_btn = QPushButton("Terms && Conditions")
        self.tab_terms_btn.setObjectName("tabButton")
        self.tab_terms_btn.setCursor(Qt.PointingHandCursor)
        self.tab_terms_btn.clicked.connect(lambda: self.select_legal_doc("terms"))

        tab_lay.addWidget(self.tab_privacy_btn)
        tab_lay.addWidget(self.tab_terms_btn)
        top_row.addWidget(tab_box)
        lay.addLayout(top_row)

        self.legal_browser = QTextBrowser()
        self.legal_browser.setObjectName("onboardingLegalView")
        self.legal_browser.setOpenExternalLinks(False)
        self.legal_browser.setReadOnly(True)
        lay.addWidget(self.legal_browser, stretch=1)

        already_accepted = (
            not self._first_boot
            and bool(self.qsettings.value("legal_accepted", False, type=bool))
        )
        self.consent_checkbox = _ConsentCheckbox(
            "I have read and accept the FileTool Terms & Conditions and Privacy Policy",
            dark_mode=self._dark_mode,
            accent_key=self._accent_key,
        )
        self.consent_checkbox.setChecked(already_accepted)
        self.consent_checkbox.toggled.connect(self._on_consent_toggled)
        lay.addWidget(self.consent_checkbox)

        self.consent_warning = QLabel(
            "Confirm above that you have read the Privacy Policy and Terms & Conditions to continue."
        )
        self.consent_warning.setObjectName("validationWarning")
        self.consent_warning.setWordWrap(True)
        self.consent_warning.setVisible(False)
        lay.addWidget(self.consent_warning)

        return page

    # --- Navigation & Actions ---

    def start_intro(self, emit_haptics: bool = True) -> None:
        """Show the window with smooth entrance motion and trigger the starter animation."""
        self.show()
        self.raise_()
        self.activateWindow()
        self._center_on_screen()

        if not should_reduce_motion():
            self.setWindowOpacity(0.0)
            self._entrance_anim.stop()
            self._entrance_anim.setStartValue(0.0)
            self._entrance_anim.setEndValue(1.0)
            self._entrance_anim.start()
        else:
            self.setWindowOpacity(1.0)

        if self._current_step == self.STEP_INTRO:
            self.hero_canvas.play_install_sequence(emit_haptics=emit_haptics)

    def _center_on_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        geom = screen.availableGeometry()
        x = geom.center().x() - self.width() // 2
        y = geom.center().y() - self.height() // 2
        self.move(max(geom.left(), x), max(geom.top(), y))

    def go_to_step(self, step_index: int, emit_haptic: bool = True) -> None:
        step = max(0, min(2, int(step_index)))
        self._current_step = step
        self.pages.setCurrentIndex(step)
        if emit_haptic:
            trigger_haptic_tick("alignment")
            self.header_logo.spin_once(60.0, 260)

        if step == self.STEP_INTRO and self.isVisible() and not self.hero_canvas._has_played:
            self.hero_canvas.play_install_sequence(emit_haptics=emit_haptic)
        elif step == self.STEP_SANDBOX:
            self.wheel_sandbox.setFocus(Qt.OtherFocusReason)
        elif step == self.STEP_LEGAL:
            self._refresh_legal_view()

        self._update_nav_chrome()

    def _update_nav_chrome(self) -> None:
        for idx, btn in enumerate(self._step_btns):
            btn.setProperty("active", idx == self._current_step)
            btn.setProperty("done", idx < self._current_step)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.back_btn.setVisible(self._current_step > 0)
        self.skip_to_legal_btn.setVisible(self._current_step < self.STEP_LEGAL)

        if self._current_step == self.STEP_INTRO:
            self.primary_btn.setText("Get Started →")
        elif self._current_step == self.STEP_SANDBOX:
            self.primary_btn.setText("Terms && Privacy →")
        else:
            self.primary_btn.setText("Accept && Launch FileTool" if self._first_boot else "Save && Return")

    def select_legal_doc(self, doc_key: str, emit_haptic: bool = True) -> None:
        normalized = "terms" if doc_key == "terms" else "privacy"
        if normalized != self._legal_doc and emit_haptic:
            trigger_haptic_tick("alignment")
        self._legal_doc = normalized
        self._refresh_legal_view()

    def _refresh_legal_view(self) -> None:
        tokens = get_tokens(self._dark_mode, self._accent_key)
        self.legal_browser.setHtml(render_legal_html(self._legal_doc, tokens))
        self.tab_privacy_btn.setProperty("active", self._legal_doc == "privacy")
        self.tab_terms_btn.setProperty("active", self._legal_doc == "terms")
        for btn in (self.tab_privacy_btn, self.tab_terms_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_install_milestone(self, idx: int) -> None:
        if 0 <= idx < len(self._cap_labels):
            pill = self._cap_labels[idx]
            pill.setProperty("ready", True)
            pill.style().unpolish(pill)
            pill.style().polish(pill)

    def _pick_sandbox_wheel(self, wheel_type: str) -> None:
        self.wheel_sandbox.set_wheel_type(wheel_type, emit_haptic=True)
        self._sync_sandbox_pills(wheel_type)

    def _sync_sandbox_pills(self, wheel_type: str) -> None:
        for key, btn in self._sandbox_mode_btns.items():
            btn.setProperty("active", key == wheel_type)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_sandbox_petal_clicked(self, wheel_type: str, label: str) -> None:
        self.sandbox_status.setText(f"Haptic detent confirmed ({wheel_type.title()}: {label})")

    def _on_consent_toggled(self, checked: bool) -> None:
        if checked:
            self.consent_warning.setVisible(False)

    def _on_back(self) -> None:
        if self._current_step > 0:
            self.go_to_step(self._current_step - 1)

    def _on_primary(self) -> None:
        if self._current_step < self.STEP_LEGAL:
            self.go_to_step(self._current_step + 1)
            return

        if not self.consent_checkbox.isChecked():
            self.consent_warning.setVisible(True)
            self.consent_checkbox.trigger_shake()
            return

        self.complete_onboarding()

    def complete_onboarding(self, animate_exit: bool = True) -> dict:
        """Persist acceptance + preferences, trigger haptic confirmation, and emit completion."""
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.qsettings.setValue("onboarding_completed", True)
        self.qsettings.setValue("legal_accepted", True)
        self.qsettings.setValue("legal_accepted_version", LEGAL_VERSION)
        self.qsettings.setValue("legal_accepted_at", now_iso)
        self.qsettings.setValue("dark_mode", self._dark_mode)
        self.qsettings.setValue("accent_preset", self._accent_key)
        self.qsettings.setValue("wheel_enabled", self.sw_wheel.isChecked())
        self.qsettings.setValue("accessory_mode", self.sw_accessory.isChecked())
        self.qsettings.sync()

        result = {
            "onboarding_completed": True,
            "legal_accepted": True,
            "legal_accepted_version": LEGAL_VERSION,
            "legal_accepted_at": now_iso,
            "dark_mode": self._dark_mode,
            "accent_key": self._accent_key,
            "wheel_enabled": self.sw_wheel.isChecked(),
            "accessory_mode": self.sw_accessory.isChecked(),
        }

        self._active_haptic_timers.extend(
            trigger_haptic_sequence([(0, "alignment"), (110, "level_change")], parent=self)
        )
        if QGuiApplication.platformName() != "offscreen":
            play_tactile_feedback("level_change", "Hero")

        if animate_exit and self.isVisible() and not should_reduce_motion():
            self.primary_btn.setEnabled(False)
            self.primary_btn.setText("Launching FileTool…")
            self._pending_result = result
            self._closing_fade = True
            self._exit_anim.stop()
            self._exit_anim.setStartValue(1.0)
            self._exit_anim.setEndValue(0.0)
            self._exit_anim.start()
        else:
            self.onboarding_completed.emit(result)
            self.hide()
            self.close()
        return result

    def _on_decline(self) -> None:
        trigger_haptic_tick("alignment")
        self._stop_all_animations()
        self.hide()
        self.close()
        self.onboarding_declined.emit()

    def _on_entrance_val(self, val) -> None:
        self.setWindowOpacity(float(val))

    def _on_exit_val(self, val) -> None:
        self.setWindowOpacity(float(val))

    def _on_exit_done(self) -> None:
        result = self._pending_result or {}
        self._pending_result = None
        self._closing_fade = False
        self._stop_all_animations()
        self.hide()
        self.close()
        self.onboarding_completed.emit(result)

    def _on_theme_toggled(self, is_dark: bool, haptic: bool = False) -> None:
        self._dark_mode = bool(is_dark)
        if haptic:
            trigger_haptic_tick("alignment")
        self._apply_theme()
        self.theme_preview_changed.emit(self._dark_mode, self._accent_key)

    def _on_accent_picked(self, accent_key: str) -> None:
        if accent_key in ACCENT_PRESETS and self._accent_key != accent_key:
            self._accent_key = accent_key
            trigger_haptic_tick("alignment")
            self._apply_theme()
            self.theme_preview_changed.emit(self._dark_mode, self._accent_key)

    def _apply_theme(self) -> None:
        self.setStyleSheet(get_stylesheet(self._dark_mode, accent_key=self._accent_key))
        accent_hex = ACCENT_PRESETS[self._accent_key]["accent"]

        self.header_logo.set_accent_color(accent_hex)
        self.theme_toggle.set_dark(self._dark_mode)
        self.hero_canvas.set_theme(self._dark_mode, self._accent_key)
        self.wheel_sandbox.set_theme(self._dark_mode, self._accent_key)
        self.consent_checkbox.set_theme(self._dark_mode, self._accent_key)

        for sw in (self.sw_wheel, self.sw_accessory):
            sw.set_dark_mode(self._dark_mode)
            sw.set_accent_color(accent_hex)

        self.ob_light_btn.setProperty("active", not self._dark_mode)
        self.ob_dark_btn.setProperty("active", self._dark_mode)
        for btn in (self.ob_light_btn, self.ob_dark_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        for key, btn in self._accent_btns.items():
            btn.setProperty("active", key == self._accent_key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._refresh_legal_view()
        self.update()

    # --- Event Handlers & Cleanup ---

    def _stop_all_animations(self) -> None:
        self._entrance_anim.stop()
        self._exit_anim.stop()
        for timer in self._active_haptic_timers:
            timer.stop()
        self._active_haptic_timers.clear()
        self.hero_canvas.stop_animations()
        self.wheel_sandbox.stop_animations()
        self.consent_checkbox.stop_animations()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._current_step == self.STEP_SANDBOX:
            key_map = {
                Qt.Key_Shift: "convert",
                Qt.Key_Control: "actions",
                Qt.Key_Meta: "tools",
            }
            if event.key() in key_map:
                self._pick_sandbox_wheel(key_map[event.key()])
                return
        if event.key() == Qt.Key_Escape and not self._first_boot:
            self._on_decline()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and event.position().y() <= 72:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def hideEvent(self, event) -> None:
        if not self._closing_fade:
            self._stop_all_animations()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._stop_all_animations()
        super().closeEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing)

        t = get_tokens(self._dark_mode, self._accent_key)
        card_rect = QRectF(
            _SHADOW_MARGIN,
            _SHADOW_MARGIN,
            self.width() - 2 * _SHADOW_MARGIN,
            self.height() - 2 * _SHADOW_MARGIN,
        )

        # Layered soft macOS window drop shadow
        for expand, alpha in ((10.0, 18), (6.0, 26), (2.5, 36)):
            shadow_col = QColor(0, 0, 0, alpha if self._dark_mode else int(alpha * 0.55))
            p.setPen(Qt.NoPen)
            p.setBrush(shadow_col)
            p.drawRoundedRect(
                card_rect.adjusted(-expand, -expand + 3.0, expand, expand + 3.0),
                18.0 + expand * 0.4,
                18.0 + expand * 0.4,
            )

        path = QPainterPath()
        path.addRoundedRect(card_rect, 18.0, 18.0)
        p.fillPath(path, QColor(t["bg_main"]))
        p.setPen(QPen(QColor(t["border_strong"]), 1.0))
        p.drawPath(path)
        p.end()
