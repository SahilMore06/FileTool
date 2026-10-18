"""Drag-and-drop zone widget supporting multiple files and recursive folders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DropZone(QFrame):
    """Interactive drag-and-drop landing area for files and folders."""

    files_dropped = Signal(list)  # List[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        # Drop icon
        self.icon_label = QLabel("🍊")
        self.icon_label.setStyleSheet("font-size: 48px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)

        # Main Title
        self.title_label = QLabel("Drag & Drop files or folders here")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Subtitle
        self.sub_label = QLabel("All processing happens offline and locally on your Mac")
        self.sub_label.setObjectName("dropSubtitle")
        self.sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sub_label)

        # "Choose Files..." button
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        self.browse_btn = QPushButton("Choose Files…")
        self.browse_btn.setObjectName("primaryButton")
        self.browse_btn.setToolTip("Browse files (Cmd+O)")
        self.browse_btn.clicked.connect(self._open_file_dialog)
        btn_layout.addWidget(self.browse_btn)

        layout.addLayout(btn_layout)

        # Shortcut Cmd+O
        self.shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut.activated.connect(self._open_file_dialog)

    def _open_file_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Files to Convert",
            str(Path.home()),
            "All Files (*.*)",
        )
        if files:
            paths = [Path(f) for f in files]
            self.files_dropped.emit(paths)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hovered", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        if not urls:
            return

        collected_paths: List[Path] = []
        for url in urls:
            local_path = Path(url.toLocalFile()).resolve()
            if not local_path.exists():
                continue

            if local_path.is_file():
                # Avoid hidden system metadata files (.DS_Store)
                if not local_path.name.startswith("."):
                    collected_paths.append(local_path)
            elif local_path.is_dir():
                # Recursively discover files in directory
                for root, _, files in os.walk(local_path):
                    for fname in files:
                        if not fname.startswith("."):
                            collected_paths.append(Path(root) / fname)

        if collected_paths:
            self.files_dropped.emit(collected_paths)
            event.acceptProposedAction()
