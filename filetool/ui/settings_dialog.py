"""Settings and preferences dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """Preferences dialog for output folder, safety toggles, and appearance."""

    settings_saved = Signal(dict)

    def __init__(
        self,
        custom_out_dir: Optional[Path] = None,
        delete_original: bool = False,
        overwrite: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("FileTool Preferences")
        self.resize(480, 320)
        self.custom_dir = custom_out_dir
        self.delete_orig = delete_original
        self.allow_overwrite = overwrite
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Output Location
        loc_box = QGroupBox("Output Location")
        loc_layout = QVBoxLayout(loc_box)

        self.radio_same = QRadioButton("Same folder as source file (Default)")
        self.radio_same.setChecked(self.custom_dir is None)
        self.radio_same.toggled.connect(self._on_loc_toggled)
        loc_layout.addWidget(self.radio_same)

        self.radio_custom = QRadioButton("Save all files to specific folder:")
        self.radio_custom.setChecked(self.custom_dir is not None)
        loc_layout.addWidget(self.radio_custom)

        custom_row = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setText(str(self.custom_dir) if self.custom_dir else "")
        self.dir_input.setEnabled(self.custom_dir is not None)
        self.dir_input.setPlaceholderText("Select output directory...")
        custom_row.addWidget(self.dir_input)

        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setEnabled(self.custom_dir is not None)
        self.browse_btn.clicked.connect(self._browse_custom_dir)
        custom_row.addWidget(self.browse_btn)

        loc_layout.addLayout(custom_row)
        layout.addWidget(loc_box)

        # Safety & File Preservation
        safe_box = QGroupBox("Safety & File Actions")
        safe_layout = QVBoxLayout(safe_box)

        self.chk_delete_orig = QCheckBox("Delete original file after successful conversion")
        self.chk_delete_orig.setChecked(self.delete_orig)
        safe_layout.addWidget(self.chk_delete_orig)

        self.chk_overwrite = QCheckBox("Overwrite existing output file instead of appending (1)")
        self.chk_overwrite.setChecked(self.allow_overwrite)
        safe_layout.addWidget(self.chk_overwrite)

        layout.addWidget(safe_box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_loc_toggled(self, checked: bool) -> None:
        self.dir_input.setEnabled(not checked)
        self.browse_btn.setEnabled(not checked)

    def _browse_custom_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            str(self.custom_dir or Path.home()),
        )
        if chosen:
            self.custom_dir = Path(chosen)
            self.dir_input.setText(chosen)

    def _save_settings(self) -> None:
        out_dir = None
        if self.radio_custom.isChecked() and self.dir_input.text().strip():
            out_dir = Path(self.dir_input.text().strip())

        settings = {
            "output_dir": out_dir,
            "delete_original": self.chk_delete_orig.isChecked(),
            "overwrite": self.chk_overwrite.isChecked(),
        }
        self.settings_saved.emit(settings)
        self.accept()
