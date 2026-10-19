"""Main macOS window for FileTool."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import filetool.core  # Load all engines
from filetool.core.deps import format_dependency_report
from filetool.core.registry import registry
from filetool.core.runner import ConversionJob, JobRunner, JobStatus
from filetool.ui.dropzone import DropZone
from filetool.ui.history_panel import HistoryPanel
from filetool.ui.job_list import JobListWidget
from filetool.ui.options_panel import OptionsPanel
from filetool.ui.settings_dialog import SettingsDialog
from filetool.ui.styles import get_stylesheet

logger = logging.getLogger("filetool.ui.main_window")

FORMAT_DESCRIPTIONS: Dict[str, str] = {
    # Images
    "png": "PNG Image",
    "jpg": "JPEG Image",
    "jpeg": "JPEG Image",
    "webp": "WebP Image",
    "heic": "HEIC Image",
    "avif": "AVIF Image",
    "tiff": "TIFF Image",
    "bmp": "Bitmap Image",
    "svg": "SVG Vector",
    "gif": "Animated GIF",
    "ico": "Icon Image",
    # Documents
    "pdf": "PDF Document",
    "docx": "Word Document (.docx)",
    "pptx": "PowerPoint Deck (.pptx)",
    "xlsx": "Excel Spreadsheet (.xlsx)",
    "ods": "OpenDocument (.ods)",
    "csv": "CSV Spreadsheet",
    "tsv": "TSV Spreadsheet",
    "txt": "Plain Text (.txt)",
    "md": "Markdown Document (.md)",
    "epub": "EPUB E-Book (.epub)",
    "html": "HTML Document (.html)",
    "rtf": "Rich Text Document (.rtf)",
    # Media
    "mp4": "MP4 Video",
    "mov": "QuickTime Video (.mov)",
    "mkv": "Matroska Video (.mkv)",
    "webm": "WebM Video (.webm)",
    "avi": "AVI Video (.avi)",
    "wmv": "WMV Video (.wmv)",
    "mp3": "MP3 Audio",
    "m4a": "AAC Audio (.m4a)",
    "wav": "WAV Audio",
    "flac": "FLAC Lossless Audio",
    "ogg": "Ogg Vorbis Audio",
    "opus": "Opus Audio",
    "aiff": "AIFF Audio",
    "wma": "WMA Audio",
    # Archives & Subtitles
    "zip": "ZIP Archive",
    "tar": "TAR Archive",
    "gz": "GZ Archive",
    "srt": "SubRip Subtitles (.srt)",
    "vtt": "WebVTT Subtitles (.vtt)",
}


def get_friendly_format_name(ext: str) -> str:
    norm = ext.lower().lstrip(".")
    return FORMAT_DESCRIPTIONS.get(norm, f"{norm.upper()} File")


class MainWindow(QMainWindow):
    """FileTool primary application window."""

    settings_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileTool")
        self.resize(840, 600)
        self.setMinimumSize(680, 480)

        # Settings state
        self.custom_output_dir: Optional[Path] = None
        self.delete_original: bool = False
        self.overwrite_files: bool = False
        self.dark_mode: bool = True

        # Runner
        self.runner = JobRunner(max_threads=4)
        self.runner.job_updated.connect(self._on_job_updated)
        self.runner.all_completed.connect(self._on_all_completed)

        self._init_menu()
        self._init_ui()
        self._apply_theme()

    def _init_menu(self) -> None:
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        act_open = QAction("&Choose Files…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._browse_files)
        file_menu.addAction(act_open)

        act_convert_all = QAction("&Convert All", self)
        act_convert_all.setShortcut(QKeySequence("Ctrl+Return"))
        act_convert_all.triggered.connect(self._start_all_jobs)
        file_menu.addAction(act_convert_all)

        act_clear = QAction("C&lear Completed", self)
        act_clear.triggered.connect(self._clear_completed)
        file_menu.addAction(act_clear)

        file_menu.addSeparator()
        act_prefs = QAction("&Preferences…", self)
        act_prefs.setShortcut(QKeySequence("Ctrl+,"))
        act_prefs.triggered.connect(self._open_settings)
        file_menu.addAction(act_prefs)

        file_menu.addSeparator()
        act_close = QAction("&Close Window", self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        # View Menu
        view_menu = menubar.addMenu("&View")
        self.act_toggle_options = QAction("Toggle &Options Panel", self, checkable=True)
        self.act_toggle_options.setChecked(True)
        self.act_toggle_options.triggered.connect(self._toggle_options)
        view_menu.addAction(self.act_toggle_options)

        self.act_toggle_theme = QAction("Toggle &Dark/Light Mode", self)
        self.act_toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        act_deps = QAction("&Dependency Health Report…", self)
        act_deps.triggered.connect(self._show_dep_report)
        help_menu.addAction(act_deps)

        act_about = QAction("&About FileTool", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # 1. Top Action Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        # "Convert All to..." bulk dropdown
        bulk_label = QLabel("Convert all to:")
        bulk_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #8E8E93;")
        toolbar_layout.addWidget(bulk_label)

        self.bulk_combo = QComboBox()
        self.bulk_combo.setObjectName("bulkCombo")
        self.bulk_combo.setMaxVisibleItems(14)
        self.bulk_combo.setToolTip("Batch change output format for all matching queued files")
        self._update_bulk_combo_formats()
        self.bulk_combo.activated.connect(self._apply_bulk_format)
        toolbar_layout.addWidget(self.bulk_combo)

        toolbar_layout.addStretch()

        # Add more files button
        self.add_btn = QPushButton("+ Add Files")
        self.add_btn.clicked.connect(self._browse_files)
        toolbar_layout.addWidget(self.add_btn)

        # Clear Completed button
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self._clear_completed)
        toolbar_layout.addWidget(self.clear_btn)

        # Convert All button
        self.convert_all_btn = QPushButton("Convert All")
        self.convert_all_btn.setObjectName("primaryButton")
        self.convert_all_btn.clicked.connect(self._start_all_jobs)
        toolbar_layout.addWidget(self.convert_all_btn)

        main_layout.addLayout(toolbar_layout)

        # 2. Main Tabbed or Stacked Display: Queue & History
        self.tabs = QTabWidget()

        # Tab 1: Queue (DropZone or JobList)
        queue_widget = QWidget()
        queue_layout = QVBoxLayout(queue_widget)
        queue_layout.setContentsMargins(0, 8, 0, 0)
        queue_layout.setSpacing(10)

        # Splitter between Queue List and Options Panel
        self.splitter = QSplitter(Qt.Horizontal)

        # Left: JobList or Dropzone
        self.stack = QStackedWidget()
        self.dropzone = DropZone()
        self.dropzone.files_dropped.connect(self._on_files_dropped)
        self.stack.addWidget(self.dropzone)  # Index 0: Dropzone

        self.job_list = JobListWidget()
        self.job_list.cancel_job.connect(self.runner.cancel_job)
        self.job_list.remove_job.connect(self._on_remove_job)
        self.stack.addWidget(self.job_list)  # Index 1: Job list

        self.splitter.addWidget(self.stack)

        # Right: Options Drawer
        self.options_panel = OptionsPanel()
        self.options_panel.setFixedWidth(280)
        self.splitter.addWidget(self.options_panel)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)

        queue_layout.addWidget(self.splitter)
        self.tabs.addTab(queue_widget, "Queue")

        # Tab 2: History
        self.history_panel = HistoryPanel()
        self.tabs.addTab(self.history_panel, "History")

        main_layout.addWidget(self.tabs, stretch=1)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status()

    def _apply_theme(self) -> None:
        self.setStyleSheet(get_stylesheet(dark_mode=self.dark_mode))

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _toggle_options(self, checked: bool) -> None:
        self.options_panel.setVisible(checked)

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Files to Convert",
            str(Path.home()),
            "All Supported Files (*.*)",
        )
        if files:
            self._on_files_dropped([Path(f) for f in files])

    def _on_files_dropped(self, paths: List[Path]) -> None:
        """Handle newly dropped/selected files."""
        current_options = self.options_panel.get_options()

        added_any = False
        for path in paths:
            if not path.is_file():
                continue

            in_ext = path.suffix.lower().lstrip(".")
            outputs = registry.list_outputs(in_ext)
            if not outputs:
                logger.info("Skipping unsupported format .%s (%s)", in_ext, path.name)
                continue

            job = ConversionJob(
                src_path=path,
                dest_ext=outputs[0],
                target_dir=self.custom_output_dir,
                options=dict(current_options),
                overwrite=self.overwrite_files,
                delete_original=self.delete_original,
            )
            self.runner.add_job(job)
            self.job_list.add_job_row(job)
            added_any = True

        if added_any or len(self.runner.jobs) > 0:
            self.stack.setCurrentIndex(1)  # Show JobList

        self._update_bulk_combo_formats()
        self._update_status()

    def _update_bulk_combo_formats(self) -> None:
        """Populate bulk conversion combo with clean format descriptions and counts."""
        self.bulk_combo.blockSignals(True)
        self.bulk_combo.clear()
        self.bulk_combo.addItem("Select format…", None)

        pending_jobs = [
            j for j in self.runner.jobs.values()
            if j.status == JobStatus.PENDING
        ]
        if not pending_jobs:
            self.bulk_combo.setEnabled(False)
            self.bulk_combo.blockSignals(False)
            return

        self.bulk_combo.setEnabled(True)
        total_pending = len(pending_jobs)

        # Count how many pending jobs can convert to each target format
        target_counts: Dict[str, int] = {}
        for job in pending_jobs:
            in_ext = job.src_path.suffix.lower().lstrip(".")
            for out in registry.list_outputs(in_ext):
                target_counts[out] = target_counts.get(out, 0) + 1

        # Sort: universal matches (applies to ALL pending files) first, then by count descending, then alphabetical
        def _sort_key(item: Tuple[str, int]):
            out_ext, count = item
            is_universal = (count == total_pending)
            return (0 if is_universal else 1, -count, out_ext)

        for out, count in sorted(target_counts.items(), key=_sort_key):
            friendly = get_friendly_format_name(out)
            if total_pending > 1:
                if count == total_pending:
                    label = f"{out.upper()}  —  {friendly}  (all {count} files)"
                else:
                    label = f"{out.upper()}  —  {friendly}  ({count} of {total_pending} files)"
            else:
                label = f"{out.upper()}  —  {friendly}"

            self.bulk_combo.addItem(label, out)

        self.bulk_combo.blockSignals(False)

    def _apply_bulk_format(self, index: int) -> None:
        out_ext = self.bulk_combo.currentData()
        if not out_ext:
            return

        applied_count = 0
        for row in self.job_list.rows.values():
            if row.job.status == JobStatus.PENDING:
                in_ext = row.job.src_path.suffix.lower().lstrip(".")
                if registry.is_supported(in_ext, out_ext):
                    idx = row.format_picker.findData(out_ext)
                    if idx >= 0:
                        row.format_picker.setCurrentIndex(idx)
                        applied_count += 1

        if applied_count > 0:
            friendly = get_friendly_format_name(out_ext)
            file_word = "file" if applied_count == 1 else "files"
            self.status_bar.showMessage(
                f"Changed {applied_count} {file_word} to {out_ext.upper()} ({friendly})",
                5000,
            )

    def _start_all_jobs(self) -> None:
        # Sync latest options before start
        current_options = self.options_panel.get_options()
        for job in self.runner.jobs.values():
            if job.status in (JobStatus.PENDING, JobStatus.FAILED):
                job.options.update(current_options)
                job.target_dir = self.custom_output_dir
                job.overwrite = self.overwrite_files
                job.delete_original = self.delete_original

        self.runner.start_all()
        self._update_status()

    def _on_job_updated(self, job_id: str) -> None:
        self.job_list.update_job_row(job_id)
        job = self.runner.jobs.get(job_id)
        if job and job.status == JobStatus.SUCCESS and job.dest_path:
            self.history_panel.add_entry(job.src_path, job.dest_path)
        self._update_status()

    def _on_all_completed(self) -> None:
        self._update_status()

    def _on_remove_job(self, job_id: str) -> None:
        self.job_list.remove_job_row(job_id)
        if job_id in self.runner.jobs:
            del self.runner.jobs[job_id]
        if len(self.runner.jobs) == 0:
            self.stack.setCurrentIndex(0)  # Return to Dropzone
        self._update_status()

    def _clear_completed(self) -> None:
        to_del = [
            jid for jid, job in self.runner.jobs.items()
            if job.status in (JobStatus.SUCCESS, JobStatus.CANCELLED)
        ]
        for jid in to_del:
            self._on_remove_job(jid)

    def _update_status(self) -> None:
        total = len(self.runner.jobs)
        running = sum(1 for j in self.runner.jobs.values() if j.status == JobStatus.RUNNING)
        success = sum(1 for j in self.runner.jobs.values() if j.status == JobStatus.SUCCESS)
        failed = sum(1 for j in self.runner.jobs.values() if j.status == JobStatus.FAILED)

        if total == 0:
            self.status_bar.showMessage("Ready. Drag files in to begin.")
        else:
            self.status_bar.showMessage(
                f"{total} files in queue • {running} running • {success} completed • {failed} failed"
            )

    def _open_settings(self) -> None:
        dlg = SettingsDialog(
            custom_out_dir=self.custom_output_dir,
            delete_original=self.delete_original,
            overwrite=self.overwrite_files,
            parent=self,
        )
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self, s: dict) -> None:
        self.custom_output_dir = s["output_dir"]
        self.delete_original = s["delete_original"]
        self.overwrite_files = s["overwrite"]
        self.settings_updated.emit(s)

    def closeEvent(self, event) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        else:
            event.accept()

    def _show_dep_report(self) -> None:
        report = format_dependency_report()
        dlg = QDialog(self)
        dlg.setWindowTitle("External Tool Dependencies")
        dlg.resize(550, 360)
        vbox = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(report)
        txt.setStyleSheet("font-family: monospace; font-size: 11px;")
        vbox.addWidget(txt)
        btn = QPushButton("OK")
        btn.clicked.connect(dlg.accept)
        vbox.addWidget(btn)
        dlg.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FileTool",
            "<h3>FileTool for macOS</h3>"
            "<p>A powerful, 100% offline, native desktop file utility designed for macOS users.</p>"
            "<p><b>Features:</b> Zero network access, multi-threaded batch conversions, "
            "safe non-overwriting filenames, and native Apple Silicon acceleration.</p>"
            "<p>Version 1.0.0</p>",
        )
