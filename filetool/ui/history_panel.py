"""Conversion history view with Reveal in Finder, Copy Path, and Open in Terminal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from filetool.ui.actions import copy_file_path, open_in_terminal, reveal_in_finder


class HistoryPanel(QFrame):
    """Panel displaying record of past conversions with direct file actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Conversion History")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(self._clear_history)
        header_layout.addWidget(self.clear_btn)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Source File",
            "Output File",
            "Size",
            "Completed At",
            "Actions",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

    def add_entry(self, src: Path, dest: Path) -> None:
        """Add completed conversion item to history table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 1. Source
        src_item = QTableWidgetItem(src.name)
        src_item.setToolTip(str(src))
        self.table.setItem(row, 0, src_item)

        # 2. Output
        dest_item = QTableWidgetItem(dest.name)
        dest_item.setToolTip(str(dest))
        self.table.setItem(row, 1, dest_item)

        # 3. Size
        size_str = "0 B"
        if dest.exists():
            bytes_val = dest.stat().st_size
            for u in ("B", "KB", "MB", "GB"):
                if bytes_val < 1024.0:
                    size_str = f"{bytes_val:.1f} {u}" if u != "B" else f"{bytes_val} B"
                    break
                bytes_val /= 1024.0
        self.table.setItem(row, 2, QTableWidgetItem(size_str))

        # 4. Timestamp
        now_str = datetime.now().strftime("%H:%M:%S")
        self.table.setItem(row, 3, QTableWidgetItem(now_str))

        # 5. Actions (Reveal button)
        action_widget = QFrame()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(6)

        reveal_btn = QPushButton("Reveal")
        reveal_btn.setToolTip("Reveal in Finder")
        reveal_btn.clicked.connect(lambda _, p=dest: reveal_in_finder(p))
        action_layout.addWidget(reveal_btn)

        copy_btn = QPushButton("Copy Path")
        copy_btn.clicked.connect(lambda _, p=dest: copy_file_path(p))
        action_layout.addWidget(copy_btn)

        term_btn = QPushButton("Terminal")
        term_btn.clicked.connect(lambda _, p=dest: open_in_terminal(p))
        action_layout.addWidget(term_btn)

        self.table.setCellWidget(row, 4, action_widget)

    def _clear_history(self) -> None:
        self.table.setRowCount(0)
