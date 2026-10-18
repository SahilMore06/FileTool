"""Tests for real audio and video conversions using local ffmpeg."""

from __future__ import annotations

from pathlib import Path
import pytest
from filetool.core.registry import registry


@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("wav", "mp3"),
        ("wav", "m4a"),
        ("wav", "flac"),
        ("wav", "ogg"),
        ("wav", "opus"),
        ("wav", "aiff"),
        ("wav", "wma"),
        ("mp3", "wav"),
        ("mp3", "m4a"),
        ("flac", "mp3"),
        ("ogg", "wav"),
        ("m4a", "mp3"),
    ],
)
def test_audio_conversion_pair(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test actual audio conversion between pairs."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists(), f"Sample file {src_file} missing"

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {"bitrate": "192k"})
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.parametrize(
    "src_ext,dest_ext",
    [
        ("mp4", "mov"),
        ("mp4", "mkv"),
        ("mp4", "webm"),
        ("mp4", "avi"),
        ("mp4", "wmv"),
        ("mp4", "gif"),
        ("mp4", "mp3"),  # Extract audio
        ("mov", "mp4"),
        ("webm", "mp4"),
        ("avi", "mp4"),
    ],
)
def test_video_conversion_pair(samples_dir: Path, tmp_path: Path, src_ext: str, dest_ext: str):
    """Test actual video transcoding and audio extraction."""
    src_file = samples_dir / f"sample.{src_ext}"
    assert src_file.exists(), f"Sample file {src_file} missing"

    dest_file = tmp_path / f"converted_{src_ext}_to_{dest_ext}.{dest_ext}"
    conv = registry.get_converter(src_ext, dest_ext)
    assert conv is not None
    assert conv.is_available()

    out = conv.convert_fn(src_file, dest_file, {"crf": 23, "preset": "ultrafast", "audio_bitrate": "128k"})
    assert out.exists()
    assert out.stat().st_size > 0
