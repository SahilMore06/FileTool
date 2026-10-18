"""Job list table/card view showing file rows, format pickers, progress, and actions."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
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
        title.setStyleSheet("font-size: 14px; color: #FF453A;")
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

        # Top row: Icon, Name, Size, Input Type Badge, Output Picker, Action Buttons
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        # Category icon
        in_ext = self.job.src_path.suffix.lower().lstrip(".")
        category = registry.get_category_for_ext(in_ext)
        icon_map = {
            "Images": "🖼️",
            "Audio": "🎵",
            "Video": "🎬",
            "Documents": "📄",
            "Slides": "📊",
            "Spreadsheets": "📈",
            "Subtitles": "💬",
            "Archives": "📦",
        }
        self.icon_label = QLabel(icon_map.get(category, "📁"))
        self.icon_label.setStyleSheet("font-size: 18px;")
        top_layout.addWidget(self.icon_label)

        # Filename & size
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.name_label = QLabel(self.job.filename)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.name_label.setToolTip(str(self.job.src_path))
        info_layout.addWidget(self.name_label)

        self.size_label = QLabel(self.job.file_size_str)
        self.size_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        info_layout.addWidget(self.size_label)
        top_layout.addLayout(info_layout, stretch=1)

        # Input Format Badge
        self.badge = QLabel(in_ext.upper())
        self.badge.setObjectName("badge")
        top_layout.addWidget(self.badge)

        # Arrow
        arrow_label = QLabel("➔")
        arrow_label.setStyleSheet("color: #8E8E93; font-weight: bold;")
        top_layout.addWidget(arrow_label)

        # Target Format Picker (QComboBox)
        self.format_picker = QComboBox()
        self._populate_formats(in_ext)
        self.format_picker.currentTextChanged.connect(self._on_format_changed)
        top_layout.addWidget(self.format_picker)

        # Action Buttons: Cancel, Reveal, Details, Remove
        self.reveal_btn = QPushButton("Reveal")
        self.reveal_btn.setVisible(False)
        self.reveal_btn.clicked.connect(self._on_reveal)
        top_layout.addWidget(self.reveal_btn)

        self.details_btn = QPushButton("Details")
        self.details_btn.setStyleSheet("color: #FF453A;")
        self.details_btn.setVisible(False)
        self.details_btn.clicked.connect(self._on_details)
        top_layout.addWidget(self.details_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.job.id))
        top_layout.addWidget(self.cancel_btn)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setToolTip("Remove from list")
        self.remove_btn.setFixedWidth(28)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.job.id))
        top_layout.addWidget(self.remove_btn)

        main_layout.addLayout(top_layout)

        # Bottom row: Progress bar & status message
        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.job.progress)
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel(self.job.status.value)
        self.status_label.setStyleSheet("font-size: 11px; color: #8E8E93;")
        bottom_layout.addWidget(self.status_label)

        main_layout.addLayout(bottom_layout)

    def _populate_formats(self, in_ext: str) -> None:
        outputs = registry.list_outputs(in_ext)
        self.format_picker.clear()
        for out in outputs:
            self.format_picker.addItem(f".{out.upper()}", out)

        # Select first or matching default
        if outputs:
            self.job.dest_ext = outputs[0]
            self.format_picker.setCurrentIndex(0)

    def _on_format_changed(self, text: str) -> None:
        dest_ext = self.format_picker.currentData()
        if dest_ext:
            self.job.dest_ext = dest_ext
            self.format_changed.emit(self.job.id, dest_ext)

    def update_view(self) -> None:
        """Refresh UI state based on job status."""
        self.status_label.setText(self.job.status.value)
        self.progress_bar.setValue(self.job.progress)

        if self.job.status == JobStatus.RUNNING:
            self.progress_bar.setVisible(True)
            self.cancel_btn.setVisible(True)
            self.remove_btn.setVisible(False)
            self.format_picker.setEnabled(False)
            self.status_label.setStyleSheet("font-size: 11px; color: #FF9500; font-weight: 500;")
        elif self.job.status == JobStatus.SUCCESS:
            self.progress_bar.setVisible(True)
            self.cancel_btn.setVisible(False)
            self.remove_btn.setVisible(True)
            self.reveal_btn.setVisible(True)
            self.details_btn.setVisible(False)
            self.status_label.setStyleSheet("font-size: 11px; color: #30D158; font-weight: 600;")
        elif self.job.status == JobStatus.FAILED:
            self.progress_bar.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.remove_btn.setVisible(True)
            self.reveal_btn.setVisible(False)
            self.details_btn.setVisible(True)
            self.status_label.setStyleSheet("font-size: 11px; color: #FF453A; font-weight: 600;")
        elif self.job.status == JobStatus.CANCELLED:
            self.progress_bar.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.remove_btn.setVisible(True)
            self.status_label.setStyleSheet("font-size: 11px; color: #8E8E93;")
        else:  # PENDING
            self.progress_bar.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.remove_btn.setVisible(True)
            self.format_picker.setEnabled(True)
            self.status_label.setStyleSheet("font-size: 11px; color: #8E8E93;")

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
