"""Tests for converter registry, options schemas, and format lookups."""

from __future__ import annotations

import filetool.core.engines.images  # noqa: F401
import filetool.core.engines.media  # noqa: F401
from filetool.core.registry import registry


def test_registry_has_image_converters():
    """Verify registry has image conversion pairs registered."""
    outputs_for_png = registry.list_outputs("png")
    assert "jpg" in outputs_for_png
    assert "webp" in outputs_for_png
    assert "heic" in outputs_for_png
    assert "pdf" in outputs_for_png
    assert "avif" in outputs_for_png


def test_registry_has_media_converters():
    """Verify registry has audio and video conversions."""
    outputs_for_wav = registry.list_outputs("wav")
    assert "mp3" in outputs_for_wav
    assert "flac" in outputs_for_wav
    assert "ogg" in outputs_for_wav

    outputs_for_mp4 = registry.list_outputs("mp4")
    assert "mov" in outputs_for_mp4
    assert "gif" in outputs_for_mp4
    assert "mp3" in outputs_for_mp4


def test_category_detection():
    """Verify category resolution for various extensions."""
    assert registry.get_category_for_ext("png") == "Images"
    assert registry.get_category_for_ext("heic") == "Images"
    assert registry.get_category_for_ext("mp3") == "Audio"
    assert registry.get_category_for_ext("mp4") == "Video"
    assert registry.get_category_for_ext("docx") == "Documents"
    assert registry.get_category_for_ext("xlsx") == "Spreadsheets"
    assert registry.get_category_for_ext("pptx") == "Slides"
    assert registry.get_category_for_ext("srt") == "Subtitles"
    assert registry.get_category_for_ext("zip") == "Archives"
