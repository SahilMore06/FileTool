"""Options drawer/panel for image quality, video CRF/resolution, audio bitrate, and PDF DPI."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class OptionsPanel(QFrame):
    """Configuration panel controlling conversion parameters."""

    options_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _add_row(self, grid: QGridLayout, row_idx: int, label_text: str, field: QWidget | QLayout) -> None:
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: 500;")
        grid.addWidget(label, row_idx, 0)
        if isinstance(field, QLayout):
            grid.addLayout(field, row_idx, 1)
        else:
            grid.addWidget(field, row_idx, 1)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(14)

        title = QLabel("Conversion Options")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        main_layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)

        img_box = QHBoxLayout()
        self.img_slider = QSlider(Qt.Horizontal)
        self.img_slider.setRange(1, 100)
        self.img_slider.setValue(85)
        self.img_val_lbl = QLabel("85%")
        self.img_val_lbl.setFixedWidth(36)
        self.img_slider.valueChanged.connect(lambda v: self.img_val_lbl.setText(f"{v}%"))
        self.img_slider.valueChanged.connect(self._emit_change)
        img_box.addWidget(self.img_slider)
        img_box.addWidget(self.img_val_lbl)
        self._add_row(grid, 0, "Image Quality:", img_box)

        crf_box = QHBoxLayout()
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_val_lbl = QLabel("23 (Good)")
        self.crf_val_lbl.setFixedWidth(70)
        self.crf_slider.valueChanged.connect(self._update_crf_label)
        self.crf_slider.valueChanged.connect(self._emit_change)
        crf_box.addWidget(self.crf_slider)
        crf_box.addWidget(self.crf_val_lbl)
        self._add_row(grid, 1, "Video CRF (Quality):", crf_box)

        self.res_combo = QComboBox()
        self.res_combo.addItems(["original", "1080p", "720p", "480p"])
        self.res_combo.setCurrentText("original")
        self.res_combo.currentTextChanged.connect(self._emit_change)
        self._add_row(grid, 2, "Video Resolution:", self.res_combo)

        self.audio_combo = QComboBox()
        self.audio_combo.addItems(["128k", "192k", "256k", "320k"])
        self.audio_combo.setCurrentText("192k")
        self.audio_combo.currentTextChanged.connect(self._emit_change)
        self._add_row(grid, 3, "Audio Bitrate:", self.audio_combo)

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItem("300 DPI (High Fidelity)", 300)
        self.dpi_combo.addItem("150 DPI (Balanced)", 150)
        self.dpi_combo.addItem("72 DPI (Web Draft)", 72)
        self.dpi_combo.addItem("600 DPI (Ultra Print)", 600)
        self.dpi_combo.currentIndexChanged.connect(self._emit_change)
        self._add_row(grid, 4, "PDF & Slide DPI:", self.dpi_combo)

        main_layout.addLayout(grid)
        main_layout.addStretch()

    def _update_crf_label(self, val: int) -> None:
        qual = "High" if val <= 18 else ("Good" if val <= 24 else "Draft")
        self.crf_val_lbl.setText(f"{val} ({qual})")

    def get_options(self) -> Dict[str, Any]:
        return {
            "quality": self.img_slider.value(),
            "crf": self.crf_slider.value(),
            "resolution": self.res_combo.currentText(),
            "bitrate": self.audio_combo.currentText(),
            "audio_bitrate": self.audio_combo.currentText(),
            "dpi": self.dpi_combo.currentData(),
        }

    def _emit_change(self) -> None:
        self.options_changed.emit(self.get_options())
