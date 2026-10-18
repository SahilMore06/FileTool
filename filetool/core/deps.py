"""Tool resolver and dependency health checker for external local binaries."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from filetool.core.utils import run_command

logger = logging.getLogger("filetool.deps")

# Search directories in strict priority order
DEFAULT_SEARCH_PATHS = [
    # 1. App bundle Resources (when packaged with PyInstaller or py2app)
    Path(sys.executable).resolve().parent.parent / "Resources" / "bin",
    Path(__file__).resolve().parent.parent / "resources" / "bin",
    # 2. Apple Silicon Homebrew
    Path("/opt/homebrew/bin"),
    # 3. Intel Homebrew / local custom
    Path("/usr/local/bin"),
    # 4. macOS System
    Path("/usr/bin"),
    # 5. LibreOffice macOS installation
    Path("/Applications/LibreOffice.app/Contents/MacOS"),
    Path.home() / "Applications/LibreOffice.app/Contents/MacOS",
]


@dataclass
class ToolDefinition:
    name: str
    aliases: tuple[str, ...]
    version_arg: list[str]
    purpose: str
    install_command: str


TOOLS_METADATA: dict[str, ToolDefinition] = {
    "ffmpeg": ToolDefinition(
        name="ffmpeg",
        aliases=("ffmpeg",),
        version_arg=["-version"],
        purpose="Audio and video transcoding, extraction, and trimming",
        install_command="brew install ffmpeg",
    ),
    "ffprobe": ToolDefinition(
        name="ffprobe",
        aliases=("ffprobe",),
        version_arg=["-version"],
        purpose="Audio and video stream analysis and inspection",
        install_command="brew install ffmpeg",
    ),
    "magick": ToolDefinition(
        name="magick",
        aliases=("magick", "convert"),
        version_arg=["-version"],
        purpose="Advanced image format processing and transformations",
        install_command="brew install imagemagick",
    ),
    "sips": ToolDefinition(
        name="sips",
        aliases=("sips",),
        version_arg=["--version"],
        purpose="macOS built-in Scriptable Image Processing System",
        install_command="Built-in on macOS (/usr/bin/sips)",
    ),
    "pandoc": ToolDefinition(
        name="pandoc",
        aliases=("pandoc",),
        version_arg=["--version"],
        purpose="Universal document markup conversion (DOCX, Markdown, EPUB, HTML, RTF)",
        install_command="brew install pandoc",
    ),
    "soffice": ToolDefinition(
        name="soffice",
        aliases=("soffice", "libreoffice"),
        version_arg=["--version"],
        purpose="Headless document and spreadsheet conversion (DOCX/PPT/ODS/XLSX to PDF)",
        install_command="brew install --cask libreoffice",
    ),
    "pdftoppm": ToolDefinition(
        name="pdftoppm",
        aliases=("pdftoppm",),
        version_arg=["-v"],
        purpose="Poppler PDF high-fidelity image rendering (300 DPI JPG/PNG)",
        install_command="brew install poppler",
    ),
    "pdftotext": ToolDefinition(
        name="pdftotext",
        aliases=("pdftotext",),
        version_arg=["-v"],
        purpose="Poppler PDF text extraction",
        install_command="brew install poppler",
    ),
    "gs": ToolDefinition(
        name="gs",
        aliases=("gs", "ghostscript"),
        version_arg=["--version"],
        purpose="Ghostscript PDF processing, compression, and PostScript rendering",
        install_command="brew install ghostscript",
    ),
    "7zz": ToolDefinition(
        name="7zz",
        aliases=("7zz", "7z"),
        version_arg=["--help"],
        purpose="7-Zip archive creation, high compression, and extraction (ZIP/TAR/GZ/RAR)",
        install_command="brew install sevenzip",
    ),
}


@dataclass
class ToolStatus:
    name: str
    available: bool
    path: Optional[Path]
    version: str
    purpose: str
    install_command: str


class ToolResolver:
    """Resolves local binary paths considering app bundles, Homebrew, and system paths."""

    def __init__(self, search_paths: list[Path] | None = None):
        self.search_paths = list(search_paths) if search_paths else list(DEFAULT_SEARCH_PATHS)
        self._cache: dict[str, Optional[Path]] = {}

    def resolve(self, tool_name: str) -> Optional[Path]:
        """Find the executable path for the given tool name or its aliases."""
        if tool_name in self._cache:
            return self._cache[tool_name]

        defn = TOOLS_METADATA.get(tool_name)
        candidate_names = defn.aliases if defn else (tool_name,)

        # Check configured search directories first
        for search_dir in self.search_paths:
            if not search_dir.is_dir():
                continue
            for name in candidate_names:
                candidate = search_dir / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    self._cache[tool_name] = candidate
                    return candidate

        # Fallback to standard system PATH
        for name in candidate_names:
            found = shutil.which(name)
            if found:
                p = Path(found)
                self._cache[tool_name] = p
                return p

        self._cache[tool_name] = None
        return None

    def get_tool_path(self, tool_name: str) -> str:
        """Return the resolved string path or raise FileNotFoundError with installation hint."""
        path = self.resolve(tool_name)
        if not path:
            defn = TOOLS_METADATA.get(tool_name)
            hint = f" Install it with: `{defn.install_command}`" if defn else ""
            raise FileNotFoundError(f"Required tool '{tool_name}' not found on system.{hint}")
        return str(path)

    def check_tool(self, tool_name: str) -> ToolStatus:
        """Check availability and retrieve version info for a tool."""
        path = self.resolve(tool_name)
        defn = TOOLS_METADATA.get(
            tool_name,
            ToolDefinition(
                name=tool_name,
                aliases=(tool_name,),
                version_arg=["--version"],
                purpose="Auxiliary utility",
                install_command="brew install " + tool_name,
            ),
        )

        if not path:
            return ToolStatus(
                name=tool_name,
                available=False,
                path=None,
                version="",
                purpose=defn.purpose,
                install_command=defn.install_command,
            )

        # Query version
        res = run_command([str(path)] + defn.version_arg, timeout=3.0)
        version_line = ""
        output = res.stdout if res.stdout.strip() else res.stderr
        if output:
            version_line = output.strip().splitlines()[0][:80]

        return ToolStatus(
            name=tool_name,
            available=True,
            path=path,
            version=version_line,
            purpose=defn.purpose,
            install_command=defn.install_command,
        )

    def check_all(self) -> dict[str, ToolStatus]:
        """Check all defined tools."""
        return {name: self.check_tool(name) for name in TOOLS_METADATA}


# Global singleton instance
resolver = ToolResolver()


def get_tool(tool_name: str) -> str:
    """Convenience helper to get resolved tool path."""
    return resolver.get_tool_path(tool_name)


def check_dependencies() -> dict[str, ToolStatus]:
    """Check all dependencies and return report."""
    return resolver.check_all()


def get_missing_dependencies() -> list[ToolStatus]:
    """Return list of unavailable tools."""
    return [status for status in resolver.check_all().values() if not status.available]


def format_dependency_report() -> str:
    """Generate a clean ASCII report of system tools."""
    results = check_dependencies()
    lines = ["FileTool External Dependency Health:", "====================================="]
    for name, s in results.items():
        status_str = "✔ FOUND" if s.available else "✖ MISSING"
        path_str = f"({s.path})" if s.path else f"-> Install: `{s.install_command}`"
        lines.append(f"[{status_str:7s}] {name:10s} {path_str}")
    return "\n".join(lines)
