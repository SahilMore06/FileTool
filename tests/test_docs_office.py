"""Tests for Documents, Office Presentations, PDF, and Spreadsheets conversion."""

from __future__ import annotations

from pathlib import Path
import pytest
import filetool.core  # loads all engines
from filetool.core.registry import registry


# 1. Document conversions
@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("docx", "md"),
        ("docx", "txt"),
        ("docx", "html"),
        ("docx", "rtf"),
        ("docx", "pdf"),  # LibreOffice
        ("md", "docx"),
        ("md", "html"),
        ("md", "rtf"),
        ("md", "epub"),
        ("html", "docx"),
        ("html", "md"),
        ("rtf", "docx"),
        ("txt", "md"),
    ],
)
def test_document_conversions(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test document format conversions."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists(), f"Sample {src_file} missing"

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {})
    assert out.exists()
    assert out.stat().st_size > 0


# 2. Slide conversions
@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("pptx", "pdf"),
        ("pptx", "png"),
        ("pptx", "jpg"),
    ],
)
def test_slide_conversions(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test slide conversions to PDF and high-res images."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists()

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {"dpi": 150})
    assert out.exists()
    assert out.stat().st_size > 0


# 3. PDF conversions
@pytest.mark.parametrize(
    "dest_ext",
    [
        "docx",
        "pptx",
        "xlsx",
        "jpg",
        "png",
        "epub",
        "txt",
        "md",
    ],
)
def test_pdf_conversions(samples_dir: Path, tmp_path: Path, dest_ext: str):
    """Test PDF conversion to DOCX, PPTX, XLSX, JPG, PNG, EPUB, TXT, MD."""
    src_file = samples_dir / "sample.pdf"
    assert src_file.exists()

    dest_file = tmp_path / f"converted_pdf_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter("pdf", dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {"dpi": 150})
    assert out.exists()
    assert out.stat().st_size > 0


# 4. Spreadsheet conversions
@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("csv", "xlsx"),
        ("csv", "tsv"),
        ("csv", "ods"),
        ("csv", "pdf"),
        ("tsv", "csv"),
        ("tsv", "xlsx"),
        ("xlsx", "csv"),
        ("xlsx", "tsv"),
        ("xlsx", "ods"),
        ("xlsx", "pdf"),
        ("ods", "csv"),
        ("ods", "xlsx"),
        ("ods", "pdf"),
    ],
)
def test_spreadsheet_conversions(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test spreadsheet conversions between CSV, TSV, XLSX, ODS, and PDF."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists()

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {})
    assert out.exists()
    assert out.stat().st_size > 0
