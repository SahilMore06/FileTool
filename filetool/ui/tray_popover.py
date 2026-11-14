"""Animated macOS menu-bar popover card replacing the plain stock tray menu."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from filetool.ui.components import LogoWidget, collect_paths_from_urls, draw_vector_icon
from filetool.ui.styles import get_tokens
from filetool.ui.wheel.animations import should_reduce_motion

_MODIFIER_GLYPHS = {
    "shift": "⇧",
    "command": "⌘",
    "cmd": "⌘",
    "control": "⌃",
    "ctrl": "⌃",
    "option": "⌥",
    "alt": "⌥",
}

_SHADOW_MARGIN = 12


def _format_trigger_chip(key_name: str, label: str) -> str:
    glyph = _MODIFIER_GLYPHS.get(key_name.strip().lower(), "")
    prefix = f"{glyph} " if glyph else f"{key_name.title()} · "
    return f"{prefix}{label}"


class _PopoverActionButton(QPushButton):
    """Custom-painted menu action row with smooth hover animation and keycap hint."""

    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str,
        shortcut_hint: str,
        danger: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._title = title
        self._subtitle = subtitle
        self._shortcut = shortcut_hint
        self._danger = danger
        self._tokens = get_tokens(False)
        self._hover_t: float = 0.0

        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setText("")

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, val) -> None:
        self._hover_t = float(val)
        self.update()

    def set_tokens(self, tokens: dict) -> None:
        self._tokens = tokens
        self.update()

    def set_subtitle(self, text: str) -> None:
        self._subtitle = text
        self.update()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if not self.underMouse():
            self._animate_hover(0.0)
        super().focusOutEvent(event)

    def _animate_hover(self, target: float) -> None:
        if should_reduce_motion():
            self._anim.stop()
            self._hover_t = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._hover_t)
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        t = self._tokens
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        hl_t = max(self._hover_t, 1.0 if self.hasFocus() else 0.0)

        bg_base = QColor(t["bg_surface"])
        bg_hover = QColor(t["error_subtle"] if self._danger else t["accent_subtle"])
        if hl_t > 0.01:
            fill = QColor(
                int(bg_base.red() + (bg_hover.red() - bg_base.red()) * hl_t),
                int(bg_base.green() + (bg_hover.green() - bg_base.green()) * hl_t),
                int(bg_base.blue() + (bg_hover.blue() - bg_base.blue()) * hl_t),
            )
            path = QPainterPath()
            path.addRoundedRect(rect, 9.0, 9.0)
            p.fillPath(path, fill)

            if self.hasFocus():
                ring_c = QColor(t["error"] if self._danger else t["border_focus"])
                p.setPen(QPen(ring_c, 1.4))
                p.drawPath(path)

        icon_box_x = 10.0 + (2.0 * hl_t)
        icon_box_y = (self.height() - 28.0) / 2.0
        badge_rect = QRectF(icon_box_x, icon_box_y, 28.0, 28.0)
        badge_bg = QColor(t["bg_surface2"])
        if hl_t > 0.01:
            tint = QColor(t["error"] if self._danger else t["accent"])
            badge_bg = QColor(
                int(badge_bg.red() + (tint.red() - badge_bg.red()) * (0.18 * hl_t)),
                int(badge_bg.green() + (tint.green() - badge_bg.green()) * (0.18 * hl_t)),
                int(badge_bg.blue() + (tint.blue() - badge_bg.blue()) * (0.18 * hl_t)),
            )
        p.setPen(Qt.NoPen)
        p.setBrush(badge_bg)
        p.drawRoundedRect(badge_rect, 7.0, 7.0)

        rest_icon = QColor(t["text_secondary"])
        active_icon = QColor(t["error"] if self._danger else t["accent_text"])
        icon_col = QColor(
            int(rest_icon.red() + (active_icon.red() - rest_icon.red()) * hl_t),
            int(rest_icon.green() + (active_icon.green() - rest_icon.green()) * hl_t),
            int(rest_icon.blue() + (active_icon.blue() - rest_icon.blue()) * hl_t),
        )
        draw_vector_icon(p, self._icon_name, icon_box_x + 5.0, icon_box_y + 5.0, 18.0, icon_col)

        title_col = QColor(t["error"] if (self._danger and hl_t > 0.35) else t["text_primary"])
        sub_col = QColor(t["text_secondary"])

        text_x = int(icon_box_x + 38.0)
        right_reserve = 56
        text_w = max(80, self.width() - text_x - right_reserve)

        title_font = QFont(".AppleSystemUIFont", 12, QFont.Weight.DemiBold)
        title_txt = QFontMetrics(title_font).elidedText(self._title, Qt.ElideRight, text_w)
        p.setFont(title_font)
        p.setPen(title_col)
        p.drawText(QRect(text_x, 6, text_w, 17), Qt.AlignLeft | Qt.AlignVCenter, title_txt)

        sub_font = QFont(".AppleSystemUIFont", 10, QFont.Weight.Normal)
        sub_txt = QFontMetrics(sub_font).elidedText(self._subtitle, Qt.ElideRight, text_w)
        p.setFont(sub_font)
        p.setPen(sub_col)
        p.drawText(QRect(text_x, 24, text_w, 15), Qt.AlignLeft | Qt.AlignVCenter, sub_txt)

        if self._shortcut:
            key_rect = QRectF(self.width() - 46.0, (self.height() - 22.0) / 2.0, 36.0, 22.0)
            p.setBrush(QColor(t["bg_surface2"]))
            p.setPen(QPen(QColor(t["border"]), 1.0))
            p.drawRoundedRect(key_rect, 5.5, 5.5)
            p.setFont(QFont(".AppleSystemUIFont", 11, QFont.Weight.Medium))
            p.setPen(QColor(t["text_secondary"]))
            p.drawText(key_rect, Qt.AlignCenter, self._shortcut)

        p.end()


class TrayPopover(QWidget):
    """Animated translucent menu-bar card for FileTool."""

    open_requested = Signal()
    preferences_requested = Signal()
    dependencies_requested = Signal()
    quit_requested = Signal()
    wheel_toggled = Signal(bool)
    files_dropped = Signal(list)

    def __init__(self, dark_mode: bool = False, accent_key: str = "amber", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        self._dark_mode = dark_mode
        self._accent_key = accent_key
        self._wheel_enabled = True
        self._drag_hovering = False
        self._last_hide_ts: float = 0.0
        self._action_buttons: List[_PopoverActionButton] = []

        self._open_anim = QVariantAnimation(self)
        self._open_anim.setDuration(150)
        self._open_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._open_anim.valueChanged.connect(self._on_open_anim)

        self._anchor_pos = QPoint(0, 0)
        self._init_ui()
        self.set_theme(dark_mode, accent_key)

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW_MARGIN, _SHADOW_MARGIN - 4, _SHADOW_MARGIN, _SHADOW_MARGIN + 2)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("trayCard")
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(12, 12, 12, 10)
        card_lay.setSpacing(8)

        # Header lockup
        header = QHBoxLayout()
        header.setSpacing(10)

        self.logo = LogoWidget(size=32)
        self.logo.clicked.connect(self._trigger_open)
        header.addWidget(self.logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self.title_lbl = QLabel("FileTool")
        self.title_lbl.setObjectName("trayTitle")
        self.subtitle_lbl = QLabel("Offline · Ready on macOS")
        self.subtitle_lbl.setObjectName("traySubtitle")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.subtitle_lbl)
        header.addLayout(title_col, stretch=1)

        self.wheel_pill = QPushButton("Wheel On")
        self.wheel_pill.setObjectName("trayWheelPill")
        self.wheel_pill.setCursor(Qt.PointingHandCursor)
        self.wheel_pill.clicked.connect(self._on_toggle_wheel)
        header.addWidget(self.wheel_pill)

        card_lay.addLayout(header)

        # Active queue progress strip (hidden when idle)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)
        card_lay.addWidget(self.progress_bar)

        # Quick drop / live trigger strip
        self.drop_card = QFrame()
        self.drop_card.setObjectName("trayTriggerCard")
        drop_lay = QVBoxLayout(self.drop_card)
        drop_lay.setContentsMargins(10, 8, 10, 8)
        drop_lay.setSpacing(6)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(5)
        self._trigger_chips: List[QLabel] = []
        for default_txt in ("⇧ Convert", "⌘ Tools", "⌃ Actions"):
            chip = QLabel(default_txt)
            chip.setObjectName("trayTriggerChip")
            chip.setAlignment(Qt.AlignCenter)
            chips_row.addWidget(chip, stretch=1)
            self._trigger_chips.append(chip)
        drop_lay.addLayout(chips_row)

        self.drop_hint_lbl = QLabel("Drag files in Finder + tap key, or drop files here")
        self.drop_hint_lbl.setObjectName("trayDropHint")
        self.drop_hint_lbl.setWordWrap(True)
        drop_lay.addWidget(self.drop_hint_lbl)
        card_lay.addWidget(self.drop_card)

        sep1 = QFrame()
        sep1.setObjectName("traySep")
        sep1.setFixedHeight(1)
        card_lay.addWidget(sep1)

        self.btn_open = _PopoverActionButton(
            "window",
            "Open FileTool",
            "Queue, history & options",
            "⌘O",
        )
        self.btn_open.clicked.connect(self._trigger_open)

        self.btn_prefs = _PopoverActionButton(
            "sliders",
            "Settings & Triggers",
            "Themes, keys & save folder",
            "⌘,",
        )
        self.btn_prefs.clicked.connect(self._trigger_prefs)

        self.btn_deps = _PopoverActionButton(
            "health",
            "Local Engines",
            "FFmpeg, Pandoc, LibreOffice & more",
            "⌘D",
        )
        self.btn_deps.clicked.connect(self._trigger_deps)

        self.btn_quit = _PopoverActionButton(
            "power",
            "Quit FileTool",
            "Stop background drag monitor",
            "⌘Q",
            danger=True,
        )
        self.btn_quit.clicked.connect(self._trigger_quit)

        for btn in (self.btn_open, self.btn_prefs, self.btn_deps):
            self._action_buttons.append(btn)
            card_lay.addWidget(btn)

        sep2 = QFrame()
        sep2.setObjectName("traySep")
        sep2.setFixedHeight(1)
        card_lay.addWidget(sep2)

        self._action_buttons.append(self.btn_quit)
        card_lay.addWidget(self.btn_quit)

        outer.addWidget(self.card)
        self.setFixedWidth(348)

    def set_theme(self, dark_mode: bool, accent_key: str) -> None:
        self._dark_mode = dark_mode
        self._accent_key = accent_key
        t = get_tokens(dark_mode, accent_key=accent_key)
        self.logo.set_accent_color(t["accent"])
        for btn in self._action_buttons:
            btn.set_tokens(t)

        pill_bg = t["accent_subtle"] if self._wheel_enabled else t["bg_surface2"]
        pill_fg = t["accent_text"] if self._wheel_enabled else t["text_secondary"]
        pill_border = t["accent"] if self._wheel_enabled else t["border"]
        drop_border = t["accent"] if self._drag_hovering else t["border"]
        drop_bg = t["accent_subtle"] if self._drag_hovering else t["bg_surface2"]

        self.setStyleSheet(
            f"""
            QFrame#trayCard {{
                background-color: {t['bg_surface']};
                border: 1px solid {t['border_strong']};
                border-radius: 14px;
            }}
            QLabel#trayTitle {{
                color: {t['text_primary']};
                font-size: 15px;
                font-weight: 700;
                letter-spacing: -0.3px;
            }}
            QLabel#traySubtitle {{
                color: {t['text_secondary']};
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton#trayWheelPill {{
                background-color: {pill_bg};
                color: {pill_fg};
                border: 1px solid {pill_border};
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QFrame#trayTriggerCard {{
                background-color: {drop_bg};
                border: 1px dashed {drop_border};
                border-radius: 10px;
            }}
            QLabel#trayTriggerChip {{
                background-color: {t['bg_surface']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 3px 6px;
                font-size: 10.5px;
                font-weight: 600;
            }}
            QLabel#trayDropHint {{
                color: {t['text_secondary']};
                font-size: 10.5px;
            }}
            QFrame#traySep {{
                background-color: {t['border']};
                border: none;
            }}
            QProgressBar {{
                background-color: {t['progress_track']};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {t['accent']};
                border-radius: 2px;
            }}
            """
        )
        self.update()

    def update_state(
        self,
        wheel_enabled: bool,
        key_mappings: Optional[Dict[str, str]] = None,
        active_jobs: int = 0,
        progress_pct: Optional[int] = None,
        tools_summary: Optional[str] = None,
    ) -> None:
        """Sync live wheel triggers, queue progress, and local tool count."""
        self._wheel_enabled = wheel_enabled
        self.wheel_pill.setText("Wheel On" if wheel_enabled else "Paused")

        if key_mappings:
            role_to_key = {role: key for key, role in key_mappings.items()}
            chips = [
                _format_trigger_chip(role_to_key.get("convert", "Shift"), "Convert"),
                _format_trigger_chip(role_to_key.get("tools", "Command"), "Tools"),
                _format_trigger_chip(role_to_key.get("actions", "Control"), "Actions"),
            ]
            for label_w, txt in zip(self._trigger_chips, chips):
                label_w.setText(txt)

        if active_jobs > 0 and progress_pct is not None:
            noun = "file" if active_jobs == 1 else "files"
            self.subtitle_lbl.setText(f"Converting {active_jobs} {noun} · {progress_pct}%")
            self.progress_bar.setValue(max(0, min(100, progress_pct)))
            self.progress_bar.setVisible(True)
            self.logo.set_active_progress(True, progress_pct)
        else:
            state_txt = "Ready" if wheel_enabled else "Wheel paused"
            self.subtitle_lbl.setText(f"Offline · {state_txt}")
            self.progress_bar.setVisible(False)
            self.logo.set_active_progress(False, None)

        if tools_summary:
            self.btn_deps.set_subtitle(tools_summary)

        self.set_theme(self._dark_mode, self._accent_key)

    def was_just_hidden(self, threshold_sec: float = 0.22) -> bool:
        """Return True if the popup just dismissed (for clean tray-click toggling)."""
        return (time.monotonic() - self._last_hide_ts) < threshold_sec

    def show_at(self, anchor_rect: QRect) -> None:
        """Position and smoothly reveal the popover below the menu-bar icon."""
        self.adjustSize()
        pw = self.width()
        ph = self.height()

        if anchor_rect.isNull() or anchor_rect.width() == 0:
            screen = QGuiApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else QRect(0, 32, 1440, 900)
            cx = avail.right() - pw // 2 - 16
            top_y = avail.top() + 4
        else:
            screen = (
                QGuiApplication.screenAt(anchor_rect.center())
                or QGuiApplication.primaryScreen()
            )
            avail = screen.availableGeometry() if screen else QRect(0, 32, 1440, 900)
            cx = anchor_rect.center().x()
            top_y = max(anchor_rect.bottom() + 4, avail.top() + 2)

        x = max(avail.left() + 4, min(cx - pw // 2, avail.right() - pw - 4))
        y = max(avail.top() + 2, min(top_y, avail.bottom() - ph - 4))
        self._anchor_pos = QPoint(x, y)

        if should_reduce_motion():
            self.move(self._anchor_pos)
            self.setWindowOpacity(1.0)
            self.show()
            self.raise_()
            self.activateWindow()
            return

        self.setWindowOpacity(0.0)
        self.move(QPoint(x, max(0, y - 6)))
        self.show()
        self.raise_()
        self.activateWindow()

        self._open_anim.stop()
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)
        self._open_anim.start()
        self.logo.spin_once(90.0, 360)

    def _on_open_anim(self, val) -> None:
        t = float(val)
        self.setWindowOpacity(t)
        offset_y = int(round((1.0 - t) * -6.0))
        self.move(self._anchor_pos.x(), max(0, self._anchor_pos.y() + offset_y))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.Antialiasing)
        card_r = self.card.geometry()
        if not card_r.isNull():
            for expand, alpha in ((8, 12), (4, 22), (2, 32)):
                sr = QRectF(card_r).adjusted(-expand * 0.4, expand * 0.3, expand * 0.4, expand * 0.7)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, alpha if self._dark_mode else int(alpha * 0.7)))
                p.drawRoundedRect(sr, 16.0, 16.0)
        p.end()

    def hideEvent(self, event) -> None:
        self._last_hide_ts = time.monotonic()
        self._drag_hovering = False
        super().hideEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Escape:
            self.hide()
            return
        if key in (Qt.Key_Down, Qt.Key_Up) and self._action_buttons:
            focused = self.focusWidget()
            idx = self._action_buttons.index(focused) if focused in self._action_buttons else -1
            step = 1 if key == Qt.Key_Down else -1
            next_idx = (idx + step) % len(self._action_buttons)
            self._action_buttons[next_idx].setFocus()
            return
        if key == Qt.Key_O and (mods & Qt.ControlModifier or mods & Qt.MetaModifier):
            self._trigger_open()
            return
        if key == Qt.Key_Comma and (mods & Qt.ControlModifier or mods & Qt.MetaModifier):
            self._trigger_prefs()
            return
        if key == Qt.Key_D and (mods & Qt.ControlModifier or mods & Qt.MetaModifier):
            self._trigger_deps()
            return
        if key == Qt.Key_Q and (mods & Qt.ControlModifier or mods & Qt.MetaModifier):
            self._trigger_quit()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self._drag_hovering = True
            self.set_theme(self._dark_mode, self._accent_key)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._drag_hovering = False
        self.set_theme(self._dark_mode, self._accent_key)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._drag_hovering = False
        self.set_theme(self._dark_mode, self._accent_key)
        if event.mimeData().hasUrls():
            paths: List[Path] = collect_paths_from_urls(event.mimeData().urls())
            if paths:
                event.acceptProposedAction()
                self.hide()
                self.files_dropped.emit(paths)
                return
        event.ignore()

    def _on_toggle_wheel(self) -> None:
        self._wheel_enabled = not self._wheel_enabled
        self.wheel_pill.setText("Wheel On" if self._wheel_enabled else "Paused")
        self.set_theme(self._dark_mode, self._accent_key)
        self.wheel_toggled.emit(self._wheel_enabled)

    def _trigger_open(self) -> None:
        self.hide()
        self.open_requested.emit()

    def _trigger_prefs(self) -> None:
        self.hide()
        self.preferences_requested.emit()

    def _trigger_deps(self) -> None:
        self.hide()
        self.dependencies_requested.emit()

    def _trigger_quit(self) -> None:
        self.hide()
        self.quit_requested.emit()
