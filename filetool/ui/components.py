"""Custom UI widgets and geometric vector icons for FileTool."""

from __future__ import annotations

from functools import lru_cache
import math
import os
from pathlib import Path
from typing import Iterable, List, Optional

from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QWidget

from filetool.platform.mac_actions import trigger_haptic_tick
from filetool.ui.wheel.animations import should_reduce_motion


class IOSSwitch(QAbstractButton):
    """Smooth toggle switch with Force Touch haptics and reduced-motion support."""

    toggled_state = Signal(bool)

    def __init__(
        self,
        checked: bool = False,
        dark_mode: bool = False,
        accent_color: str = "#F28A32",
        parent=None,
    ):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._dark_mode = dark_mode
        self._accent = QColor(accent_color)

        self._thumb_pos: float = 1.0 if checked else 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.valueChanged.connect(self._on_anim_val)

        self.toggled.connect(self._on_toggled)
        self.clicked.connect(lambda _c=False: trigger_haptic_tick("alignment"))

    def set_dark_mode(self, is_dark: bool) -> None:
        if self._dark_mode != is_dark:
            self._dark_mode = is_dark
            self.update()

    def set_accent_color(self, hex_color: str) -> None:
        self._accent = QColor(hex_color)
        self.update()

    def _on_anim_val(self, val):
        self._thumb_pos = float(val)
        self.update()

    def _on_toggled(self, checked: bool):
        target = 1.0 if checked else 0.0
        if should_reduce_motion():
            self._anim.stop()
            self._thumb_pos = target
            self.update()
        else:
            self._anim.stop()
            self._anim.setStartValue(self._thumb_pos)
            self._anim.setEndValue(target)
            self._anim.start()
        self.toggled_state.emit(checked)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._thumb_pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2.0

        t = self._thumb_pos
        base_r, base_g, base_b = (0x3A, 0x3B, 0x3E) if self._dark_mode else (0xD7, 0xD5, 0xCF)
        cr = int(base_r + (self._accent.red() - base_r) * t)
        cg = int(base_g + (self._accent.green() - base_g) * t)
        cb = int(base_b + (self._accent.blue() - base_b) * t)
        track_color = QColor(cr, cg, cb)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        painter.fillPath(path, track_color)

        thumb_r = r - 2.5
        thumb_x = 2.5 + t * (w - 2 * r)
        thumb_y = 2.5

        shadow_path = QPainterPath()
        shadow_path.addEllipse(QRectF(thumb_x - 0.5, thumb_y + 0.5, 2 * thumb_r + 1, 2 * thumb_r + 1))
        painter.fillPath(shadow_path, QColor(0, 0, 0, 45 if self._dark_mode else 25))

        thumb_path = QPainterPath()
        thumb_path.addEllipse(QRectF(thumb_x, thumb_y, 2 * thumb_r, 2 * thumb_r))
        painter.fillPath(thumb_path, QColor(0xFF, 0xFF, 0xFF))
        painter.end()


class ThemeToggle(QWidget):
    """Pill toggle switch with Sun and Moon icons."""

    theme_changed = Signal(bool)

    def __init__(self, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(58, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._dark = is_dark

    def set_dark(self, is_dark: bool):
        if self._dark != is_dark:
            self._dark = is_dark
            self.update()

    def mousePressEvent(self, event):
        self._dark = not self._dark
        self.update()
        trigger_haptic_tick("alignment")
        self.theme_changed.emit(self._dark)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2.0

        pill_path = QPainterPath()
        pill_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.fillPath(pill_path, QColor(0xEAE8E3) if not self._dark else QColor(0x2A, 0x2B, 0x2E))
        p.setPen(QPen(QColor(0xE1, 0xDF, 0xD9) if not self._dark else QColor(0x3A, 0x3B, 0x3E), 1.0))
        p.drawPath(pill_path)

        thumb_x = 2.0 if not self._dark else (w - h + 2.0)
        thumb_rect = QRectF(thumb_x, 2.0, h - 4.0, h - 4.0)
        thumb_path = QPainterPath()
        thumb_path.addEllipse(thumb_rect)
        p.fillPath(thumb_path, QColor(0xFF, 0xFF, 0xFF) if not self._dark else QColor(0x3E, 0x40, 0x44))
        p.setPen(QPen(QColor(0, 0, 0, 20), 0.5))
        p.drawPath(thumb_path)

        sun_color = QColor(0xF2, 0x8A, 0x32) if not self._dark else QColor(0x77, 0x78, 0x73)
        moon_color = QColor(0xFF, 0xFF, 0xFF) if self._dark else QColor(0x77, 0x78, 0x73)
        draw_vector_icon(p, "sun", 6.0, (h - 14.0) / 2.0, 14.0, sun_color)
        draw_vector_icon(p, "moon", w - 20.0, (h - 13.0) / 2.0, 13.0, moon_color)
        p.end()


def draw_vector_icon(painter: QPainter, name: str, x: float, y: float, size: float, color: QColor) -> None:
    """Draw a vector icon scaled cleanly into the given square bounds."""
    if not painter.isActive():
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    stroke_w = max(1.4, size * 0.085)
    painter.setPen(QPen(color, stroke_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)

    cx = x + size / 2.0
    cy = y + size / 2.0
    pad = size * 0.15

    if name == "folder":
        path = QPainterPath()
        path.moveTo(x + pad, y + pad + 3)
        path.lineTo(x + pad + size * 0.32, y + pad + 3)
        path.lineTo(x + pad + size * 0.42, y + pad + 6)
        path.lineTo(x + size - pad, y + pad + 6)
        path.lineTo(x + size - pad, y + size - pad)
        path.lineTo(x + pad, y + size - pad)
        path.closeSubpath()
        painter.drawPath(path)

    elif name == "compress":
        for offset in (-size * 0.18, 0, size * 0.18):
            path = QPainterPath()
            path.moveTo(x + pad, cy + offset)
            path.lineTo(cx, cy + offset + size * 0.12)
            path.lineTo(x + size - pad, cy + offset)
            painter.drawPath(path)

    elif name == "convert":
        arc_r = size * 0.26
        rect = QRectF(cx - arc_r, cy - arc_r, 2 * arc_r, 2 * arc_r)
        painter.drawArc(rect, 45 * 16, 120 * 16)
        painter.drawArc(rect, 225 * 16, 120 * 16)
        head = size * 0.12
        painter.drawLine(QPointF(cx + arc_r, cy), QPointF(cx + arc_r - head, cy - head * 0.8))
        painter.drawLine(QPointF(cx + arc_r, cy), QPointF(cx + arc_r + head * 0.8, cy - head * 0.8))
        painter.drawLine(QPointF(cx - arc_r, cy), QPointF(cx - arc_r + head, cy + head * 0.8))
        painter.drawLine(QPointF(cx - arc_r, cy), QPointF(cx - arc_r - head * 0.8, cy + head * 0.8))

    elif name in ("resize", "crop"):
        arm = size * 0.32
        painter.drawLine(QPointF(cx - arm, cy - arm * 0.5), QPointF(cx - arm * 0.5, cy - arm * 0.5))
        painter.drawLine(QPointF(cx - arm * 0.5, cy - arm), QPointF(cx - arm * 0.5, cy + arm * 0.5))
        painter.drawLine(QPointF(cx + arm, cy + arm * 0.5), QPointF(cx + arm * 0.5, cy + arm * 0.5))
        painter.drawLine(QPointF(cx + arm * 0.5, cy + arm), QPointF(cx + arm * 0.5, cy - arm * 0.5))

    elif name in ("more", "dots"):
        painter.setBrush(color)
        radius = max(2.0, size * 0.09)
        spacing = size * 0.24
        painter.drawEllipse(QPointF(cx - spacing, cy), radius, radius)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.drawEllipse(QPointF(cx + spacing, cy), radius, radius)

    elif name == "upload":
        box_w = size * 0.58
        box_h = size * 0.36
        painter.drawRoundedRect(QRectF(cx - box_w / 2, cy - box_h / 2, box_w, box_h), box_h / 2, box_h / 2)
        painter.drawLine(QPointF(cx, cy + size * 0.16), QPointF(cx, cy - size * 0.14))
        painter.drawLine(QPointF(cx - size * 0.10, cy - size * 0.04), QPointF(cx, cy - size * 0.14))
        painter.drawLine(QPointF(cx + size * 0.10, cy - size * 0.04), QPointF(cx, cy - size * 0.14))

    elif name == "check":
        path = QPainterPath()
        path.moveTo(cx - size * 0.28, cy)
        path.lineTo(cx - size * 0.08, cy + size * 0.22)
        path.lineTo(cx + size * 0.28, cy - size * 0.22)
        painter.drawPath(path)

    elif name == "link":
        link_w = size * 0.4
        link_h = size * 0.22
        painter.drawRoundedRect(QRectF(cx - link_w / 2 - 2, cy - link_h / 2 - 2, link_w, link_h), link_h / 2, link_h / 2)
        painter.drawRoundedRect(QRectF(cx - link_w / 2 + 2, cy - link_h / 2 + 2, link_w, link_h), link_h / 2, link_h / 2)

    elif name == "copy":
        box_w = size * 0.38
        box_h = size * 0.44
        painter.drawRoundedRect(QRectF(cx - box_w / 2 - 2, cy - box_h / 2 - 2, box_w, box_h), 3, 3)
        painter.drawRoundedRect(QRectF(cx - box_w / 2 + 2, cy - box_h / 2 + 2, box_w, box_h), 3, 3)

    elif name == "sun":
        core_r = size * 0.20
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)
        for idx in range(8):
            ang = idx * math.pi / 4.0
            r1 = size * 0.31
            r2 = size * 0.41
            painter.drawLine(
                QPointF(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                QPointF(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
            )

    elif name == "moon":
        path = QPainterPath()
        radius = size * 0.34
        path.addEllipse(QPointF(cx, cy), radius, radius)
        cut = QPainterPath()
        cut.addEllipse(QPointF(cx + radius * 0.45, cy - radius * 0.25), radius * 0.85, radius * 0.85)
        painter.setBrush(color)
        painter.drawPath(path.subtracted(cut))

    elif name == "image":
        rect = QRectF(x + pad, y + pad + size * 0.06, size - 2 * pad, size - 2 * pad - size * 0.12)
        painter.drawRoundedRect(rect, 3, 3)
        painter.setBrush(color)
        painter.drawEllipse(
            QPointF(rect.left() + rect.width() * 0.30, rect.top() + rect.height() * 0.34),
            size * 0.07,
            size * 0.07,
        )
        painter.setBrush(Qt.NoBrush)
        mountains = QPainterPath()
        mountains.moveTo(rect.left() + 2, rect.bottom() - 2)
        mountains.lineTo(rect.left() + rect.width() * 0.42, rect.bottom() - rect.height() * 0.42)
        mountains.lineTo(rect.left() + rect.width() * 0.65, rect.bottom() - rect.height() * 0.20)
        mountains.lineTo(rect.left() + rect.width() * 0.78, rect.bottom() - rect.height() * 0.35)
        mountains.lineTo(rect.right() - 2, rect.bottom() - 2)
        painter.drawPath(mountains)

    elif name == "audio":
        bar_heights = (0.28, 0.56, 0.40, 0.64, 0.32)
        gap = (size - 2 * pad) / (len(bar_heights) - 1)
        for idx, frac in enumerate(bar_heights):
            bx = x + pad + idx * gap
            half_h = size * frac * 0.5
            painter.drawLine(QPointF(bx, cy - half_h), QPointF(bx, cy + half_h))

    elif name == "video":
        rect = QRectF(x + pad, y + pad + size * 0.06, size - 2 * pad, size - 2 * pad - size * 0.12)
        painter.drawRoundedRect(rect, 3, 3)
        triangle = QPainterPath()
        triangle.moveTo(cx - size * 0.09, cy - size * 0.14)
        triangle.lineTo(cx + size * 0.15, cy)
        triangle.lineTo(cx - size * 0.09, cy + size * 0.14)
        triangle.closeSubpath()
        painter.drawPath(triangle)

    elif name in ("document", "pdf", "file", "slides", "spreadsheets", "subtitles"):
        fold = size * 0.22
        left = x + pad + size * 0.08
        top = y + pad
        right = x + size - pad - size * 0.08
        bottom = y + size - pad
        path = QPainterPath()
        path.moveTo(left, top)
        path.lineTo(right - fold, top)
        path.lineTo(right, top + fold)
        path.lineTo(right, bottom)
        path.lineTo(left, bottom)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(right - fold, top), QPointF(right - fold, top + fold))
        painter.drawLine(QPointF(right - fold, top + fold), QPointF(right, top + fold))
        painter.drawLine(QPointF(left + size * 0.14, cy + size * 0.04), QPointF(right - size * 0.14, cy + size * 0.04))
        painter.drawLine(QPointF(left + size * 0.14, cy + size * 0.20), QPointF(right - size * 0.22, cy + size * 0.20))

    elif name == "archive":
        rect = QRectF(x + pad, y + pad + size * 0.08, size - 2 * pad, size - 2 * pad - size * 0.10)
        painter.drawRoundedRect(rect, 2.5, 2.5)
        painter.drawLine(QPointF(rect.left(), rect.top() + rect.height() * 0.34), QPointF(rect.right(), rect.top() + rect.height() * 0.34))
        painter.drawLine(QPointF(cx - size * 0.10, cy + size * 0.12), QPointF(cx + size * 0.10, cy + size * 0.12))

    elif name == "rotate":
        radius = size * 0.29
        rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        painter.drawArc(rect, 40 * 16, 280 * 16)
        ax = cx + radius * math.cos(math.radians(40))
        ay = cy - radius * math.sin(math.radians(40))
        painter.drawLine(QPointF(ax, ay), QPointF(ax - size * 0.14, ay - size * 0.04))
        painter.drawLine(QPointF(ax, ay), QPointF(ax + size * 0.04, ay - size * 0.15))

    elif name in ("shield", "metadata"):
        path = QPainterPath()
        path.moveTo(cx, y + pad)
        path.lineTo(x + size - pad, y + pad + size * 0.16)
        path.lineTo(x + size - pad, cy + size * 0.05)
        path.quadTo(cx, y + size - pad * 0.6, x + pad, cy + size * 0.05)
        path.lineTo(x + pad, y + pad + size * 0.16)
        path.closeSubpath()
        painter.drawPath(path)

    elif name == "trim":
        radius = size * 0.11
        ring_top = QPointF(x + pad + radius, cy - size * 0.16)
        ring_bot = QPointF(x + pad + radius, cy + size * 0.16)
        painter.drawEllipse(ring_top, radius, radius)
        painter.drawEllipse(ring_bot, radius, radius)
        painter.drawLine(QPointF(ring_top.x() + radius * 0.7, ring_top.y() + radius * 0.4), QPointF(x + size - pad, cy + size * 0.18))
        painter.drawLine(QPointF(ring_bot.x() + radius * 0.7, ring_bot.y() - radius * 0.4), QPointF(x + size - pad, cy - size * 0.18))

    elif name == "split":
        rect = QRectF(x + pad, y + pad + size * 0.08, size - 2 * pad, size - 2 * pad - size * 0.16)
        painter.drawRoundedRect(rect, 2.5, 2.5)
        painter.drawLine(QPointF(cx, rect.top()), QPointF(cx, rect.bottom()))

    elif name == "merge":
        box_w = size * 0.44
        box_h = size * 0.50
        painter.drawRoundedRect(QRectF(cx - box_w * 0.7, cy - box_h * 0.65, box_w, box_h), 2, 2)
        painter.drawRoundedRect(QRectF(cx - box_w * 0.3, cy - box_h * 0.35, box_w, box_h), 2, 2)

    elif name == "airdrop":
        painter.setBrush(color)
        painter.drawEllipse(QPointF(cx, cy + size * 0.12), size * 0.06, size * 0.06)
        painter.setBrush(Qt.NoBrush)
        for frac in (0.20, 0.36):
            radius = size * frac
            rect = QRectF(cx - radius, cy + size * 0.12 - radius, 2 * radius, 2 * radius)
            painter.drawArc(rect, 35 * 16, 110 * 16)

    elif name == "float":
        rect = QRectF(x + pad, y + pad + size * 0.10, size - 2 * pad, size - 2 * pad - size * 0.16)
        painter.drawRoundedRect(rect, 2.5, 2.5)
        inner = QRectF(cx - size * 0.04, y + pad, size * 0.40, size * 0.28)
        painter.drawRoundedRect(inner, 2, 2)

    elif name == "terminal":
        rect = QRectF(x + pad, y + pad + size * 0.08, size - 2 * pad, size - 2 * pad - size * 0.16)
        painter.drawRoundedRect(rect, 2.5, 2.5)
        painter.drawLine(QPointF(x + pad + size * 0.14, cy - size * 0.08), QPointF(x + pad + size * 0.28, cy + size * 0.02))
        painter.drawLine(QPointF(x + pad + size * 0.28, cy + size * 0.02), QPointF(x + pad + size * 0.14, cy + size * 0.12))
        painter.drawLine(QPointF(cx, cy + size * 0.12), QPointF(cx + size * 0.20, cy + size * 0.12))

    elif name == "close":
        delta = size * 0.24
        painter.drawLine(QPointF(cx - delta, cy - delta), QPointF(cx + delta, cy + delta))
        painter.drawLine(QPointF(cx + delta, cy - delta), QPointF(cx - delta, cy + delta))

    elif name == "window":
        rect = QRectF(x + pad, y + pad + size * 0.06, size - 2 * pad, size - 2 * pad - size * 0.12)
        painter.drawRoundedRect(rect, 3, 3)
        bar_y = rect.top() + rect.height() * 0.28
        painter.drawLine(QPointF(rect.left(), bar_y), QPointF(rect.right(), bar_y))

    elif name == "sliders":
        for idx, (row_y, knob_x) in enumerate((
            (cy - size * 0.20, cx - size * 0.12),
            (cy, cx + size * 0.14),
            (cy + size * 0.20, cx - size * 0.04),
        )):
            painter.drawLine(QPointF(x + pad, row_y), QPointF(x + size - pad, row_y))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(knob_x, row_y), size * 0.08, size * 0.08)
            painter.setBrush(Qt.NoBrush)

    elif name == "health":
        radius = size * 0.34
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        pulse = QPainterPath()
        pulse.moveTo(cx - size * 0.22, cy)
        pulse.lineTo(cx - size * 0.10, cy)
        pulse.lineTo(cx - size * 0.03, cy - size * 0.14)
        pulse.lineTo(cx + size * 0.05, cy + size * 0.14)
        pulse.lineTo(cx + size * 0.12, cy)
        pulse.lineTo(cx + size * 0.22, cy)
        painter.drawPath(pulse)

    elif name == "power":
        radius = size * 0.30
        rect = QRectF(cx - radius, cy - radius + size * 0.02, 2 * radius, 2 * radius)
        painter.drawArc(rect, 130 * 16, 280 * 16)
        painter.drawLine(QPointF(cx, cy - size * 0.35), QPointF(cx, cy - size * 0.02))

    painter.restore()


class IconWidget(QWidget):
    """Widget wrapper that paints a named vector icon."""

    def __init__(self, name: str, size: int = 20, color: Optional[QColor] = None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._name = name
        self._size = size
        self._color = color or QColor(0x77, 0x78, 0x73)

    def set_icon(self, name: str) -> None:
        self._name = name
        self.update()

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not painter.isActive():
            return
        draw_vector_icon(painter, self._name, 0, 0, self._size, self._color)
        painter.end()


_CATEGORY_ICON_MAP = {
    "Images": "image",
    "Audio": "audio",
    "Video": "video",
    "Documents": "document",
    "PDF": "document",
    "Slides": "slides",
    "Spreadsheets": "spreadsheets",
    "Subtitles": "subtitles",
    "Archives": "archive",
}


def icon_name_for_category(category: Optional[str]) -> str:
    """Return vector icon name matching a registry category."""
    return _CATEGORY_ICON_MAP.get(category or "", "file")


def collect_paths_from_urls(urls: Iterable) -> List[Path]:
    """Expand dropped QUrl items into non-hidden file paths (recursively for folders)."""
    collected: List[Path] = []
    for url in urls:
        local = url.toLocalFile() if hasattr(url, "toLocalFile") else str(url)
        if not local:
            continue
        local_path = Path(local).resolve()
        if not local_path.exists():
            continue
        if local_path.is_file():
            if not local_path.name.startswith("."):
                collected.append(local_path)
        elif local_path.is_dir():
            for root, _, files in os.walk(local_path):
                for fname in sorted(files):
                    if not fname.startswith("."):
                        collected.append(Path(root) / fname)
    return collected


def format_byte_size(num_bytes: int) -> str:
    """Format byte size using human-readable units."""
    size = float(max(0, num_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def _build_emblem_petal(
    cx: float,
    cy: float,
    index: int,
    total: int,
    r_in: float,
    r_out: float,
    gap_rad: float,
    rot_rad: float,
) -> QPainterPath:
    """Build one sculpted rounded radial petal aligned to the wheel identity."""
    span = (2.0 * math.pi) / total
    mid = rot_rad - math.pi / 2.0 + index * span
    half_inner = max(0.08, span * 0.5 - gap_rad * (r_out / max(r_in, 1.0)) * 0.36)
    half_outer = max(0.12, span * 0.5 - gap_rad * 0.5)

    def _pt(r: float, ang: float) -> QPointF:
        return QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang))

    cut_in = r_in + (r_out - r_in) * 0.14
    cut_out = r_out - (r_out - r_in) * 0.14
    ang_i_l, ang_i_r = mid - half_inner, mid + half_inner
    ang_o_l, ang_o_r = mid - half_outer, mid + half_outer

    path = QPainterPath()
    path.moveTo(_pt(cut_in, ang_i_l))
    path.lineTo(_pt(cut_out, ang_o_l))
    path.quadTo(_pt(r_out, ang_o_l), _pt(r_out, ang_o_l + 0.14))

    steps = 10
    arc_s = ang_o_l + 0.14
    arc_e = ang_o_r - 0.14
    for s in range(1, steps):
        a = arc_s + (arc_e - arc_s) * (s / float(steps))
        path.lineTo(_pt(r_out, a))

    path.lineTo(_pt(r_out, arc_e))
    path.quadTo(_pt(r_out, ang_o_r), _pt(cut_out, ang_o_r))
    path.lineTo(_pt(cut_in, ang_i_r))
    path.quadTo(_pt(r_in, ang_i_r), _pt(r_in, ang_i_r - 0.12))

    i_s = ang_i_r - 0.12
    i_e = ang_i_l + 0.12
    for s in range(1, 7):
        a = i_s + (i_e - i_s) * (s / 7.0)
        path.lineTo(_pt(r_in, a))

    path.lineTo(_pt(r_in, i_e))
    path.quadTo(_pt(r_in, ang_i_l), _pt(cut_in, ang_i_l))
    path.closeSubpath()
    return path


def draw_brand_emblem(
    painter: QPainter,
    rect: QRectF,
    accent_color: str = "#F28A32",
    rotation_deg: float = 0.0,
    hover_t: float = 0.0,
    progress: Optional[int] = None,
    done_t: float = 0.0,
    monochrome: bool = False,
) -> None:
    """Paint FileTool's sculpted 6-petal radial aperture emblem inside `rect`."""
    if not painter.isActive():
        return

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)

    sz = min(rect.width(), rect.height())
    cx = rect.center().x()
    cy = rect.center().y()
    accent = QColor(accent_color)
    done_col = QColor("#2DA368")
    if done_t > 0.0:
        accent = QColor(
            int(accent.red() + (done_col.red() - accent.red()) * done_t),
            int(accent.green() + (done_col.green() - accent.green()) * done_t),
            int(accent.blue() + (done_col.blue() - accent.blue()) * done_t),
        )

    outer_r = sz * (0.435 if progress is None else 0.39)
    inner_r = outer_r * 0.41
    rot_rad = math.radians(rotation_deg)
    gap_rad = 0.155

    # Subtle ambient glow behind the wheel on hover or active progress
    glow_strength = max(hover_t * 0.45, 0.35 if progress is not None else 0.0, done_t * 0.55)
    if glow_strength > 0.01 and not monochrome:
        halo = QRadialGradient(QPointF(cx, cy), outer_r * 1.15)
        c_mid = QColor(accent.red(), accent.green(), accent.blue(), int(90 * glow_strength))
        c_edge = QColor(accent.red(), accent.green(), accent.blue(), 0)
        halo.setColorAt(0.45, c_mid)
        halo.setColorAt(1.0, c_edge)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(cx, cy), outer_r * 1.15, outer_r * 1.15)

    # Outer precision progress ring when converting
    if progress is not None:
        ring_r = sz * 0.46
        ring_rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2.0, ring_r * 2.0)
        stroke = max(1.6, sz * 0.075)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 55), stroke))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring_rect)

        pct = max(0, min(100, int(progress)))
        painter.setPen(QPen(accent.lighter(120), stroke, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(ring_rect, 90 * 16, int(-pct * 3.6 * 16))

    # 6 sculpted radial petals
    petal_count = 6
    grad_hi = accent.lighter(124)
    grad_mid = accent
    grad_lo = accent.darker(118)

    for idx in range(petal_count):
        petal = _build_emblem_petal(cx, cy, idx, petal_count, inner_r, outer_r, gap_rad, rot_rad)
        if monochrome:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 235 if idx == 0 else 190))
            painter.drawPath(petal)
            continue

        # Lead blade catches bright highlight so rotation stays legible even at 20pt
        is_hero = idx == 0
        fill = QRadialGradient(QPointF(cx, cy), outer_r)
        if is_hero:
            fill.setColorAt(0.25, grad_hi.lighter(115))
            fill.setColorAt(0.75, grad_hi)
            fill.setColorAt(1.0, grad_mid)
        else:
            fill.setColorAt(0.25, grad_hi if idx in (1, 5) else grad_mid)
            fill.setColorAt(0.78, grad_mid)
            fill.setColorAt(1.0, grad_lo)

        painter.setPen(QPen(QColor(255, 255, 255, 65 if is_hero else 28), max(0.5, sz * 0.02)))
        painter.setBrush(QBrush(fill))
        painter.drawPath(petal)

    # Dark precision hub + luminous inner aperture ring
    hub_r = inner_r * 0.84
    if not monochrome:
        painter.setPen(QPen(QColor(255, 255, 255, 48), max(0.6, sz * 0.03)))
        painter.setBrush(QColor(0x1B, 0x1D, 0x22))
        painter.drawEllipse(QPointF(cx, cy), hub_r, hub_r)

    core_r = hub_r * (0.44 + 0.10 * hover_t)
    painter.setPen(Qt.NoPen)
    if done_t > 0.45:
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QPointF(cx, cy), core_r * 1.1, core_r * 1.1)
    else:
        core_col = QColor(255, 255, 255, 240) if not monochrome else QColor(255, 255, 255, 220)
        painter.setBrush(core_col)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

    painter.restore()


@lru_cache(maxsize=256)
def _cached_brand_pixmap(
    app_id: int,
    size: int,
    accent_color: str,
    dpr: float,
    rot_q: float,
    hover_q: float,
    progress: Optional[int],
    done_q: float,
    monochrome: bool,
) -> QPixmap:
    phys = max(16, int(round(size * dpr)))
    pix = QPixmap(phys, phys)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    if p.isActive():
        draw_brand_emblem(
            p,
            QRectF(0.0, 0.0, float(size), float(size)),
            accent_color=accent_color,
            rotation_deg=rot_q,
            hover_t=hover_q,
            progress=progress,
            done_t=done_q,
            monochrome=monochrome,
        )
        p.end()
    return pix


def create_brand_pixmap(
    size: int = 20,
    accent_color: str = "#F28A32",
    dpr: float = 2.0,
    rotation_deg: float = 0.0,
    hover_t: float = 0.0,
    progress: Optional[int] = None,
    done_t: float = 0.0,
    monochrome: bool = False,
) -> QPixmap:
    """Render the FileTool radial emblem into a Retina-ready QPixmap."""
    app_id = id(QCoreApplication.instance())
    rot_q = round(rotation_deg % 360.0, 1)
    hover_q = round(hover_t, 2)
    done_q = round(done_t, 2)
    prog_val = int(progress) if progress is not None else None
    return _cached_brand_pixmap(
        app_id,
        size,
        accent_color,
        dpr,
        rot_q,
        hover_q,
        prog_val,
        done_q,
        monochrome,
    )


@lru_cache(maxsize=32)
def _cached_brand_icon(app_id: int, accent_color: str) -> QIcon:
    icon = QIcon()
    for sz in (16, 20, 32, 64):
        icon.addPixmap(create_brand_pixmap(size=sz, accent_color=accent_color, dpr=2.0))
    return icon


def create_brand_icon(accent_color: str = "#F28A32") -> QIcon:
    """Build a multi-resolution FileTool QIcon for window and app branding."""
    return _cached_brand_icon(id(QCoreApplication.instance()), accent_color)


class LogoWidget(QWidget):
    """Interactive animated radial wheel brand emblem rendered with QPainter."""

    clicked = Signal()

    def __init__(self, size: int = 28, accent_color: str = "#F28A32", parent=None):
        super().__init__(parent)
        self._sz = size
        self._accent = accent_color
        self._rotation_deg: float = 0.0
        self._hover_t: float = 0.0
        self._progress: Optional[int] = None
        self._done_t: float = 0.0
        self._spinning: bool = False

        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._tick_spin)

        self._rot_anim = QVariantAnimation(self)
        self._rot_anim.setDuration(320)
        self._rot_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._rot_anim.valueChanged.connect(self._on_rot_anim)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_anim)

        self._done_anim = QVariantAnimation(self)
        self._done_anim.setDuration(850)
        self._done_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._done_anim.valueChanged.connect(self._on_done_anim)

    def _on_rot_anim(self, val) -> None:
        self._rotation_deg = float(val) % 360.0
        self.update()

    def _on_hover_anim(self, val) -> None:
        self._hover_t = float(val)
        self.update()

    def _on_done_anim(self, val) -> None:
        self._done_t = float(val)
        self.update()

    def _tick_spin(self) -> None:
        if not self._spinning:
            self._spin_timer.stop()
            return
        self._rotation_deg = (self._rotation_deg + 2.6) % 360.0
        self.update()

    def set_accent_color(self, hex_color: str) -> None:
        if self._accent == hex_color:
            return
        self._accent = hex_color
        self.update()

    def spin_once(self, delta_deg: float = 60.0, duration_ms: int = 340) -> None:
        """Play a brief smooth rotational turn unless Reduce Motion is active."""
        if should_reduce_motion():
            return
        self._rot_anim.stop()
        self._rot_anim.setDuration(duration_ms)
        self._rot_anim.setStartValue(self._rotation_deg)
        self._rot_anim.setEndValue(self._rotation_deg + delta_deg)
        self._rot_anim.start()

    def set_active_progress(self, spinning: bool, progress: Optional[int] = None) -> None:
        """Toggle continuous spin and circular progress arc during conversions."""
        target_spinning = spinning and not should_reduce_motion()
        if self._spinning == target_spinning and self._progress == progress:
            return
        self._spinning = target_spinning
        self._progress = progress
        if self._spinning:
            if not self._spin_timer.isActive():
                self._spin_timer.start()
        else:
            self._spin_timer.stop()
        self.update()

    def trigger_done_flash(self) -> None:
        """Briefly tint toward emerald on batch completion."""
        self._progress = None
        self._spinning = False
        self._spin_timer.stop()
        if should_reduce_motion():
            self._done_t = 0.0
            self.update()
            return
        self._done_anim.stop()
        self._done_anim.setStartValue(1.0)
        self._done_anim.setEndValue(0.0)
        self._done_anim.start()

    def enterEvent(self, event) -> None:
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
            if not self._spinning:
                self.spin_once(60.0, 280)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not should_reduce_motion():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.spin_once(120.0, 320)
            trigger_haptic_tick("alignment")
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        draw_brand_emblem(
            p,
            QRectF(0.0, 0.0, float(self._sz), float(self._sz)),
            accent_color=self._accent,
            rotation_deg=self._rotation_deg,
            hover_t=self._hover_t,
            progress=self._progress,
            done_t=self._done_t,
        )
        p.end()

