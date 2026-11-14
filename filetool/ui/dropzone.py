"""Drag-and-drop zone widget supporting multiple files and recursive folders."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from filetool.ui.components import IconWidget, collect_paths_from_urls


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

        self.icon_label = IconWidget("upload", size=44, color=QColor(0xBF, 0x45, 0x20))
        icon_row = QHBoxLayout()
        icon_row.setAlignment(Qt.AlignCenter)
        icon_row.addWidget(self.icon_label)
        layout.addLayout(icon_row)

        self.title_label = QLabel("Drag & Drop files or folders here")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.sub_label = QLabel(
            "Offline on your Mac · Tap Shift, Cmd, or Ctrl while dragging in Finder — release to keep wheel open"
        )
        self.sub_label.setObjectName("dropSubtitle")
        self.sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sub_label)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        self.browse_btn = QPushButton("Choose Files…")
        self.browse_btn.setObjectName("primaryButton")
        self.browse_btn.setToolTip("Browse files (Cmd+O)")
        self.browse_btn.clicked.connect(self._open_file_dialog)
        btn_layout.addWidget(self.browse_btn)

        layout.addLayout(btn_layout)

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
            self.files_dropped.emit([Path(f) for f in files])

    def set_accent_color(self, hex_color: str) -> None:
        self.icon_label.set_color(QColor(hex_color))

    def _set_hovered(self, hovered: bool) -> None:
        if bool(self.property("hovered")) == hovered:
            return
        self.setProperty("hovered", hovered)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hovered(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_hovered(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_hovered(False)

        urls = event.mimeData().urls()
        if not urls:
            return

        collected_paths = collect_paths_from_urls(urls)
        if collected_paths:
            self.files_dropped.emit(collected_paths)
            event.acceptProposedAction()
