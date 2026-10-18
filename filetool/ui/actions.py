"""macOS native file actions: Reveal in Finder, Copy Path, Open in Terminal."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from PySide6.QtGui import QGuiApplication

logger = logging.getLogger("filetool.actions")


def reveal_in_finder(path: Path | str) -> bool:
    """Reveal the given file or folder in macOS Finder."""
    p = Path(path).resolve()
    if not p.exists():
        logger.warning("Cannot reveal non-existent path: %s", p)
        return False

    try:
        subprocess.run(["open", "-R", str(p)], check=True)
        return True
    except Exception as exc:
        logger.error("Failed revealing path in Finder: %s", exc)
        return False


def copy_file_path(path: Path | str) -> bool:
    """Copy the file's absolute path to the system clipboard."""
    p = str(Path(path).resolve())
    clipboard = QGuiApplication.clipboard()
    if clipboard:
        clipboard.setText(p)
        return True
    return False


def open_in_terminal(path: Path | str) -> bool:
    """Open the containing directory of the file in macOS Terminal."""
    p = Path(path).resolve()
    target_dir = p if p.is_dir() else p.parent

    try:
        subprocess.run(["open", "-a", "Terminal", str(target_dir)], check=True)
        return True
    except Exception as exc:
        logger.error("Failed opening folder in Terminal: %s", exc)
        return False
