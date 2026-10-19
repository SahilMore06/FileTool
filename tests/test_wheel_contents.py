"""Unit tests for wheel content resolution and file type filtering."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from filetool.core.registry import registry
from filetool.ui.wheel.wheel_window import WheelWindow


@pytest.fixture
def wheel_window(qapp):
    win = WheelWindow()
    yield win
    win.close()


def test_convert_wheel_outputs_for_image(wheel_window, tmp_path):
    img = tmp_path / "test.png"
    img.write_text("dummy")

    wheel_window.dragged_files = [str(img)]
    wheel_window.wheel_type = "convert"
    wheel_window._populate_segments()

    assert len(wheel_window.primary_segments) > 0
    assert len(wheel_window.primary_segments) <= 8

    labels = [s.label.upper() for s in wheel_window.primary_segments]
    assert "JPG" in labels or "JPEG" in labels
    assert "WEBP" in labels or "PDF" in labels


def test_convert_wheel_second_ring_when_more_than_8(wheel_window, tmp_path):
    img = tmp_path / "test.png"
    img.write_text("dummy")

    wheel_window.dragged_files = [str(img)]
    wheel_window.wheel_type = "convert"
    wheel_window._populate_segments()

    # If outputs exceed 8, the 8th segment is MORE…
    if len(registry.list_outputs("png")) > 8:
        labels = [s.label for s in wheel_window.primary_segments]
        assert "MORE…" in labels
        more_seg = next(s for s in wheel_window.primary_segments if s.label == "MORE…")
        assert len(more_seg.sub_items) > 0


def test_tools_wheel_filtered_for_image(wheel_window, tmp_path):
    img = tmp_path / "test.png"
    img.write_text("dummy")

    wheel_window.dragged_files = [str(img)]
    wheel_window.wheel_type = "tools"
    wheel_window._populate_segments()

    labels = [s.label for s in wheel_window.primary_segments]
    assert "COMPRESS" in labels
    assert "RESIZE" in labels
    assert "CROP" in labels
    assert "ROTATE" in labels
    assert "METADATA" in labels


def test_tools_wheel_filtered_for_video(wheel_window, tmp_path):
    vid = tmp_path / "test.mp4"
    vid.write_text("dummy")

    wheel_window.dragged_files = [str(vid)]
    wheel_window.wheel_type = "tools"
    wheel_window._populate_segments()

    labels = [s.label for s in wheel_window.primary_segments]
    assert "COMPRESS" in labels
    assert "TRIM" in labels
    assert "SPLIT" in labels
    assert "RESIZE" not in labels  # video resize isn't in default tools list


def test_file_actions_wheel_contents(wheel_window, tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("dummy")

    wheel_window.dragged_files = [str(f)]
    wheel_window.wheel_type = "actions"
    wheel_window._populate_segments()

    labels = [s.label for s in wheel_window.primary_segments]
    assert "AIRDROP" in labels
    assert "FLOAT" in labels
    assert "COPY" in labels
    assert "MOVE" in labels
    assert "PATH" in labels
    assert "TERMINAL" in labels


def test_folder_forces_actions_wheel(wheel_window, tmp_path):
    folder = tmp_path / "my_folder"
    folder.mkdir()

    wheel_window.dragged_files = [str(folder)]
    # Request convert wheel on a directory
    wheel_window.wheel_type = "convert"
    wheel_window._populate_segments()

    # Must fall back to Actions wheel
    labels = [s.label for s in wheel_window.primary_segments]
    assert "AIRDROP" in labels
    assert "TERMINAL" in labels


def test_mixed_selection_forces_actions_wheel(wheel_window, tmp_path):
    f1 = tmp_path / "test.png"
    f1.write_text("dummy")
    f2 = tmp_path / "test.mp4"
    f2.write_text("dummy")

    wheel_window.dragged_files = [str(f1), str(f2)]
    wheel_window.wheel_type = "tools"
    wheel_window._populate_segments()

    # Must fall back to Actions wheel
    labels = [s.label for s in wheel_window.primary_segments]
    assert "AIRDROP" in labels
    assert "MOVE" in labels
