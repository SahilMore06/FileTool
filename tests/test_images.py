"""Tests for real image conversions across JPG, PNG, WebP, HEIC, TIFF, AVIF, BMP, PDF, and SVG."""

from __future__ import annotations

from pathlib import Path
import pytest
from filetool.core.engines.images import convert_image
from filetool.core.registry import registry


@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("png", "jpg"),
        ("png", "webp"),
        ("png", "heic"),
        ("png", "tiff"),
        ("png", "avif"),
        ("png", "bmp"),
        ("png", "pdf"),
        ("jpg", "png"),
        ("jpg", "webp"),
        ("jpg", "heic"),
        ("jpg", "avif"),
        ("webp", "png"),
        ("webp", "jpg"),
        ("heic", "png"),
        ("heic", "jpg"),
        ("tiff", "png"),
        ("bmp", "png"),
        ("avif", "png"),
        ("avif", "jpg"),
        ("svg", "png"),
        ("svg", "jpg"),
        ("svg", "webp"),
        ("svg", "pdf"),
    ],
)
def test_image_conversion_pair(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test actual image conversion from src_ext to dest_ext with sample file."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists(), f"Sample file {src_file} missing"

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None, f"No converter registered for {src_ext} -> {dest_ext}"
    assert conv.is_available(), f"Converter for {src_ext} -> {dest_ext} missing external tools"

    out = conv.convert_fn(src_file, dest_file, {"quality": 85, "dpi": 300})
    assert out.exists()
    assert out.stat().st_size > 0
