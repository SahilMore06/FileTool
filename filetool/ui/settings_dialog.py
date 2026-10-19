"""Settings and preferences dialog including Launch-at-Login and Drag Wheel triggers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from filetool.platform.mac_actions import (
    is_launch_at_login_enabled,
    set_launch_at_login,
)

MODIFIER_CHOICES = ["Shift", "Command", "Control", "Option"]


class SettingsDialog(QDialog):
    """Preferences dialog for output folder, safety toggles, drag wheel, and launch-at-login."""

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
        self.resize(520, 480)
        self.custom_dir = custom_out_dir
        self.delete_orig = delete_original
        self.allow_overwrite = overwrite

        self.qsettings = QSettings("FileTool", "FileTool")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 1. Output Location
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

        # 2. Radial Drag Wheel Overlay
        wheel_box = QGroupBox("Radial Drag Wheel Overlay")
        wheel_layout = QVBoxLayout(wheel_box)

        self.chk_wheel_enabled = QCheckBox("Enable radial drag wheel overlay")
        self.chk_wheel_enabled.setChecked(
            self.qsettings.value("wheel_enabled", True, type=bool)
        )
        wheel_layout.addWidget(self.chk_wheel_enabled)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 6, 6, 6)
        form_layout.setSpacing(8)

        self.combo_convert = QComboBox()
        self.combo_convert.addItems(MODIFIER_CHOICES)
        self.combo_convert.setCurrentText(
            self.qsettings.value("trigger_convert", "Shift", type=str)
        )
        form_layout.addRow("Convert Wheel Trigger:", self.combo_convert)

        self.combo_tools = QComboBox()
        self.combo_tools.addItems(MODIFIER_CHOICES)
        self.combo_tools.setCurrentText(
            self.qsettings.value("trigger_tools", "Command", type=str)
        )
        form_layout.addRow("File Tools Trigger:", self.combo_tools)

        self.combo_actions = QComboBox()
        self.combo_actions.addItems(MODIFIER_CHOICES)
        self.combo_actions.setCurrentText(
            self.qsettings.value("trigger_actions", "Control", type=str)
        )
        form_layout.addRow("File Actions Trigger:", self.combo_actions)

        wheel_layout.addLayout(form_layout)
        layout.addWidget(wheel_box)

        # 3. System & Startup (Launch at Login / Menu-bar Mode)
        sys_box = QGroupBox("System & Startup")
        sys_layout = QVBoxLayout(sys_box)

        self.chk_launch_login = QCheckBox("Launch FileTool automatically at login")
        self.chk_launch_login.setChecked(is_launch_at_login_enabled())
        sys_layout.addWidget(self.chk_launch_login)

        self.chk_menu_bar_only = QCheckBox("Run as background menu-bar app (Hide Dock icon)")
        self.chk_menu_bar_only.setChecked(
            self.qsettings.value("accessory_mode", True, type=bool)
        )
        sys_layout.addWidget(self.chk_menu_bar_only)

        layout.addWidget(sys_box)

        # 4. Safety & File Preservation
        safe_box = QGroupBox("Safety & File Actions")
        safe_layout = QVBoxLayout(safe_box)

        self.chk_delete_orig = QCheckBox("Delete original file after successful conversion")
        self.chk_delete_orig.setChecked(self.delete_orig)
        safe_layout.addWidget(self.chk_delete_orig)

        self.chk_overwrite = QCheckBox("Overwrite existing output file instead of appending (1)")
        self.chk_overwrite.setChecked(self.allow_overwrite)
        safe_layout.addWidget(self.chk_overwrite)

        layout.addWidget(safe_box)

        # 5. Buttons
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

        # Update Launch at login
        want_launch = self.chk_launch_login.isChecked()
        if want_launch != is_launch_at_login_enabled():
            set_launch_at_login(want_launch)

        # Persist preferences
        self.qsettings.setValue("wheel_enabled", self.chk_wheel_enabled.isChecked())
        self.qsettings.setValue("trigger_convert", self.combo_convert.currentText())
        self.qsettings.setValue("trigger_tools", self.combo_tools.currentText())
        self.qsettings.setValue("trigger_actions", self.combo_actions.currentText())
        self.qsettings.setValue("accessory_mode", self.chk_menu_bar_only.isChecked())

        settings = {
            "output_dir": out_dir,
            "delete_original": self.chk_delete_orig.isChecked(),
            "overwrite": self.chk_overwrite.isChecked(),
            "wheel_enabled": self.chk_wheel_enabled.isChecked(),
            "key_mappings": {
                self.combo_convert.currentText().lower(): "convert",
                self.combo_tools.currentText().lower(): "tools",
                self.combo_actions.currentText().lower(): "actions",
            },
            "accessory_mode": self.chk_menu_bar_only.isChecked(),
        }
        self.settings_saved.emit(settings)
        self.accept()
