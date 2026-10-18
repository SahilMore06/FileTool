"""Tests for Subtitles (SRT, VTT, TXT) and Archives (ZIP, TAR, GZ, RAR)."""

from __future__ import annotations

from pathlib import Path
import pytest
import filetool.core  # loads all engines
from filetool.core.engines.archives import extract_archive
from filetool.core.registry import registry


@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("srt", "vtt"),
        ("srt", "txt"),
        ("vtt", "srt"),
        ("vtt", "txt"),
    ],
)
def test_subtitle_conversions(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test subtitle format conversions."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists()

    dest_file = tmp_path / f"converted_sub_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None

    out = conv.convert_fn(src_file, dest_file, {})
    assert out.exists()
    assert out.stat().st_size > 0
    content = out.read_text(encoding="utf-8")
    assert "Hello and welcome" in content


@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("zip", "tar"),
        ("zip", "gz"),
        ("tar", "zip"),
        ("gz", "zip"),
    ],
)
def test_archive_conversions(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test archive repacking between container formats."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists()

    dest_file = tmp_path / f"converted_arch_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {})
    assert out.exists()
    assert out.stat().st_size > 0


def test_extract_archive(samples_dir: Path, tmp_path: Path):
    """Test extracting archive contents to a target folder."""
    src_file = samples_dir / "sample.zip"
    extract_target = tmp_path / "extracted_folder"
    out_dir = extract_archive(src_file, extract_target)
    assert out_dir.exists()
    extracted_file = out_dir / "test_in_zip.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text(encoding="utf-8") == "Archive payload"
