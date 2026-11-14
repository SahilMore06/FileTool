"""Simple native Fluxora window coordinating conversion queue, history, and settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from filetool.ui.onboarding import OnboardingWindow

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from filetool.core.registry import registry
from filetool.core.runner import ConversionJob, JobRunner, JobStatus
from filetool.platform.mac_actions import trigger_haptic_tick
from filetool.ui.components import (
    LogoWidget,
    ThemeToggle,
    collect_paths_from_urls,
    create_brand_icon,
)
from filetool.ui.dropzone import DropZone
from filetool.ui.history_panel import HistoryPanel
from filetool.ui.job_list import JobListWidget
from filetool.ui.options_panel import OptionsPanel
from filetool.ui.settings_page import SettingsPage
from filetool.ui.styles import ACCENT_PRESETS, get_stylesheet

logger = logging.getLogger("filetool.ui.main_window")


class MainWindow(QMainWindow):
    """Focused desktop window for local offline file conversion."""

    settings_updated = Signal(dict)
    theme_updated = Signal(bool, str)
    queue_progress_changed = Signal(int, int, bool)

    _TAB_KEYS = ("queue", "history", "settings")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fluxora")
        self.resize(880, 560)
        self.setMinimumSize(720, 480)
        self.setAcceptDrops(True)
        self._was_running = False
        self._last_indicator_sig: Optional[tuple] = None
        self._done_reset_timer = QTimer(self)
        self._done_reset_timer.setSingleShot(True)
        self._done_reset_timer.timeout.connect(self._reset_brand_pill)

        self.qsettings = QSettings("Fluxora", "Fluxora")
        self.dark_mode: bool = self.qsettings.value("dark_mode", False, type=bool)
        accent_val = self.qsettings.value("accent_preset", "amber", type=str)
        self.accent_key: str = accent_val if accent_val in ACCENT_PRESETS else "amber"

        out_dir_str = self.qsettings.value("output_dir", "", type=str)
        self.custom_output_dir: Optional[Path] = Path(out_dir_str) if out_dir_str else None
        self.overwrite_files: bool = self.qsettings.value("overwrite_files", False, type=bool)
        self.delete_original: bool = self.qsettings.value("delete_original", False, type=bool)

        self.runner = JobRunner()
        self._onboarding_win: Optional[OnboardingWindow] = None

        self._init_ui()
        self._connect_signals()
        self._apply_theme()
        self._navigate("queue")
        self._refresh_queue_indicators()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_convert_page())
        self.pages.addWidget(self._build_history_page())
        self.settings_page = SettingsPage(dark_mode=self.dark_mode, accent_key=self.accent_key)
        self.pages.addWidget(self.settings_page)
        root.addWidget(self.pages, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbarBar")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        accent_hex = ACCENT_PRESETS[self.accent_key]["accent"]
        self.logo = LogoWidget(size=28, accent_color=accent_hex)
        title = QLabel("Fluxora")
        title.setObjectName("appTitle")
        self.brand_pill = QLabel("Offline")
        self.brand_pill.setObjectName("brandStatusPill")
        self.brand_pill.setProperty("state", "idle")
        self.brand_pill.setFixedHeight(20)
        self.brand_pill.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo, alignment=Qt.AlignVCenter)
        layout.addWidget(title, alignment=Qt.AlignVCenter)
        layout.addWidget(self.brand_pill, alignment=Qt.AlignVCenter)
        layout.addStretch()

        tab_group = QFrame()
        tab_group.setObjectName("tabGroup")
        tab_layout = QHBoxLayout(tab_group)
        tab_layout.setContentsMargins(3, 3, 3, 3)
        tab_layout.setSpacing(2)

        self._tab_buttons: dict[str, QPushButton] = {}
        labels = [("queue", "Convert"), ("history", "History"), ("settings", "Settings")]
        for key, text in labels:
            btn = QPushButton(text)
            btn.setObjectName("tabButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", key == "queue")
            btn.clicked.connect(lambda _checked=False, k=key: (trigger_haptic_tick("alignment"), self._navigate(k)))
            tab_layout.addWidget(btn)
            self._tab_buttons[key] = btn

        layout.addWidget(tab_group)
        layout.addStretch()

        self.add_btn = QPushButton("+ Add Files")
        self.add_btn.setObjectName("secondaryButton")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.add_btn)

        self.theme_toggle = ThemeToggle(is_dark=self.dark_mode)
        self.theme_toggle.setToolTip("Toggle Light / Dark appearance")
        layout.addWidget(self.theme_toggle)

        return bar

    def _build_convert_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 12)
        body.setSpacing(12)

        self.stack = QStackedWidget()
        self.dropzone = DropZone()
        self.job_list = JobListWidget()
        self.stack.addWidget(self.dropzone)  # 0
        self.stack.addWidget(self.job_list)  # 1
        body.addWidget(self.stack, stretch=1)

        self.options_panel = OptionsPanel()
        self.options_panel.setVisible(False)
        body.addWidget(self.options_panel)

        outer.addLayout(body, stretch=1)

        footer = QWidget()
        footer.setObjectName("actionFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.setSpacing(10)

        self.bulk_combo = QComboBox()
        self.bulk_combo.setMinimumWidth(170)
        self._update_bulk_combo_formats()
        footer_layout.addWidget(self.bulk_combo)

        self.options_btn = QPushButton("Options")
        self.options_btn.setObjectName("secondaryButton")
        self.options_btn.setCheckable(True)
        self.options_btn.setCursor(Qt.PointingHandCursor)
        footer_layout.addWidget(self.options_btn)

        footer_layout.addStretch()

        self.clear_btn = QPushButton("Clear Done")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        footer_layout.addWidget(self.clear_btn)

        self.convert_btn = QPushButton("Convert All")
        self.convert_btn.setObjectName("primaryButton")
        self.convert_btn.setMinimumWidth(120)
        self.convert_btn.setCursor(Qt.PointingHandCursor)
        footer_layout.addWidget(self.convert_btn)

        outer.addWidget(footer)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        self.history_panel = HistoryPanel()
        layout.addWidget(self.history_panel)
        return page

    def _connect_signals(self) -> None:
        self.add_btn.clicked.connect(self._browse_add_files)
        self.theme_toggle.theme_changed.connect(self._on_theme_toggled)

        self.dropzone.files_dropped.connect(self._on_files_dropped)
        self.job_list.cancel_job.connect(self.runner.cancel_job)
        self.job_list.remove_job.connect(self._on_remove_job)

        self.bulk_combo.currentIndexChanged.connect(self._apply_bulk_format)
        self.options_btn.toggled.connect(self.options_panel.setVisible)
        self.clear_btn.clicked.connect(self._clear_completed)
        self.convert_btn.clicked.connect(self._start_all_jobs)

        self.settings_page.theme_changed.connect(self._on_theme_toggled)
        self.settings_page.accent_changed.connect(self._on_accent_changed)
        self.settings_page.settings_changed.connect(self._on_settings_saved)
        self.settings_page.replay_onboarding_requested.connect(lambda: self.open_onboarding(first_boot=False, initial_step=0))
        self.settings_page.review_privacy_requested.connect(
            lambda: self.open_onboarding(first_boot=False, initial_step=2, initial_legal_doc="privacy")
        )
        self.settings_page.review_terms_requested.connect(
            lambda: self.open_onboarding(first_boot=False, initial_step=2, initial_legal_doc="terms")
        )

        self.runner.signals.completed.connect(self._on_job_completed)
        self.runner.signals.failed.connect(self._on_job_failed)
        self.runner.job_updated.connect(self.job_list.update_job_row)
        self.runner.job_updated.connect(lambda _jid: self._refresh_queue_indicators())

    def _navigate(self, key: str) -> None:
        if key not in self._TAB_KEYS:
            return
        self.pages.setCurrentIndex(self._TAB_KEYS.index(key))
        for tab_key, btn in self._tab_buttons.items():
            btn.setProperty("active", tab_key == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_theme_toggled(self, is_dark: bool) -> None:
        self.dark_mode = bool(is_dark)
        self.qsettings.setValue("dark_mode", self.dark_mode)
        self._apply_theme()

    def _on_accent_changed(self, accent_key: str) -> None:
        if accent_key in ACCENT_PRESETS:
            self.accent_key = accent_key
            self.qsettings.setValue("accent_preset", accent_key)
            self._apply_theme()

    def _apply_theme(self) -> None:
        accent_hex = ACCENT_PRESETS[self.accent_key]["accent"]
        self.setStyleSheet(get_stylesheet(self.dark_mode, accent_key=self.accent_key))
        self.setWindowIcon(create_brand_icon(accent_hex))
        self.logo.set_accent_color(accent_hex)
        self.dropzone.set_accent_color(accent_hex)
        self.theme_toggle.set_dark(self.dark_mode)
        self.job_list.set_dark_mode(self.dark_mode)
        self.settings_page.set_theme(self.dark_mode, self.accent_key)
        self.theme_updated.emit(self.dark_mode, self.accent_key)

    def _browse_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Convert",
            str(Path.home()),
            "All Files (*.*)",
        )
        if files:
            self._on_files_dropped([Path(f) for f in files])

    def _on_files_dropped(self, paths: List[Path]) -> None:
        if not paths:
            return
        added_count = 0
        ext_default_cache: dict[str, str] = {}
        self.job_list.container.setUpdatesEnabled(False)
        try:
            for path in paths:
                if not path.exists() or not path.is_file():
                    continue
                in_ext = path.suffix.lower().lstrip(".")
                if in_ext not in ext_default_cache:
                    outputs = registry.list_outputs(in_ext)
                    ext_default_cache[in_ext] = outputs[0] if outputs else ""
                job = ConversionJob(
                    src_path=path,
                    dest_ext=ext_default_cache[in_ext],
                    target_dir=self.custom_output_dir,
                    overwrite=self.overwrite_files,
                    delete_original=self.delete_original,
                )
                self.runner.add_job(job)
                self.job_list.add_job_row(job)
                added_count += 1
        finally:
            self.job_list.container.setUpdatesEnabled(True)

        if added_count:
            self.stack.setCurrentIndex(1)
            self._navigate("queue")
            self._update_bulk_combo_formats()
            self._refresh_queue_indicators()
            self.status_bar.showMessage(f"Added {added_count} file(s)", 3000)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = collect_paths_from_urls(event.mimeData().urls())
        if paths:
            self._on_files_dropped(paths)
            event.acceptProposedAction()

    def _on_job_completed(self, job_id: str, out_path_str: str) -> None:
        job = self.runner.jobs.get(job_id)
        if job:
            dest = Path(out_path_str)
            self.history_panel.add_entry(job.src_path, dest)
            self.status_bar.showMessage(f"Saved: {dest.name}", 4000)
        self._refresh_queue_indicators()

    def _on_job_failed(self, job_id: str, msg: str, _tail: str) -> None:
        self._refresh_queue_indicators()
        job = self.runner.jobs.get(job_id)
        if job:
            self.status_bar.showMessage(f"Failed ({job.filename}): {msg}", 5000)

    def _on_remove_job(self, job_id: str) -> None:
        self.runner.cancel_job(job_id)
        self.runner.jobs.pop(job_id, None)
        self.job_list.remove_job_row(job_id)
        if not self.runner.jobs:
            self.stack.setCurrentIndex(0)
        self._update_bulk_combo_formats()
        self._refresh_queue_indicators()

    def _clear_completed(self) -> None:
        done = [
            jid
            for jid, j in self.runner.jobs.items()
            if j.status in (JobStatus.SUCCESS, JobStatus.CANCELLED)
        ]
        if not done:
            return
        self.job_list.container.setUpdatesEnabled(False)
        try:
            for jid in done:
                self.runner.jobs.pop(jid, None)
                self.job_list.remove_job_row(jid)
        finally:
            self.job_list.container.setUpdatesEnabled(True)

        if not self.runner.jobs:
            self.stack.setCurrentIndex(0)
        self._update_bulk_combo_formats()
        self._refresh_queue_indicators()

    def _start_all_jobs(self) -> None:
        opts = self.options_panel.get_options()
        for job in self.runner.jobs.values():
            if job.status in (JobStatus.PENDING, JobStatus.FAILED):
                job.options.update(opts)
                job.target_dir = self.custom_output_dir
                job.overwrite = self.overwrite_files
                job.delete_original = self.delete_original
        self.runner.start_all()
        self._refresh_queue_indicators()

    def _set_brand_pill(self, text: str, state: str) -> None:
        self.brand_pill.setText(text)
        if self.brand_pill.property("state") != state:
            self.brand_pill.setProperty("state", state)
            self.brand_pill.style().unpolish(self.brand_pill)
            self.brand_pill.style().polish(self.brand_pill)

    def _reset_brand_pill(self) -> None:
        if not any(j.status == JobStatus.RUNNING for j in self.runner.jobs.values()):
            self._set_brand_pill("Offline", "idle")

    def _refresh_queue_indicators(self) -> None:
        jobs = list(self.runner.jobs.values())
        total = len(jobs)
        pending = sum(1 for j in jobs if j.status in (JobStatus.PENDING, JobStatus.FAILED))
        running_jobs = [j for j in jobs if j.status == JobStatus.RUNNING]
        running = len(running_jobs)
        done = sum(1 for j in jobs if j.status in (JobStatus.SUCCESS, JobStatus.CANCELLED))
        succeeded = sum(1 for j in jobs if j.status == JobStatus.SUCCESS)
        avg_pct = int(sum(j.progress for j in running_jobs) / running) if running > 0 else 0

        sig = (total, pending, running, done, succeeded, avg_pct, self._was_running, self._done_reset_timer.isActive())
        if sig == self._last_indicator_sig:
            return
        self._last_indicator_sig = sig

        self._tab_buttons["queue"].setText(f"Convert ({total})" if total else "Convert")
        self.bulk_combo.setEnabled(total > 0)
        self.clear_btn.setEnabled(done > 0)
        self.convert_btn.setEnabled(pending > 0 and running == 0)

        just_finished = False
        if running > 0:
            self._done_reset_timer.stop()
            self.logo.set_active_progress(True, avg_pct)
            self._set_brand_pill(f"Converting · {avg_pct}%", "active")
            self._was_running = True
            self.queue_progress_changed.emit(running, avg_pct, False)
        elif self._was_running:
            self._was_running = False
            just_finished = succeeded > 0
            if just_finished:
                self.logo.trigger_done_flash()
                self._set_brand_pill("Done", "done")
                self._done_reset_timer.start(1400)
                trigger_haptic_tick("level_change")
            else:
                self.logo.set_active_progress(False, None)
                self._set_brand_pill("Offline", "idle")
            self.queue_progress_changed.emit(0, 100 if just_finished else 0, just_finished)
        else:
            self.logo.set_active_progress(False, None)
            if not self._done_reset_timer.isActive():
                self._set_brand_pill("Offline", "idle")
            self.queue_progress_changed.emit(0, 0, False)

    def _update_bulk_combo_formats(self) -> None:
        self.bulk_combo.blockSignals(True)
        self.bulk_combo.clear()
        self.bulk_combo.addItem("Bulk target…", "")

        seen: set[str] = set()
        for fmt in ("jpg", "png", "webp", "pdf", "mp4", "mp3"):
            self.bulk_combo.addItem(fmt.upper(), fmt)
            seen.add(fmt)

        for job in self.runner.jobs.values():
            in_ext = job.src_path.suffix.lower().lstrip(".")
            for fmt in registry.list_outputs(in_ext):
                if fmt not in seen:
                    self.bulk_combo.addItem(fmt.upper(), fmt)
                    seen.add(fmt)

        self.bulk_combo.blockSignals(False)

    def _apply_bulk_format(self, _index: int) -> None:
        fmt = self.bulk_combo.currentData()
        if not fmt:
            return
        for row in self.job_list.rows.values():
            idx = row.format_picker.findData(fmt)
            if idx >= 0:
                row.format_picker.setCurrentIndex(idx)

    def _on_settings_saved(self, settings: dict) -> None:
        self.custom_output_dir = settings.get("output_dir")
        self.delete_original = bool(settings.get("delete_original", False))
        self.overwrite_files = bool(settings.get("overwrite", False))
        self.settings_updated.emit(settings)

    def _open_settings(self) -> None:
        self._navigate("settings")

    def _show_dep_report(self) -> None:
        self._navigate("settings")
        self.settings_page.refresh_dependency_status(run_version_probe=True)
        self.settings_page.ensureWidgetVisible(self.settings_page.rescan_btn)

    def open_onboarding(
        self,
        first_boot: bool = False,
        initial_step: int = 0,
        initial_legal_doc: str = "privacy",
        qsettings: Optional[QSettings] = None,
    ) -> OnboardingWindow:
        """Open the animated starter onboarding and Terms & Privacy window."""
        from filetool.ui.onboarding import OnboardingWindow

        if self._onboarding_win is not None:
            self._onboarding_win.close()

        win = OnboardingWindow(
            dark_mode=self.dark_mode,
            accent_key=self.accent_key,
            first_boot=first_boot,
            qsettings=qsettings or self.qsettings,
            initial_step=initial_step,
            initial_legal_doc=initial_legal_doc,
        )
        win.theme_preview_changed.connect(self._on_onboarding_theme_preview)
        win.onboarding_completed.connect(self._on_onboarding_completed)
        self._onboarding_win = win
        if initial_step == OnboardingWindow.STEP_INTRO:
            win.start_intro(emit_haptics=True)

        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            win.move(
                avail.center().x() - win.width() // 2,
                avail.center().y() - win.height() // 2,
            )

        if QGuiApplication.platformName() == "cocoa":
            try:
                from AppKit import NSApp

                NSApp.activateIgnoringOtherApps_(True)
            except Exception:
                pass
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def _on_onboarding_theme_preview(self, is_dark: bool, accent_key: str) -> None:
        self._on_theme_toggled(is_dark)
        self._on_accent_changed(accent_key)

    def _on_onboarding_completed(self, result: dict) -> None:
        self._on_theme_toggled(bool(result.get("dark_mode", self.dark_mode)))
        accent_val = result.get("accent_key") or result.get("accent_preset")
        if accent_val:
            self._on_accent_changed(str(accent_val))
        wheel_val = result.get("wheel_enabled")
        if wheel_val is None:
            wheel_val = result.get("drag_wheel_enabled")
        if wheel_val is not None:
            self.settings_page.sw_wheel.blockSignals(True)
            self.settings_page.sw_wheel.setChecked(bool(wheel_val))
            self.settings_page.sw_wheel.blockSignals(False)
        if "accessory_mode" in result:
            self.settings_page.sw_accessory.blockSignals(True)
            self.settings_page.sw_accessory.setChecked(bool(result["accessory_mode"]))
            self.settings_page.sw_accessory.blockSignals(False)
        self.settings_page.refresh_legal_status()
        self.settings_page._persist_and_emit()
        if QGuiApplication.platformName() == "cocoa":
            try:
                from AppKit import NSApp

                NSApp.activateIgnoringOtherApps_(True)
            except Exception:
                pass
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.logo.spin_once(180.0, 480)

    def closeEvent(self, event) -> None:
        if self._onboarding_win is not None:
            self._onboarding_win.close()
            self._onboarding_win = None
        super().closeEvent(event)
