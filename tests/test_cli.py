"""Tests for FileTool CLI interface."""

from __future__ import annotations

from pathlib import Path
from filetool.cli import main
from filetool.core.utils import get_unique_output_path


def test_unique_output_path(tmp_path: Path):
    """Verify non-overwriting naming produces 'file (1).ext' and 'file (2).ext'."""
    test_file = tmp_path / "document.pdf"
    test_file.write_text("initial")

    path1 = get_unique_output_path(test_file)
    assert path1.name == "document (1).pdf"
    path1.write_text("second")

    path2 = get_unique_output_path(test_file)
    assert path2.name == "document (2).pdf"


def test_cli_check_deps(capsys):
    """Verify cli --check-deps executes and prints report."""
    code = main(["--check-deps"])
    captured = capsys.readouterr()
    assert code == 0
    assert "FileTool External Dependency Health:" in captured.out


def test_cli_list_formats(samples_dir: Path, capsys):
    """Verify cli --list-formats displays outputs for an input file."""
    src = samples_dir / "sample.png"
    code = main([str(src), "--list-formats"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Available output formats for .png:" in captured.out
    assert "JPG" in captured.out


def test_cli_convert_file(samples_dir: Path, tmp_path: Path):
    """Verify full CLI conversion runs end-to-end."""
    src = samples_dir / "sample.png"
    code = main([str(src), "--to", "jpg", "--out-dir", str(tmp_path), "--quality", "80"])
    assert code == 0
    expected_out = tmp_path / "sample.jpg"
    assert expected_out.exists()
    assert expected_out.stat().st_size > 0
