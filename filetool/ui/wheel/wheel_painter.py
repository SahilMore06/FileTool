"""High-performance radial wheel renderer using QPainter and SF Symbols."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

from filetool.ui.wheel.animations import (
    DROP_COLLAPSE_DURATION_MS,
    DROP_FLASH_DURATION_MS,
    HOVER_BRIGHTNESS,
    HOVER_SCALE,
)
from filetool.ui.wheel.geometry import (
    HUB_RADIUS,
    RING1_INNER_RADIUS,
    RING1_OUTER_RADIUS,
    RING2_INNER_RADIUS,
    RING2_OUTER_RADIUS,
    SEGMENT_GAP_DEG,
    TANGERINE_BACKDROP_RADIUS,
    TANGERINE_CORNER_RADIUS,
    TANGERINE_GAP,
    TANGERINE_INNER_RADIUS,
    TANGERINE_LABEL_INNER,
    TANGERINE_OUTER_RADIUS,
    HitResult,
    SegmentArc,
    tangerine_angle,
    tangerine_be,
    tangerine_petal_pos,
)

logger = logging.getLogger("filetool.ui.wheel.painter")

# SF Symbol mapping
SYMBOL_MAP = {
    # Convert
    "jpg": "photo",
    "jpeg": "photo",
    "png": "photo.artframe",
    "webp": "sparkles",
    "heic": "camera",
    "gif": "play.square",
    "pdf": "doc.richtext",
    "svg": "square.and.pencil",
    "mp4": "film",
    "mov": "film",
    "mp3": "waveform",
    "wav": "waveform",
    "zip": "archivebox",
    "convert": "arrow.triangle.2.circlepath",
    # Tools
    "compress": "rectangle.compress.vertical",
    "crop": "crop",
    "trim": "scissors",
    "split": "square.split.2x1",
    "merge": "plus.square.on.square",
    "resize": "arrow.up.left.and.arrow.down.right",
    "rotate": "rotate.right",
    "metadata": "shield.slash",
    # Actions
    "airdrop": "paperplane.fill",
    "float": "macwindow.badge.plus",
    "copy": "doc.on.doc",
    "move": "folder",
    "copy_path": "link",
    "terminal": "terminal",
}


@dataclass
class WheelState:
    """State bundle passed to WheelPainter for each frame."""
    wheel_type: str = "convert"  # "convert", "tools", "actions"
    primary_segments: List[SegmentArc] = field(default_factory=list)
    secondary_segments: Optional[List[SegmentArc]] = None
    hovered_index: int = -1
    hovered_ring: int = 1
    hover_progress: float = 0.0

    # Lifecycle & transitions
    open_scale: float = 1.0
    open_opacity: float = 1.0
    segment_stagger_progress: List[float] = field(default_factory=list)
    switch_rotation: float = 0.0
    switch_opacity: float = 1.0

    # Drop & Job progress
    drop_state: str = "none"  # "none", "flash", "collapse", "progress", "done", "error"
    drop_progress: float = 0.0
    job_progress: int = 0
    shake_offset_x: float = 0.0

    # File information
    file_path: Optional[str] = None
    file_name: str = ""
    file_icon: Optional[QPixmap] = None


class IconCache:
    """Caches rasterized SF Symbols or fallback vector icons at high resolution."""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, int], QPixmap] = {}
        self._appkit_available = False
        self._init_appkit()

    def _init_appkit(self) -> None:
        try:
            from AppKit import (
                NSBitmapImageRep,
                NSFontWeightMedium,
                NSImage,
                NSImageSymbolConfiguration,
                NSPNGFileType,
            )
            self._NSImage = NSImage
            self._NSImageSymbolConfiguration = NSImageSymbolConfiguration
            self._NSBitmapImageRep = NSBitmapImageRep
            self._NSPNGFileType = NSPNGFileType
            self._NSFontWeightMedium = NSFontWeightMedium
            self._appkit_available = True
        except Exception:
            self._appkit_available = False

    def get_icon(self, name: str, size: int = 24, tint: QColor = QColor(255, 255, 255)) -> QPixmap:
        key = (name.lower(), size)
        if key in self._cache:
            return self._cache[key]

        symbol_name = SYMBOL_MAP.get(name.lower(), name)
        pix = self._load_sf_symbol(symbol_name, size)
        if not pix or pix.isNull():
            pix = self._draw_fallback_icon(name, size, tint)

        self._cache[key] = pix
        return pix

    def _load_sf_symbol(self, symbol_name: str, size: int) -> Optional[QPixmap]:
        if not self._appkit_available:
            return None
        try:
            config = self._NSImageSymbolConfiguration.configurationWithPointSize_weight_(
                float(size), self._NSFontWeightMedium
            )
            ns_img = self._NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol_name, None)
            if not ns_img:
                return None
            configured = ns_img.imageWithSymbolConfiguration_(config)
            tiff_data = configured.TIFFRepresentation()
            if not tiff_data:
                return None
            rep = self._NSBitmapImageRep.imageRepsWithData_(tiff_data)[0]
            png_data = rep.representationUsingType_properties_(self._NSPNGFileType, None)
            if not png_data:
                return None
            qimg = QImage.fromData(bytes(png_data))
            if not qimg.isNull():
                return QPixmap.fromImage(qimg)
        except Exception as exc:
            logger.debug("Failed loading SF symbol %s: %s", symbol_name, exc)
        return None

    def _draw_fallback_icon(self, name: str, size: int, tint: QColor) -> QPixmap:
        """Render a clean geometric vector icon fallback."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(tint, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)

        m = size * 0.2
        r = QRectF(m, m, size - 2 * m, size - 2 * m)
        p.drawRoundedRect(r, 3, 3)
        p.end()
        return pix


class WheelPainter:
    """Paints radial segments, center hub, animations, and status indicators."""

    def __init__(self) -> None:
        self.icon_cache = IconCache()

    def paint(self, painter: QPainter, width: int, height: int, state: WheelState) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        cx = width / 2.0 + state.shake_offset_x
        cy = height / 2.0

        # Apply global open scale and switch rotation
        painter.translate(cx, cy)
        if state.switch_rotation != 0.0:
            painter.rotate(state.switch_rotation)
        if state.open_scale != 1.0:
            painter.scale(state.open_scale, state.open_scale)
        painter.setOpacity(state.open_opacity * state.switch_opacity)

        # 1. Soft frosted glass backdrop ring matching Tangerine
        if state.drop_state not in ("progress", "done", "error") or state.drop_progress < 1.0:
            self._draw_backdrop(painter)

        # 2. Draw outer segments (unless fully collapsed)
        if state.drop_state not in ("progress", "done", "error") or state.drop_progress < 1.0:
            self._draw_segments(painter, state)

        # 3. Draw secondary outer ring if present
        if state.secondary_segments and state.drop_state == "none":
            self._draw_secondary_ring(painter, state)

        # 4. Draw center pill hub
        self._draw_hub(painter, state)

        painter.restore()

    def _draw_backdrop(self, painter: QPainter) -> None:
        """Render Tangerine's subtle frosted glass disc beneath the petals."""
        disc_r = TANGERINE_BACKDROP_RADIUS
        hole_r = TANGERINE_INNER_RADIUS - 1.5

        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), disc_r, disc_r)
        hole = QPainterPath()
        hole.addEllipse(QPointF(0, 0), hole_r, hole_r)
        glass_ring = path.subtracted(hole)

        painter.save()
        painter.fillPath(glass_ring, QColor(192, 201, 205, 50))
        painter.setPen(QPen(QColor(255, 255, 255, 75), 0.75))
        painter.drawPath(glass_ring)
        painter.restore()

    def _draw_segments(self, painter: QPainter, state: WheelState) -> None:
        segs = state.primary_segments
        if not segs:
            return

        collapse_factor = 0.0
        if state.drop_state == "collapse":
            collapse_factor = min(1.0, state.drop_progress)

        n = len(segs)
        for i, seg in enumerate(segs):
            is_hovered = (state.hovered_index == i and state.hovered_ring == 1)

            # Staggered open progress
            stagger = 1.0
            if i < len(state.segment_stagger_progress):
                stagger = state.segment_stagger_progress[i]
            if stagger <= 0.01:
                continue

            r_in = TANGERINE_INNER_RADIUS
            r_out = TANGERINE_OUTER_RADIUS

            # Collapse towards hub during drop
            if collapse_factor > 0.0:
                r_out = r_out - (r_out - r_in) * collapse_factor

            # Hover expansion
            if is_hovered and state.hover_progress > 0.0:
                scale_delta = (HOVER_SCALE - 1.0) * state.hover_progress
                r_out += (r_out - r_in) * scale_delta

            # Build Tangerine curved petal
            path = self._build_tangerine_petal(i, n, r_in, r_out, TANGERINE_CORNER_RADIUS, TANGERINE_GAP)

            # Colors matching Tangerine
            if state.drop_state == "flash" and is_hovered:
                # Flash bright accent/white
                flash_alpha = int(240 * (1.0 - state.drop_progress))
                fill_brush = QBrush(QColor(255, 255, 255, max(150, flash_alpha)))
                border_pen = QPen(QColor(255, 255, 255), 1.5)
            elif is_hovered:
                # Vibrant Tangerine Orange (#ff5200)
                fill_brush = QBrush(QColor(255, 82, 0, 255))
                border_pen = QPen(QColor(194, 101, 52, 115), 0.85)
            else:
                # Translucent frosted pearlescent glass
                grad = QRadialGradient(0, 0, r_out)
                grad.setColorAt(0.0, QColor(255, 255, 255, 215))
                grad.setColorAt(0.68, QColor(243, 246, 247, 160))
                grad.setColorAt(1.0, QColor(244, 246, 246, 195))
                fill_brush = QBrush(grad)
                border_pen = QPen(QColor(93, 102, 102, 58), 0.75)

            # Fill & Stroke
            painter.save()
            painter.setOpacity(stagger)
            painter.fillPath(path, fill_brush)
            painter.setPen(border_pen)
            painter.drawPath(path)

            # Draw icon and label at petal centroid
            if collapse_factor < 0.7:
                self._draw_segment_content(painter, seg, is_hovered, state.hover_progress, n)
            painter.restore()

    def _draw_secondary_ring(self, painter: QPainter, state: WheelState) -> None:
        if not state.secondary_segments:
            return

        n = len(state.secondary_segments)
        for i, seg in enumerate(state.secondary_segments):
            is_hovered = (state.hovered_index == i and state.hovered_ring == 2)
            r_in = RING2_INNER_RADIUS
            r_out = RING2_OUTER_RADIUS

            if is_hovered and state.hover_progress > 0.0:
                scale_delta = (HOVER_SCALE - 1.0) * state.hover_progress
                r_out += (r_out - r_in) * scale_delta

            path = self._build_annular_sector(
                0, 0, r_in, r_out, seg.start_angle, seg.end_angle, SEGMENT_GAP_DEG
            )

            fill_brush = QBrush(QColor(255, 82, 0, 255)) if is_hovered else QBrush(QColor(244, 246, 246, 210))
            border_pen = QPen(QColor(194, 101, 52, 115) if is_hovered else QColor(93, 102, 102, 58), 0.75)

            painter.fillPath(path, fill_brush)
            painter.setPen(border_pen)
            painter.drawPath(path)

            self._draw_segment_content(painter, seg, is_hovered, state.hover_progress, n)

    def _draw_segment_content(
        self, painter: QPainter, seg: SegmentArc, is_hovered: bool, hover_prog: float, total_items: int = 8
    ) -> None:
        # Centroid matching Tangerine
        cx, cy = tangerine_petal_pos(seg.index, total_items)

        is_tool = seg.action_type in ("tool", "action") or (seg.icon_name and seg.icon_name != seg.label.lower())

        if is_tool:
            # Tool or Action: Icon + 8.5px label
            icon_size = 18
            icon_name = seg.icon_name or seg.label.lower()
            tint = QColor(255, 255, 255) if is_hovered else QColor(35, 38, 36)
            pix = self.icon_cache.get_icon(icon_name, size=icon_size, tint=tint)

            if pix and not pix.isNull():
                ix = cx - pix.width() / 2.0
                iy = cy - 16.5
                painter.drawPixmap(int(ix), int(iy), pix)

            painter.setFont(QFont("SF Pro Rounded", 8, QFont.Bold))
            painter.setPen(QColor(255, 255, 255) if is_hovered else QColor(15, 18, 16))
            label_rect = QRectF(cx - 36, cy + 2.0, 72, 14)
            painter.drawText(label_rect, Qt.AlignCenter, seg.label.upper())

        else:
            # Format: 13.5px bold label
            painter.setFont(QFont("SF Pro Rounded", 13, QFont.Bold))
            painter.setPen(QColor(255, 255, 255) if is_hovered else QColor(15, 18, 16))
            label_rect = QRectF(cx - 36, cy - 10.0, 72, 20)
            painter.drawText(label_rect, Qt.AlignCenter, seg.label.upper())

    def _draw_hub(self, painter: QPainter, state: WheelState) -> None:
        # Center pill badge matching Tangerine
        pill_w = 76.0
        pill_h = 34.0
        pill_r = 17.0
        pill_rect = QRectF(-pill_w / 2.0, -pill_h / 2.0, pill_w, pill_h)

        if state.drop_state == "progress":
            self._draw_progress_ring(painter, TANGERINE_INNER_RADIUS - 4.0, state.job_progress)
        elif state.drop_state == "done":
            self._draw_done_indicator(painter, TANGERINE_INNER_RADIUS - 4.0)
        elif state.drop_state == "error":
            self._draw_error_indicator(painter, TANGERINE_INNER_RADIUS - 4.0)
        else:
            # Frosted glass pill badge
            pill_path = QPainterPath()
            pill_path.addRoundedRect(pill_rect, pill_r, pill_r)

            painter.save()
            painter.fillPath(pill_path, QColor(255, 255, 255, 230))
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            painter.drawPath(pill_path)

            # Pill text / icon
            hover_seg: Optional[SegmentArc] = None
            if state.hovered_index >= 0:
                if state.hovered_ring == 1 and state.hovered_index < len(state.primary_segments):
                    hover_seg = state.primary_segments[state.hovered_index]
                elif state.secondary_segments and state.hovered_index < len(state.secondary_segments):
                    hover_seg = state.secondary_segments[state.hovered_index]

            if hover_seg:
                # Show highlighted action/format name in pill
                painter.setFont(QFont("SF Pro Rounded", 11, QFont.Bold))
                painter.setPen(QColor(255, 82, 0))  # Tangerine Orange
                painter.drawText(pill_rect, Qt.AlignCenter, hover_seg.label.upper())
            elif state.file_icon and not state.file_icon.isNull():
                # Show source file icon
                scaled = state.file_icon.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(int(-scaled.width() / 2.0), int(-scaled.height() / 2.0), scaled)
            else:
                # Show source format
                painter.setFont(QFont("SF Pro Rounded", 10, QFont.Bold))
                painter.setPen(QColor(100, 105, 100))
                ext = Path(state.file_name).suffix.upper().lstrip(".") or "FILE"
                painter.drawText(pill_rect, Qt.AlignCenter, ext)
            painter.restore()

    def _draw_progress_ring(self, painter: QPainter, radius: float, progress: int) -> None:
        ring_r = radius - 2.0
        track_rect = QRectF(-ring_r, -ring_r, ring_r * 2, ring_r * 2)

        painter.setPen(QPen(QColor(0, 0, 0, 30), 3.5))
        painter.drawEllipse(track_rect)

        pct = max(0, min(100, progress))
        sweep = int(-pct * 3.6 * 16)

        # Progress in Tangerine Orange (#ff5200)
        painter.setPen(QPen(QColor(255, 82, 0), 4.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(track_rect, 90 * 16, sweep)

        painter.setFont(QFont("SF Pro Rounded", 12, QFont.Bold))
        painter.setPen(QColor(30, 32, 30))
        painter.drawText(QRectF(-35, -12, 70, 24), Qt.AlignCenter, f"{pct}%")

    def _draw_done_indicator(self, painter: QPainter, radius: float) -> None:
        ring_r = radius - 2.0
        rect = QRectF(-ring_r, -ring_r, ring_r * 2, ring_r * 2)

        # Glowing green ring
        painter.setPen(QPen(QColor(48, 209, 88), 4.0))
        painter.drawEllipse(rect)

        # Checkmark
        path = QPainterPath()
        path.moveTo(-11, 0)
        path.lineTo(-3, 8)
        path.lineTo(12, -8)

        painter.setPen(QPen(QColor(48, 209, 88), 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

    def _draw_error_indicator(self, painter: QPainter, radius: float) -> None:
        ring_r = radius - 2.0
        rect = QRectF(-ring_r, -ring_r, ring_r * 2, ring_r * 2)

        painter.setPen(QPen(QColor(255, 69, 58), 4.0))
        painter.drawEllipse(rect)

        painter.setFont(QFont("SF Pro Rounded", 18, QFont.Bold))
        painter.setPen(QColor(255, 69, 58))
        painter.drawText(QRectF(-20, -20, 40, 40), Qt.AlignCenter, "!")

    @staticmethod
    def _build_tangerine_petal(
        index: int, total: int, r_in: float, r_out: float, corner_r: float = 20.16, gap: float = 4.0
    ) -> QPainterPath:
        """Construct exact rounded petal geometry matching Tangerine for Mac."""
        a = tangerine_angle(index, total)
        n = math.pi * 2.0 / total
        l = a - n / 2.0
        s = a + n / 2.0

        def r_gap(J: float) -> float:
            return math.asin(min(0.95, gap / 2.0 / max(J, gap / 2.0 + 0.01)))

        d = l + r_gap(r_out)
        i = s - r_gap(r_out)
        c = l + r_gap(r_in)
        g = s - r_gap(r_in)

        f = min(0.15, (i - d) * 0.24)
        u = min(0.18, (g - c) * 0.18)
        v = r_in / max(0.01, math.cos(u))
        y = v + r_in * math.tan(u)
        O = r_out - corner_r

        p1 = tangerine_be(y, l + r_gap(y))
        p2 = tangerine_be(O, l + r_gap(O))
        c_out1 = tangerine_be(r_out, d)
        p3 = tangerine_be(r_out, d + f)
        p4 = tangerine_be(r_out, i - f)
        c_out2 = tangerine_be(r_out, i)
        p5 = tangerine_be(O, s - r_gap(O))
        p6 = tangerine_be(y, s - r_gap(y))
        c_in2 = tangerine_be(v, s - r_gap(v))
        p7 = tangerine_be(r_in, g - u)
        p8 = tangerine_be(r_in, c + u)
        c_in1 = tangerine_be(v, l + r_gap(v))

        path = QPainterPath()
        path.moveTo(p1[0], p1[1])
        path.lineTo(p2[0], p2[1])
        path.quadTo(c_out1[0], c_out1[1], p3[0], p3[1])

        steps = 10
        for step in range(1, steps):
            ang = (d + f) + (i - f - (d + f)) * (step / float(steps))
            pt = tangerine_be(r_out, ang)
            path.lineTo(pt[0], pt[1])
        path.lineTo(p4[0], p4[1])

        path.quadTo(c_out2[0], c_out2[1], p5[0], p5[1])
        path.lineTo(p6[0], p6[1])
        path.quadTo(c_in2[0], c_in2[1], p7[0], p7[1])

        for step in range(1, steps):
            ang = (g - u) - (g - u - (c + u)) * (step / float(steps))
            pt = tangerine_be(r_in, ang)
            path.lineTo(pt[0], pt[1])
        path.lineTo(p8[0], p8[1])

        path.quadTo(c_in1[0], c_in1[1], p1[0], p1[1])
        path.closeSubpath()
        return path

    @staticmethod
    def _build_annular_sector(
        cx: float, cy: float, r_in: float, r_out: float, start_deg: float, end_deg: float, gap_deg: float = 2.0
    ) -> QPainterPath:
        path = QPainterPath()
        half_gap = gap_deg / 2.0
        s_clk = start_deg + half_gap
        e_clk = end_deg - half_gap
        span_clk = (e_clk - s_clk) % 360.0
        if span_clk <= 0:
            span_clk = 360.0 - gap_deg

        qt_start = (90.0 - s_clk) % 360.0
        qt_sweep = -span_clk

        rect_out = QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
        rect_in = QRectF(cx - r_in, cy - r_in, r_in * 2, r_in * 2)

        path.arcMoveTo(rect_out, qt_start)
        path.arcTo(rect_out, qt_start, qt_sweep)
        path.arcTo(rect_in, qt_start + qt_sweep, -qt_sweep)
        path.closeSubpath()
        return path
