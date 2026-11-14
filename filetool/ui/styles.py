"""Centralized color tokens and QSS stylesheet builder for light and dark themes."""

from __future__ import annotations

from typing import Optional

ACCENT_PRESETS = {
    "amber": {
        "label": "Tangerine",
        "accent": "#F28A32",
        "accent_hover": "#F09B4E",
        "accent_pressed": "#D97520",
        "accent_fg": "#202124",
        "accent_subtle_light": "#FEF2E7",
        "accent_subtle_dark": "#2A1E0E",
        "accent_text_light": "#B84718",
        "accent_text_dark": "#F09B4E",
    },
    "ocean": {
        "label": "Ocean",
        "accent": "#2F6FED",
        "accent_hover": "#245CD0",
        "accent_pressed": "#2258C7",
        "accent_fg": "#FFFFFF",
        "accent_subtle_light": "#EDF3FE",
        "accent_subtle_dark": "#142038",
        "accent_text_light": "#1E52BA",
        "accent_text_dark": "#6E9EF7",
    },
    "emerald": {
        "label": "Emerald",
        "accent": "#258055",
        "accent_hover": "#1E6B47",
        "accent_pressed": "#185739",
        "accent_fg": "#FFFFFF",
        "accent_subtle_light": "#E8F5EF",
        "accent_subtle_dark": "#0D2218",
        "accent_text_light": "#1D6846",
        "accent_text_dark": "#4CC38A",
    },
    "slate": {
        "label": "Graphite",
        "accent": "#4F5D75",
        "accent_hover": "#62718C",
        "accent_pressed": "#3D495C",
        "accent_fg": "#FFFFFF",
        "accent_subtle_light": "#ECEFF4",
        "accent_subtle_dark": "#1D222B",
        "accent_text_light": "#394457",
        "accent_text_dark": "#93A2BC",
    },
}

TOKENS_LIGHT = {
    "bg_main": "#F3F2EF",
    "bg_surface": "#FFFFFF",
    "bg_surface_hover": "#EDECEA",
    "bg_surface2": "#EAE8E3",
    "bg_input": "#FFFFFF",
    "tooltip_bg": "#202124",
    "tooltip_text": "#E8E6E1",
    "tooltip_border": "#2E3033",
    "text_primary": "#202124",
    "text_secondary": "#5E5F5B",
    "text_muted": "#605F5A",
    "text_inverse": "#FFFFFF",
    "border": "#E1DFD9",
    "border_strong": "#C8C6C0",
    "border_focus": "#F28A32",
    "accent": "#F28A32",
    "accent_hover": "#F09B4E",
    "accent_pressed": "#D97520",
    "accent_fg": "#202124",
    "accent_subtle": "#FEF2E7",
    "accent_text": "#B84718",
    "success": "#1C6E48",
    "success_subtle": "#E8F5EF",
    "error": "#AC3232",
    "error_subtle": "#FAE8E8",
    "warning": "#8F5907",
    "warning_subtle": "#FEF5E5",
    "progress_track": "#E8E6E1",
    "progress_fill": "#F28A32",
    "shadow_color": "rgba(32, 33, 36, 0.10)",
    "shadow_strong": "rgba(32, 33, 36, 0.18)",
}

TOKENS_DARK = {
    "bg_main": "#171819",
    "bg_surface": "#202123",
    "bg_surface_hover": "#2A2B2E",
    "bg_surface2": "#252628",
    "bg_input": "#252628",
    "tooltip_bg": "#111214",
    "tooltip_text": "#D8D6D1",
    "tooltip_border": "#1A1B1E",
    "text_primary": "#E8E6E1",
    "text_secondary": "#A19F98",
    "text_muted": "#92908A",
    "text_inverse": "#202124",
    "border": "#2E2F32",
    "border_strong": "#3A3B3E",
    "border_focus": "#F28A32",
    "accent": "#F28A32",
    "accent_hover": "#F09B4E",
    "accent_pressed": "#D97520",
    "accent_fg": "#202124",
    "accent_subtle": "#2A1E0E",
    "accent_text": "#F09B4E",
    "success": "#2DA368",
    "success_subtle": "#0D2218",
    "error": "#E06E6E",
    "error_subtle": "#2A0E0E",
    "warning": "#D9953A",
    "warning_subtle": "#2A1D09",
    "progress_track": "#2E2F32",
    "progress_fill": "#F28A32",
    "shadow_color": "rgba(0, 0, 0, 0.30)",
    "shadow_strong": "rgba(0, 0, 0, 0.50)",
}


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.x relative luminance for a `#RRGGBB` hex string."""
    h = hex_color.lstrip("#")
    lin = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255.0
        lin.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Compute WCAG 2.x contrast ratio between two `#RRGGBB` hex colors."""
    l1 = relative_luminance(fg_hex)
    l2 = relative_luminance(bg_hex)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def get_tokens(dark_mode: bool = False, accent_key: Optional[str] = None) -> dict:
    """Resolve theme tokens with the selected accent preset applied."""
    base = dict(TOKENS_DARK if dark_mode else TOKENS_LIGHT)
    if accent_key and accent_key in ACCENT_PRESETS:
        preset = ACCENT_PRESETS[accent_key]
        base["accent"] = preset["accent"]
        base["accent_hover"] = preset["accent_hover"]
        base["accent_pressed"] = preset["accent_pressed"]
        base["accent_fg"] = preset.get("accent_fg", "#FFFFFF")
        base["border_focus"] = preset["accent"]
        base["progress_fill"] = preset["accent"]
        base["accent_subtle"] = (
            preset["accent_subtle_dark"] if dark_mode else preset["accent_subtle_light"]
        )
        base["accent_text"] = (
            preset["accent_text_dark"] if dark_mode else preset["accent_text_light"]
        )
    return base


def get_stylesheet(dark_mode: bool = False, accent_key: Optional[str] = None) -> str:
    """Build the application QSS stylesheet for the given theme and accent."""
    return _build_stylesheet(get_tokens(dark_mode, accent_key=accent_key))


def _build_stylesheet(t: dict) -> str:
    return f"""
QMainWindow {{
    background-color: {t['bg_main']};
    color: {t['text_primary']};
    font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

QWidget {{
    color: {t['text_primary']};
    font-family: ".AppleSystemUIFont", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

QFrame#dropzone {{
    background-color: {t['bg_surface']};
    border: 2px dashed {t['border_strong']};
    border-radius: 16px;
}}

QFrame#dropzone:hover {{
    border-color: {t['accent']};
    background-color: {t['accent_subtle']};
}}

QLabel#dropTitle {{
    font-size: 16px;
    font-weight: 600;
    color: {t['text_primary']};
}}

QLabel#dropSubtitle {{
    font-size: 12px;
    color: {t['text_secondary']};
}}

QFrame#jobCard {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 12px;
    padding: 4px;
}}

QFrame#jobCard:hover {{
    border-color: {t['border_focus']};
    background-color: {t['bg_surface_hover']};
}}

QLabel#badge {{
    background-color: {t['accent_subtle']};
    color: {t['accent_text']};
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
}}

QLabel#badgeSuccess {{
    background-color: {t['success_subtle']};
    color: {t['success']};
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
}}

QLabel#badgeError {{
    background-color: {t['error_subtle']};
    color: {t['error']};
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
}}

QPushButton {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    color: {t['text_primary']};
}}

QPushButton:hover {{
    background-color: {t['bg_surface_hover']};
    border-color: {t['border_strong']};
}}

QPushButton:pressed {{
    background-color: {t['bg_surface2']};
}}

QPushButton#primaryButton {{
    background-color: {t['accent']};
    border: 1px solid {t['accent']};
    color: {t['accent_fg']};
    font-weight: 600;
    border-radius: 8px;
    padding: 7px 18px;
}}

QPushButton#primaryButton:hover {{
    background-color: {t['accent_hover']};
    border-color: {t['accent_hover']};
}}

QPushButton#primaryButton:pressed {{
    background-color: {t['accent_pressed']};
    border-color: {t['accent_pressed']};
}}

QPushButton#primaryButton:disabled {{
    background-color: {t['bg_surface2']};
    border-color: {t['border']};
    color: {t['text_muted']};
}}

QPushButton#secondaryButton {{
    background-color: {t['bg_surface2']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#secondaryButton:hover {{
    background-color: {t['bg_surface_hover']};
    border-color: {t['border_strong']};
}}

QPushButton#secondaryButton:disabled {{
    color: {t['text_muted']};
    background-color: {t['bg_surface2']};
    border-color: {t['border']};
}}

QPushButton#iconButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 7px;
    padding: 0px;
    font-size: 13px;
    font-weight: 500;
    color: {t['text_secondary']};
}}

QPushButton#iconButton:hover {{
    background-color: {t['bg_surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text_primary']};
}}

QPushButton#iconButton:pressed {{
    background-color: {t['bg_surface2']};
}}

QComboBox {{
    background-color: {t['bg_input']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 6px 12px;
    padding-right: 28px;
    min-width: 90px;
    font-size: 13px;
    font-weight: 500;
    color: {t['text_primary']};
}}

QComboBox:hover {{
    border-color: {t['border_strong']};
}}

QComboBox:focus {{
    border: 1.5px solid {t['accent']};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['text_secondary']};
    width: 0px;
    height: 0px;
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 6px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_fg']};
    color: {t['text_primary']};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 6px 12px;
    border-radius: 6px;
    color: {t['text_primary']};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {t['accent']};
    color: {t['accent_fg']};
}}

QProgressBar {{
    background-color: {t['progress_track']};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {t['progress_fill']};
    border-radius: 4px;
}}

QLineEdit {{
    background-color: {t['bg_input']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 7px 12px;
    color: {t['text_primary']};
    font-size: 13px;
    selection-background-color: {t['accent']};
}}

QLineEdit:focus {{
    border-color: {t['border_focus']};
}}

QTextEdit {{
    background-color: {t['bg_input']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 8px;
    color: {t['text_primary']};
    font-size: 13px;
    selection-background-color: {t['accent']};
}}

QScrollArea,
QScrollArea > QWidget,
QScrollArea > QWidget > QWidget,
QWidget#scrollBody {{
    border: none;
    background-color: {t['bg_main']};
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 7px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {t['border']};
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t['border_strong']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 7px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: {t['border']};
    min-width: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {t['border_strong']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QTableWidget {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    gridline-color: {t['border']};
    color: {t['text_primary']};
    font-size: 12px;
    alternate-background-color: {t['bg_main']};
    selection-background-color: {t['accent_subtle']};
    selection-color: {t['text_primary']};
    outline: none;
}}

QTableWidget::item {{
    padding: 6px 10px;
}}

QHeaderView::section {{
    background-color: {t['bg_surface2']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    color: {t['text_secondary']};
    letter-spacing: 0.3px;
}}

QStatusBar {{
    background-color: {t['bg_surface']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
    color: {t['text_secondary']};
    padding: 2px 12px;
}}

QMenuBar {{
    background-color: {t['bg_surface']};
    border-bottom: 1px solid {t['border']};
    padding: 2px 8px;
    color: {t['text_primary']};
    font-size: 13px;
}}

QMenuBar::item:selected {{
    background-color: {t['bg_surface_hover']};
    border-radius: 5px;
    color: {t['text_primary']};
}}

QMenu {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 6px;
    color: {t['text_primary']};
}}

QMenu::item {{
    padding: 6px 20px;
    border-radius: 6px;
    font-size: 13px;
}}

QMenu::item:selected {{
    background-color: {t['accent']};
    color: {t['accent_fg']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {t['border']};
    margin: 4px 8px;
}}

QSlider::groove:horizontal {{
    border: none;
    height: 4px;
    background-color: {t['progress_track']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {t['accent']};
    border: none;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background-color: {t['accent']};
    border-radius: 2px;
}}

QToolTip {{
    background-color: {t['tooltip_bg']};
    color: {t['tooltip_text']};
    border: 1px solid {t['tooltip_border']};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}}

QFrame#cardPanel, QWidget#cardPanel {{
    background-color: {t['bg_surface']};
    border: 1px solid {t['border']};
    border-radius: 12px;
}}

QLabel#panelHeading {{
    color: {t['text_primary']};
    font-size: 13px;
    font-weight: 700;
}}

QLabel#jobFilename {{
    color: {t['text_primary']};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#mutedMeta {{
    color: {t['text_secondary']};
    font-size: 11px;
}}

QLabel#statusRunning {{
    color: {t['accent_text']};
    font-size: 11px;
    font-weight: 500;
}}

QLabel#statusSuccess {{
    color: {t['success']};
    font-size: 11px;
    font-weight: 600;
}}

QLabel#statusError, QLabel#errorTitle {{
    color: {t['error']};
    font-size: 11px;
    font-weight: 600;
}}

QLabel#errorTitle {{
    font-size: 14px;
}}

QPushButton#dangerLink {{
    color: {t['error']};
    font-weight: 600;
}}

QLabel#validationWarning {{
    background-color: {t['warning_subtle']};
    color: {t['warning']};
    border: 1px solid {t['warning']};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 500;
}}

QLabel#pillTag {{
    background-color: {t['bg_surface2']};
    color: {t['text_secondary']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 600;
}}

QWidget#toolbarBar {{
    background-color: {t['bg_surface']};
    border-bottom: 1px solid {t['border']};
}}

QLabel#appTitle {{
    color: {t['text_primary']};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.4px;
}}

QLabel#brandStatusPill {{
    background-color: {t['bg_surface2']};
    color: {t['text_secondary']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 10.5px;
    font-weight: 600;
}}

QLabel#brandStatusPill[state="active"] {{
    background-color: {t['accent_subtle']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
}}

QLabel#brandStatusPill[state="done"] {{
    background-color: {t['success_subtle']};
    color: {t['success']};
    border: 1px solid {t['success']};
}}

QFrame#tabGroup {{
    background-color: {t['bg_surface2']};
    border: 1px solid {t['border']};
    border-radius: 9px;
}}

QPushButton#tabButton {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: none;
    border-radius: 7px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#tabButton:hover {{
    color: {t['text_primary']};
}}

QPushButton#tabButton[active="true"] {{
    background-color: {t['bg_surface']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    font-weight: 600;
}}

QWidget#actionFooter {{
    background-color: {t['bg_surface']};
    border-top: 1px solid {t['border']};
}}

QPushButton#filterPill {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#filterPill:hover {{
    background-color: {t['bg_surface_hover']};
    color: {t['text_primary']};
}}

QPushButton#filterPill[active="true"] {{
    background-color: {t['accent_subtle']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    font-weight: 600;
}}

QComboBox[invalid="true"], QLineEdit[invalid="true"] {{
    border: 1.5px solid {t['error']};
    background-color: {t['error_subtle']};
}}

QPushButton:focus-visible, QComboBox:focus-visible {{
    outline: none;
    border: 1.5px solid {t['border_focus']};
}}
"""
