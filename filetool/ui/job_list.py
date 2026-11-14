"""Job list table/card view showing file rows, format pickers, progress, and actions."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from filetool.core.registry import registry
from filetool.core.runner import ConversionJob, JobStatus
from filetool.ui.actions import copy_file_path, open_in_terminal, reveal_in_finder
from filetool.ui.components import IconWidget, icon_name_for_category
from filetool.ui.styles import get_tokens


class ErrorDetailsDialog(QDialog):
    """Clean human-readable modal dialog showing conversion error and stderr tail."""

    def __init__(self, job: ConversionJob, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Conversion Error - {job.filename}")
        self.resize(550, 360)
        self._init_ui(job)

    def _init_ui(self, job: ConversionJob) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(f"Failed to convert <b>{job.filename}</b> to .{job.dest_ext.upper()}")
        title.setObjectName("errorTitle")
        layout.addWidget(title)

        reason = QLabel(job.error_message or "Unknown conversion error")
        reason.setWordWrap(True)
        layout.addWidget(reason)

        if job.stderr_tail:
            lbl = QLabel("Tool Diagnostics (Stderr):")
            lbl.setStyleSheet("font-weight: 600; font-size: 12px; margin-top: 6px;")
            layout.addWidget(lbl)

            log_box = QTextEdit()
            log_box.setReadOnly(True)
            log_box.setPlainText(job.stderr_tail)
            log_box.setStyleSheet(
                "background-color: #121214; color: #30D158; font-family: monospace; font-size: 11px;"
            )
            layout.addWidget(log_box)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class JobRow(QFrame):
    """Individual file conversion card/row."""

    cancel_clicked = Signal(str)
    remove_clicked = Signal(str)
    format_changed = Signal(str, str)

    def __init__(self, job: ConversionJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setObjectName("jobCard")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        in_ext = self.job.src_path.suffix.lower().lstrip(".")
        category = registry.get_category_for_ext(in_ext)
        self.icon_label = IconWidget(
            icon_name_for_category(category),
            size=20,
            color=QColor(get_tokens(False)["text_secondary"]),
        )
        top_layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.name_label = QLabel(self.job.filename)
        self.name_label.setObjectName("jobFilename")
        self.name_label.setToolTip(str(self.job.src_path))
        info_layout.addWidget(self.name_label)

        self.size_label = QLabel(self.job.file_size_str)
        self.size_label.setObjectName("mutedMeta")
        info_layout.addWidget(self.size_label)
        top_layout.addLayout(info_layout, stretch=1)

        self.badge = QLabel(in_ext.upper())
        self.badge.setObjectName("badge")
        top_layout.addWidget(self.badge)

        arrow_label = QLabel("->")
        arrow_label.setObjectName("mutedMeta")
        top_layout.addWidget(arrow_label)

        self.format_picker = QComboBox()
        self._populate_formats(in_ext)
        self.format_picker.currentTextChanged.connect(self._on_format_changed)
        top_layout.addWidget(self.format_picker)

        self.reveal_btn = QPushButton("Reveal")
        self.reveal_btn.setVisible(False)
        self.reveal_btn.clicked.connect(self._on_reveal)
        top_layout.addWidget(self.reveal_btn)

        self.details_btn = QPushButton("Details")
        self.details_btn.setObjectName("dangerLink")
        self.details_btn.setVisible(False)
        self.details_btn.clicked.connect(self._on_details)
        top_layout.addWidget(self.details_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.job.id))
        top_layout.addWidget(self.cancel_btn)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("iconButton")
        self.remove_btn.setToolTip("Remove from list")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.job.id))
        top_layout.addWidget(self.remove_btn)

        main_layout.addLayout(top_layout)

        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.job.progress)
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel(self.job.status.value)
        self.status_label.setObjectName("mutedMeta")
        bottom_layout.addWidget(self.status_label)

        main_layout.addLayout(bottom_layout)

    def _populate_formats(self, in_ext: str) -> None:
        self.format_picker.blockSignals(True)
        self.format_picker.clear()
        op = getattr(self.job, "operation", "convert")
        if op != "convert":
            # Same-format tools (resize/compress) keep the source extension
            self.format_picker.addItem(f"{op.title()} .{in_ext.upper()}", self.job.dest_ext or in_ext)
            self.format_picker.setEnabled(False)
            self.format_picker.blockSignals(False)
            return

        outputs = registry.list_outputs(in_ext)
        for out in outputs:
            self.format_picker.addItem(f".{out.upper()}", out)

        if outputs:
            if self.job.dest_ext not in outputs:
                self.job.dest_ext = outputs[0]
            self.format_picker.setCurrentIndex(outputs.index(self.job.dest_ext))
        self.format_picker.blockSignals(False)

    def _on_format_changed(self, text: str) -> None:
        dest_ext = self.format_picker.currentData()
        if dest_ext:
            self.job.dest_ext = dest_ext
            self.format_changed.emit(self.job.id, dest_ext)

    _STATUS_VIEW_STATE = {
        JobStatus.RUNNING: (True, True, False, False, False, "statusRunning"),
        JobStatus.SUCCESS: (True, False, True, True, False, "statusSuccess"),
        JobStatus.FAILED: (False, False, True, False, True, "statusError"),
        JobStatus.CANCELLED: (False, False, True, None, None, "mutedMeta"),
    }

    def update_view(self) -> None:
        """Refresh controls and status styling from job state."""
        status = self.job.status
        self.status_label.setText(status.value)
        self.progress_bar.setValue(self.job.progress)

        state = self._STATUS_VIEW_STATE.get(status)
        if state is None:
            show_progress, show_cancel, show_remove, show_reveal, show_details, obj_name = (
                False, False, True, None, None, "mutedMeta",
            )
            self.format_picker.setEnabled(getattr(self.job, "operation", "convert") == "convert")
        else:
            show_progress, show_cancel, show_remove, show_reveal, show_details, obj_name = state
            if status == JobStatus.RUNNING:
                self.format_picker.setEnabled(False)

        self.progress_bar.setVisible(show_progress)
        self.cancel_btn.setVisible(show_cancel)
        self.remove_btn.setVisible(show_remove)
        if show_reveal is not None:
            self.reveal_btn.setVisible(show_reveal)
        if show_details is not None:
            self.details_btn.setVisible(show_details)
        if self.status_label.objectName() != obj_name:
            self.status_label.setObjectName(obj_name)
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)

    def set_dark_mode(self, is_dark: bool) -> None:
        self.icon_label.set_color(QColor(get_tokens(is_dark)["text_secondary"]))

    def _on_reveal(self) -> None:
        if self.job.dest_path and self.job.dest_path.exists():
            reveal_in_finder(self.job.dest_path)
        else:
            reveal_in_finder(self.job.src_path)

    def _on_details(self) -> None:
        dlg = ErrorDetailsDialog(self.job, self)
        dlg.exec()

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        target_path = self.job.dest_path if (self.job.dest_path and self.job.dest_path.exists()) else self.job.src_path

        act_reveal = menu.addAction("Reveal in Finder")
        act_reveal.triggered.connect(lambda: reveal_in_finder(target_path))

        act_copy = menu.addAction("Copy File Path")
        act_copy.triggered.connect(lambda: copy_file_path(target_path))

        act_term = menu.addAction("Open Containing Folder in Terminal")
        act_term.triggered.connect(lambda: open_in_terminal(target_path))

        menu.exec(self.mapToGlobal(pos))


class JobListWidget(QScrollArea):
    """Scrollable list of conversion jobs."""

    cancel_job = Signal(str)
    remove_job = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.rows: Dict[str, JobRow] = {}

        self.container = QWidget()
        self.container.setObjectName("scrollBody")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)
        self.layout.addStretch()

        self.setWidget(self.container)

    def add_job_row(self, job: ConversionJob) -> JobRow:
        row = JobRow(job, self.container)
        row.cancel_clicked.connect(self.cancel_job.emit)
        row.remove_clicked.connect(self.remove_job.emit)

        # Insert before stretch
        self.layout.insertWidget(self.layout.count() - 1, row)
        self.rows[job.id] = row
        return row

    def update_job_row(self, job_id: str) -> None:
        if job_id in self.rows:
            self.rows[job_id].update_view()

    def remove_job_row(self, job_id: str) -> None:
        if job_id in self.rows:
            row = self.rows.pop(job_id)
            self.layout.removeWidget(row)
            row.deleteLater()

    def set_all_formats(self, in_ext: str, out_ext: str) -> None:
        """Update destination format for all jobs sharing an input extension."""
        for row in self.rows.values():
            row_in = row.job.src_path.suffix.lower().lstrip(".")
            if row_in == in_ext and row.job.status == JobStatus.PENDING:
                idx = row.format_picker.findData(out_ext)
                if idx >= 0:
                    row.format_picker.setCurrentIndex(idx)

    _FILTER_STATUS_MAP = {
        "pending": JobStatus.PENDING,
        "running": JobStatus.RUNNING,
        "completed": JobStatus.SUCCESS,
        "failed": JobStatus.FAILED,
    }

    def apply_filter(self, status_filter: str = "all", query: str = "") -> None:
        """Filter visible rows by status category and search substring."""
        norm_status = status_filter.strip().lower()
        target_status = self._FILTER_STATUS_MAP.get(norm_status)
        q = query.strip().lower()
        for row in self.rows.values():
            status_match = norm_status == "all" or row.job.status == target_status
            name_match = not q or q in row.job.filename.lower() or q in row.job.dest_ext.lower()
            row.setVisible(status_match and name_match)

    def set_dark_mode(self, is_dark: bool) -> None:
        for row in self.rows.values():
            row.set_dark_mode(is_dark)
