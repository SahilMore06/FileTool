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
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

from filetool.ui.styles import contrast_ratio, get_tokens
from filetool.ui.wheel.animations import HOVER_SCALE
from filetool.ui.wheel.geometry import (
    RING2_INNER_RADIUS,
    RING2_OUTER_RADIUS,
    SEGMENT_GAP_DEG,
    TANGERINE_BACKDROP_RADIUS,
    TANGERINE_CORNER_RADIUS,
    TANGERINE_GAP,
    TANGERINE_INNER_RADIUS,
    TANGERINE_OUTER_RADIUS,
    SegmentArc,
    tangerine_angle,
    tangerine_be,
    tangerine_petal_pos,
)

logger = logging.getLogger("filetool.ui.wheel.painter")

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

_VECTOR_FALLBACK_ALIAS = {
    "move": "folder",
    "copy_path": "link",
    "metadata": "shield",
    "more": "dots",
}


def _wcag_contrast_ink(bg: QColor) -> QColor:
    """Pick dark `#202124` or `#FFFFFF` ink with higher WCAG contrast on `bg`."""
    bg_hex = bg.name()
    dark_ink = QColor(0x20, 0x21, 0x24)
    return dark_ink if contrast_ratio("#202124", bg_hex) > contrast_ratio("#FFFFFF", bg_hex) else QColor(255, 255, 255)


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    """Linearly interpolate two QColors over t in [0.0, 1.0]."""
    k = max(0.0, min(1.0, float(t)))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * k),
        int(c1.green() + (c2.green() - c1.green()) * k),
        int(c1.blue() + (c2.blue() - c1.blue()) * k),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * k),
    )


@dataclass
class WheelState:
    """State bundle passed to WheelPainter for each frame."""

    wheel_type: str = "convert"  # "convert", "tools", "actions"
    primary_segments: List[SegmentArc] = field(default_factory=list)
    secondary_segments: Optional[List[SegmentArc]] = None
    hovered_index: int = -1
    hovered_ring: int = 1
    hover_progress: float = 0.0

    # Theme
    dark_mode: bool = False
    accent_color: str = "#F28A32"
    accent_hover: str = "#D9751F"

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
    file_count: int = 1
    file_icon: Optional[QPixmap] = None


class IconCache:
    """Caches rasterized SF Symbols or crisp vector fallback icons."""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, int, int], QPixmap] = {}
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
        key = (name.lower(), size, int(tint.rgba()))
        if key in self._cache:
            return self._cache[key]

        symbol_name = SYMBOL_MAP.get(name.lower(), name)
        raw_pix = self._load_sf_symbol(symbol_name, size)
        if raw_pix and not raw_pix.isNull():
            pix = self._tint_pixmap(raw_pix, tint)
        else:
            pix = self._draw_fallback_icon(name, size, tint)

        self._cache[key] = pix
        return pix

    @staticmethod
    def _tint_pixmap(pix: QPixmap, tint: QColor) -> QPixmap:
        tinted = QPixmap(pix.size())
        tinted.setDevicePixelRatio(pix.devicePixelRatio())
        tinted.fill(Qt.transparent)
        p = QPainter(tinted)
        if p.isActive():
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawPixmap(0, 0, pix)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(tinted.rect(), tint)
            p.end()
        return tinted

    def _load_sf_symbol(self, symbol_name: str, size: int) -> Optional[QPixmap]:
        if not self._appkit_available:
            return None
        try:
            config = self._NSImageSymbolConfiguration.configurationWithPointSize_weight_(
                float(size) * 1.15, self._NSFontWeightMedium
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

    @staticmethod
    def _draw_fallback_icon(name: str, size: int, tint: QColor) -> QPixmap:
        """Render a crisp geometric vector fallback icon at 2x scale."""
        from filetool.ui.components import draw_vector_icon

        scale = 2.0
        pix = QPixmap(int(size * scale), int(size * scale))
        pix.setDevicePixelRatio(scale)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        if p.isActive():
            icon_key = _VECTOR_FALLBACK_ALIAS.get(name.lower(), name.lower())
            draw_vector_icon(p, icon_key, 0.0, 0.0, float(size), tint)
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

        painter.translate(cx, cy)
        if state.switch_rotation != 0.0:
            painter.rotate(state.switch_rotation)
        if state.open_scale != 1.0:
            painter.scale(state.open_scale, state.open_scale)
        painter.setOpacity(state.open_opacity * state.switch_opacity)

        show_petals = state.drop_state not in ("progress", "done", "error") or state.drop_progress < 1.0
        if show_petals:
            self._draw_backdrop(painter, state)
            self._draw_segments(painter, state)
            if state.secondary_segments and state.drop_state == "none":
                self._draw_secondary_ring(painter, state)

        self._draw_hub(painter, state)
        painter.restore()

    def _draw_backdrop(self, painter: QPainter, state: WheelState) -> None:
        """Render ambient shadow halo and frosted backing disc beneath the petals."""
        disc_r = TANGERINE_BACKDROP_RADIUS
        hole_r = TANGERINE_INNER_RADIUS - 2.0

        # Soft ambient radial drop shadow around the wheel
        halo_r = disc_r + 22.0
        halo = QRadialGradient(0, 3, halo_r)
        base_shadow = 72 if state.dark_mode else 34
        halo.setColorAt(0.0, QColor(0, 0, 0, base_shadow))
        halo.setColorAt(disc_r / halo_r, QColor(0, 0, 0, int(base_shadow * 0.55)))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(0, 3), halo_r, halo_r)
        painter.restore()

        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), disc_r, disc_r)
        hole = QPainterPath()
        hole.addEllipse(QPointF(0, 0), hole_r, hole_r)
        glass_ring = path.subtracted(hole)

        painter.save()
        if state.dark_mode:
            fill = QColor(18, 19, 22, 168)
            rim = QColor(255, 255, 255, 36)
        else:
            fill = QColor(225, 223, 217, 130)
            rim = QColor(255, 255, 255, 190)

        painter.fillPath(glass_ring, fill)
        painter.setPen(QPen(rim, 1.0))
        painter.drawPath(glass_ring)
        painter.restore()

    def _petal_colors(self, state: WheelState, is_hovered: bool, r_out: float):
        accent = QColor(state.accent_color)
        accent_dark = QColor(state.accent_hover)
        hover_t = state.hover_progress if is_hovered else 0.0

        if state.dark_mode:
            idle_inner = QColor(0x2A, 0x2C, 0x31, 244)
            idle_mid = QColor(0x21, 0x23, 0x27, 238)
            idle_outer = QColor(0x19, 0x1B, 0x1E, 246)
            idle_border = QColor(255, 255, 255, 34)
            idle_ink = QColor(0xED, 0xEC, 0xE8)
        else:
            idle_inner = QColor(0xFF, 0xFE, 0xFC, 248)
            idle_mid = QColor(0xF6, 0xF4, 0xEF, 240)
            idle_outer = QColor(0xEC, 0xEA, 0xE4, 246)
            idle_border = QColor(0xD8, 0xD5, 0xCE, 225)
            idle_ink = QColor(0x20, 0x21, 0x24)

        if hover_t > 0.01:
            act_top = accent.lighter(116)
            act_bot = accent_dark
            act_border = accent.lighter(142)

            c_inner = _lerp_color(idle_inner, act_top, hover_t)
            c_mid = _lerp_color(idle_mid, accent, hover_t)
            c_outer = _lerp_color(idle_outer, act_bot, hover_t)
            border_c = _lerp_color(idle_border, act_border, hover_t)
            target_ink = _wcag_contrast_ink(accent)
            ink_c = _lerp_color(idle_ink, target_ink, hover_t)

            grad = QRadialGradient(0, 0, r_out)
            grad.setColorAt(0.0, c_inner)
            grad.setColorAt(0.65, c_mid)
            grad.setColorAt(1.0, c_outer)
            return QBrush(grad), QPen(border_c, 1.0 + 0.35 * hover_t), ink_c

        grad = QRadialGradient(0, 0, r_out)
        grad.setColorAt(0.0, idle_inner)
        grad.setColorAt(0.7, idle_mid)
        grad.setColorAt(1.0, idle_outer)
        return QBrush(grad), QPen(idle_border, 0.9), idle_ink

    def _draw_segments(self, painter: QPainter, state: WheelState) -> None:
        segs = state.primary_segments
        if not segs:
            return

        collapse_factor = min(1.0, state.drop_progress) if state.drop_state == "collapse" else 0.0

        n = len(segs)
        for i, seg in enumerate(segs):
            is_hovered = state.hovered_index == i and state.hovered_ring == 1

            stagger = 1.0
            if i < len(state.segment_stagger_progress):
                stagger = state.segment_stagger_progress[i]
            if stagger <= 0.01:
                continue

            r_in = TANGERINE_INNER_RADIUS
            r_out = TANGERINE_OUTER_RADIUS

            if collapse_factor > 0.0:
                r_out = r_out - (r_out - r_in) * collapse_factor

            if is_hovered and state.hover_progress > 0.0:
                scale_delta = (HOVER_SCALE - 1.0) * state.hover_progress
                r_out += (r_out - r_in) * scale_delta

            path = self._build_tangerine_petal(i, n, r_in, r_out, TANGERINE_CORNER_RADIUS, TANGERINE_GAP)

            if state.drop_state == "flash" and is_hovered:
                flash_alpha = int(245 * (1.0 - state.drop_progress))
                fill_brush = QBrush(QColor(255, 255, 255, max(165, flash_alpha)))
                border_pen = QPen(QColor(state.accent_color), 1.6)
                ink_color = QColor(0x20, 0x21, 0x24)
            else:
                fill_brush, border_pen, ink_color = self._petal_colors(state, is_hovered, r_out)

            painter.save()
            painter.setOpacity(stagger)
            painter.fillPath(path, fill_brush)
            painter.setPen(border_pen)
            painter.drawPath(path)

            if collapse_factor < 0.7:
                self._draw_segment_content(painter, seg, ink_color, n)
            painter.restore()

    def _draw_secondary_ring(self, painter: QPainter, state: WheelState) -> None:
        if not state.secondary_segments:
            return

        n = len(state.secondary_segments)
        for i, seg in enumerate(state.secondary_segments):
            is_hovered = state.hovered_index == i and state.hovered_ring == 2

            r_in = RING2_INNER_RADIUS
            r_out = RING2_OUTER_RADIUS
            if is_hovered and state.hover_progress > 0.0:
                scale_delta = (HOVER_SCALE - 1.0) * state.hover_progress
                r_out += (r_out - r_in) * scale_delta

            path = self._build_annular_sector(
                0, 0, r_in, r_out, seg.start_angle, seg.end_angle, SEGMENT_GAP_DEG
            )

            fill_brush, border_pen, ink_color = self._petal_colors(state, is_hovered, r_out)
            painter.fillPath(path, fill_brush)
            painter.setPen(border_pen)
            painter.drawPath(path)

            self._draw_segment_content(painter, seg, ink_color, n)

    def _draw_segment_content(
        self, painter: QPainter, seg: SegmentArc, ink_color: QColor, total_items: int = 8
    ) -> None:
        if seg.ring == 2:
            cx, cy = seg.centroid
            font = QFont(".AppleSystemUIFont", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(ink_color)
            label_rect = QRectF(cx - 34, cy - 10, 68, 20)
            painter.drawText(label_rect, Qt.AlignCenter, seg.label.upper())
            return

        cx, cy = tangerine_petal_pos(seg.index, total_items)
        is_tool = seg.action_type in ("tool", "action", "more") or (
            seg.icon_name and seg.icon_name != seg.label.lower()
        )

        if is_tool:
            icon_size = 18
            icon_name = seg.icon_name or seg.label.lower()
            pix = self.icon_cache.get_icon(icon_name, size=icon_size, tint=ink_color)
            if pix and not pix.isNull():
                logical_w = pix.width() / max(1.0, pix.devicePixelRatio())
                logical_h = pix.height() / max(1.0, pix.devicePixelRatio())
                ix = cx - logical_w / 2.0
                iy = cy - logical_h - 1.0
                painter.drawPixmap(QPointF(ix, iy), pix)

            font = QFont(".AppleSystemUIFont", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(ink_color)
            label_rect = QRectF(cx - 38, cy + 3.0, 76, 14)
            elided = QFontMetrics(font).elidedText(seg.label.upper(), Qt.ElideRight, 72)
            painter.drawText(label_rect, Qt.AlignCenter, elided)
        else:
            font = QFont(".AppleSystemUIFont", 11, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(ink_color)
            label_rect = QRectF(cx - 38, cy - 10.0, 76, 20)
            painter.drawText(label_rect, Qt.AlignCenter, seg.label.upper())

    def _draw_hub(self, painter: QPainter, state: WheelState) -> None:
        accent = QColor(state.accent_color)

        if state.drop_state == "progress":
            self._draw_progress_ring(painter, TANGERINE_INNER_RADIUS - 4.0, state.job_progress, state)
            return
        if state.drop_state == "done":
            self._draw_done_indicator(painter, TANGERINE_INNER_RADIUS - 4.0, state)
            return
        if state.drop_state == "error":
            self._draw_error_indicator(painter, TANGERINE_INNER_RADIUS - 4.0, state)
            return

        hub_r = TANGERINE_INNER_RADIUS - 6.0
        hub_rect = QRectF(-hub_r, -hub_r, 2 * hub_r, 2 * hub_r)
        painter.save()

        hover_seg: Optional[SegmentArc] = None
        if state.hovered_index >= 0:
            if state.hovered_ring == 1 and state.hovered_index < len(state.primary_segments):
                hover_seg = state.primary_segments[state.hovered_index]
            elif (
                state.hovered_ring == 2
                and state.secondary_segments
                and state.hovered_index < len(state.secondary_segments)
            ):
                hover_seg = state.secondary_segments[state.hovered_index]

        # Subtle outer shadow around hub
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 60 if state.dark_mode else 36))
        painter.drawEllipse(QRectF(-hub_r - 2, -hub_r - 1, 2 * hub_r + 4, 2 * hub_r + 4))

        hub_bg = QColor(0x1D, 0x1F, 0x24) if state.dark_mode else QColor(0x20, 0x21, 0x24)
        rim_idle = QColor(0x45, 0x47, 0x4E) if state.dark_mode else QColor(0x3B, 0x3D, 0x42)
        rim_color = _lerp_color(rim_idle, accent, state.hover_progress if hover_seg else 0.0)
        painter.setPen(QPen(rim_color, 1.4))
        painter.setBrush(hub_bg)
        painter.drawEllipse(hub_rect)

        drawn_thumb = False
        if state.file_path and Path(state.file_path).exists():
            ext = Path(state.file_path).suffix.lower()
            if ext in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".bmp"):
                img = QImage(state.file_path)
                if not img.isNull():
                    thumb_r = hub_r - 3.5
                    clip_p = QPainterPath()
                    clip_p.addEllipse(QRectF(-thumb_r, -thumb_r, 2 * thumb_r, 2 * thumb_r))
                    painter.save()
                    painter.setClipPath(clip_p)
                    scaled = img.scaled(
                        int(2 * thumb_r),
                        int(2 * thumb_r),
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                    painter.drawImage(int(-thumb_r), int(-thumb_r), scaled)
                    painter.restore()
                    drawn_thumb = True

        if not drawn_thumb and state.file_icon and not state.file_icon.isNull():
            scaled = state.file_icon.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(-scaled.width() / 2.0), int(-scaled.height() / 2.0 - 4.0), scaled)
            drawn_thumb = True

        painter.restore()

        # Center overlay badge (hovered petal readout, count pill, or wheel mode hint)

        if hover_seg:
            label = hover_seg.label.upper()
            font = QFont(".AppleSystemUIFont", 9, QFont.Weight.Bold)
            fm = QFontMetrics(font)
            max_w = hub_r * 2.25
            pill_w = max(68.0, min(max_w, fm.horizontalAdvance(label) + 22.0))
            pill_h = 24.0
            pill_rect = QRectF(-pill_w / 2.0, -pill_h / 2.0, pill_w, pill_h)
            pill_path = QPainterPath()
            pill_path.addRoundedRect(pill_rect, 12, 12)
            painter.fillPath(pill_path, QColor(0x18, 0x19, 0x1D, 238))
            painter.setPen(QPen(accent, 1.25))
            painter.drawPath(pill_path)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            elided = fm.elidedText(label, Qt.ElideRight, int(pill_w - 14))
            painter.drawText(pill_rect, Qt.AlignCenter, elided)
            return

        if not drawn_thumb:
            ext = Path(state.file_name).suffix.upper().lstrip(".") or "FILE"
            painter.setFont(QFont(".AppleSystemUIFont", 10, QFont.Weight.Bold))
            painter.setPen(QColor(0xEC, 0xEA, 0xE4))
            painter.drawText(QRectF(-hub_r + 6, -15, 2 * hub_r - 12, 20), Qt.AlignCenter, ext[:6])

        # Quiet mode or multi-file badge tucked cleanly inside lower half of hub
        footer_text = f"{state.file_count} FILES" if state.file_count > 1 else state.wheel_type.upper()
        sub_font = QFont(".AppleSystemUIFont", 7, QFont.Weight.Bold)
        sub_fm = QFontMetrics(sub_font)
        sub_w = min(hub_r * 1.65, sub_fm.horizontalAdvance(footer_text) + 12.0)
        sub_rect = QRectF(-sub_w / 2.0, hub_r - 17.5, sub_w, 13.0)
        sub_path = QPainterPath()
        sub_path.addRoundedRect(sub_rect, 6.5, 6.5)
        painter.fillPath(sub_path, QColor(0x12, 0x13, 0x16, 210))
        painter.setFont(sub_font)
        painter.setPen(QColor(0xB8, 0xB5, 0xAE))
        painter.drawText(sub_rect, Qt.AlignCenter, footer_text)

    def _draw_status_disc(self, painter: QPainter, ring_r: float, state: WheelState) -> QRectF:
        """Paint an opaque frosted disc under progress/done/error rings for wallpaper contrast."""
        disc_r = ring_r + 4.0
        disc_rect = QRectF(-disc_r, -disc_r, disc_r * 2, disc_r * 2)
        bg = QColor(0x1D, 0x1E, 0x22, 240) if state.dark_mode else QColor(0xFB, 0xFA, 0xF7, 246)
        border = QColor(0x36, 0x38, 0x3E) if state.dark_mode else QColor(0xE1, 0xDF, 0xD9)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(bg)
        painter.drawEllipse(disc_rect)
        return QRectF(-ring_r, -ring_r, ring_r * 2, ring_r * 2)

    def _draw_progress_ring(self, painter: QPainter, radius: float, progress: int, state: WheelState) -> None:
        ring_r = radius - 3.0
        track_rect = self._draw_status_disc(painter, ring_r, state)

        track_c = QColor(255, 255, 255, 36) if state.dark_mode else QColor(0x20, 0x21, 0x24, 38)
        painter.setPen(QPen(track_c, 3.5))
        painter.drawEllipse(track_rect)

        pct = max(0, min(100, progress))
        sweep = int(-pct * 3.6 * 16)
        painter.setPen(QPen(QColor(state.accent_color), 4.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(track_rect, 90 * 16, sweep)

        painter.setFont(QFont(".AppleSystemUIFont", 12, QFont.Weight.Bold))
        painter.setPen(QColor(0xEC, 0xEA, 0xE4) if state.dark_mode else QColor(0x20, 0x21, 0x24))
        painter.drawText(QRectF(-35, -12, 70, 24), Qt.AlignCenter, f"{pct}%")

    def _draw_done_indicator(self, painter: QPainter, radius: float, state: WheelState) -> None:
        from filetool.ui.components import draw_vector_icon

        ring_r = radius - 3.0
        rect = self._draw_status_disc(painter, ring_r, state)
        success = QColor(get_tokens(state.dark_mode)["success"])

        painter.setPen(QPen(success, 3.8))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)
        draw_vector_icon(painter, "check", -14.0, -14.0, 28.0, success)

    def _draw_error_indicator(self, painter: QPainter, radius: float, state: WheelState) -> None:
        from filetool.ui.components import draw_vector_icon

        ring_r = radius - 3.0
        rect = self._draw_status_disc(painter, ring_r, state)
        err = QColor(get_tokens(state.dark_mode)["error"])

        painter.setPen(QPen(err, 3.8))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)
        draw_vector_icon(painter, "close", -13.0, -13.0, 26.0, err)

    @staticmethod
    def _build_tangerine_petal(
        index: int, total: int, r_in: float, r_out: float, corner_r: float = 20.16, gap: float = 4.0
    ) -> QPainterPath:
        """Build a rounded petal path separated by constant-width radial gaps."""
        center_ang = tangerine_angle(index, total)
        sector_span = math.pi * 2.0 / total
        left_edge = center_ang - sector_span / 2.0
        right_edge = center_ang + sector_span / 2.0

        def half_gap_angle(radius: float) -> float:
            return math.asin(min(0.95, gap / 2.0 / max(radius, gap / 2.0 + 0.01)))

        outer_start = left_edge + half_gap_angle(r_out)
        outer_end = right_edge - half_gap_angle(r_out)
        inner_start = left_edge + half_gap_angle(r_in)
        inner_end = right_edge - half_gap_angle(r_in)

        outer_fillet = min(0.15, (outer_end - outer_start) * 0.24)
        inner_fillet = min(0.18, (inner_end - inner_start) * 0.18)
        inner_corner_r = r_in / max(0.01, math.cos(inner_fillet))
        inner_side_r = inner_corner_r + r_in * math.tan(inner_fillet)
        outer_side_r = r_out - corner_r

        p_in_left = tangerine_be(inner_side_r, left_edge + half_gap_angle(inner_side_r))
        p_out_left = tangerine_be(outer_side_r, left_edge + half_gap_angle(outer_side_r))
        c_out_left = tangerine_be(r_out, outer_start)
        p_arc_out_start = tangerine_be(r_out, outer_start + outer_fillet)
        p_arc_out_end = tangerine_be(r_out, outer_end - outer_fillet)
        c_out_right = tangerine_be(r_out, outer_end)
        p_out_right = tangerine_be(outer_side_r, right_edge - half_gap_angle(outer_side_r))
        p_in_right = tangerine_be(inner_side_r, right_edge - half_gap_angle(inner_side_r))
        c_in_right = tangerine_be(inner_corner_r, right_edge - half_gap_angle(inner_corner_r))
        p_arc_in_end = tangerine_be(r_in, inner_end - inner_fillet)
        p_arc_in_start = tangerine_be(r_in, inner_start + inner_fillet)
        c_in_left = tangerine_be(inner_corner_r, left_edge + half_gap_angle(inner_corner_r))

        path = QPainterPath()
        path.moveTo(*p_in_left)
        path.lineTo(*p_out_left)
        path.quadTo(*c_out_left, *p_arc_out_start)

        outer_arc_start = outer_start + outer_fillet
        outer_arc_end = outer_end - outer_fillet
        outer_steps = max(20, int(abs(outer_arc_end - outer_arc_start) * 48))
        for step in range(1, outer_steps):
            ang = outer_arc_start + (outer_arc_end - outer_arc_start) * (step / float(outer_steps))
            path.lineTo(*tangerine_be(r_out, ang))
        path.lineTo(*p_arc_out_end)

        path.quadTo(*c_out_right, *p_out_right)
        path.lineTo(*p_in_right)
        path.quadTo(*c_in_right, *p_arc_in_end)

        inner_arc_start = inner_start + inner_fillet
        inner_arc_end = inner_end - inner_fillet
        inner_steps = max(16, int(abs(inner_arc_end - inner_arc_start) * 40))
        for step in range(1, inner_steps):
            ang = inner_arc_end - (inner_arc_end - inner_arc_start) * (step / float(inner_steps))
            path.lineTo(*tangerine_be(r_in, ang))
        path.lineTo(*p_arc_in_start)

        path.quadTo(*c_in_left, *p_in_left)
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
