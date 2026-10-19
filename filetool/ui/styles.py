"""Tangerine-inspired macOS native stylesheets for light and dark modes."""

from __future__ import annotations


def get_stylesheet(dark_mode: bool = True) -> str:
    """Return polished QSS styling adapting to macOS Dark or Light mode."""
    if dark_mode:
        bg_main = "#1C1C1E"
        bg_card = "#2C2C2E"
        bg_card_hover = "#3A3A3C"
        bg_input = "#323236"
        border = "#3A3A3C"
        border_focus = "#FF8C1A"
        text_primary = "#F2F2F7"
        text_secondary = "#8E8E93"
        accent = "#FF7A00"
        accent_hover = "#FF9224"
        accent_pressed = "#E06800"
        progress_bg = "#3A3A3C"
        badge_bg = "#38383A"
        badge_text = "#FF9D3B"
    else:
        bg_main = "#F5F5F7"
        bg_card = "#FFFFFF"
        bg_card_hover = "#F2F2F7"
        bg_input = "#FFFFFF"
        border = "#D1D1D6"
        border_focus = "#FF7A00"
        text_primary = "#1C1C1E"
        text_secondary = "#6C6C70"
        accent = "#FF7A00"
        accent_hover = "#FF9224"
        accent_pressed = "#E06800"
        progress_bg = "#E5E5EA"
        badge_bg = "#FFF0E6"
        badge_text = "#E06800"

    return f"""
    QMainWindow {{
        background-color: {bg_main};
        color: {text_primary};
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    }}

    QWidget {{
        color: {text_primary};
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    }}

    QFrame#dropzone {{
        background-color: {bg_card};
        border: 2px dashed {border};
        border-radius: 14px;
    }}

    QFrame#dropzone:hover {{
        border: 2px dashed {accent};
        background-color: {bg_card_hover};
    }}

    QFrame#jobCard {{
        background-color: {bg_card};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 8px;
    }}

    QFrame#jobCard:hover {{
        border-color: {accent};
    }}

    QLabel#dropTitle {{
        font-size: 18px;
        font-weight: 600;
        color: {text_primary};
    }}

    QLabel#dropSubtitle {{
        font-size: 13px;
        color: {text_secondary};
    }}

    QLabel#badge {{
        background-color: {badge_bg};
        color: {badge_text};
        font-size: 11px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 6px;
    }}

    QPushButton {{
        background-color: {bg_card};
        border: 1px solid {border};
        border-radius: 7px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        color: {text_primary};
    }}

    QPushButton:hover {{
        background-color: {bg_card_hover};
        border-color: {text_secondary};
    }}

    QPushButton#primaryButton {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #FFFFFF;
        font-weight: 600;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {accent_hover};
        border-color: {accent_hover};
    }}

    QPushButton#primaryButton:pressed {{
        background-color: {accent_pressed};
        border-color: {accent_pressed};
    }}

    QPushButton#iconButton {{
        border: none;
        background: transparent;
        padding: 4px;
        border-radius: 5px;
    }}

    QPushButton#iconButton:hover {{
        background-color: {bg_card_hover};
    }}

    QComboBox {{
        background-color: {bg_input};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 5px 12px;
        padding-right: 28px;
        min-width: 90px;
        font-size: 13px;
        font-weight: 500;
        color: {text_primary};
    }}

    QComboBox:hover {{
        background-color: {bg_card_hover};
        border-color: {text_secondary};
    }}

    QComboBox:focus {{
        border: 1.5px solid {accent};
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
        border-top: 5px solid {text_secondary};
        width: 0px;
        height: 0px;
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {bg_card};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 6px;
        selection-background-color: {accent};
        selection-color: #FFFFFF;
        color: {text_primary};
        outline: none;
    }}

    QComboBox QAbstractItemView::item {{
        min-height: 28px;
        padding: 6px 12px;
        border-radius: 6px;
        color: {text_primary};
    }}

    QComboBox QAbstractItemView::item:selected {{
        background-color: {accent};
        color: #FFFFFF;
    }}

    QComboBox#bulkCombo {{
        background-color: {bg_card};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 6px 14px;
        padding-right: 32px;
        min-width: 220px;
        font-weight: 500;
        font-size: 13px;
        color: {text_primary};
    }}

    QComboBox#bulkCombo:hover {{
        background-color: {bg_card_hover};
        border-color: {accent};
    }}

    QComboBox#bulkCombo:focus {{
        border: 1.5px solid {accent};
    }}

    QProgressBar {{
        background-color: {progress_bg};
        border: none;
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {accent};
        border-radius: 4px;
    }}

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {border};
        min-height: 20px;
        border-radius: 4px;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QTabWidget::pane {{
        border: 1px solid {border};
        background-color: {bg_card};
        border-radius: 8px;
    }}

    QTabBar::tab {{
        background: transparent;
        border: none;
        padding: 8px 16px;
        font-size: 13px;
        color: {text_secondary};
    }}

    QTabBar::tab:selected {{
        color: {accent};
        font-weight: 600;
        border-bottom: 2px solid {accent};
    }}

    QStatusBar {{
        background-color: {bg_main};
        border-top: 1px solid {border};
        font-size: 12px;
        color: {text_secondary};
    }}
    """
