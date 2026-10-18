"""Tests for UI components, JobRunner, and main window integration."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from filetool.core.runner import ConversionJob, JobRunner, JobStatus
from filetool.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_job_runner_workflow(qapp, samples_dir: Path, tmp_path: Path):
    """Test background runner executes a conversion job and emits signals."""
    runner = JobRunner(max_threads=2)
    src_file = samples_dir / "sample.png"

    job = ConversionJob(
        src_path=src_file,
        dest_ext="jpg",
        target_dir=tmp_path,
        options={"quality": 85},
    )

    runner.add_job(job)
    assert job.id in runner.jobs
    assert job.status == JobStatus.PENDING

    # Start job and wait for thread execution
    runner.start_job(job.id)
    runner.thread_pool.waitForDone(5000)

    assert job.status == JobStatus.SUCCESS
    assert job.dest_path is not None
    assert job.dest_path.exists()
    assert job.progress == 100


def test_job_runner_cancellation(qapp, samples_dir: Path, tmp_path: Path):
    """Test cancelling a pending job."""
    runner = JobRunner(max_threads=2)
    src_file = samples_dir / "sample.mp4"

    job = ConversionJob(
        src_path=src_file,
        dest_ext="mov",
        target_dir=tmp_path,
    )

    runner.add_job(job)
    runner.cancel_job(job.id)
    assert job.status == JobStatus.CANCELLED


def test_main_window_add_files(qapp, samples_dir: Path):
    """Test adding files to MainWindow populates queue and switches view."""
    window = MainWindow()
    src1 = samples_dir / "sample.png"
    src2 = samples_dir / "sample.wav"

    window._on_files_dropped([src1, src2])
    assert len(window.runner.jobs) == 2
    assert window.stack.currentIndex() == 1  # Switched from dropzone to joblist

    # Test bulk combo
    window.bulk_combo.setCurrentIndex(1)
    window._apply_bulk_format(1)

    window.close()
