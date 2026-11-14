"""Unit tests for wheel content resolution and file type filtering."""

from __future__ import annotations

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


def test_execute_wheel_tool_actions(samples_dir: Path, tmp_path: Path):
    import shutil
    import zipfile
    import pypdf
    from PIL import Image
    from filetool.ui.wheel.wheel_window import execute_wheel_tool

    img_src = tmp_path / "pic.png"
    pdf_a = tmp_path / "doc_a.pdf"
    pdf_b = tmp_path / "doc_b.pdf"
    wav_src = tmp_path / "clip.wav"
    shutil.copy(samples_dir / "sample.png", img_src)
    shutil.copy(samples_dir / "sample.pdf", pdf_a)
    shutil.copy(samples_dir / "sample.pdf", pdf_b)
    shutil.copy(samples_dir / "sample.wav", wav_src)

    with Image.open(img_src) as orig:
        orig_w, orig_h = orig.size

    resized = execute_wheel_tool("resize_image", [str(img_src)])
    assert resized.exists()
    with Image.open(resized) as im:
        assert im.size == (max(1, int(orig_w * 0.5)), max(1, int(orig_h * 0.5)))

    cropped = execute_wheel_tool("crop_image", [str(img_src)])
    assert cropped.exists()

    clean_img = execute_wheel_tool("strip_metadata", [str(img_src)])
    clean_pdf = execute_wheel_tool("strip_metadata", [str(pdf_a)])
    assert clean_img.exists() and clean_pdf.exists()

    pdf_out = execute_wheel_tool("to_pdf", [str(img_src), str(resized)])
    assert pdf_out.exists()
    assert len(pypdf.PdfReader(str(pdf_out)).pages) == 2

    zip_out = execute_wheel_tool("compress_generic", [str(wav_src), str(img_src)])
    assert zip_out.exists()
    with zipfile.ZipFile(zip_out, "r") as zf:
        assert "clip.wav" in zf.namelist()
        assert "pic.png" in zf.namelist()

    split_dir = execute_wheel_tool("split_pdf", [str(pdf_a)])
    assert split_dir.is_dir() and any(split_dir.glob("*.pdf"))

    merged_pdf = execute_wheel_tool("merge_pdf", [str(pdf_a), str(pdf_b)])
    assert merged_pdf.exists()

    with pytest.raises(ValueError):
        execute_wheel_tool("merge_pdf", [str(pdf_a)])

    with pytest.raises(ValueError):
        execute_wheel_tool("unknown_tool", [str(img_src)])


def test_wheel_theme_icon_tinting_and_painting(wheel_window, samples_dir: Path):
    """WheelPainter renders light/dark states, tinted icons, secondary ring, and status rings cleanly."""
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from filetool.ui.wheel.wheel_painter import IconCache, WheelPainter, WheelState

    cache = IconCache()
    pix_dark = cache.get_icon("compress", 18, QColor(0x20, 0x21, 0x24))
    pix_white = cache.get_icon("compress", 18, QColor(0xFF, 0xFF, 0xFF))
    assert not pix_dark.isNull() and not pix_white.isNull()
    assert len(cache._cache) >= 2

    img = samples_dir / "sample.png"
    wheel_window.dragged_files = [str(img)]
    wheel_window.wheel_type = "convert"
    wheel_window._populate_segments()
    wheel_window.set_theme(True, "ocean")
    assert wheel_window.dark_mode is True

    painter_engine = WheelPainter()
    canvas = QPixmap(520, 520)
    more_seg = next((s for s in wheel_window.primary_segments if s.sub_items), None)
    sec_segs = more_seg.sub_items if more_seg else None

    for drop_st in ("none", "progress", "done", "error"):
        for dark in (False, True):
            qp = QPainter(canvas)
            painter_engine.paint(
                qp,
                520,
                520,
                WheelState(
                    wheel_type="convert",
                    primary_segments=wheel_window.primary_segments,
                    secondary_segments=sec_segs,
                    hovered_index=0,
                    hovered_ring=2 if sec_segs else 1,
                    hover_progress=0.8,
                    dark_mode=dark,
                    accent_color="#2E86DE",
                    accent_hover="#1F6EC4",
                    drop_state=drop_st,
                    job_progress=64,
                    file_path=str(img),
                    file_name="sample.png",
                    file_count=2,
                ),
            )
            qp.end()


def test_wheel_switch_updates_segments_between_modes(wheel_window, tmp_path: Path):
    img = tmp_path / "shot.png"
    img.write_text("x")

    wheel_window.dragged_files = [str(img)]
    wheel_window.wheel_type = "convert"
    wheel_window._populate_segments()
    convert_types = {seg.action_type for seg in wheel_window.primary_segments}
    assert "convert" in convert_types

    wheel_window.switch_wheel("tools")
    tool_types = {seg.action_type for seg in wheel_window.primary_segments}
    assert tool_types == {"tool"}


def test_wheel_window_paint_event_all_presets(wheel_window, qapp, samples_dir: Path):
    """Exercise live WheelWindow.paintEvent across all accent presets."""
    from filetool.ui.styles import ACCENT_PRESETS

    img = samples_dir / "sample.png"
    wheel_window.show_wheel("convert", 300.0, 300.0, [str(img)])
    try:
        for dark in (False, True):
            for preset_key in ACCENT_PRESETS:
                wheel_window.set_theme(dark, preset_key)
                qapp.processEvents()
                pix = wheel_window.grab()
                assert not pix.isNull()
    finally:
        if wheel_window._open_anim:
            wheel_window._open_anim.stop()
        wheel_window.hide()


def test_wheel_stays_open_in_sticky_mode_on_hub_release(wheel_window, qapp, samples_dir: Path):
    """Releasing at the center hub before picking a petal keeps the wheel open cleanly."""
    img = samples_dir / "sample.png"
    sticky_signals = []
    wheel_window.sticky_entered.connect(lambda: sticky_signals.append(True))

    wheel_window.show_wheel("convert", 300.0, 300.0, [str(img)])
    try:
        if wheel_window._open_anim:
            wheel_window._open_anim.stop()
            wheel_window.open_scale = 1.0
            wheel_window.open_opacity = 1.0
            wheel_window.segment_stagger = [1.0] * len(wheel_window.primary_segments)

        # Center coordinates of the wheel window
        cx = wheel_window.x() + wheel_window.width() / 2.0
        cy = wheel_window.y() + wheel_window.height() / 2.0

        # Dropping at hub right after trigger keeps wheel open instead of canceling
        wheel_window.trigger_drop_at(cx, cy)
        qapp.processEvents()
        assert wheel_window.isVisible()
        assert wheel_window._sticky_mode is True
        assert len(sticky_signals) == 1

        # Immediate duplicate drop signal within 150ms deduplication window is ignored
        wheel_window.trigger_drop_at(cx, cy)
        qapp.processEvents()
        assert wheel_window.isVisible()

        # Once past debounce window, clicking center hub closes the sticky wheel
        wheel_window._ignore_drop_until = 0.0
        wheel_window.trigger_drop_at(cx, cy)
        if wheel_window._cancel_anim:
            wheel_window._cancel_anim.setCurrentTime(wheel_window._cancel_anim.duration())
        qapp.processEvents()
        assert not wheel_window.isVisible()
    finally:
        if wheel_window._cancel_anim:
            wheel_window._cancel_anim.stop()
        wheel_window.hide()


def test_wheel_painter_caches_backdrop_paths_and_thumbnails(samples_dir: Path):
    """WheelPainter caches backdrop pixmap, petal paths, and circular image thumbnails."""
    from PySide6.QtGui import QPainter, QPixmap
    from filetool.ui.wheel.geometry import layout_segments
    from filetool.ui.wheel.wheel_painter import WheelPainter, WheelState

    painter_engine = WheelPainter()
    img = samples_dir / "sample.png"
    segs = layout_segments(
        [{"label": ext.upper(), "icon": ext, "action_type": "convert", "action_data": ext} for ext in ("jpg", "webp", "pdf", "png")],
        ring=1,
    )
    canvas = QPixmap(520, 520)
    state = WheelState(
        wheel_type="convert",
        primary_segments=segs,
        hovered_index=0,
        hovered_ring=1,
        hover_progress=0.5,
        dark_mode=False,
        file_path=str(img),
        file_name="sample.png",
    )

    qp = QPainter(canvas)
    painter_engine.paint(qp, 520, 520, state)
    qp.end()

    assert len(painter_engine._backdrop_cache) == 1
    assert len(painter_engine._petal_path_cache) == len(segs)
    assert len(painter_engine._thumb_cache) == 1

    # Repaint with same geometry/thumbnail: caches stay warm with zero new allocations
    qp2 = QPainter(canvas)
    painter_engine.paint(qp2, 520, 520, state)
    qp2.end()
    assert len(painter_engine._backdrop_cache) == 1
    assert len(painter_engine._petal_path_cache) == len(segs)
    assert len(painter_engine._thumb_cache) == 1
