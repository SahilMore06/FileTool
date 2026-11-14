"""Settings page, preferences persistence, dependency health, and onboarding dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from filetool.core.deps import TOOLS_METADATA, check_dependencies, resolver
from filetool.platform.mac_actions import is_launch_at_login_enabled, set_launch_at_login
from filetool.ui.components import IOSSwitch
from filetool.ui.styles import ACCENT_PRESETS, get_tokens

MODIFIER_KEYS = ["Shift", "Command", "Control", "Option"]


class SettingsPage(QScrollArea):
    """Persistent preferences view synced directly with QSettings."""

    theme_changed = Signal(bool)
    accent_changed = Signal(str)
    settings_changed = Signal(dict)

    def __init__(self, dark_mode: bool = False, accent_key: str = "amber", parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        self.qsettings = QSettings("FileTool", "FileTool")
        self._switches: list[IOSSwitch] = []
        self._swatch_btns: Dict[str, QPushButton] = {}
        self._dep_rows: Dict[str, QLabel] = {}
        self._init_ui()
        self.refresh_dependency_status(run_version_probe=False)

    def _init_ui(self) -> None:
        accent_hex = get_tokens(self._dark_mode, accent_key=self._accent_key)["accent"]

        outer = QWidget()
        outer.setObjectName("scrollBody")
        outer_lay = QHBoxLayout(outer)
        outer_lay.setContentsMargins(28, 24, 28, 28)
        outer_lay.addStretch(1)

        body = QWidget()
        body.setObjectName("scrollBody")
        body.setMaximumWidth(780)
        body.setMinimumWidth(520)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        appearance_card = self._make_card("Appearance", lay)
        appearance_lay = appearance_card.layout()

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme Mode"))
        theme_row.addStretch()
        self.light_btn = QPushButton("Light")
        self.light_btn.setObjectName("filterPill")
        self.light_btn.setCursor(Qt.PointingHandCursor)
        self.light_btn.clicked.connect(lambda: self._on_theme_picked(False))

        self.dark_btn = QPushButton("Dark")
        self.dark_btn.setObjectName("filterPill")
        self.dark_btn.setCursor(Qt.PointingHandCursor)
        self.dark_btn.clicked.connect(lambda: self._on_theme_picked(True))
        theme_row.addWidget(self.light_btn)
        theme_row.addWidget(self.dark_btn)
        appearance_lay.addLayout(theme_row)

        accent_row = QHBoxLayout()
        accent_row.addWidget(QLabel("Accent Color"))
        accent_row.addStretch()
        for key, preset in ACCENT_PRESETS.items():
            btn = QPushButton(preset["label"])
            btn.setObjectName("filterPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._on_accent_picked(k))
            accent_row.addWidget(btn)
            self._swatch_btns[key] = btn
        appearance_lay.addLayout(accent_row)

        wheel_card = self._make_card("Drag Wheel & macOS Integration", lay)
        wheel_lay = wheel_card.layout()

        self.sw_wheel = self._add_switch_row(
            wheel_lay,
            "Enable Finder Drag Wheel",
            "Show radial action wheel when tapping a modifier key during a Finder drag",
            self.qsettings.value("wheel_enabled", True, type=bool),
            accent_hex,
        )

        self.combo_convert = self._add_combo_row(
            wheel_lay,
            "Convert Wheel Trigger",
            self.qsettings.value("trigger_convert", "Shift", type=str),
        )
        self.combo_tools = self._add_combo_row(
            wheel_lay,
            "Tools Wheel Trigger",
            self.qsettings.value("trigger_tools", "Command", type=str),
        )
        self.combo_actions = self._add_combo_row(
            wheel_lay,
            "Actions Wheel Trigger",
            self.qsettings.value("trigger_actions", "Control", type=str),
        )

        self.trigger_warning = QLabel()
        self.trigger_warning.setObjectName("validationWarning")
        self.trigger_warning.setWordWrap(True)
        self.trigger_warning.setVisible(False)
        wheel_lay.addWidget(self.trigger_warning)

        self.sw_accessory = self._add_switch_row(
            wheel_lay,
            "Run in Menu Bar Only",
            "Hide Dock icon and keep FileTool accessible from the macOS menu bar",
            self.qsettings.value("accessory_mode", True, type=bool),
            accent_hex,
        )
        self.sw_login = self._add_switch_row(
            wheel_lay,
            "Launch at Login",
            "Start FileTool automatically when signing in to macOS",
            is_launch_at_login_enabled(),
            accent_hex,
        )

        out_card = self._make_card("Output & File Safety", lay)
        out_lay = out_card.layout()

        saved_dir = self.qsettings.value("output_dir", "", type=str)
        self.sw_custom_dir = self._add_switch_row(
            out_lay,
            "Save Outputs to Custom Folder",
            "Off saves converted files beside each source file",
            bool(saved_dir),
            accent_hex,
        )

        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit(saved_dir)
        self.dir_input.setPlaceholderText("Default: Same folder as source file")
        dir_row.addWidget(self.dir_input, stretch=1)

        self.browse_btn = QPushButton("Choose Folder…")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.browse_btn)
        out_lay.addLayout(dir_row)

        self.dir_warning = QLabel()
        self.dir_warning.setObjectName("validationWarning")
        self.dir_warning.setWordWrap(True)
        self.dir_warning.setVisible(False)
        out_lay.addWidget(self.dir_warning)

        self.dir_input.setEnabled(self.sw_custom_dir.isChecked())
        self.browse_btn.setEnabled(self.sw_custom_dir.isChecked())
        self.sw_custom_dir.toggled_state.connect(self._on_custom_dir_toggled)

        self.sw_overwrite = self._add_switch_row(
            out_lay,
            "Overwrite Existing Output Files",
            "When off, FileTool appends numeric suffixes to avoid overwriting files",
            self.qsettings.value("overwrite_files", False, type=bool),
            accent_hex,
        )
        self.sw_delete_orig = self._add_switch_row(
            out_lay,
            "Delete Original After Success",
            "Move source files out only after verified conversion completion",
            self.qsettings.value("delete_original", False, type=bool),
            accent_hex,
        )

        deps_card = self._make_card("Local Engine Dependencies", lay)
        deps_lay = deps_card.layout()

        for tool_name, meta in TOOLS_METADATA.items():
            row = QHBoxLayout()
            name_label = QLabel(f"{tool_name} — {meta.purpose}")
            row.addWidget(name_label, stretch=1)
            badge = QLabel("Checking…")
            badge.setObjectName("pillTag")
            row.addWidget(badge)
            self._dep_rows[tool_name] = badge
            deps_lay.addLayout(row)

        rescan_row = QHBoxLayout()
        rescan_row.addStretch()
        self.rescan_btn = QPushButton("Verify Installed Tools")
        self.rescan_btn.setObjectName("secondaryButton")
        self.rescan_btn.setCursor(Qt.PointingHandCursor)
        self.rescan_btn.clicked.connect(lambda: self.refresh_dependency_status(run_version_probe=True))
        rescan_row.addWidget(self.rescan_btn)
        deps_lay.addLayout(rescan_row)

        initial_triggers = [
            self.combo_convert.currentText(),
            self.combo_tools.currentText(),
            self.combo_actions.currentText(),
        ]
        self._last_valid_triggers = (
            tuple(initial_triggers)
            if len(set(initial_triggers)) == 3
            else ("Shift", "Command", "Control")
        )

        self.sw_wheel.toggled_state.connect(self._persist_and_emit)
        self.sw_accessory.toggled_state.connect(self._persist_and_emit)
        self.sw_login.toggled_state.connect(self._on_login_toggled)
        self.sw_overwrite.toggled_state.connect(self._persist_and_emit)
        self.sw_delete_orig.toggled_state.connect(self._persist_and_emit)
        self.dir_input.textChanged.connect(lambda _t: self.validate())
        self.dir_input.editingFinished.connect(self._persist_and_emit)
        self.combo_convert.currentIndexChanged.connect(self._persist_and_emit)
        self.combo_tools.currentIndexChanged.connect(self._persist_and_emit)
        self.combo_actions.currentIndexChanged.connect(self._persist_and_emit)

        lay.addStretch()
        outer_lay.addWidget(body, stretch=4)
        outer_lay.addStretch(1)
        self.setWidget(outer)

        self._refresh_theme_pills()
        self.validate()

    def _make_card(self, title: str, parent_lay: QVBoxLayout) -> QFrame:
        card = QFrame()
        card.setObjectName("cardPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("panelHeading")
        card_layout.addWidget(heading)
        parent_lay.addWidget(card)
        return card

    def _add_switch_row(
        self,
        parent_lay: QVBoxLayout,
        title: str,
        subtitle: str,
        checked: bool,
        accent_hex: str,
    ) -> IOSSwitch:
        row = QHBoxLayout()
        row.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title_label = QLabel(title)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("mutedMeta")
        subtitle_label.setWordWrap(True)
        text_col.addWidget(title_label)
        text_col.addWidget(subtitle_label)
        row.addLayout(text_col, stretch=1)

        switch = IOSSwitch(checked=checked, dark_mode=self._dark_mode, accent_color=accent_hex)
        self._switches.append(switch)
        row.addWidget(switch)
        parent_lay.addLayout(row)
        return switch

    def _add_combo_row(self, parent_lay: QVBoxLayout, label: str, current_val: str) -> QComboBox:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addStretch()
        combo = QComboBox()
        combo.addItems(MODIFIER_KEYS)
        if current_val in MODIFIER_KEYS:
            combo.setCurrentText(current_val)
        combo.setFixedWidth(130)
        row.addWidget(combo)
        parent_lay.addLayout(row)
        return combo

    def _on_theme_picked(self, is_dark: bool) -> None:
        if self._dark_mode != is_dark:
            self._dark_mode = is_dark
            self._refresh_theme_pills()
            self.theme_changed.emit(is_dark)

    def _on_accent_picked(self, accent_key: str) -> None:
        if self._accent_key != accent_key:
            self._accent_key = accent_key
            self._refresh_theme_pills()
            self.accent_changed.emit(accent_key)

    def _on_custom_dir_toggled(self, enabled: bool) -> None:
        self.dir_input.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        if not enabled:
            self.qsettings.setValue("output_dir", "")
        self._persist_and_emit()

    def _browse_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.dir_input.text() or str(Path.home()),
        )
        if chosen:
            self.dir_input.setText(chosen)
            self.sw_custom_dir.setChecked(True)
            self._persist_and_emit()

    def _on_login_toggled(self, enabled: bool) -> None:
        set_launch_at_login(enabled)

    def validate(self) -> list[str]:
        """Validate trigger uniqueness and custom output folder state inline."""
        errors: list[str] = []

        trigger_combos = [self.combo_convert, self.combo_tools, self.combo_actions]
        triggers = [c.currentText() for c in trigger_combos]
        counts = {key: triggers.count(key) for key in triggers}
        has_conflict = len(set(triggers)) < len(triggers)

        for combo in trigger_combos:
            is_dup = counts.get(combo.currentText(), 0) > 1
            if combo.property("invalid") != is_dup:
                combo.setProperty("invalid", is_dup)
                self._repolish(combo)

        if has_conflict:
            msg = "Convert, Tools, and Actions triggers should use different modifier keys."
            errors.append(msg)
            self.trigger_warning.setText(msg)
            self.trigger_warning.setVisible(True)
        else:
            self.trigger_warning.clear()
            self.trigger_warning.setVisible(False)

        dir_invalid = False
        if self.sw_custom_dir.isChecked():
            raw_dir = self.dir_input.text().strip()
            if not raw_dir:
                msg = "Choose a destination folder, or turn this off to save beside source files."
                errors.append(msg)
                self.dir_warning.setText(msg)
                self.dir_warning.setVisible(True)
                dir_invalid = True
            elif not Path(raw_dir).expanduser().is_dir():
                msg = f"Folder not found: {raw_dir}. Outputs will fall back to source folders."
                errors.append(msg)
                self.dir_warning.setText(msg)
                self.dir_warning.setVisible(True)
                dir_invalid = True
            else:
                self.dir_warning.clear()
                self.dir_warning.setVisible(False)
        else:
            self.dir_warning.clear()
            self.dir_warning.setVisible(False)

        if self.dir_input.property("invalid") != dir_invalid:
            self.dir_input.setProperty("invalid", dir_invalid)
            self._repolish(self.dir_input)

        return errors

    def _persist_and_emit(self, *_args) -> None:
        self.validate()

        custom_dir: Optional[Path] = None
        if self.sw_custom_dir.isChecked() and self.dir_input.text().strip():
            candidate = Path(self.dir_input.text().strip()).expanduser()
            if candidate.is_dir():
                custom_dir = candidate

        triggers = (
            self.combo_convert.currentText(),
            self.combo_tools.currentText(),
            self.combo_actions.currentText(),
        )
        if len(set(triggers)) == len(triggers):
            self._last_valid_triggers = triggers
            self.qsettings.setValue("trigger_convert", triggers[0])
            self.qsettings.setValue("trigger_tools", triggers[1])
            self.qsettings.setValue("trigger_actions", triggers[2])

        active_convert, active_tools, active_actions = self._last_valid_triggers

        self.qsettings.setValue("wheel_enabled", self.sw_wheel.isChecked())
        self.qsettings.setValue("accessory_mode", self.sw_accessory.isChecked())
        self.qsettings.setValue("output_dir", str(custom_dir) if custom_dir else "")
        self.qsettings.setValue("overwrite_files", self.sw_overwrite.isChecked())
        self.qsettings.setValue("delete_original", self.sw_delete_orig.isChecked())

        self.settings_changed.emit(
            {
                "output_dir": custom_dir,
                "delete_original": self.sw_delete_orig.isChecked(),
                "overwrite": self.sw_overwrite.isChecked(),
                "wheel_enabled": self.sw_wheel.isChecked(),
                "key_mappings": {
                    active_convert.lower(): "convert",
                    active_tools.lower(): "tools",
                    active_actions.lower(): "actions",
                },
                "accessory_mode": self.sw_accessory.isChecked(),
            }
        )

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def refresh_dependency_status(self, run_version_probe: bool = False) -> None:
        if run_version_probe:
            results = check_dependencies()
            for name, status in results.items():
                if name in self._dep_rows:
                    badge = self._dep_rows[name]
                    badge.setText("Installed" if status.available else status.install_command)
                    badge.setObjectName("badgeSuccess" if status.available else "badgeError")
                    self._repolish(badge)
            return

        for name, meta in TOOLS_METADATA.items():
            resolved = resolver.resolve(name)
            badge = self._dep_rows[name]
            badge.setText("Available" if resolved else meta.install_command)
            badge.setObjectName("badgeSuccess" if resolved else "pillTag")
            self._repolish(badge)

    def _refresh_theme_pills(self) -> None:
        self.light_btn.setProperty("active", not self._dark_mode)
        self.dark_btn.setProperty("active", self._dark_mode)
        self._repolish(self.light_btn)
        self._repolish(self.dark_btn)

        for key, btn in self._swatch_btns.items():
            btn.setProperty("active", key == self._accent_key)
            self._repolish(btn)

    def set_theme(self, dark_mode: bool, accent_key: str) -> None:
        self._dark_mode = dark_mode
        self._accent_key = accent_key if accent_key in ACCENT_PRESETS else "amber"
        accent_hex = get_tokens(dark_mode, accent_key=self._accent_key)["accent"]
        for sw in self._switches:
            sw.set_dark_mode(dark_mode)
            sw.set_accent_color(accent_hex)
        self._refresh_theme_pills()
