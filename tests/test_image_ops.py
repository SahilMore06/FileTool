"""Tests for same-format image operations (resize / compress) and runner dispatch."""

from pathlib import Path

from PIL import Image

from filetool.core import image_ops
from filetool.core.runner import ConversionJob, ConversionTask, JobStatus, WorkerSignals


def _make_png(path: Path, size=(400, 200)) -> Path:
    Image.new("RGB", size, (242, 138, 50)).save(path)
    return path


def test_resize_keeps_aspect(tmp_path: Path):
    src = _make_png(tmp_path / "a.png")
    dest = tmp_path / "out.png"
    image_ops.resize_image(src, dest, {"width": 100, "height": 100, "keep_aspect": True})
    with Image.open(dest) as img:
        assert img.size == (100, 50)


def test_resize_exact(tmp_path: Path):
    src = _make_png(tmp_path / "a.png")
    dest = tmp_path / "out.png"
    image_ops.resize_image(src, dest, {"width": 120, "height": 90, "keep_aspect": False})
    with Image.open(dest) as img:
        assert img.size == (120, 90)


def test_compress_jpeg_smaller(tmp_path: Path):
    src = tmp_path / "a.jpg"
    Image.effect_noise((600, 600), 80).convert("RGB").save(src, quality=95)
    dest = tmp_path / "out.jpg"
    image_ops.compress_image(src, dest, {"quality": 30})
    assert dest.stat().st_size < src.stat().st_size


def test_runner_resize_job_keeps_original(qapp, tmp_path: Path):
    src = _make_png(tmp_path / "photo.png")
    job = ConversionJob(src_path=src, dest_ext="png", operation="resize",
                        options={"width": 50, "height": 50})
    ConversionTask(job, WorkerSignals()).run()
    assert job.status == JobStatus.SUCCESS, job.error_message
    assert job.dest_path.name == "photo_resized.png"
    assert src.exists()


def test_runner_rejects_unsupported(qapp, tmp_path: Path):
    src = tmp_path / "notes.txt"
    src.write_text("hi")
    job = ConversionJob(src_path=src, dest_ext="txt", operation="compress")
    ConversionTask(job, WorkerSignals()).run()
    assert job.status == JobStatus.FAILED
