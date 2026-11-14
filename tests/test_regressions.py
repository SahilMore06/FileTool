"""Regression tests for platform services, runner safety, tools, and UI/wheel fixes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pypdf
from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication

from filetool.core.registry import registry
from filetool.core.runner import ConversionJob, ConversionTask, JobRunner, JobStatus, WorkerSignals
from filetool.core.tools.split import split_pdf_by_pages, split_video_by_time
from filetool.core.tools.trim import trim_media
from filetool.core.utils import CommandResult
from filetool.platform import mac_actions
from filetool.platform.mac_drag_monitor import INTERVAL_ACTIVE_MS, INTERVAL_IDLE_MS, MacDragMonitor
from filetool.platform.mac_window import clamp_window_to_screen
from filetool.ui.job_list import JobRow
from filetool.ui.wheel.wheel_window import WheelWindow


def test_clamp_window_to_screen_exact_bounds(qapp):
    """Right/bottom edge clamping aligns flush with screen bounds without a 1px offset."""
    w, h = 240, 180
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    geom = screen.availableGeometry()

    expected_max_x = geom.x() + max(0, geom.width() - w)
    expected_max_y = geom.y() + max(0, geom.height() - h)
    # Center point inside the primary screen, then push desired top-left past edges.
    cx_far = geom.x() + geom.width() - 1
    cy_far = geom.y() + geom.height() - 1
    target_screen = QGuiApplication.screenAt(QPoint(cx_far, cy_far)) or screen
    t_geom = target_screen.availableGeometry()
    t_max_x = t_geom.x() + max(0, t_geom.width() - w)
    t_max_y = t_geom.y() + max(0, t_geom.height() - h)

    assert clamp_window_to_screen(cx_far, cy_far, w, h) == (t_max_x, t_max_y)
    assert clamp_window_to_screen(geom.x() + 1, geom.y() + 1, w, h) == (geom.x(), geom.y())
    assert expected_max_x >= geom.x() and expected_max_y >= geom.y()


def test_get_finder_selection_preserves_commas_in_filenames(monkeypatch):
    """Linefeed-delimited AppleScript output does not split filenames containing ', '."""
    fake_stdout = "/tmp/report, final (2026).pdf\n/tmp/image.png/\n"
    monkeypatch.setattr(
        mac_actions.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=fake_stdout, stderr=""),
    )

    assert mac_actions.get_finder_selection() == [
        "/tmp/report, final (2026).pdf",
        "/tmp/image.png",
    ]


def test_action_move_files_skips_same_folder_and_moves_to_other_folder(tmp_path: Path):
    """Moving files into their own directory is a no-op without creating stem_1 duplicates."""
    src = tmp_path / "draft.txt"
    src.write_text("payload", encoding="utf-8")

    same_dir_result = mac_actions.action_move_files([str(src)], target_folder=str(tmp_path))
    assert same_dir_result == [str(src)]
    assert [p.name for p in tmp_path.iterdir()] == ["draft.txt"]

    dest_dir = tmp_path / "moved"
    dest_dir.mkdir()
    moved_result = mac_actions.action_move_files([str(src)], target_folder=str(dest_dir))
    assert moved_result == [str(dest_dir / "draft.txt")]
    assert not src.exists()
    assert (dest_dir / "draft.txt").read_text(encoding="utf-8") == "payload"


def test_mac_drag_monitor_disable_resets_interval_and_wheel_state(qapp):
    """Disabling MacDragMonitor clears active wheel state and drops polling back to idle."""
    monitor = MacDragMonitor(key_mappings={"shift": "convert"})
    monitor.state_machine.wheel_open = True
    monitor._last_return_down = True
    monitor._current_interval_ms = INTERVAL_ACTIVE_MS
    monitor._timer.setInterval(INTERVAL_ACTIVE_MS)

    monitor.set_enabled(False)
    assert monitor.enabled is False
    assert monitor.state_machine.wheel_open is False
    assert monitor._last_return_down is False
    assert monitor._current_interval_ms == INTERVAL_IDLE_MS
    assert monitor._timer.interval() == INTERVAL_IDLE_MS

    # Calling _poll_tick directly while disabled keeps _in_poll clean and idle interval intact.
    monitor._quartz_available = True
    monitor._current_interval_ms = INTERVAL_ACTIVE_MS
    monitor._last_return_down = True
    monitor._poll_tick()
    assert monitor._in_poll is False
    assert monitor._last_return_down is False
    assert monitor._current_interval_ms == INTERVAL_IDLE_MS


def test_job_row_reenables_format_picker_after_failure(qapp, tmp_path: Path):
    """Failed convertible jobs re-enable the format picker so users can pick another format."""
    src = tmp_path / "sample.png"
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(src, "PNG")

    job = ConversionJob(src_path=src, dest_ext="jpg")
    row = JobRow(job)
    try:
        job.status = JobStatus.RUNNING
        row.update_view()
        assert row.format_picker.isEnabled() is False

        job.status = JobStatus.FAILED
        job.error_message = "simulated error"
        row.update_view()
        assert row.format_picker.isEnabled() is True
    finally:
        row.close()
        row.deleteLater()


def test_conversion_task_does_not_delete_in_place_output(monkeypatch, tmp_path: Path):
    """delete_original=True never deletes the file when conversion resolves to the same path."""
    src = tmp_path / "photo.png"
    Image.new("RGB", (16, 16), color=(40, 80, 120)).save(src, "PNG")

    monkeypatch.setattr(
        registry,
        "get_converter",
        lambda in_ext, out_ext: SimpleNamespace(convert_fn=lambda s, d, opts: s),
    )

    job = ConversionJob(src_path=src, dest_ext="jpg", delete_original=True)
    signals = WorkerSignals()
    completed: list[str] = []
    signals.completed.connect(lambda _jid, out: completed.append(out))

    task = ConversionTask(job, signals)
    task.run()

    assert job.status == JobStatus.SUCCESS
    assert src.exists()
    assert completed == [str(src)]


def test_wheel_batch_convert_submits_every_selected_file(qapp, monkeypatch, tmp_path: Path):
    """Choosing Convert on the wheel converts all selected files rather than only the first."""
    p1 = tmp_path / "one.png"
    p2 = tmp_path / "two.png"
    for p in (p1, p2):
        Image.new("RGB", (16, 16), color=(100, 150, 200)).save(p, "PNG")

    runner = JobRunner()
    added_jobs: list[ConversionJob] = []
    started_ids: list[str] = []
    monkeypatch.setattr(runner, "add_job", lambda job: added_jobs.append(job) or job.id)
    monkeypatch.setattr(runner, "start_job", lambda job_id: started_ids.append(job_id))

    wheel = WheelWindow(runner=runner)
    try:
        wheel.show_wheel("convert", 300.0, 300.0, [str(p1), str(p2)])
        convert_seg = next(s for s in wheel.primary_segments if s.action_type == "convert")
        wheel._start_action_execution(convert_seg)

        assert len(added_jobs) == 2
        assert [Path(j.src_path) for j in added_jobs] == [p1, p2]
        assert len(started_ids) == 2
        assert wheel._batch_jobs == {j.id for j in added_jobs}

        wheel._finish_and_close()
        assert wheel._batch_jobs == set()
    finally:
        wheel.close()
        wheel.deleteLater()


def test_trim_media_places_to_before_input_and_split_handles_brackets(monkeypatch, tmp_path: Path):
    """trim_media applies -to in source timeline; split handles [bracket] stems and empty ranges."""
    captured_cmds: list[list[str]] = []

    def fake_trim_cmd(cmd, **kwargs):
        captured_cmds.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"mp4")
        return CommandResult(returncode=0, stdout="", stderr="", cmd=list(cmd))

    src_vid = tmp_path / "clip [1].mp4"
    src_vid.write_bytes(b"mp4")
    dest_vid = tmp_path / "trimmed.mp4"

    monkeypatch.setattr("filetool.core.tools.trim.run_command", fake_trim_cmd)
    out = trim_media(src_vid, dest_vid, start_time=2.0, end_time=5.5)
    assert out == dest_vid
    cmd = captured_cmds[0]
    assert cmd.index("-ss") < cmd.index("-i")
    assert cmd.index("-to") < cmd.index("-i")
    assert cmd[cmd.index("-ss") + 1] == "2.0"
    assert cmd[cmd.index("-to") + 1] == "5.5"

    # split_video_by_time with bracketed filename stem avoids Path.glob character-class matching.
    split_dir = tmp_path / "splits"

    def fake_split_cmd(cmd, **kwargs):
        split_dir.mkdir(parents=True, exist_ok=True)
        (split_dir / "clip [1]_part_000.mp4").write_bytes(b"p0")
        (split_dir / "clip [1]_part_001.mp4").write_bytes(b"p1")
        (split_dir / "other_part_000.mp4").write_bytes(b"decoy")
        return CommandResult(returncode=0, stdout="", stderr="", cmd=list(cmd))

    monkeypatch.setattr("filetool.core.tools.split.run_command", fake_split_cmd)
    parts = split_video_by_time(src_vid, split_dir, segment_duration_seconds=10.0)
    assert [p.name for p in parts] == ["clip [1]_part_000.mp4", "clip [1]_part_001.mp4"]

    # split_pdf_by_pages skips out-of-order/out-of-bounds empty ranges without creating 0-page PDFs.
    pdf_path = tmp_path / "doc [1].pdf"
    writer = pypdf.PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=72, height=72)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    pdf_out_dir = tmp_path / "pdf_splits"
    pdf_parts = split_pdf_by_pages(pdf_path, pdf_out_dir, ranges=[(1, 2), (5, 3), (9, 12)])
    assert [p.name for p in pdf_parts] == ["doc [1]_part_1.pdf"]
