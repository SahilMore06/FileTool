"""Native macOS 3-step onboarding: interactive kinetic aperture studio, Finder drag wheel sandbox, and legal consent."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
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
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from filetool.core.legal import LEGAL_VERSION, render_legal_html
from filetool.platform.mac_actions import play_tactile_feedback, trigger_haptic_tick
from filetool.ui.components import (
    IOSSwitch,
    LogoWidget,
    _build_emblem_petal,
    collect_paths_from_urls,
    draw_vector_icon,
)
from filetool.ui.styles import ACCENT_PRESETS, get_stylesheet, get_tokens, migrate_accent_setting, normalize_accent_key
from filetool.ui.wheel.animations import should_reduce_motion
from filetool.ui.wheel.geometry import hit_test_radial, layout_segments
from filetool.ui.wheel.wheel_painter import WheelPainter, WheelState, _lerp_color


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _ease_out_cubic(t: float) -> float:
    x = _clamp01(t)
    return 1.0 - (1.0 - x) ** 3


def _ease_out_back(t: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1.0
    x = _clamp01(t) - 1.0
    return 1.0 + c3 * (x ** 3) + c1 * (x ** 2)


def _draw_rounded_tick(painter: QPainter, rect: QRectF, radius: float) -> None:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.drawPath(path)


_MODIFIER_SYMBOLS = {
    "Shift": "⇧",
    "Command": "⌘",
    "Control": "⌃",
    "Option": "⌥",
}

_MODIFIER_SHORT_NAMES = {
    "Shift": "Shift",
    "Command": "Cmd",
    "Control": "Ctrl",
    "Option": "Opt",
}

_QT_KEY_FOR_MODIFIER = {
    "Shift": Qt.Key_Shift,
    "Command": Qt.Key_Control,
    "Control": Qt.Key_Meta,
    "Option": Qt.Key_Alt,
}

_WHEEL_MODE_TITLES = {
    "convert": "Convert Wheel",
    "tools": "Tools Wheel",
    "actions": "Actions Wheel",
    "sticky": "Sticky & Keyboard Mode",
}


def _format_key_badge(key_name: str, *, short: bool = False) -> str:
    """Format a modifier key name with its macOS symbol badge."""
    sym = _MODIFIER_SYMBOLS.get(key_name, "⇧")
    label = _MODIFIER_SHORT_NAMES.get(key_name, key_name) if short else key_name
    return f"{sym} {label}"


class _VectorIcon(QWidget):
    """Crisp borderless vector icon rendered cleanly in theme color."""

    def __init__(self, icon_name: str, tokens: dict, tone: str = "accent", size: int = 18, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._tokens = tokens
        self._tone = tone
        self.setFixedSize(size, size)

    def set_theme(self, tokens: dict, tone: Optional[str] = None) -> None:
        self._tokens = tokens
        if tone is not None:
            self._tone = tone
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._tone == "success":
            fg = QColor(self._tokens["success"])
        elif self._tone == "muted":
            fg = QColor(self._tokens["text_secondary"])
        else:
            fg = QColor(self._tokens["accent_text"])
        draw_vector_icon(painter, self._icon_name, 0.0, 0.0, float(self.width()), fg)


def _infer_command_icon(badge: str, raw: str) -> str:
    """Resolve a crisp vector icon name matching the active category or command."""
    mapping = (
        (("document", "pdf", "split pdf", "merge pdf"), "document"),
        (("compress", "quantized"), "compress"),
        (("video", "audio", ".mov", ".mp4", "mp3", "wav", "trim"), "video"),
        (("image", "raw", "jpg", "png", "webp", "svg", ".heic"), "image"),
        (("drag wheel", "tap", "calibrat", "starting"), "sliders"),
        (("convert",), "convert"),
        (("tools", "resize", "rotate", "crop"), "resize"),
        (("action", "airdrop", "terminal", "copy"), "airdrop"),
        (("sticky", "pinned", "float"), "float"),
        (("100%", "local", "offline", "meta", "exif", "ffmpeg", "imagemagick", "poppler", "mit"), "shield"),
        (("drop", "loaded", "ready", "preview"), "file"),
    )
    badge_low = badge.lower()
    for needles, icon_name in mapping:
        if any(needle in badge_low for needle in needles):
            return icon_name
    raw_low = raw.lower()
    for needles, icon_name in mapping:
        if any(needle in raw_low for needle in needles):
            return icon_name
    return "sliders"


def _parse_command_state(raw_text: str, active: bool) -> Dict[str, object]:
    """Convert status/command telemetry strings into structured capsule fields."""
    text = (raw_text or "").strip()
    clean = text[9:].strip() if text.startswith("Selected:") else text

    badge = ""
    primary = clean
    secondary = ""
    arrow = False

    sep = "  ·  " if "  ·  " in clean else (" · " if " · " in clean else "")
    if sep:
        parts = [p.strip() for p in clean.split(sep) if p.strip()]
        if parts:
            badge = parts[0]
            rest = " ".join(parts[1:]) if len(parts) > 1 else ""
            if len(parts) >= 3 and "->" not in parts[1] and "→" not in parts[1]:
                primary = parts[1]
                secondary = " · ".join(parts[2:])
                arrow = True
            else:
                for arrow_tok in ("  ->  ", " -> ", "  →  ", " → "):
                    if arrow_tok in rest:
                        left, right = rest.split(arrow_tok, 1)
                        primary = left.strip()
                        secondary = right.strip()
                        arrow = True
                        break
                else:
                    primary = rest
    else:
        low = clean.lower()
        if "calibrat" in low or "checking" in low:
            badge = "Starting"
        elif "hover" in low or "scrub" in low:
            badge = "Ready"
        elif clean.startswith("Loaded "):
            badge = "File Ready"
            primary = clean.removeprefix("Loaded ").strip()
        else:
            badge = "Ready"

    if badge == "100% On Your Mac":
        badge = "100% Local"
    elif badge == "Sticky Pinned":
        badge = "Sticky"
    elif badge.startswith("Convert Wheel"):
        badge = "Convert"
    elif badge.startswith("Tools Wheel"):
        badge = "Tools"
    elif badge.startswith("Actions Wheel"):
        badge = "Actions"
    elif badge.startswith("Sticky "):
        badge = "Sticky"

    return {
        "badge": badge or "Ready",
        "icon": _infer_command_icon(badge, clean),
        "primary": primary,
        "secondary": secondary,
        "arrow": arrow and bool(secondary),
        "active": bool(active),
        "raw_text": text,
    }


class _ActiveCommandBar(QWidget):
    """Elevated command-palette telemetry capsule with animated flow transitions."""

    def __init__(self, tokens: dict, max_width: int = 452, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tokens = tokens
        self._max_width = max_width
        self._hovered = False
        self._swap_t = 1.0
        self._active_t = 0.0
        self._active_target = 0.0
        self._sheen_t = 1.0
        self._prev_state: Optional[Dict[str, object]] = None
        self._cur_state: Dict[str, object] = _parse_command_state("", active=False)

        self.setFixedSize(max_width, 39)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMouseTracking(True)

        self._swap_anim = QVariantAnimation(self)
        self._swap_anim.setDuration(220)
        self._swap_anim.setStartValue(0.0)
        self._swap_anim.setEndValue(1.0)
        self._swap_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._swap_anim.valueChanged.connect(self._on_swap_step)
        self._swap_anim.finished.connect(self._on_swap_done)

        self._active_anim = QVariantAnimation(self)
        self._active_anim.setDuration(190)
        self._active_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._active_anim.valueChanged.connect(self._on_active_step)

        self._sheen_anim = QVariantAnimation(self)
        self._sheen_anim.setDuration(340)
        self._sheen_anim.setStartValue(0.0)
        self._sheen_anim.setEndValue(1.0)
        self._sheen_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._sheen_anim.valueChanged.connect(self._on_sheen_step)

    def sizeHint(self) -> QSize:
        return QSize(self._max_width, 39)

    def text(self) -> str:
        return str(self._cur_state.get("raw_text", ""))

    def setWordWrap(self, _wrap: bool) -> None:
        return None

    def setAlignment(self, _align: Qt.AlignmentFlag) -> None:
        return None

    def set_theme(self, tokens: dict) -> None:
        self._tokens = tokens
        self.update()

    def setText(self, text: str) -> None:
        active_prop = str(self.property("active") or self.property("triggered") or "false").lower() == "true"
        self._apply_state(_parse_command_state(text, active=active_prop))

    def set_command(
        self,
        *,
        badge: str,
        source: str,
        outcome: str = "",
        active: bool = True,
        raw_text: Optional[str] = None,
        icon: Optional[str] = None,
        arrow: Optional[bool] = None,
    ) -> None:
        """Update the displayed command structure directly and animate the transition."""
        has_arrow = bool(outcome) if arrow is None else bool(arrow and outcome)
        text = raw_text if raw_text is not None else (f"{badge}  ·  {source} → {outcome}" if outcome else f"{badge}  ·  {source}")
        self.setProperty("active", "true" if active else "false")
        self.setProperty("triggered", "true" if active else "false")
        self.setAccessibleName(text)
        self._apply_state(
            {
                "badge": badge,
                "icon": icon or _infer_command_icon(badge, source),
                "primary": source,
                "secondary": outcome,
                "arrow": has_arrow,
                "active": bool(active),
                "raw_text": text,
            }
        )

    def _apply_state(self, new_state: Dict[str, object]) -> None:
        cur = self._cur_state
        keys = ("badge", "icon", "primary", "secondary", "arrow", "active")
        if all(cur.get(k) == new_state.get(k) for k in keys):
            self._cur_state["raw_text"] = new_state["raw_text"]
            return

        text_changed = any(cur.get(k) != new_state.get(k) for k in ("badge", "primary", "secondary", "arrow"))
        self._active_target = 1.0 if new_state["active"] else 0.0

        if should_reduce_motion():
            self._swap_anim.stop()
            self._active_anim.stop()
            self._sheen_anim.stop()
            self._prev_state = None
            self._cur_state = new_state
            self._swap_t = 1.0
            self._active_t = self._active_target
            self._sheen_t = 1.0
            self.update()
            return

        if text_changed:
            if self._swap_t > 0.35:
                self._prev_state = dict(cur)
            else:
                self._prev_state = None
            self._cur_state = new_state
            self._swap_t = 0.0
            self._swap_anim.stop()
            self._swap_anim.start()
            if new_state["active"]:
                self._sheen_t = 0.0
                self._sheen_anim.stop()
                self._sheen_anim.start()
        else:
            self._cur_state = new_state

        if abs(self._active_t - self._active_target) > 0.005:
            self._active_anim.stop()
            self._active_anim.setStartValue(self._active_t)
            self._active_anim.setEndValue(self._active_target)
            self._active_anim.start()
        self.update()

    def _on_swap_step(self, value: object) -> None:
        self._swap_t = float(value)
        self.update()

    def _on_swap_done(self) -> None:
        self._swap_t = 1.0
        self._prev_state = None
        self.update()

    def _on_active_step(self, value: object) -> None:
        self._active_t = float(value)
        self.update()

    def _on_sheen_step(self, value: object) -> None:
        self._sheen_t = float(value)
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _draw_arrow_glyph(painter: QPainter, x: float, cy: float, width: float, color: QColor) -> None:
        painter.save()
        painter.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        x2 = x + width
        painter.drawLine(QPointF(x, cy), QPointF(x2, cy))
        head = 3.5
        painter.drawLine(QPointF(x2 - head, cy - head), QPointF(x2, cy))
        painter.drawLine(QPointF(x2 - head, cy + head), QPointF(x2, cy))
        painter.restore()

    def _draw_command_state(
        self,
        painter: QPainter,
        state: Dict[str, object],
        rect: QRectF,
        opacity: float,
        dy: float,
        arrow_slide: float,
    ) -> None:
        if opacity <= 0.02:
            return
        t = self._tokens
        is_dark = QColor(t["bg_main"]).lightnessF() < 0.5
        is_act = bool(state.get("active"))
        cy = rect.center().y() + dy

        painter.save()
        painter.setOpacity(opacity)

        # Left tonal mode chip (no inner border -> zero nested card box)
        badge = str(state.get("badge") or "Ready")
        icon_name = str(state.get("icon") or "sliders")
        badge_font = QFont(".AppleSystemUIFont", 11, QFont.Weight.DemiBold)
        badge_fm = QFontMetrics(badge_font)
        badge_tw = badge_fm.horizontalAdvance(badge)
        pill_h = 24.0
        icon_sz = 12.0
        pad_l, pad_r, icon_gap = 7.5, 8.5, 5.5
        pill_w = min(134.0, pad_l + icon_sz + icon_gap + badge_tw + pad_r)
        pill_rect = QRectF(rect.x() + 6.0, cy - pill_h / 2.0, pill_w, pill_h)

        if is_act:
            pill_bg = QColor(t["accent"])
            pill_bg.setAlpha(38 if is_dark else 26)
            pill_fg = QColor(t["accent_text"])
        else:
            pill_bg = QColor(t["bg_surface2"])
            pill_fg = QColor(t["text_secondary"])

        painter.setPen(Qt.NoPen)
        painter.setBrush(pill_bg)
        painter.drawRoundedRect(pill_rect, 6.5, 6.5)

        draw_vector_icon(painter, icon_name, pill_rect.x() + pad_l, cy - icon_sz / 2.0, icon_sz, pill_fg)
        painter.setFont(badge_font)
        painter.setPen(pill_fg)
        painter.drawText(
            QRectF(pill_rect.x() + pad_l + icon_sz + icon_gap, pill_rect.y(), pill_w - pad_l - icon_sz - icon_gap - pad_r + 2.0, pill_h),
            Qt.AlignVCenter | Qt.AlignLeft,
            badge_fm.elidedText(badge, Qt.ElideRight, int(pill_w - pad_l - icon_sz - icon_gap - pad_r)),
        )

        # Command pipeline: source -> vector arrow -> outcome
        x = pill_rect.right() + 10.0
        max_right = rect.right() - 10.0
        avail = max(40.0, max_right - x)

        primary = str(state.get("primary") or "")
        secondary = str(state.get("secondary") or "")
        has_arrow = bool(state.get("arrow") and secondary)

        prim_font = QFont(".AppleSystemUIFont", 12, QFont.Weight.DemiBold if is_act else QFont.Weight.Medium)
        prim_fm = QFontMetrics(prim_font)
        painter.setFont(prim_font)
        painter.setPen(QColor(t["text_primary"] if is_act else t["text_secondary"]))

        if has_arrow:
            arrow_w = 11.5
            arrow_gap = 8.0
            total_arrow_span = arrow_w + 2.0 * arrow_gap
            prim_cap = max(84.0, (avail - total_arrow_span) * 0.44)
            prim_text = prim_fm.elidedText(primary, Qt.ElideRight, int(prim_cap))
            prim_w = min(prim_cap, float(prim_fm.horizontalAdvance(prim_text)))
            painter.drawText(
                QRectF(x, cy - 11.0, prim_w + 2.0, 22.0),
                Qt.AlignVCenter | Qt.AlignLeft,
                prim_text,
            )
            x += prim_w + arrow_gap
            self._draw_arrow_glyph(painter, x + arrow_slide, cy, arrow_w, QColor(t["accent_text"]))
            x += arrow_w + arrow_gap

            sec_avail = max(30.0, max_right - x)
            sec_font = QFont(".AppleSystemUIFont", 11.5, QFont.Weight.Medium)
            sec_fm = QFontMetrics(sec_font)
            painter.setFont(sec_font)
            painter.setPen(QColor(t["text_secondary"]))
            sec_text = sec_fm.elidedText(secondary, Qt.ElideRight, int(sec_avail))
            painter.drawText(
                QRectF(x, cy - 11.0, sec_avail, 22.0),
                Qt.AlignVCenter | Qt.AlignLeft,
                sec_text,
            )
        else:
            single_text = prim_fm.elidedText(primary, Qt.ElideRight, int(avail))
            painter.drawText(
                QRectF(x, cy - 11.0, avail, 22.0),
                Qt.AlignVCenter | Qt.AlignLeft,
                single_text,
            )

        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        t = self._tokens
        is_dark = QColor(t["bg_main"]).lightnessF() < 0.5

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 3.0)
        capsule_path = QPainterPath()
        capsule_path.addRoundedRect(rect, 11.5, 11.5)

        # Tactile bottom hairline shadow for native macOS HUD elevation
        shadow_col = QColor(0, 0, 0, 52 if is_dark else 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow_col)
        painter.drawRoundedRect(rect.translated(0.0, 1.0), 11.5, 11.5)

        fill_mix = max(self._active_t, 0.78 if self._hovered else 0.58)
        bg_col = _lerp_color(QColor(t["bg_surface2"]), QColor(t["bg_surface"]), fill_mix)
        idle_border = QColor(t["border_strong"] if self._hovered else t["border"])
        active_border = _lerp_color(QColor(t["border_strong"]), QColor(t["accent"]), 0.14)
        border_col = _lerp_color(idle_border, active_border, self._active_t)

        painter.setBrush(bg_col)
        painter.setPen(QPen(border_col, 1.0))
        painter.drawPath(capsule_path)

        painter.save()
        painter.setClipPath(capsule_path)

        # Subtle top-rim accent sheen on mode/command trigger
        if 0.01 < self._sheen_t < 0.99:
            sheen_cx = self._sheen_t * rect.width() + rect.x()
            sheen = QRadialGradient(QPointF(sheen_cx, rect.top()), 96.0)
            s_core = QColor(t["accent"])
            s_core.setAlpha(int(68 * math.sin(math.pi * self._sheen_t)))
            s_out = QColor(t["accent"])
            s_out.setAlpha(0)
            sheen.setColorAt(0.0, s_core)
            sheen.setColorAt(1.0, s_out)
            painter.setPen(Qt.NoPen)
            painter.setBrush(sheen)
            painter.drawRect(QRectF(rect.x(), rect.top(), rect.width(), 3.0))

        eased = _ease_out_cubic(self._swap_t)
        if self._prev_state is not None and self._swap_t < 0.55:
            out_alpha = (1.0 - _clamp01(self._swap_t * 1.9)) ** 1.4
            self._draw_command_state(painter, self._prev_state, rect, out_alpha, -4.5 * self._swap_t, 0.0)

        in_alpha = 1.0 if self._swap_t >= 0.99 else _clamp01((self._swap_t - 0.12) / 0.88) ** 0.85
        in_dy = 0.0 if self._swap_t >= 0.99 else 5.5 * (1.0 - eased)
        arrow_slide = 0.0 if self._swap_t >= 0.99 else -4.5 * (1.0 - eased)
        self._draw_command_state(painter, self._cur_state, rect, in_alpha, in_dy, arrow_slide)

        painter.restore()


class _ThemeToggleButton(QAbstractButton):
    """Compact header button toggling Light and Dark themes directly from any step."""

    def __init__(self, dark_mode: bool, tokens: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._dark_mode = bool(dark_mode)
        self._tokens = tokens
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self._sync_a11y()

    def _sync_a11y(self) -> None:
        tip = "Switch to Light appearance" if self._dark_mode else "Switch to Dark appearance"
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def set_theme(self, dark_mode: bool, tokens: dict) -> None:
        self._dark_mode = bool(dark_mode)
        self._tokens = tokens
        self._sync_a11y()
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._tokens
        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)

        bg = QColor(t["bg_main"] if self._hovered else "transparent")
        if self._hovered or self.hasFocus():
            p.setBrush(bg)
            p.setPen(QPen(QColor(t["border_focus"] if self.hasFocus() else t["border"]), 1.2))
            p.drawRoundedRect(rect, 7.0, 7.0)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        fg = QColor(t["text_primary"] if self._hovered else t["text_secondary"])

        if self._dark_mode:
            # Sun icon indicating Light toggle
            p.setPen(QPen(fg, 1.4, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 3.6, 3.6)
            for idx in range(8):
                ang = idx * (math.pi / 4.0)
                p.drawLine(
                    QPointF(cx + math.cos(ang) * 5.8, cy + math.sin(ang) * 5.8),
                    QPointF(cx + math.cos(ang) * 7.6, cy + math.sin(ang) * 7.6),
                )
        else:
            # Crisp crescent moon indicating Dark toggle
            moon = QPainterPath()
            moon.addEllipse(QPointF(cx, cy), 6.2, 6.2)
            cut = QPainterPath()
            cut.addEllipse(QPointF(cx + 2.8, cy - 2.2), 5.0, 5.0)
            p.setPen(Qt.NoPen)
            p.setBrush(fg)
            p.drawPath(moon.subtracted(cut))


class _AccentSwatchButton(QPushButton):
    """macOS System Settings style circular accent dot."""

    def __init__(self, key: str, label: str, swatch_hex: str, tokens: dict, parent: Optional[QWidget] = None):
        super().__init__("", parent)
        self._accent_key = key
        self._swatch_hex = swatch_hex
        self._tokens = tokens
        self._active = False
        self._hovered = False
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setToolTip(label)
        self.setAccessibleName(f"{label} accent color")

    def set_state(self, active: bool, tokens: dict) -> None:
        self._active = bool(active)
        self._tokens = tokens
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self._active or self.hasFocus():
            ring_col = QColor(self._tokens["text_primary"] if self._active else self._tokens["border_focus"])
            painter.setPen(QPen(ring_col, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), 9.6, 9.6)
        elif self._hovered:
            painter.setPen(QPen(QColor(self._tokens["border_strong"]), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), 9.2, 9.2)

        radius = 6.8 if self._active else 7.6
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._swatch_hex))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        if self._active:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(QPointF(cx, cy), 2.1, 2.1)


class _InteractivePillarRow(QAbstractButton):
    """Tactile animated capability row that drives and syncs with the optical hero dial."""

    activated = Signal(int)

    def __init__(
        self,
        index: int,
        icon_name: str,
        title: str,
        subtitle: str,
        initial_badge: str,
        tokens: dict,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._index = index
        self._icon_name = icon_name
        self._title = title
        self._subtitle = subtitle
        self._tokens = tokens
        self._selected = False
        self._hover_t = 0.0

        self.setFixedHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setAccessibleName(f"{title}: {subtitle}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(52, 0, 10, 0)
        layout.addStretch(1)

        self.status_label = QLabel(initial_badge)
        self.status_label.setObjectName("onboardingCapStatus")
        self.status_label.setProperty("ready", False)
        layout.addWidget(self.status_label, 0, Qt.AlignVCenter)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

        self.clicked.connect(lambda: self.activated.emit(self._index))

    def _on_hover_step(self, val: object) -> None:
        self._hover_t = float(val)
        self.update()

    def set_theme(self, tokens: dict) -> None:
        self._tokens = tokens
        self.update()

    def set_selected(self, selected: bool) -> None:
        if self._selected != bool(selected):
            self._selected = bool(selected)
            self._animate_hover(1.0 if self._selected or self.underMouse() else 0.0)
            self.update()

    def _animate_hover(self, target: float) -> None:
        if should_reduce_motion():
            self._hover_anim.stop()
            self._hover_t = target
            self.update()
            return
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(1.0 if self._selected else 0.0)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._tokens

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        blend = max(self._hover_t, 1.0 if self._selected else 0.0)

        bg_base = QColor(t["bg_surface"])
        bg_hot = QColor(t["bg_main"])
        if blend > 0.01:
            fill = _lerp_color(bg_base, bg_hot, blend)
            path = QPainterPath()
            path.addRoundedRect(rect, 8.0, 8.0)
            p.fillPath(path, fill)

            if self.hasFocus():
                p.setPen(QPen(QColor(t["border_focus"]), 1.2))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)

        if self._selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t["accent"]))
            _draw_rounded_tick(p, QRectF(2.5, 16.0, 2.5, self.height() - 32.0), 1.25)

        icon_col = _lerp_color(QColor(t["text_secondary"]), QColor(t["accent_text"]), blend)
        draw_vector_icon(p, self._icon_name, 14.0, (self.height() - 18.0) / 2.0, 18.0, icon_col)

        badge_w = max(78, self.status_label.sizeHint().width() + 14)
        text_x = 42
        text_w = max(90, self.width() - text_x - badge_w)

        title_font = QFont(".AppleSystemUIFont", 13, QFont.Weight.DemiBold)
        p.setFont(title_font)
        p.setPen(QColor(t["text_primary"]))
        title_str = QFontMetrics(title_font).elidedText(self._title, Qt.ElideRight, text_w)
        p.drawText(QPointF(text_x, 26.0), title_str)

        sub_font = QFont(".AppleSystemUIFont", 11, QFont.Weight.Normal)
        p.setFont(sub_font)
        p.setPen(QColor(t["text_secondary"]))
        sub_str = QFontMetrics(sub_font).elidedText(self._subtitle, Qt.ElideRight, text_w)
        p.drawText(QPointF(text_x, 45.0), sub_str)


class _StarterInstallCanvas(QWidget):
    """Interactive machined-dial studio centerpiece with rotary inertia, key demos, haptic detents, and file drop."""

    install_finished = Signal()
    capability_unlocked = Signal(int)
    petal_hovered = Signal(int)
    petal_clicked = Signal(int)
    file_dropped_preview = Signal(str, str)

    PETAL_LABELS = (
        "Images & RAW",
        "Video & Audio",
        "Documents & PDF",
        "Batch Compress",
        "Finder Drag Wheel",
        "100% Local on Mac",
    )

    SECTOR_SPECS: Tuple[Tuple[str, str, str], ...] = (
        ("Images & RAW", "HEIC → JPG", "vacation.heic → vacation.jpg (1.2 MB, -71%)"),
        ("Video & Audio", "MOV → MP4", "demo_clip.mov → demo_clip.mp4 (9.4 MB)"),
        ("Documents", "Split PDF", "deck_final.pdf → 6 single pages (300 DPI)"),
        ("Compress", "-71% Size", "asset_bundle.png → quantized WebP (680 KB)"),
        ("Drag Wheel", "Tap Shift", "Tap Shift → Quartz drag state ready locally"),
        ("100% Local", "Offline Mac", "Zero uploads → Originals stay untouched on Mac"),
    )

    STUDIO_MODE_SPECS: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
        "overview": SECTOR_SPECS,
        "key_convert": (
            ("JPG", "→ .jpg", "Convert photo to JPG (-71% size)"),
            ("PNG", "→ .png", "Export lossless RGB/RGBA PNG locally"),
            ("WebP", "→ .webp", "Save fast 680 KB web image offline"),
            ("MP4", "→ .mp4", "Transcode MOV/MKV locally via ffmpeg"),
            ("PDF", "→ .pdf", "Wrap images or Markdown to PDF"),
            ("ZIP", "Archive", "Package Finder selection into ZIP"),
        ),
        "key_tools": (
            ("Compress", "-71% Size", "Shrink image, video, audio, or PDF"),
            ("Resize", "1920 px", "Scale dimensions keeping aspect ratio"),
            ("Rotate", "90 deg", "Lossless image or PDF page rotation"),
            ("Crop", "16:9 / 1:1", "Trim frames offline without upload"),
            ("Split PDF", "Per Page", "Split PDF pages or video segments"),
            ("Strip EXIF", "No GPS", "Remove camera GPS & EXIF metadata"),
        ),
        "key_actions": (
            ("AirDrop", "Share", "Send dragged items via macOS AirDrop"),
            ("Float", "Pin Top", "Open always-on-top Quick Look window"),
            ("Copy To", "Duplicate", "Copy files into any chosen folder"),
            ("Move To", "Organize", "Move Finder files without overwrites"),
            ("Copy Path", "Clipboard", "Copy full POSIX paths to clipboard"),
            ("Terminal", "Open cd", "Open Terminal at dragged folder"),
        ),
        "key_sticky": (
            ("1. Select", "In Finder", "Highlight one or more Finder items"),
            ("2. Return", "Opens Wheel", "Pin wheel open without holding mouse"),
            ("3. Arrows", "← → Step", "Step petals with ← →; switch with ↑ ↓"),
            ("4. Mod Keys", "⇧ / ⌘ / ⌃", "Swap Convert, Tools, or Actions rings"),
            ("5. Return", "Run Petal", "Execute highlighted petal immediately"),
            ("6. Esc", "Dismiss", "Close pinned wheel anytime with Esc"),
        ),
        "local": (
            ("Zero Network", "Offline", "No uploads, accounts, or analytics"),
            ("Safe Output", "name (1)", "Originals stay safe (Overwrite off)"),
            ("ffmpeg", "Media", "Local video and audio processing"),
            ("ImageMagick", "Images", "Local HEIC, RAW, WebP & SVG engine"),
            ("Poppler / GS", "PDF", "Local PDF split, merge & compress"),
            ("MIT Code", "Auditable", "Transparent offline macOS source"),
        ),
    }

    _CENTER_BADGE_BY_MODE = {
        "key_convert": "⇧",
        "key_tools": "⌘",
        "key_actions": "⌃",
        "key_sticky": "↩",
        "local": "Local",
    }

    def __init__(self, tokens: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tokens = tokens
        self._install_t = 0.0
        self._unlocked_count = 0
        self._rotation_deg = -36.0
        self._scale = 1.0
        self._hover_t = 0.0
        self._done_t = 0.0
        self._ripple_t = 0.0
        self._hovered_idx: Optional[int] = None
        self._selected_idx: int = 0
        self._studio_mode: str = "overview"
        self._dragging = False
        self._drag_hovering_file = False
        self._drag_last_angle: Optional[float] = None
        self._drag_last_detent: Optional[int] = None
        self._spin_last_detent: Optional[int] = None
        self._spin_velocity: float = 0.0
        self._emit_haptics = True
        self._drop_label: Optional[str] = None
        self._petal_anim_hover: List[float] = [0.0] * 6

        self.setFixedSize(468, 322)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        self._install_anim = QVariantAnimation(self)
        self._install_anim.setDuration(1180)
        self._install_anim.setStartValue(0.0)
        self._install_anim.setEndValue(1.0)
        self._install_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._install_anim.valueChanged.connect(self._on_install_step)
        self._install_anim.finished.connect(self._on_install_done)

        self._spin_anim = QVariantAnimation(self)
        self._spin_anim.setDuration(480)
        self._spin_anim.setEasingCurve(QEasingCurve.OutBack)
        self._spin_anim.valueChanged.connect(self._on_spin_step)
        self._spin_anim.finished.connect(self._on_spin_done)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

        self._ripple_anim = QVariantAnimation(self)
        self._ripple_anim.setDuration(420)
        self._ripple_anim.setStartValue(0.0)
        self._ripple_anim.setEndValue(1.0)
        self._ripple_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._ripple_anim.valueChanged.connect(self._on_ripple_step)

        self._drop_anim = QVariantAnimation(self)
        self._drop_anim.setDuration(460)
        self._drop_anim.setStartValue(0.0)
        self._drop_anim.setEndValue(1.0)
        self._drop_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._drop_anim.valueChanged.connect(self._on_drop_step)
        self._drop_anim.finished.connect(self._on_drop_done)

        self._inertia_timer = QTimer(self)
        self._inertia_timer.setInterval(16)
        self._inertia_timer.timeout.connect(self._tick_physics)

    def active_specs(self) -> Tuple[Tuple[str, str, str], ...]:
        """Return the 6 sector tuples active for the current studio mode."""
        return self.STUDIO_MODE_SPECS.get(self._studio_mode, self.SECTOR_SPECS)

    def set_theme(self, tokens: dict) -> None:
        self._tokens = tokens
        self.update()

    def set_studio_mode(
        self,
        mode: str,
        *,
        target_sector: int = 0,
        spin_degrees: float = 240.0,
        emit_haptics: bool = True,
    ) -> None:
        """Switch the wheel demo mode and spin through detent ticks cleanly."""
        self._studio_mode = mode if mode in self.STUDIO_MODE_SPECS else "overview"
        self._selected_idx = target_sector % 6
        self._hovered_idx = None
        self._spin_velocity = 0.0
        self._emit_haptics = emit_haptics

        if should_reduce_motion():
            self._spin_anim.stop()
            self._rotation_deg = -(self._selected_idx * 60.0)
        else:
            start_rot = self._rotation_deg
            desired_mod = (-(self._selected_idx * 60.0)) % 360.0
            base_rot = start_rot + max(120.0, spin_degrees)
            rem = (desired_mod - (base_rot % 360.0)) % 360.0
            target_rot = base_rot + rem
            self._spin_last_detent = int(round(start_rot / 60.0))
            self._spin_anim.stop()
            self._spin_anim.setStartValue(start_rot)
            self._spin_anim.setEndValue(target_rot)
            self._spin_anim.start()
            self._ripple_anim.stop()
            self._ripple_anim.start()
            self._ensure_physics_loop()

        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(0.9)
        self._hover_anim.start()
        self.update()

    def set_external_highlight(self, idx: Optional[int]) -> None:
        if idx is not None and 0 <= idx < 6:
            self._selected_idx = idx
            if not should_reduce_motion():
                start_rot = self._rotation_deg
                target_rot = -idx * 60.0
                if abs(target_rot - start_rot) < 40.0:
                    target_rot += 180.0
                self._spin_last_detent = int(round(start_rot / 60.0))
                self._spin_anim.stop()
                self._spin_anim.setStartValue(start_rot)
                self._spin_anim.setEndValue(target_rot)
                self._spin_anim.start()
            else:
                self._rotation_deg = -idx * 60.0
        target = 0.9 if idx is not None else 0.0
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()
        self.update()

    def play_install_sequence(self, emit_haptics: bool = True) -> None:
        self.stop_animations()
        self._emit_haptics = emit_haptics
        self._unlocked_count = 0
        self._done_t = 0.0
        self._ripple_t = 0.0
        self._drop_label = None
        self._spin_velocity = 0.0

        if should_reduce_motion():
            self._install_t = 1.0
            self._rotation_deg = 0.0
            self._scale = 1.0
            for idx in range(3):
                self._unlocked_count = idx + 1
                self.capability_unlocked.emit(idx)
            if emit_haptics:
                trigger_haptic_tick("level_change")
            self.update()
            self.install_finished.emit()
            return

        self._install_t = 0.0
        self._rotation_deg = -36.0
        self._scale = 0.88
        self._install_anim.start()
        if emit_haptics:
            trigger_haptic_tick("generic")
        self.update()

    def stop_animations(self) -> None:
        self._install_anim.stop()
        self._spin_anim.stop()
        self._hover_anim.stop()
        self._ripple_anim.stop()
        self._drop_anim.stop()
        self._inertia_timer.stop()
        self._spin_velocity = 0.0

    def hideEvent(self, event) -> None:
        self._inertia_timer.stop()
        super().hideEvent(event)

    def _on_install_step(self, value: object) -> None:
        self._install_t = _clamp01(float(value))
        eased = _ease_out_back(min(1.0, self._install_t * 1.05))
        self._rotation_deg = -36.0 * (1.0 - _ease_out_cubic(self._install_t))
        self._scale = 0.88 + 0.12 * min(1.03, eased)

        for idx, thresh in enumerate((0.26, 0.56, 0.86)):
            if self._unlocked_count <= idx and self._install_t >= thresh:
                self._unlocked_count = idx + 1
                if self._emit_haptics:
                    trigger_haptic_tick("alignment")
                self.capability_unlocked.emit(idx)
        self.update()

    def _on_install_done(self) -> None:
        self._install_t = 1.0
        self._rotation_deg = 0.0
        self._scale = 1.0
        while self._unlocked_count < 3:
            self.capability_unlocked.emit(self._unlocked_count)
            self._unlocked_count += 1
        if self._emit_haptics:
            trigger_haptic_tick("level_change")
        if not should_reduce_motion():
            self._ripple_anim.stop()
            self._ripple_anim.start()
        self.update()
        self.install_finished.emit()

    def _on_spin_step(self, value: object) -> None:
        self._rotation_deg = float(value)
        detent = int(round(self._rotation_deg / 60.0))
        if self._spin_last_detent is None:
            self._spin_last_detent = detent
        elif detent != self._spin_last_detent:
            self._spin_last_detent = detent
            if self._emit_haptics:
                trigger_haptic_tick("alignment")
            self.petal_hovered.emit((-detent) % 6)
        self.update()

    def _on_spin_done(self) -> None:
        self._spin_last_detent = None
        self.update()

    def _on_hover_step(self, value: object) -> None:
        self._hover_t = float(value)
        self.update()

    def _on_ripple_step(self, value: object) -> None:
        self._ripple_t = float(value)
        self.update()

    def _on_drop_step(self, value: object) -> None:
        self._install_t = 0.25 + 0.75 * float(value)
        self._done_t = max(0.0, (float(value) - 0.75) * 4.0)
        self.update()

    def _on_drop_done(self) -> None:
        self._install_t = 1.0
        self._done_t = 0.0
        if not should_reduce_motion():
            self._ripple_anim.stop()
            self._ripple_anim.start()
        self.update()

    def _tick_physics(self) -> None:
        changed = False
        if abs(self._spin_velocity) > 0.08:
            prev_detent = int(round(self._rotation_deg / 60.0))
            self._rotation_deg += self._spin_velocity
            self._spin_velocity *= 0.90
            new_detent = int(round(self._rotation_deg / 60.0))
            if new_detent != prev_detent:
                trigger_haptic_tick("alignment")
                self._selected_idx = (-new_detent) % 6
                self.petal_hovered.emit(self._selected_idx)
            changed = True
        else:
            self._spin_velocity = 0.0

        for idx in range(6):
            target = 1.0 if idx == self._hovered_idx else (0.45 if idx == self._selected_idx else 0.0)
            cur = self._petal_anim_hover[idx]
            if abs(target - cur) > 0.01:
                self._petal_anim_hover[idx] = cur + (target - cur) * 0.26
                changed = True
            elif cur != target:
                self._petal_anim_hover[idx] = target
                changed = True

        if not changed:
            self._inertia_timer.stop()
        else:
            self.update()

    def _orbital_node_rects(self) -> List[QRectF]:
        cx, cy = self.width() / 2.0, self.height() / 2.0
        offsets = (
            (0.0, -138.0),
            (166.0, -58.0),
            (166.0, 58.0),
            (0.0, 138.0),
            (-166.0, 58.0),
            (-166.0, -58.0),
        )
        w, h = 114.0, 36.0
        return [QRectF(cx + dx - w / 2.0, cy + dy - h / 2.0, w, h) for dx, dy in offsets]

    def _hit_sector(self, pos: QPointF) -> Optional[int]:
        for idx, r in enumerate(self._orbital_node_rects()):
            if r.contains(pos):
                return idx
        cx, cy = self.width() / 2.0, self.height() / 2.0
        dx, dy = pos.x() - cx, pos.y() - cy
        dist = math.hypot(dx, dy)
        if 16.0 <= dist <= 120.0:
            raw_deg = math.degrees(math.atan2(dy, dx)) + 90.0 - self._rotation_deg
            norm_deg = (raw_deg + 30.0) % 360.0
            return int(norm_deg // 60.0) % 6
        return None

    def _ensure_physics_loop(self) -> None:
        if not should_reduce_motion() and not self._inertia_timer.isActive():
            self._inertia_timer.start()

    def enterEvent(self, event) -> None:
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered_idx = None
        self.petal_hovered.emit(-1)
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()
            self._ensure_physics_loop()
        else:
            self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        cx, cy = self.width() / 2.0, self.height() / 2.0
        if self._dragging and self._drag_last_angle is not None:
            cur_angle = math.degrees(math.atan2(pos.y() - cy, pos.x() - cx))
            delta = (cur_angle - self._drag_last_angle + 180.0) % 360.0 - 180.0
            self._drag_last_angle = cur_angle
            self._rotation_deg += delta
            self._spin_velocity = max(-14.0, min(14.0, delta))
            detent = int(round(self._rotation_deg / 60.0))
            if self._drag_last_detent is None or detent != self._drag_last_detent:
                self._drag_last_detent = detent
                self._selected_idx = (-detent) % 6
                trigger_haptic_tick("alignment")
                self.petal_hovered.emit(self._selected_idx)
            self.update()
            return

        sector = self._hit_sector(pos)
        if sector != self._hovered_idx:
            self._hovered_idx = sector
            if sector is not None:
                trigger_haptic_tick("alignment")
                self.petal_hovered.emit(sector)
            self._ensure_physics_loop()
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position()
            cx, cy = self.width() / 2.0, self.height() / 2.0
            hit = self._hit_sector(pos)
            self._spin_velocity = 0.0
            self._dragging = True
            self._drag_last_angle = math.degrees(math.atan2(pos.y() - cy, pos.x() - cx))
            self._drag_last_detent = int(round(self._rotation_deg / 60.0))
            self._drop_label = None
            trigger_haptic_tick("level_change")
            target_idx = hit if hit is not None else self._selected_idx
            self._selected_idx = target_idx
            self.petal_clicked.emit(target_idx)
            if not should_reduce_motion():
                start_rot = self._rotation_deg
                self._spin_last_detent = int(round(start_rot / 60.0))
                self._spin_anim.stop()
                self._spin_anim.setStartValue(start_rot)
                self._spin_anim.setEndValue(start_rot + 60.0)
                self._spin_anim.start()
                self._ripple_anim.stop()
                self._ripple_anim.start()
                self._ensure_physics_loop()
            else:
                self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        self._drag_last_angle = None
        if abs(self._spin_velocity) > 0.25 and not should_reduce_motion():
            self._ensure_physics_loop()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self._drag_hovering_file = True
            self.update()
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._drag_hovering_file = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._drag_hovering_file = False
        paths = collect_paths_from_urls(event.mimeData().urls())
        if paths:
            path = paths[0]
            ext = path.suffix.lower().lstrip(".") or "file"
            self._drop_label = path.name
            trigger_haptic_tick("level_change")
            if not should_reduce_motion():
                self._drop_anim.stop()
                self._drop_anim.start()
            self.file_dropped_preview.emit(path.name, ext)
            event.acceptProposedAction()
            self.update()
        else:
            super().dropEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = self._tokens

        cx, cy = self.width() / 2.0, self.height() / 2.0
        accent = QColor(t["accent"])
        accent_text = QColor(t["accent_text"])
        border = QColor(t["border"])
        border_strong = QColor(t["border_strong"])

        # 1. Soft atmospheric radial lighting anchored behind instrument
        glow = QRadialGradient(QPointF(cx, cy), 158.0)
        glow_core = QColor(accent)
        glow_core.setAlpha(int(26 + self._hover_t * 14 + (18 if self._drag_hovering_file else 0)))
        glow_mid = QColor(accent)
        glow_mid.setAlpha(7)
        glow_out = QColor(accent)
        glow_out.setAlpha(0)
        glow.setColorAt(0.0, glow_core)
        glow.setColorAt(0.55, glow_mid)
        glow.setColorAt(1.0, glow_out)
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(cx, cy), 158.0, 158.0)

        # 2. Machined optical bezel + rotating 72 degree ticks
        ring_col = QColor(accent if self._drag_hovering_file else border)
        ring_col.setAlpha(190 if self._drag_hovering_file else 155)
        painter.setPen(QPen(ring_col, 1.4 if self._drag_hovering_file else 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), 108.0, 108.0)

        is_spinning = self._spin_anim.state() == QVariantAnimation.Running or abs(self._spin_velocity) > 0.25
        if is_spinning:
            sweep_rect = QRectF(cx - 108.0, cy - 108.0, 216.0, 216.0)
            sweep_col = QColor(accent)
            sweep_col.setAlpha(185)
            painter.setPen(QPen(sweep_col, 2.2, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(sweep_rect, int((90.0 - self._rotation_deg) * 16), -84 * 16)

        rot_rad = math.radians(self._rotation_deg)
        for tick_idx in range(72):
            ang = rot_rad - math.pi / 2.0 + tick_idx * ((2.0 * math.pi) / 72.0)
            is_major = tick_idx % 12 == 0
            r1 = 100.5 if is_major else 103.0
            r2 = 107.0
            tick_col = QColor(accent if is_major else border_strong)
            tick_col.setAlpha(190 if is_major else 95)
            painter.setPen(QPen(tick_col, 1.5 if is_major else 0.9, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                QPointF(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                QPointF(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
            )

        # Stationary 12 o'clock optical index chevron
        pointer = QPainterPath()
        pointer.moveTo(cx, cy - 110.0)
        pointer.lineTo(cx - 4.5, cy - 116.5)
        pointer.lineTo(cx + 4.5, cy - 116.5)
        pointer.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawPath(pointer)

        # Expanding shockwave ring on detent click / completion
        if 0.01 < self._ripple_t < 0.99:
            rip_r = 93.0 + self._ripple_t * 32.0
            rip_c = QColor(accent)
            rip_c.setAlpha(int((1.0 - self._ripple_t) * 110))
            painter.setPen(QPen(rip_c, 1.8 * (1.0 - self._ripple_t)))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), rip_r, rip_r)

        # Progress sweep arc during assembly or file drop
        if self._install_t < 0.995:
            arc_rect = QRectF(cx - 94.5, cy - 94.5, 189.0, 189.0)
            track_col = QColor(accent)
            track_col.setAlpha(45)
            painter.setPen(QPen(track_col, 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(arc_rect)
            painter.setPen(QPen(accent.lighter(115), 2.8, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(arc_rect, 90 * 16, int(-self._install_t * 360.0 * 16))

        # 3. Sculpted 6-petal kinetic aperture with per-petal hover pop
        painter.save()
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)

        outer_r = 86.0
        inner_r = 32.0
        gap_rad = 0.155
        base_grad_hi = accent.lighter(122)
        base_grad_lo = accent.darker(116)
        ready_sheen = accent.lighter(108)

        for idx in range(6):
            hover_amt = max(
                self._petal_anim_hover[idx],
                1.0 if idx == self._hovered_idx else 0.0,
            )
            mid_ang = rot_rad - math.pi / 2.0 + idx * ((2.0 * math.pi) / 6.0)
            pop = hover_amt * 4.0
            px = cx + math.cos(mid_ang) * pop
            py = cy + math.sin(mid_ang) * pop

            petal = _build_emblem_petal(px, py, idx, 6, inner_r, outer_r, gap_rad, rot_rad)
            is_active = idx == self._selected_idx or idx == self._hovered_idx
            fill = QRadialGradient(QPointF(px, py), outer_r)
            if is_active or hover_amt > 0.25:
                fill.setColorAt(0.20, accent.lighter(134))
                fill.setColorAt(0.75, base_grad_hi)
                fill.setColorAt(1.0, ready_sheen)
            else:
                fill.setColorAt(0.22, base_grad_hi if idx in (0, 1, 5) else ready_sheen)
                fill.setColorAt(0.78, accent)
                fill.setColorAt(1.0, base_grad_lo)

            rim_col = QColor(255, 255, 255, 110 if is_active else 36)
            painter.setPen(QPen(rim_col, 1.3 if is_active else 0.9))
            painter.setBrush(QBrush(fill))
            painter.drawPath(petal)

        # Machined center optical hub
        hub_r = 28.0
        hub_fill = QColor(t["tooltip_bg"])
        painter.setPen(QPen(QColor(255, 255, 255, 48), 1.0))
        painter.setBrush(hub_fill)
        painter.drawEllipse(QPointF(cx, cy), hub_r, hub_r)

        inner_ring = QColor(accent)
        inner_ring.setAlpha(int(120 + 90 * self._hover_t))
        painter.setPen(QPen(inner_ring, 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), hub_r * 0.72, hub_r * 0.72)

        center_badge = self._CENTER_BADGE_BY_MODE.get(self._studio_mode)
        if center_badge:
            painter.setPen(QColor("#FFFFFF"))
            badge_font = QFont(
                ".AppleSystemUIFont",
                14 if len(center_badge) == 1 else 9,
                QFont.Weight.Bold,
            )
            painter.setFont(badge_font)
            painter.drawText(
                QRectF(cx - hub_r, cy - hub_r, hub_r * 2.0, hub_r * 2.0),
                Qt.AlignCenter,
                center_badge,
            )
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 240))
            core_r = 8.5 + 1.8 * self._hover_t
            painter.drawEllipse(QPointF(cx, cy), core_r, core_r)
        painter.restore()

        # 4. Open precision dial captions around the ring (no floating card boxes)
        chip_rects = self._orbital_node_rects()
        title_font = QFont(".AppleSystemUIFont", 11, QFont.Weight.DemiBold)
        sub_font = QFont(".AppleSystemUIFont", 10, QFont.Weight.Normal)

        for idx, (rect, (name, tag, _preview)) in enumerate(zip(chip_rects, self.active_specs())):
            is_sel = idx == self._selected_idx
            is_hov = idx == self._hovered_idx
            hot = is_sel or is_hov

            p_center = rect.center()
            dx, dy = p_center.x() - cx, p_center.y() - cy
            dist = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / dist, dy / dist
            dot_r = cx + ux * 112.5, cy + uy * 112.5

            if hot:
                start_pt = QPointF(dot_r[0], dot_r[1])
                edge_t = min(
                    (rect.width() * 0.5) / max(0.001, abs(ux)) if abs(ux) > 0.01 else 999.0,
                    (rect.height() * 0.5) / max(0.001, abs(uy)) if abs(uy) > 0.01 else 999.0,
                )
                end_pt = QPointF(p_center.x() - ux * (edge_t + 3.0), p_center.y() - uy * (edge_t + 3.0))
                if idx != 0 and math.hypot(end_pt.x() - start_pt.x(), end_pt.y() - start_pt.y()) > 4.0:
                    leader = QColor(accent)
                    leader.setAlpha(175 if is_hov else 120)
                    painter.setPen(QPen(leader, 1.1, Qt.SolidLine, Qt.RoundCap))
                    painter.drawLine(start_pt, end_pt)

            if idx != 0:
                pip = QColor(accent if hot else border_strong)
                pip.setAlpha(235 if hot else 140)
                painter.setPen(Qt.NoPen)
                painter.setBrush(pip)
                painter.drawEllipse(QPointF(dot_r[0], dot_r[1]), 2.2 if hot else 1.6, 2.2 if hot else 1.6)

            painter.setFont(title_font)
            painter.setPen(QColor(accent_text if hot else t["text_primary"]))
            painter.drawText(
                QRectF(rect.x(), rect.y() + 4.0, rect.width(), 15.0),
                Qt.AlignCenter,
                name,
            )

            painter.setFont(sub_font)
            painter.setPen(QColor(t["text_secondary"] if hot else t["text_muted"]))
            painter.drawText(
                QRectF(rect.x(), rect.y() + 19.0, rect.width(), 14.0),
                Qt.AlignCenter,
                tag,
            )


class _HapticWheelSandbox(QWidget):
    """Real WheelPainter sandbox with smooth hover morph, key spin, sticky preview, and Finder file drops."""

    petal_triggered = Signal(str, str, str)
    real_file_dropped = Signal(str, str)
    sticky_toggled = Signal(bool)
    sticky_petal_changed = Signal(str, str)

    SAMPLE_SPECS: Dict[str, Tuple[str, str, str]] = {
        "sample_photo": ("vacation_photo.heic", "image", "4.2 MB"),
        "sample_video": ("launch_demo.mov", "video", "28.6 MB"),
        "sample_doc": ("architecture_spec.pdf", "document", "6 pages"),
    }

    DYNAMIC_ITEMS: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
        "sample_photo": {
            "convert": [("JPG", "jpg"), ("PNG", "png"), ("WebP", "webp"), ("GIF", "gif"), ("PDF", "pdf"), ("SVG", "svg")],
            "tools": [("Compress", "compress"), ("Resize", "resize"), ("Rotate", "rotate"), ("Strip EXIF", "metadata"), ("Crop", "crop"), ("ZIP", "zip")],
            "actions": [("Quick Look", "float"), ("AirDrop", "airdrop"), ("Copy Path", "copy_path"), ("Duplicate", "copy"), ("Terminal", "terminal"), ("Reveal", "move")],
        },
        "sample_video": {
            "convert": [("MP4", "mp4"), ("GIF", "gif"), ("MP3", "mp3"), ("WAV", "wav"), ("MOV", "mov"), ("ZIP", "zip")],
            "tools": [("Compress", "compress"), ("Trim Clip", "trim"), ("Split", "split"), ("Resize", "resize"), ("Strip Meta", "metadata"), ("Merge", "merge")],
            "actions": [("Quick Look", "float"), ("AirDrop", "airdrop"), ("Copy Path", "copy_path"), ("Duplicate", "copy"), ("Terminal", "terminal"), ("Reveal", "move")],
        },
        "sample_doc": {
            "convert": [("DOCX", "pdf"), ("PNG", "png"), ("JPG", "jpg"), ("TXT", "convert"), ("SVG", "svg"), ("ZIP", "zip")],
            "tools": [("Compress", "compress"), ("Split PDF", "split"), ("Merge PDF", "merge"), ("Strip Meta", "metadata"), ("Rotate", "rotate"), ("ZIP", "zip")],
            "actions": [("Quick Look", "float"), ("AirDrop", "airdrop"), ("Copy Path", "copy_path"), ("Duplicate", "copy"), ("Terminal", "terminal"), ("Reveal", "move")],
        },
    }

    OUTCOME_PREVIEWS: Dict[Tuple[str, str], str] = {
        ("sample_photo", "JPG"): "vacation_photo.jpg (1.2 MB, -71%)",
        ("sample_photo", "PNG"): "vacation_photo.png (lossless RGB)",
        ("sample_photo", "WebP"): "vacation_photo.webp (680 KB)",
        ("sample_photo", "GIF"): "vacation_photo.gif (256-color)",
        ("sample_photo", "PDF"): "vacation_photo.pdf (print page)",
        ("sample_photo", "SVG"): "vacation_photo.svg (vector wrap)",
        ("sample_photo", "Compress"): "vacation_photo.heic (1.3 MB, -69%)",
        ("sample_photo", "Resize"): "vacation_photo_1920.heic ready",
        ("sample_photo", "Rotate"): "vacation_photo_90deg.heic ready",
        ("sample_photo", "Strip EXIF"): "vacation_photo_clean.heic (no EXIF)",
        ("sample_photo", "Crop"): "vacation_photo_crop.heic (16:9)",
        ("sample_video", "MP4"): "launch_demo.mp4 (1080p, 9.4 MB)",
        ("sample_video", "GIF"): "launch_demo.gif (15 fps loop)",
        ("sample_video", "MP3"): "launch_demo.mp3 (192 kbps audio)",
        ("sample_video", "WAV"): "launch_demo.wav (24-bit PCM)",
        ("sample_video", "Compress"): "launch_demo.mov (8.2 MB, -71%)",
        ("sample_video", "Trim Clip"): "launch_demo_trim.mov (keyframe)",
        ("sample_video", "Split"): "launch_demo_1..2.mov (2 parts)",
        ("sample_doc", "DOCX"): "architecture_spec.docx ready",
        ("sample_doc", "PNG"): "architecture_spec_1..6.png (300 DPI)",
        ("sample_doc", "TXT"): "architecture_spec.txt (UTF-8)",
        ("sample_doc", "Compress"): "architecture_spec.pdf (1.1 MB)",
        ("sample_doc", "Split PDF"): "architecture_spec_1..6.pdf (6 files)",
        ("sample_doc", "Merge PDF"): "architecture_spec_merged.pdf",
        ("sample_doc", "Strip Meta"): "architecture_spec_clean.pdf",
    }

    def __init__(self, tokens: dict, dark_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tokens = tokens
        self._dark_mode = bool(dark_mode)
        self._accent_key = "amber"
        self._wheel_type = "convert"
        self._sample_key = "sample_photo"
        self._custom_filename: Optional[str] = None
        self._hovered_idx: Optional[int] = None
        self._hover_progress: float = 0.0
        self._last_clicked_idx: Optional[int] = None
        self._open_scale: float = 1.0
        self._switch_rotation: float = 0.0
        self._switch_last_detent: Optional[int] = None
        self._sticky_locked: bool = False
        self._drop_state: str = "none"
        self._drop_progress: float = 0.0
        self._job_progress: int = 0
        self._painter = WheelPainter()
        self._segments = []

        # Center remains (width()/2, height()/2) so (cx, cy - 80) always hits petal 0
        self.setFixedSize(336, 276)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(110)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_anim)

        self._switch_anim = QVariantAnimation(self)
        self._switch_anim.setDuration(360)
        self._switch_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._switch_anim.valueChanged.connect(self._on_switch_anim)
        self._switch_anim.finished.connect(self._on_switch_done)

        self._burst_anim = QVariantAnimation(self)
        self._burst_anim.setDuration(720)
        self._burst_anim.setStartValue(0.0)
        self._burst_anim.setEndValue(1.0)
        self._burst_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._burst_anim.valueChanged.connect(self._on_burst_step)
        self._burst_anim.finished.connect(self._on_burst_done)

        self._rebuild_segments()

    def set_theme(self, tokens: dict, accent_key: str, dark_mode: Optional[bool] = None) -> None:
        self._tokens = tokens
        if dark_mode is not None:
            self._dark_mode = bool(dark_mode)
        self._accent_key = accent_key
        self.update()

    def set_sample_file(self, sample_key: str) -> None:
        if sample_key in self.SAMPLE_SPECS and self._sample_key != sample_key:
            self._sample_key = sample_key
            self._custom_filename = None
            self._hovered_idx = None
            self._hover_progress = 0.0
            self._last_clicked_idx = None
            self._rebuild_segments()
            self._play_switch_morph()
            self.update()

    def set_wheel_type(self, wheel_type: str) -> None:
        if wheel_type not in ("convert", "tools", "actions"):
            return
        self._wheel_type = wheel_type
        if not self._sticky_locked:
            self._hovered_idx = None
            self._hover_progress = 0.0
        else:
            self._hovered_idx = 0 if self._segments else None
            self._hover_progress = 1.0 if self._hovered_idx is not None else 0.0
        self._last_clicked_idx = None
        self._rebuild_segments()
        self._play_switch_morph(-120.0)
        self.update()

    def set_sticky_preview(self, locked: bool, *, spin: bool = True) -> None:
        """Toggle sticky keep-open preview right in the sandbox wheel."""
        self._sticky_locked = bool(locked)
        if self._sticky_locked and self._segments:
            if self._hovered_idx is None:
                self._hovered_idx = 0
            self._hover_progress = 1.0
        elif not self._sticky_locked:
            self._hovered_idx = None
            self._hover_progress = 0.0
        if spin:
            self._play_switch_morph(60.0 if self._sticky_locked else -45.0)
        self.update()

    def step_selection(self, delta: int) -> None:
        """Step hovered petal clockwise/counterclockwise via arrow keys."""
        if not self._segments:
            return
        n = len(self._segments)
        cur = 0 if self._hovered_idx is None else self._hovered_idx
        nxt = (cur + delta) % n
        self._hovered_idx = nxt
        self._hover_progress = 1.0
        trigger_haptic_tick("alignment")
        self._play_switch_morph(-36.0 if delta >= 0 else 36.0)
        seg = self._segments[nxt]
        self.sticky_petal_changed.emit(seg.label, self._simulate_outcome(seg.label))
        self.update()

    def stop_animations(self) -> None:
        self._hover_anim.stop()
        self._switch_anim.stop()
        self._burst_anim.stop()

    def _play_switch_morph(self, spin_deg: float = -120.0) -> None:
        if should_reduce_motion():
            self._open_scale = 1.0
            self._switch_rotation = 0.0
            return
        self._spin_deg_start = float(spin_deg)
        self._switch_last_detent = None
        self._switch_anim.stop()
        self._switch_anim.setStartValue(0.0)
        self._switch_anim.setEndValue(1.0)
        self._switch_anim.start()

    def _on_switch_anim(self, value: object) -> None:
        p = _clamp01(float(value))
        self._open_scale = 0.92 + 0.08 * min(1.0, p * 1.15)
        start_deg = getattr(self, "_spin_deg_start", -120.0)
        self._switch_rotation = start_deg * (1.0 - p)
        detent = int(round(self._switch_rotation / 60.0))
        if self._switch_last_detent is not None and detent != self._switch_last_detent:
            trigger_haptic_tick("alignment")
        self._switch_last_detent = detent
        self.update()

    def _on_switch_done(self) -> None:
        self._switch_rotation = 0.0
        self._open_scale = 1.0
        self._switch_last_detent = None
        self.update()

    def _on_hover_anim(self, value: object) -> None:
        self._hover_progress = float(value)
        self.update()

    def _on_burst_step(self, value: object) -> None:
        p = float(value)
        if p < 0.48:
            self._drop_state = "progress"
            self._job_progress = int((p / 0.48) * 100.0)
            self._drop_progress = 0.0
            self._open_scale = 1.0 + 0.02 * math.sin(p / 0.48 * math.pi)
        else:
            if self._drop_state != "done":
                self._drop_state = "done"
                trigger_haptic_tick("alignment")
            self._job_progress = 100
            self._drop_progress = (p - 0.48) / 0.52
            self._open_scale = 1.0
        self.update()

    def _on_burst_done(self) -> None:
        self._drop_state = "none"
        self._drop_progress = 0.0
        self._job_progress = 0
        self._open_scale = 1.0
        self.update()

    def _rebuild_segments(self) -> None:
        raw_items = self.DYNAMIC_ITEMS.get(self._sample_key, self.DYNAMIC_ITEMS["sample_photo"]).get(
            self._wheel_type, self.DYNAMIC_ITEMS["sample_photo"]["convert"]
        )
        seg_action_type = {"convert": "convert", "tools": "tool", "actions": "action"}.get(
            self._wheel_type, self._wheel_type
        )
        items = [
            {"label": label, "icon": icon, "action_type": seg_action_type}
            for label, icon in raw_items
        ]
        self._segments = layout_segments(items, ring=1)

    def _update_hover(self, pos: QPointF) -> None:
        cx, cy = self.width() / 2.0, self.height() / 2.0
        hit = hit_test_radial(pos.x() - cx, pos.y() - cy, len(self._segments))
        new_hover = hit if hit >= 0 else None
        if new_hover != self._hovered_idx:
            self._hovered_idx = new_hover
            target = 1.0 if new_hover is not None else 0.0
            if should_reduce_motion():
                self._hover_progress = target
            else:
                self._hover_anim.stop()
                self._hover_anim.setStartValue(self._hover_progress)
                self._hover_anim.setEndValue(target)
                self._hover_anim.start()
            if new_hover is not None:
                trigger_haptic_tick("alignment")
            self.update()

    def mouseMoveEvent(self, event) -> None:
        self._update_hover(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._sticky_locked and self._hovered_idx is not None:
            self._hovered_idx = None
            if should_reduce_motion():
                self._hover_progress = 0.0
            else:
                self._hover_anim.stop()
                self._hover_anim.setStartValue(self._hover_progress)
                self._hover_anim.setEndValue(0.0)
                self._hover_anim.start()
            self.update()
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = collect_paths_from_urls(event.mimeData().urls())
        if paths:
            path = paths[0]
            ext = path.suffix.lower().lstrip(".")
            if ext in ("mp4", "mov", "mkv", "webm", "avi", "mp3", "wav", "m4a", "aac", "flac"):
                self._sample_key = "sample_video"
            elif ext in ("pdf", "docx", "doc", "txt", "md", "html", "rtf"):
                self._sample_key = "sample_doc"
            else:
                self._sample_key = "sample_photo"
            self._custom_filename = path.name
            self._rebuild_segments()
            self._play_switch_morph()
            trigger_haptic_tick("level_change")
            self.real_file_dropped.emit(path.name, self._sample_key)
            event.acceptProposedAction()
            self.update()
        else:
            super().dropEvent(event)

    def _simulate_outcome(self, label: str) -> str:
        sample_name, _, _ = self.SAMPLE_SPECS.get(self._sample_key, ("sample.heic", "image", "4.2 MB"))
        display_name = self._custom_filename or sample_name
        stem = display_name.rsplit(".", 1)[0]
        if not self._custom_filename and (self._sample_key, label) in self.OUTCOME_PREVIEWS:
            return self.OUTCOME_PREVIEWS[(self._sample_key, label)]
        if label == "ZIP":
            return f"{stem}.zip saved"
        if label == "Quick Look":
            return f"Quick Look opened for {display_name}"
        if label == "AirDrop":
            return f"AirDrop ready for {display_name}"
        if label == "Copy Path":
            return f"Copied ~/Desktop/{display_name}"
        if label == "Duplicate":
            return f"Saved {stem} (1).{display_name.rsplit('.', 1)[-1]}"
        if label == "Terminal":
            return f"Terminal opened at {display_name}"
        if label == "Reveal":
            return f"Revealed {display_name} in Finder"
        if self._wheel_type == "convert":
            return f"{stem}.{label.lower()} ready"
        return f"Simulated {label} ready for {display_name}"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position()
            cx, cy = self.width() / 2.0, self.height() / 2.0
            dist_center = math.hypot(pos.x() - cx, pos.y() - cy)
            if dist_center < 40.0:
                self.set_sticky_preview(not self._sticky_locked)
                trigger_haptic_tick("level_change")
                self.sticky_toggled.emit(self._sticky_locked)
                super().mousePressEvent(event)
                return
            self._update_hover(pos)
            if self._hovered_idx is not None and 0 <= self._hovered_idx < len(self._segments):
                seg = self._segments[self._hovered_idx]
                self._last_clicked_idx = self._hovered_idx
                play_tactile_feedback("level_change", sound_name="Pop")
                if not should_reduce_motion():
                    self._burst_anim.stop()
                    self._burst_anim.start()
                outcome = self._simulate_outcome(seg.label)
                self.petal_triggered.emit(self._wheel_type, seg.label, outcome)
                self.update()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        sample_name = self._custom_filename or self.SAMPLE_SPECS.get(self._sample_key, ("sample.heic",))[0]
        state = WheelState(
            wheel_type=self._wheel_type,
            primary_segments=self._segments,
            hovered_index=self._hovered_idx if self._hovered_idx is not None else -1,
            hovered_ring=1,
            hover_progress=self._hover_progress,
            dark_mode=self._dark_mode,
            accent_color=self._tokens["accent"],
            accent_hover=self._tokens["accent_hover"],
            open_scale=self._open_scale,
            open_opacity=1.0,
            switch_rotation=self._switch_rotation,
            drop_state=self._drop_state,
            drop_progress=self._drop_progress,
            job_progress=self._job_progress,
            file_name=sample_name,
            file_count=1,
        )
        self._painter.paint(painter, self.width(), self.height(), state)

        if self._sticky_locked:
            cx, cy = self.width() / 2.0, self.height() / 2.0
            accent = QColor(self._tokens["accent"])
            ring_c = QColor(accent)
            ring_c.setAlpha(210)
            painter.setPen(QPen(ring_c, 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), 41.0, 41.0)
            pill = QRectF(cx - 24.0, cy + 29.0, 48.0, 14.0)
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawRoundedRect(pill, 7.0, 7.0)
            painter.setPen(QColor(self._tokens["accent_fg"]))
            painter.setFont(QFont(".AppleSystemUIFont", 8, QFont.Weight.Bold))
            painter.drawText(pill, Qt.AlignCenter, "PINNED")


class _ConsentCheckbox(QAbstractButton):
    """Crisp keyboard-accessible checkbox for Privacy Policy & Terms consent."""

    def __init__(self, text: str, tokens: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tokens = tokens
        self._hovered = False
        self.setCheckable(True)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(26)

    def set_theme(self, tokens: dict) -> None:
        self._tokens = tokens
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = self._tokens
        checked = self.isChecked()

        box_size = 18.0
        box_y = (self.height() - box_size) / 2.0
        box_rect = QRectF(1.0, box_y, box_size, box_size)

        if self.hasFocus():
            focus_rect = box_rect.adjusted(-2.5, -2.5, 2.5, 2.5)
            painter.setPen(QPen(QColor(t["border_focus"]), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(focus_rect, 6.5, 6.5)

        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(t["accent"]))
            painter.drawRoundedRect(box_rect, 5.0, 5.0)

            pen = QPen(QColor(t["accent_fg"]), 2.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            check = QPainterPath()
            check.moveTo(box_rect.left() + 4.3, box_rect.top() + 9.4)
            check.lineTo(box_rect.left() + 7.7, box_rect.top() + 12.8)
            check.lineTo(box_rect.left() + 13.7, box_rect.top() + 5.6)
            painter.drawPath(check)
        else:
            bg = QColor(t["bg_surface_hover"] if self._hovered else t["bg_surface"])
            bd = QColor(t["accent"] if self._hovered else t["border_strong"])
            painter.setPen(QPen(bd, 1.4))
            painter.setBrush(bg)
            painter.drawRoundedRect(box_rect, 5.0, 5.0)

        painter.setPen(QColor(t["text_primary"]))
        painter.setFont(QFont(".AppleSystemUIFont", 12, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(28.0, 0.0, max(10.0, self.width() - 32.0), float(self.height())),
            Qt.AlignVCenter | Qt.AlignLeft | Qt.TextSingleLine,
            self.text(),
        )


class OnboardingWindow(QWidget):
    """3-step macOS onboarding sheet: interactive kinetic aperture studio, Finder wheel sandbox, and legal consent."""

    onboarding_completed = Signal(dict)
    onboarding_declined = Signal()
    theme_preview_changed = Signal(bool, str)

    STEP_INTRO = 0
    STEP_SANDBOX = 1
    STEP_LEGAL = 2

    def __init__(
        self,
        *,
        dark_mode: Optional[bool] = None,
        accent_key: Optional[str] = None,
        first_boot: bool = True,
        initial_step: int = STEP_INTRO,
        initial_legal_doc: str = "privacy",
        qsettings: Optional[QSettings] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.qsettings = qsettings if qsettings is not None else QSettings("Fluxora", "Fluxora")
        self._first_boot = bool(first_boot)
        self._dark_mode = bool(dark_mode) if dark_mode is not None else bool(self.qsettings.value("dark_mode", False, type=bool))
        self._accent_key = (
            normalize_accent_key(accent_key)
            if accent_key is not None
            else migrate_accent_setting(self.qsettings)
        )
        self._tokens = get_tokens(self._dark_mode, accent_key=self._accent_key)
        self._current_step = max(0, min(2, int(initial_step)))
        self._legal_doc = "terms" if initial_legal_doc == "terms" else "privacy"
        self._drag_origin: Optional[QPoint] = None
        self._shake_anim: Optional[QVariantAnimation] = None
        self._fade_anim: Optional[QVariantAnimation] = None

        self.setObjectName("onboardingRoot")
        self.setWindowTitle("Welcome to Fluxora")
        self.setFixedSize(880, 568)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._cap_labels: List[QLabel] = []
        self._pillar_rows: List[_InteractivePillarRow] = []
        self._intro_key_btns: Dict[str, QPushButton] = {}
        self._active_intro_key: Optional[str] = None
        self._trigger_keys: Dict[str, str] = {
            "convert": self._read_trigger_key("trigger_convert", "Shift"),
            "tools": self._read_trigger_key("trigger_tools", "Command"),
            "actions": self._read_trigger_key("trigger_actions", "Control"),
        }
        self._trust_icons: List[_VectorIcon] = []
        self._sample_btns: Dict[str, QPushButton] = {}
        self._build_ui()
        self._apply_tokens()
        self.go_to_step(self._current_step, emit_haptic=False)
        self.select_legal_doc(self._legal_doc, emit_haptic=False)

    def _read_trigger_key(self, pref_key: str, default: str) -> str:
        raw = str(self.qsettings.value(pref_key, default, type=str) or default)
        return raw if raw in _MODIFIER_SYMBOLS else default

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Native macOS stepper header with centered step rail
        self.header = QWidget()
        self.header.setObjectName("onboardingHeader")
        self.header.setFixedHeight(48)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(18, 0, 16, 0)
        h_layout.setSpacing(0)

        left_brand = QWidget()
        left_brand.setFixedWidth(180)
        lb_layout = QHBoxLayout(left_brand)
        lb_layout.setContentsMargins(0, 0, 0, 0)
        lb_layout.setSpacing(8)
        self.header_logo = LogoWidget(size=22)
        self.header_logo.set_accent_color(self._tokens["accent"])
        lb_layout.addWidget(self.header_logo, 0, Qt.AlignVCenter)
        title_lbl = QLabel("Fluxora")
        title_lbl.setObjectName("onboardingRowLabel")
        lb_layout.addWidget(title_lbl, 0, Qt.AlignVCenter)
        lb_layout.addStretch(1)
        h_layout.addWidget(left_brand)

        h_layout.addStretch(1)

        step_group = QFrame()
        step_group.setObjectName("onboardingStepGroup")
        step_group.setFixedHeight(32)
        sg_layout = QHBoxLayout(step_group)
        sg_layout.setContentsMargins(3, 3, 3, 3)
        sg_layout.setSpacing(2)

        self._step_pills: List[QPushButton] = []
        for idx, name in enumerate(("Intro", "Drag Wheel", "Privacy && Terms")):
            pill = QPushButton(name)
            pill.setObjectName("onboardingStepPill")
            pill.setFixedHeight(26)
            pill.setCursor(Qt.PointingHandCursor)
            pill.clicked.connect(lambda _=False, s=idx: self.go_to_step(s))
            sg_layout.addWidget(pill)
            self._step_pills.append(pill)
        h_layout.addWidget(step_group, 0, Qt.AlignVCenter)

        h_layout.addStretch(1)

        right_actions = QWidget()
        right_actions.setFixedWidth(180)
        ra_layout = QHBoxLayout(right_actions)
        ra_layout.setContentsMargins(0, 0, 0, 0)
        ra_layout.setSpacing(6)
        ra_layout.addStretch(1)

        self.theme_toggle_btn = _ThemeToggleButton(self._dark_mode, self._tokens)
        self.theme_toggle_btn.clicked.connect(lambda: self._on_theme_picked(not self._dark_mode))
        ra_layout.addWidget(self.theme_toggle_btn, 0, Qt.AlignVCenter)

        self.skip_to_legal_btn = QPushButton("Skip")
        self.skip_to_legal_btn.setObjectName("subtleLinkButton")
        self.skip_to_legal_btn.setCursor(Qt.PointingHandCursor)
        sp_skip = self.skip_to_legal_btn.sizePolicy()
        sp_skip.setRetainSizeWhenHidden(True)
        self.skip_to_legal_btn.setSizePolicy(sp_skip)
        self.skip_to_legal_btn.clicked.connect(lambda: self.go_to_step(self.STEP_LEGAL))
        ra_layout.addWidget(self.skip_to_legal_btn, 0, Qt.AlignVCenter)
        h_layout.addWidget(right_actions)
        root.addWidget(self.header)

        # Body stack
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_intro_page())
        self.stack.addWidget(self._build_sandbox_page())
        self.stack.addWidget(self._build_legal_page())
        root.addWidget(self.stack, 1)

        # Footer action bar
        self.footer = QWidget()
        self.footer.setObjectName("onboardingFooter")
        self.footer.setFixedHeight(58)
        f_layout = QHBoxLayout(self.footer)
        f_layout.setContentsMargins(20, 0, 20, 0)
        f_layout.setSpacing(10)

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._on_back)
        f_layout.addWidget(self.back_btn)

        self.replay_anim_btn = QPushButton("Replay Intro")
        self.replay_anim_btn.setObjectName("subtleLinkButton")
        self.replay_anim_btn.setCursor(Qt.PointingHandCursor)
        self.replay_anim_btn.clicked.connect(lambda: self.start_intro(emit_haptics=True))
        f_layout.addWidget(self.replay_anim_btn)

        self.decline_btn = QPushButton("Decline && Quit" if self._first_boot else "Close")
        self.decline_btn.setObjectName("dangerSubtleButton" if self._first_boot else "secondaryButton")
        self.decline_btn.setCursor(Qt.PointingHandCursor)
        self.decline_btn.clicked.connect(self._on_decline)
        f_layout.addWidget(self.decline_btn)

        self.footer_hint_lbl = QLabel("")
        self.footer_hint_lbl.setObjectName("onboardingRowSub")
        f_layout.addWidget(self.footer_hint_lbl)

        f_layout.addStretch()

        self.primary_btn = QPushButton("Get Started")
        self.primary_btn.setObjectName("primaryButton")
        self.primary_btn.setCursor(Qt.PointingHandCursor)
        self.primary_btn.setMinimumHeight(34)
        self.primary_btn.clicked.connect(self._on_primary)
        f_layout.addWidget(self.primary_btn)

        root.addWidget(self.footer)

    def _build_intro_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left editorial column
        left_pane = QWidget()
        left_pane.setObjectName("onboardingEditorialPane")
        left_pane.setFixedWidth(396)
        left_lay = QVBoxLayout(left_pane)
        left_lay.setContentsMargins(24, 28, 20, 22)
        left_lay.setSpacing(0)

        headline = QLabel("File tools at\nyour cursor.")
        headline.setObjectName("onboardingHeroTitle")
        left_lay.addWidget(headline)

        left_lay.addSpacing(10)

        lead = QLabel(
            "Convert 266 format pairs, compress media, and trigger macOS actions locally right from Finder."
        )
        lead.setObjectName("onboardingLead")
        lead.setWordWrap(True)
        left_lay.addWidget(lead)

        left_lay.addSpacing(26)

        self._cap_labels.clear()
        self._pillar_rows.clear()
        wheel_sub = (
            f"Tap {_MODIFIER_SHORT_NAMES.get(self._trigger_keys['convert'], 'Shift')}, "
            f"{_MODIFIER_SHORT_NAMES.get(self._trigger_keys['tools'], 'Cmd')} or "
            f"{_MODIFIER_SHORT_NAMES.get(self._trigger_keys['actions'], 'Ctrl')} mid-drag"
        )
        pillars = (
            ("convert", "266 Format Pairs", "Images, RAW, video & PDF", "Codecs verified", 0),
            ("sliders", "Finder Drag Wheel", wheel_sub, "Quartz ready", 4),
            ("shield", "100% On Your Mac", "Zero cloud uploads or telemetry", "100% offline", 5),
        )
        for cap_idx, (icon_name, title, desc, initial_badge, target_sector) in enumerate(pillars):
            row = _InteractivePillarRow(
                index=target_sector,
                icon_name=icon_name,
                title=title,
                subtitle=desc,
                initial_badge=initial_badge,
                tokens=self._tokens,
            )
            row.set_selected(cap_idx == 0)
            row.activated.connect(lambda sec, ci=cap_idx: self._on_pillar_activated(ci, sec))
            left_lay.addWidget(row)
            if cap_idx < len(pillars) - 1:
                left_lay.addSpacing(6)
            self._pillar_rows.append(row)
            self._cap_labels.append(row.status_label)

        left_lay.addStretch(1)
        layout.addWidget(left_pane)

        vdiv = QFrame()
        vdiv.setObjectName("onboardingVDivider")
        layout.addWidget(vdiv)

        # Right interactive kinetic dial studio
        right_pane = QWidget()
        right_pane.setObjectName("onboardingSplitStage")
        right_lay = QVBoxLayout(right_pane)
        right_lay.setContentsMargins(14, 12, 14, 16)
        right_lay.setSpacing(8)

        right_lay.addStretch(1)
        self.hero_canvas = _StarterInstallCanvas(self._tokens)
        self.hero_canvas.capability_unlocked.connect(self._on_cap_unlocked)
        self.hero_canvas.install_finished.connect(self._on_intro_finished)
        self.hero_canvas.petal_hovered.connect(self._on_hero_petal_hovered)
        self.hero_canvas.petal_clicked.connect(self._on_hero_petal_clicked)
        self.hero_canvas.file_dropped_preview.connect(self._on_hero_file_dropped)
        right_lay.addWidget(self.hero_canvas, 0, Qt.AlignHCenter)

        intro_key_row = QHBoxLayout()
        intro_key_row.setSpacing(6)
        intro_key_row.addStretch()
        self._intro_key_btns.clear()
        intro_keys = (
            ("convert", _format_key_badge(self._trigger_keys["convert"], short=True)),
            ("tools", _format_key_badge(self._trigger_keys["tools"], short=True)),
            ("actions", _format_key_badge(self._trigger_keys["actions"], short=True)),
            ("sticky", "↩ Sticky"),
        )
        for mode_key, label in intro_keys:
            btn = QPushButton(label)
            btn.setObjectName("onboardingKeycap")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", "false")
            btn.clicked.connect(lambda _=False, mk=mode_key: self._select_intro_wheel_key(mk))
            intro_key_row.addWidget(btn)
            self._intro_key_btns[mode_key] = btn
        intro_key_row.addStretch()
        right_lay.addLayout(intro_key_row)

        self.hero_status_lbl = _ActiveCommandBar(self._tokens, max_width=448)
        self.hero_status_lbl.setObjectName("onboardingHeroStatus")
        self.hero_status_lbl.set_command(
            badge="Starting",
            source="Checking local codecs...",
            active=False,
            raw_text="Checking local codecs...",
            icon="sliders",
        )
        right_lay.addWidget(self.hero_status_lbl, 0, Qt.AlignHCenter)
        right_lay.addStretch(1)

        layout.addWidget(right_pane, 1)
        return page

    def _build_sandbox_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left Finder drop backdrop
        stage = QWidget()
        stage.setObjectName("onboardingSplitStage")
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(20, 12, 20, 16)
        stage_layout.setSpacing(8)

        sample_group = QFrame()
        sample_group.setObjectName("tabGroup")
        sg_layout = QHBoxLayout(sample_group)
        sg_layout.setContentsMargins(3, 3, 3, 3)
        sg_layout.setSpacing(2)
        for sample_key, label in (
            ("sample_photo", "Photo.heic"),
            ("sample_video", "Clip.mov"),
            ("sample_doc", "Spec.pdf"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("tabButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("padding: 4px 12px; font-size: 11.5px;")
            btn.clicked.connect(lambda _=False, sk=sample_key: self._pick_sample_file(sk))
            sg_layout.addWidget(btn)
            self._sample_btns[sample_key] = btn
        stage_layout.addWidget(sample_group, 0, Qt.AlignHCenter)

        # Active Finder file caption showing live context for the wheel
        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 2, 0, 0)
        file_row.setSpacing(6)
        file_row.addStretch()
        self._sandbox_file_icon = _VectorIcon("file", self._tokens, tone="accent", size=14)
        file_row.addWidget(self._sandbox_file_icon)
        self.sandbox_file_lbl = QLabel("vacation_photo.heic  ·  4.2 MB")
        self.sandbox_file_lbl.setObjectName("onboardingRowSub")
        file_row.addWidget(self.sandbox_file_lbl)
        file_row.addStretch()
        stage_layout.addLayout(file_row)

        stage_layout.addStretch(1)
        self.wheel_sandbox = _HapticWheelSandbox(self._tokens, dark_mode=self._dark_mode)
        self.wheel_sandbox.petal_triggered.connect(self._on_sandbox_petal)
        self.wheel_sandbox.real_file_dropped.connect(self._on_sandbox_real_drop)
        self.wheel_sandbox.sticky_toggled.connect(self._on_sandbox_sticky_toggled)
        self.wheel_sandbox.sticky_petal_changed.connect(self._on_sandbox_sticky_petal)
        stage_layout.addWidget(self.wheel_sandbox, 0, Qt.AlignHCenter)
        stage_layout.addStretch(1)

        # Hardware modifier keycaps
        keycap_row = QHBoxLayout()
        keycap_row.setSpacing(6)
        keycap_row.addStretch()
        self._sandbox_mode_btns: Dict[str, QPushButton] = {}
        for mode_key, suffix in (("convert", "Convert"), ("tools", "Tools"), ("actions", "Actions")):
            sym = _MODIFIER_SYMBOLS.get(self._trigger_keys[mode_key], "⇧")
            btn = QPushButton(f"{sym}  {suffix}")
            btn.setObjectName("onboardingKeycap")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, m=mode_key: self._pick_sandbox_wheel(m))
            keycap_row.addWidget(btn)
            self._sandbox_mode_btns[mode_key] = btn

        self.sandbox_sticky_btn = QPushButton("↩  Sticky")
        self.sandbox_sticky_btn.setObjectName("onboardingKeycap")
        self.sandbox_sticky_btn.setCursor(Qt.PointingHandCursor)
        self.sandbox_sticky_btn.setProperty("active", "false")
        self.sandbox_sticky_btn.clicked.connect(self._toggle_sandbox_sticky)
        keycap_row.addWidget(self.sandbox_sticky_btn)
        keycap_row.addStretch()
        stage_layout.addLayout(keycap_row)

        self.sandbox_status = _ActiveCommandBar(self._tokens, max_width=496)
        self.sandbox_status.setObjectName("onboardingSandboxStatus")
        self.sandbox_status.set_command(
            badge="Preview",
            source="Hover or click a wheel petal to inspect output",
            active=False,
            raw_text="Hover or click a wheel petal to preview output",
            icon="sliders",
        )
        stage_layout.addWidget(self.sandbox_status, 0, Qt.AlignHCenter)

        layout.addWidget(stage, 1)

        vdiv = QFrame()
        vdiv.setObjectName("onboardingVDivider")
        layout.addWidget(vdiv)

        # Right native macOS Inspector pane
        inspector = QWidget()
        inspector.setObjectName("onboardingInspector")
        inspector.setFixedWidth(292)
        ins_layout = QVBoxLayout(inspector)
        ins_layout.setContentsMargins(22, 20, 22, 18)
        ins_layout.setSpacing(14)

        head_col = QVBoxLayout()
        head_col.setSpacing(2)
        ins_title = QLabel("Customize")
        ins_title.setObjectName("onboardingSectionTitle")
        ins_sub = QLabel("Changes apply across Fluxora")
        ins_sub.setObjectName("onboardingRowSub")
        head_col.addWidget(ins_title)
        head_col.addWidget(ins_sub)
        ins_layout.addLayout(head_col)

        app_col = QVBoxLayout()
        app_col.setSpacing(6)
        app_lbl = QLabel("Appearance")
        app_lbl.setObjectName("onboardingRowLabel")
        app_col.addWidget(app_lbl)

        mode_seg = QFrame()
        mode_seg.setObjectName("tabGroup")
        ms_layout = QHBoxLayout(mode_seg)
        ms_layout.setContentsMargins(3, 3, 3, 3)
        ms_layout.setSpacing(2)
        self.ob_light_btn = QPushButton("Light")
        self.ob_light_btn.setObjectName("tabButton")
        self.ob_light_btn.setCursor(Qt.PointingHandCursor)
        self.ob_light_btn.clicked.connect(lambda: self._on_theme_picked(False))
        self.ob_dark_btn = QPushButton("Dark")
        self.ob_dark_btn.setObjectName("tabButton")
        self.ob_dark_btn.setCursor(Qt.PointingHandCursor)
        self.ob_dark_btn.clicked.connect(lambda: self._on_theme_picked(True))
        ms_layout.addWidget(self.ob_light_btn, 1)
        ms_layout.addWidget(self.ob_dark_btn, 1)
        app_col.addWidget(mode_seg)
        ins_layout.addLayout(app_col)

        acc_row = QHBoxLayout()
        acc_lbl_col = QVBoxLayout()
        acc_lbl_col.setSpacing(1)
        acc_lbl = QLabel("Accent")
        acc_lbl.setObjectName("onboardingRowLabel")
        self.accent_name_lbl = QLabel(ACCENT_PRESETS[self._accent_key]["label"])
        self.accent_name_lbl.setObjectName("onboardingRowSub")
        acc_lbl_col.addWidget(acc_lbl)
        acc_lbl_col.addWidget(self.accent_name_lbl)
        acc_row.addLayout(acc_lbl_col, 1)

        self._accent_btns: Dict[str, QPushButton] = {}
        swatch_box = QHBoxLayout()
        swatch_box.setSpacing(6)
        for key, preset in ACCENT_PRESETS.items():
            btn = _AccentSwatchButton(key, preset["label"], preset["accent"], self._tokens)
            btn.clicked.connect(lambda _=False, k=key: self._on_accent_picked(k))
            swatch_box.addWidget(btn)
            self._accent_btns[key] = btn
        acc_row.addLayout(swatch_box)
        ins_layout.addLayout(acc_row)

        div = QFrame()
        div.setObjectName("onboardingDivider")
        ins_layout.addWidget(div)

        wheel_row = QHBoxLayout()
        wl_col = QVBoxLayout()
        wl_col.setSpacing(1)
        wl_title = QLabel("Finder Drag Wheel")
        wl_title.setObjectName("onboardingRowLabel")
        wl_sub = QLabel("Trigger on modifier taps")
        wl_sub.setObjectName("onboardingRowSub")
        wl_col.addWidget(wl_title)
        wl_col.addWidget(wl_sub)
        wheel_row.addLayout(wl_col, 1)
        wheel_lay_checked = (
            bool(self.qsettings.value("wheel_enabled", True, type=bool))
            if self.qsettings.contains("wheel_enabled")
            else bool(self.qsettings.value("drag_wheel_enabled", True, type=bool))
        )
        self.sw_wheel = IOSSwitch(
            checked=wheel_lay_checked,
            dark_mode=self._dark_mode,
        )
        self.sw_wheel.toggled.connect(lambda _c: trigger_haptic_tick("generic"))
        wheel_row.addWidget(self.sw_wheel)
        ins_layout.addLayout(wheel_row)

        acc_mode_row = QHBoxLayout()
        am_col = QVBoxLayout()
        am_col.setSpacing(1)
        am_title = QLabel("Menu-Bar Companion")
        am_title.setObjectName("onboardingRowLabel")
        am_sub = QLabel("Quick drops from top bar")
        am_sub.setObjectName("onboardingRowSub")
        am_col.addWidget(am_title)
        am_col.addWidget(am_sub)
        acc_mode_row.addLayout(am_col, 1)
        self.sw_accessory = IOSSwitch(
            checked=bool(self.qsettings.value("accessory_mode", True, type=bool)),
            dark_mode=self._dark_mode,
        )
        self.sw_accessory.toggled.connect(lambda _c: trigger_haptic_tick("generic"))
        acc_mode_row.addWidget(self.sw_accessory)
        ins_layout.addLayout(acc_mode_row)

        ins_layout.addStretch()

        perm_note = QLabel(
            "Uses Quartz CGEventSource drag state queries locally. Press 1-4, modifier keys, or ← → to inspect."
        )
        perm_note.setObjectName("onboardingRowSub")
        perm_note.setWordWrap(True)
        ins_layout.addWidget(perm_note)

        layout.addWidget(inspector)
        self._pick_sample_file("sample_photo", emit_haptic=False)
        self._pick_sandbox_wheel("convert", emit_haptic=False)
        return page

    def _build_legal_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._trust_icons.clear()

        # Left macOS source-list sidebar
        sidebar = QWidget()
        sidebar.setObjectName("onboardingSidebar")
        sidebar.setFixedWidth(248)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(24, 24, 20, 20)
        sb_layout.setSpacing(6)

        headline = QLabel("Privacy & Terms")
        headline.setObjectName("onboardingHeadline")
        lead = QLabel("All processing runs locally on your Mac.")
        lead.setObjectName("onboardingRowSub")
        lead.setWordWrap(True)
        sb_layout.addWidget(headline)
        sb_layout.addWidget(lead)
        sb_layout.addSpacing(12)

        self.tab_privacy_btn = QPushButton("Privacy Policy")
        self.tab_privacy_btn.setObjectName("onboardingSidebarTab")
        self.tab_privacy_btn.setCursor(Qt.PointingHandCursor)
        self.tab_privacy_btn.clicked.connect(lambda: self.select_legal_doc("privacy"))
        sb_layout.addWidget(self.tab_privacy_btn)

        self.tab_terms_btn = QPushButton("Terms && Conditions")
        self.tab_terms_btn.setObjectName("onboardingSidebarTab")
        self.tab_terms_btn.setCursor(Qt.PointingHandCursor)
        self.tab_terms_btn.clicked.connect(lambda: self.select_legal_doc("terms"))
        sb_layout.addWidget(self.tab_terms_btn)

        sb_layout.addStretch(1)

        hdiv = QFrame()
        hdiv.setObjectName("onboardingDivider")
        sb_layout.addWidget(hdiv)
        sb_layout.addSpacing(8)

        for summary_line in (
            "Zero network calls or telemetry",
            "Originals stay untouched",
            "MIT Open Source, provided AS IS",
            f"Legal version {LEGAL_VERSION}",
        ):
            note_lbl = QLabel(summary_line)
            note_lbl.setObjectName("onboardingRowSub")
            note_lbl.setWordWrap(True)
            sb_layout.addWidget(note_lbl)

        layout.addWidget(sidebar)

        vdiv = QFrame()
        vdiv.setObjectName("onboardingVDivider")
        layout.addWidget(vdiv)

        # Right open reading sheet + single consent hairline footer
        paper = QWidget()
        paper.setObjectName("onboardingLegalPaper")
        paper_lay = QVBoxLayout(paper)
        paper_lay.setContentsMargins(0, 0, 0, 0)
        paper_lay.setSpacing(0)

        paper_body = QWidget()
        pb_layout = QVBoxLayout(paper_body)
        pb_layout.setContentsMargins(32, 22, 12, 16)
        pb_layout.setSpacing(0)

        self.legal_browser = QTextBrowser()
        self.legal_browser.setObjectName("onboardingLegalView")
        self.legal_browser.setOpenExternalLinks(False)
        self.legal_browser.document().setDocumentMargin(0)
        pb_layout.addWidget(self.legal_browser, 1)
        paper_lay.addWidget(paper_body, 1)

        consent_strip = QWidget()
        consent_strip.setObjectName("onboardingConsentStrip")
        cs_layout = QHBoxLayout(consent_strip)
        cs_layout.setContentsMargins(32, 12, 32, 12)
        cs_layout.setSpacing(10)

        self.consent_checkbox = _ConsentCheckbox(
            "I accept the Offline Privacy Policy and MIT Terms of Use.",
            self._tokens,
        )
        self.consent_checkbox.toggled.connect(self._on_consent_toggled)
        cs_layout.addWidget(self.consent_checkbox, 1)

        self.consent_warning = QLabel("Please accept terms above to continue.")
        self.consent_warning.setObjectName("statusError")
        self.consent_warning.hide()
        cs_layout.addWidget(self.consent_warning)
        paper_lay.addWidget(consent_strip)

        layout.addWidget(paper, 1)
        return page

    def _apply_tokens(self) -> None:
        self._tokens = get_tokens(self._dark_mode, accent_key=self._accent_key)
        theme_key = (self._dark_mode, self._accent_key)
        if getattr(self, "_applied_theme_key", None) != theme_key:
            self._applied_theme_key = theme_key
            self.setStyleSheet(get_stylesheet(self._dark_mode, accent_key=self._accent_key))

        self.header_logo.set_accent_color(self._tokens["accent"])
        self.theme_toggle_btn.set_theme(self._dark_mode, self._tokens)
        self.hero_canvas.set_theme(self._tokens)
        self.wheel_sandbox.set_theme(self._tokens, self._accent_key, dark_mode=self._dark_mode)
        self.hero_status_lbl.set_theme(self._tokens)
        self.sandbox_status.set_theme(self._tokens)
        self.consent_checkbox.set_theme(self._tokens)
        self._sandbox_file_icon.set_theme(self._tokens)
        self.sw_wheel.set_dark_mode(self._dark_mode)
        self.sw_wheel.set_accent_color(self._tokens["accent"])
        self.sw_accessory.set_dark_mode(self._dark_mode)
        self.sw_accessory.set_accent_color(self._tokens["accent"])

        for row in self._pillar_rows:
            row.set_theme(self._tokens)
        for icon_w in self._trust_icons:
            icon_w.set_theme(self._tokens)

        self.ob_light_btn.setProperty("active", "false" if self._dark_mode else "true")
        self.ob_dark_btn.setProperty("active", "true" if self._dark_mode else "false")
        for btn in (self.ob_light_btn, self.ob_dark_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        for key, btn in self._accent_btns.items():
            if isinstance(btn, _AccentSwatchButton):
                btn.set_state(key == self._accent_key, self._tokens)
        self.accent_name_lbl.setText(ACCENT_PRESETS[self._accent_key]["label"])

        self.legal_browser.setHtml(render_legal_html(self._legal_doc, self._tokens))
        self._refresh_chrome_state()
        self.update()

    def _refresh_chrome_state(self) -> None:
        base_names = ("Intro", "Drag Wheel", "Privacy && Terms")
        for idx, (pill, label) in enumerate(zip(self._step_pills, base_names)):
            is_done = idx < self._current_step
            pill.setText(f"✓  {label}" if is_done else label)
            pill.setProperty("active", "true" if idx == self._current_step else "false")
            pill.setProperty("done", "true" if is_done else "false")
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            pill.updateGeometry()
        if self._step_pills and self._step_pills[0].parentWidget() is not None:
            grp = self._step_pills[0].parentWidget()
            grp.updateGeometry()
            if grp.layout() is not None:
                grp.layout().activate()

        is_intro = self._current_step == self.STEP_INTRO
        is_legal = self._current_step == self.STEP_LEGAL

        self.back_btn.setVisible(not is_intro)
        self.replay_anim_btn.setVisible(is_intro)
        self.skip_to_legal_btn.setVisible(not is_legal)
        self.decline_btn.setVisible(is_legal)

        if self._current_step == self.STEP_INTRO:
            self.primary_btn.setText("Get Started")
            self.footer_hint_lbl.setText("Click a petal, spin the dial, or drop a file onto the lens")
        elif self._current_step == self.STEP_SANDBOX:
            self.primary_btn.setText("Continue")
            self.footer_hint_lbl.setText("Press 1-4, modifier keys, ← →, or drop a Finder file")
        else:
            self.primary_btn.setText("Accept && Launch" if self._first_boot else "Done")
            self.footer_hint_lbl.setText(f"Offline MIT License · Version {LEGAL_VERSION}")

    def start_intro(self, emit_haptics: bool = True) -> None:
        self._set_intro_key_active(None)
        self.hero_canvas._studio_mode = "overview"
        for i, row in enumerate(self._pillar_rows):
            row.set_selected(i == 0)
        default_texts = ("Verifying...", "Preparing...", "Checking...")
        for lbl, txt in zip(self._cap_labels, default_texts):
            lbl.setProperty("ready", False)
            lbl.setText(txt)
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        self.hero_status_lbl.set_command(
            badge="Starting",
            source="Calibrating local Fluxora engines...",
            active=False,
            raw_text="Calibrating local Fluxora engines...",
            icon="sliders",
        )
        self.hero_canvas.play_install_sequence(emit_haptics=emit_haptics)

    def _mark_caps_ready(self) -> None:
        """Mark all three starter capability badges ready without resetting hero copy."""
        done_texts = ("Codecs ready", "Quartz ready", "100% offline")
        for lbl, txt in zip(self._cap_labels, done_texts):
            lbl.setProperty("ready", True)
            lbl.setText(txt)
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _finalize_intro_if_running(self) -> None:
        if self.hero_canvas._install_anim.state() == QVariantAnimation.Running:
            self.hero_canvas._install_anim.stop()
            self.hero_canvas._install_t = 1.0
            self.hero_canvas._scale = 1.0
            self.hero_canvas._unlocked_count = 3
            self.hero_canvas.update()
            self._mark_caps_ready()

    def _on_cap_unlocked(self, index: int) -> None:
        done_texts = ("Codecs ready", "Quartz ready", "100% offline")
        if 0 <= index < len(self._cap_labels):
            lbl = self._cap_labels[index]
            lbl.setProperty("ready", True)
            lbl.setText(done_texts[index])
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _on_intro_finished(self) -> None:
        self._mark_caps_ready()
        self.hero_status_lbl.set_command(
            badge="Ready",
            source="Hover a petal, scrub-spin with momentum, or drop a file",
            active=False,
            raw_text="Hover a petal, scrub-spin with momentum, or drop a file",
            icon="convert",
        )

    def _set_intro_key_active(self, active_key: Optional[str]) -> None:
        self._active_intro_key = active_key
        for key, btn in self._intro_key_btns.items():
            btn.setProperty("active", "true" if key == active_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_pillar_activated(self, row_idx: int, sector_idx: int) -> None:
        self._finalize_intro_if_running()
        for i, row in enumerate(self._pillar_rows):
            row.set_selected(i == row_idx)
        trigger_haptic_tick("alignment")
        if row_idx == 1:
            self._select_intro_wheel_key("convert", sector_override=4, emit_haptic=False)
            return
        if row_idx == 2:
            self._set_intro_key_active(None)
            self.hero_canvas.set_studio_mode("local", target_sector=5, spin_degrees=240.0)
            self.hero_status_lbl.set_command(
                badge="100% Local",
                source="On Your Mac",
                outcome="Zero uploads or telemetry",
                active=True,
                raw_text="Selected: 100% On Your Mac  ·  Zero uploads or telemetry",
                icon="shield",
            )
            return

        self._set_intro_key_active(None)
        self.hero_canvas.set_studio_mode("overview", target_sector=sector_idx, spin_degrees=180.0)
        self._on_hero_petal_clicked(sector_idx)

    def _select_intro_wheel_key(
        self,
        mode_key: str,
        *,
        sector_override: Optional[int] = None,
        emit_haptic: bool = True,
    ) -> None:
        self._finalize_intro_if_running()
        studio_map = {
            "convert": ("key_convert", 0),
            "tools": ("key_tools", 1),
            "actions": ("key_actions", 2),
            "sticky": ("key_sticky", 3),
        }
        if mode_key not in studio_map:
            return
        for i, row in enumerate(self._pillar_rows):
            row.set_selected(i == 1)
        self._set_intro_key_active(mode_key)
        studio_mode, default_sector = studio_map[mode_key]
        target_sector = default_sector if sector_override is None else sector_override
        self.hero_canvas.set_studio_mode(
            studio_mode,
            target_sector=target_sector,
            spin_degrees=240.0,
            emit_haptics=emit_haptic,
        )
        key_badge = (
            "↩ Return / Hub"
            if mode_key == "sticky"
            else _format_key_badge(self._trigger_keys[mode_key])
        )
        self.hero_status_lbl.set_command(
            badge="Drag Wheel",
            source=key_badge,
            outcome=_WHEEL_MODE_TITLES[mode_key],
            active=True,
            raw_text=f"Selected: Drag Wheel  ·  {key_badge} → {_WHEEL_MODE_TITLES[mode_key]}",
            icon="sliders",
        )
        if emit_haptic:
            trigger_haptic_tick("alignment")

    def _show_hero_sector_command(self, idx: int, *, selected: bool) -> None:
        specs = self.hero_canvas.active_specs()
        if not (0 <= idx < len(specs)):
            return
        name, tag, preview = specs[idx]
        short_modes = {
            "convert": "Convert",
            "tools": "Tools",
            "actions": "Actions",
            "sticky": "Sticky",
        }
        if self._active_intro_key:
            badge = short_modes.get(self._active_intro_key, "Drag Wheel")
            source = name
            outcome = preview
            prefix = f"{_WHEEL_MODE_TITLES[self._active_intro_key]}  ·  "
        else:
            badge = name
            if " → " in preview:
                source, outcome = (part.strip() for part in preview.split(" → ", 1))
            else:
                source, outcome = tag, preview
            prefix = "Selected: " if selected else ""
        self.hero_status_lbl.set_command(
            badge=badge,
            source=source,
            outcome=outcome,
            active=True,
            raw_text=f"{prefix}{name}  ·  {preview}",
        )

    def _on_hero_petal_hovered(self, idx: int) -> None:
        self._show_hero_sector_command(idx, selected=False)

    def _on_hero_petal_clicked(self, idx: int) -> None:
        if self.hero_canvas._studio_mode == "overview":
            if idx == 4:
                self._select_intro_wheel_key("convert", sector_override=4, emit_haptic=False)
                return
            sector_to_pillar = {0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 2}
            target_row = sector_to_pillar.get(idx, 0)
            for i, row in enumerate(self._pillar_rows):
                row.set_selected(i == target_row)
        self._show_hero_sector_command(idx, selected=True)

    def _on_hero_file_dropped(self, filename: str, ext: str) -> None:
        self.hero_status_lbl.set_command(
            badge="Drop Ready",
            source=f"{filename} ({ext.upper()})",
            outcome="Drag Wheel ready for Convert & Tools",
            active=True,
            raw_text=f"Selected: {filename} ({ext.upper()})  ·  Drag Wheel ready for Convert / Tools",
            icon="file",
        )

    def _pick_sample_file(self, sample_key: str, emit_haptic: bool = True) -> None:
        self._active_sample = sample_key
        self.wheel_sandbox.set_sample_file(sample_key)
        for key, btn in self._sample_btns.items():
            btn.setProperty("active", "true" if key == sample_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        sample_name, _, sample_meta = self.wheel_sandbox.SAMPLE_SPECS.get(
            sample_key, ("vacation_photo.heic", "image", "4.2 MB")
        )
        self.sandbox_file_lbl.setText(f"{sample_name}  ·  {sample_meta}")
        mode_name = self.wheel_sandbox._wheel_type.capitalize()
        self.sandbox_status.set_command(
            badge=mode_name,
            source=f"{sample_name} ({sample_meta})",
            outcome="Hover or click a petal",
            active=False,
            raw_text=f"{mode_name}  ·  Hover or click a petal for {sample_name} ({sample_meta})",
        )
        if emit_haptic:
            trigger_haptic_tick("alignment")

    def _pick_sandbox_wheel(self, mode_key: str, emit_haptic: bool = True) -> None:
        self.wheel_sandbox.set_wheel_type(mode_key)
        for key, btn in self._sandbox_mode_btns.items():
            btn.setProperty("active", "true" if key == mode_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        sample_name, _, sample_meta = self.wheel_sandbox.SAMPLE_SPECS.get(
            self._active_sample, ("vacation_photo.heic", "image", "4.2 MB")
        )
        display_name = self.wheel_sandbox._custom_filename or sample_name
        key_badge = _format_key_badge(self._trigger_keys.get(mode_key, "Shift"))
        self.sandbox_status.set_command(
            badge=mode_key.capitalize(),
            source=key_badge,
            outcome=f"{display_name} ({sample_meta})",
            active=False,
            raw_text=f"{mode_key.capitalize()}  ·  {key_badge} active for {display_name} ({sample_meta})",
        )
        if emit_haptic:
            trigger_haptic_tick("alignment")

    def _toggle_sandbox_sticky(self) -> None:
        next_state = not self.wheel_sandbox._sticky_locked
        self.wheel_sandbox.set_sticky_preview(next_state)
        trigger_haptic_tick("level_change")
        self._on_sandbox_sticky_toggled(next_state)

    def _on_sandbox_sticky_toggled(self, locked: bool) -> None:
        self.sandbox_sticky_btn.setProperty("active", "true" if locked else "false")
        self.sandbox_sticky_btn.style().unpolish(self.sandbox_sticky_btn)
        self.sandbox_sticky_btn.style().polish(self.sandbox_sticky_btn)
        sample_name, _, sample_meta = self.wheel_sandbox.SAMPLE_SPECS.get(
            self._active_sample, ("vacation_photo.heic", "image", "4.2 MB")
        )
        display_name = self.wheel_sandbox._custom_filename or sample_name
        if locked:
            self.sandbox_status.set_command(
                badge="Sticky",
                source="← → Step petals",
                outcome=f"{display_name} (Esc to unpin)",
                active=True,
                raw_text=f"Sticky Pinned  ·  Use ← → to step petals for {display_name} ({sample_meta}), Esc to unpin",
                icon="float",
            )
        else:
            mode_key = self.wheel_sandbox._wheel_type
            self.sandbox_status.set_command(
                badge=mode_key.capitalize(),
                source="Sticky closed",
                outcome=f"{display_name} ({sample_meta})",
                active=False,
                raw_text=f"{mode_key.capitalize()}  ·  Sticky closed for {display_name} ({sample_meta})",
            )

    def _on_sandbox_sticky_petal(self, label: str, outcome: str) -> None:
        mode_name = self.wheel_sandbox._wheel_type.capitalize()
        self.sandbox_status.set_command(
            badge=f"{mode_name} · Sticky",
            source=label,
            outcome=outcome,
            active=True,
            raw_text=f"{mode_name} (Sticky)  ·  {label}  →  {outcome}",
            icon="float",
        )

    def _on_sandbox_real_drop(self, filename: str, inferred_sample_key: str) -> None:
        self._active_sample = inferred_sample_key
        for key, btn in self._sample_btns.items():
            btn.setProperty("active", "true" if key == inferred_sample_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.sandbox_file_lbl.setText(f"{filename}  ·  Custom Finder File")
        self.sandbox_status.set_command(
            badge="Loaded",
            source=filename,
            outcome="Click any wheel petal to simulate",
            active=True,
            raw_text=f"Loaded {filename}  ·  Click any wheel petal to simulate",
            icon="file",
        )

    def _on_sandbox_petal(self, wheel_type: str, label: str, outcome: str) -> None:
        self.sandbox_status.set_command(
            badge=wheel_type.capitalize(),
            source=label,
            outcome=outcome,
            active=True,
            raw_text=f"{wheel_type.capitalize()}  ·  {label}  →  {outcome}",
        )

    def _on_theme_picked(self, dark_mode: bool) -> None:
        self._dark_mode = bool(dark_mode)
        trigger_haptic_tick("generic")
        self._apply_tokens()
        self.theme_preview_changed.emit(self._dark_mode, self._accent_key)

    def _on_accent_picked(self, accent_key: str) -> None:
        if accent_key in ACCENT_PRESETS:
            self._accent_key = accent_key
            trigger_haptic_tick("alignment")
            self._apply_tokens()
            self.theme_preview_changed.emit(self._dark_mode, self._accent_key)

    def select_legal_doc(self, doc_key: str, emit_haptic: bool = True) -> None:
        self._legal_doc = "terms" if doc_key == "terms" else "privacy"
        self.tab_privacy_btn.setProperty("active", "true" if self._legal_doc == "privacy" else "false")
        self.tab_terms_btn.setProperty("active", "true" if self._legal_doc == "terms" else "false")
        for btn in (self.tab_privacy_btn, self.tab_terms_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.legal_browser.setHtml(render_legal_html(self._legal_doc, self._tokens))
        if emit_haptic:
            trigger_haptic_tick("generic")

    def go_to_step(self, step_index: int, emit_haptic: bool = True) -> None:
        target = max(0, min(2, int(step_index)))
        if target != self.STEP_INTRO:
            self.hero_canvas.stop_animations()
        if target != self.STEP_SANDBOX:
            self.wheel_sandbox.stop_animations()
        self._current_step = target
        self.stack.setCurrentIndex(target)
        self.header_logo.spin_once(60.0 if emit_haptic else 0.0)
        self._refresh_chrome_state()
        if emit_haptic:
            trigger_haptic_tick("generic")
        if target == self.STEP_INTRO:
            self.start_intro(emit_haptics=emit_haptic)

    def _on_consent_toggled(self, checked: bool) -> None:
        if checked:
            self.consent_warning.hide()
            trigger_haptic_tick("alignment")

    def _on_back(self) -> None:
        if self._current_step > self.STEP_INTRO:
            self.go_to_step(self._current_step - 1)

    def _on_primary(self) -> None:
        if self._current_step < self.STEP_LEGAL:
            self.go_to_step(self._current_step + 1)
            return
        if not self.consent_checkbox.isChecked():
            self.consent_warning.show()
            trigger_haptic_tick("generic")
            self._shake_consent()
            return
        self.complete_onboarding(animate_exit=True)

    def _shake_consent(self) -> None:
        if should_reduce_motion():
            return
        origin = self.consent_checkbox.pos()
        if self._shake_anim is not None:
            self._shake_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def _step(val: object) -> None:
            p = float(val)
            offset = int(round(math.sin(p * math.pi * 4.0) * 6.0 * (1.0 - p)))
            self.consent_checkbox.move(origin.x() + offset, origin.y())

        anim.valueChanged.connect(_step)
        anim.finished.connect(lambda: self.consent_checkbox.move(origin))
        self._shake_anim = anim
        anim.start()

    def complete_onboarding(self, animate_exit: bool = True) -> dict:
        """Persist onboarding preferences and consent version cleanly."""
        accepted_at = datetime.now(timezone.utc).isoformat()
        self.qsettings.setValue("onboarding_completed", True)
        self.qsettings.setValue("legal_accepted", True)
        self.qsettings.setValue("legal_accepted_version", LEGAL_VERSION)
        self.qsettings.setValue("legal_accepted_at", accepted_at)
        self.qsettings.setValue("dark_mode", self._dark_mode)
        self.qsettings.setValue("accent_preset", self._accent_key)
        wheel_enabled = bool(self.sw_wheel.isChecked())
        accessory_mode = bool(self.sw_accessory.isChecked())
        self.qsettings.setValue("wheel_enabled", wheel_enabled)
        self.qsettings.setValue("drag_wheel_enabled", wheel_enabled)
        self.qsettings.setValue("accessory_mode", accessory_mode)
        self.qsettings.sync()

        result = {
            "onboarding_completed": True,
            "legal_accepted": True,
            "legal_accepted_version": LEGAL_VERSION,
            "legal_accepted_at": accepted_at,
            "dark_mode": self._dark_mode,
            "accent_key": self._accent_key,
            "accent_preset": self._accent_key,
            "wheel_enabled": wheel_enabled,
            "drag_wheel_enabled": wheel_enabled,
            "accessory_mode": accessory_mode,
        }
        play_tactile_feedback("level_change", sound_name="Glass")

        if animate_exit and not should_reduce_motion() and self.isVisible():
            fade = QVariantAnimation(self)
            fade.setDuration(180)
            fade.setStartValue(1.0)
            fade.setEndValue(0.0)
            fade.setEasingCurve(QEasingCurve.OutCubic)
            fade.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))

            def _done() -> None:
                self.close()
                self.onboarding_completed.emit(result)

            fade.finished.connect(_done)
            self._fade_anim = fade
            fade.start()
        else:
            self.close()
            self.onboarding_completed.emit(result)
        return result

    def _on_decline(self) -> None:
        self.hero_canvas.stop_animations()
        self.wheel_sandbox.stop_animations()
        self.close()
        self.onboarding_declined.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.primary_btn.setFocus(Qt.OtherFocusReason)

    def closeEvent(self, event) -> None:
        self.hero_canvas.stop_animations()
        self.wheel_sandbox.stop_animations()
        if self._shake_anim is not None:
            self._shake_anim.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
        super().closeEvent(event)

    def _wheel_mode_for_key(self, qt_key: int) -> Optional[str]:
        if qt_key == Qt.Key_1:
            return "convert"
        if qt_key == Qt.Key_2:
            return "tools"
        if qt_key == Qt.Key_3:
            return "actions"
        if qt_key == Qt.Key_4:
            return "sticky"
        for mode_key, name in self._trigger_keys.items():
            if _QT_KEY_FOR_MODIFIER.get(name) == qt_key:
                return mode_key
        return None

    def keyPressEvent(self, event) -> None:
        if not event.isAutoRepeat():
            mapped_mode = self._wheel_mode_for_key(event.key())
            if self._current_step == self.STEP_INTRO:
                if mapped_mode is not None:
                    self._select_intro_wheel_key(mapped_mode)
                    return
                if event.key() in (Qt.Key_Left, Qt.Key_Right):
                    delta = 1 if event.key() == Qt.Key_Right else -1
                    next_idx = (self.hero_canvas._selected_idx + delta) % 6
                    self.hero_canvas.set_external_highlight(next_idx)
                    self._on_hero_petal_clicked(next_idx)
                    return
            elif self._current_step == self.STEP_SANDBOX:
                if mapped_mode == "sticky":
                    self._toggle_sandbox_sticky()
                    return
                if mapped_mode in ("convert", "tools", "actions"):
                    self._pick_sandbox_wheel(mapped_mode)
                    return
                if event.key() in (Qt.Key_Left, Qt.Key_Right):
                    delta = 1 if event.key() == Qt.Key_Right else -1
                    if not self.wheel_sandbox._sticky_locked:
                        self.wheel_sandbox.set_sticky_preview(True, spin=False)
                        self._on_sandbox_sticky_toggled(True)
                    self.wheel_sandbox.step_selection(delta)
                    return
                if event.key() == Qt.Key_Escape and self.wheel_sandbox._sticky_locked:
                    self.wheel_sandbox.set_sticky_preview(False)
                    self._on_sandbox_sticky_toggled(False)
                    return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if isinstance(focused, QPushButton):
                focused.click()
            else:
                self.primary_btn.click()
            return
        if event.key() == Qt.Key_Escape and not self._first_boot:
            self._on_decline()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14.0, 14.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._tokens["bg_surface"]))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(self._tokens["border_strong"]), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and event.position().y() <= 48.0:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_origin = None
        super().mouseReleaseEvent(event)
