"""Tests for external tool resolver and dependency checking."""

from __future__ import annotations

import sys
from pathlib import Path
from filetool.core.deps import ToolResolver, check_dependencies, format_dependency_report, resolver


def test_resolver_finds_essential_tools():
    """Verify that essential installed tools are located by ToolResolver."""
    for tool in ("ffmpeg", "ffprobe", "magick", "sips", "pandoc", "soffice", "pdftoppm", "pdftotext", "gs", "7zz"):
        path = resolver.resolve(tool)
        assert path is not None, f"Expected {tool} to be resolved"
        assert path.exists(), f"Path {path} does not exist"
        assert path.is_file(), f"Path {path} is not a file"


def test_resolver_custom_paths(tmp_path):
    """Verify ToolResolver respects custom search paths."""
    fake_bin = tmp_path / "custom_bin"
    fake_bin.mkdir()
    fake_tool = fake_bin / "mytool"
    fake_tool.write_text("#!/bin/sh\necho 1.0\n")
    fake_tool.chmod(0o755)

    custom_resolver = ToolResolver(search_paths=[fake_bin])
    resolved = custom_resolver.resolve("mytool")
    assert resolved == fake_tool


def test_dependency_report_string():
    """Verify format_dependency_report returns readable health text."""
    report = format_dependency_report()
    assert "FileTool External Dependency Health:" in report
    assert "ffmpeg" in report
    assert "magick" in report
    assert "soffice" in report
