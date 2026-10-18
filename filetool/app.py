"""GUI entry point for FileTool."""

from __future__ import annotations

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from filetool.core.utils import setup_logging
from filetool.ui.main_window import MainWindow


def main() -> int:
    setup_logging()

    # Enable native high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FileTool")
    app.setApplicationDisplayName("FileTool")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
