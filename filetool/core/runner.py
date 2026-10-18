"""Job queue, background worker threads, cancellation, and progress dispatching."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from filetool.core.registry import registry
from filetool.core.utils import get_unique_output_path

logger = logging.getLogger("filetool.runner")


class JobStatus(Enum):
    PENDING = "Pending"
    RUNNING = "Converting..."
    SUCCESS = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class ConversionJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    src_path: Path = field(default_factory=Path)
    dest_ext: str = ""
    target_dir: Optional[Path] = None
    options: Dict[str, Any] = field(default_factory=dict)
    overwrite: bool = False
    delete_original: bool = False

    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    dest_path: Optional[Path] = None
    error_message: Optional[str] = None
    stderr_tail: Optional[str] = None
    cancel_requested: bool = False

    @property
    def filename(self) -> str:
        return self.src_path.name

    @property
    def file_size_str(self) -> str:
        if not self.src_path.exists():
            return "0 B"
        bytes_size = self.src_path.stat().st_size
        for unit in ("B", "KB", "MB", "GB"):
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}" if unit != "B" else f"{bytes_size} B"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"


class WorkerSignals(QObject):
    """Signals emitted by background conversion worker."""
    started = Signal(str)                          # job_id
    progress = Signal(str, int)                    # job_id, percent
    completed = Signal(str, str)                   # job_id, output_path
    failed = Signal(str, str, str)                 # job_id, error_message, stderr_tail
    cancelled = Signal(str)                        # job_id


class ConversionTask(QRunnable):
    """QRunnable unit of work executing on QThreadPool."""

    def __init__(self, job: ConversionJob, signals: WorkerSignals):
        super().__init__()
        self.job = job
        self.signals = signals

    def run(self) -> None:
        if self.job.cancel_requested:
            self.job.status = JobStatus.CANCELLED
            self.signals.cancelled.emit(self.job.id)
            return

        self.job.status = JobStatus.RUNNING
        self.job.progress = 10
        self.signals.started.emit(self.job.id)
        self.signals.progress.emit(self.job.id, 15)

        src = self.job.src_path
        in_ext = src.suffix.lower().lstrip(".")
        out_ext = self.job.dest_ext.lower().lstrip(".")

        conv = registry.get_converter(in_ext, out_ext)
        if not conv:
            msg = f"No converter available for .{in_ext} -> .{out_ext}"
            self.job.status = JobStatus.FAILED
            self.job.error_message = msg
            self.signals.failed.emit(self.job.id, msg, "")
            return

        # Target directory
        out_dir = self.job.target_dir if self.job.target_dir else src.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        dest_candidate = out_dir / f"{src.stem}.{out_ext}"

        if not self.job.overwrite:
            dest_path = get_unique_output_path(dest_candidate)
        else:
            dest_path = dest_candidate

        self.job.dest_path = dest_path

        try:
            self.signals.progress.emit(self.job.id, 40)
            if self.job.cancel_requested:
                self.job.status = JobStatus.CANCELLED
                self.signals.cancelled.emit(self.job.id)
                return

            result_path = conv.convert_fn(src, dest_path, self.job.options)
            self.signals.progress.emit(self.job.id, 90)

            if self.job.cancel_requested:
                self.job.status = JobStatus.CANCELLED
                self.signals.cancelled.emit(self.job.id)
                return

            # Optionally delete original
            if self.job.delete_original and src.exists() and result_path.exists():
                try:
                    src.unlink()
                except Exception as del_err:
                    logger.warning("Failed deleting original file %s: %s", src, del_err)

            self.job.status = JobStatus.SUCCESS
            self.job.progress = 100
            self.signals.progress.emit(self.job.id, 100)
            self.signals.completed.emit(self.job.id, str(result_path))

        except Exception as exc:
            logger.error("Job %s failed: %s", self.job.id, exc, exc_info=True)
            self.job.status = JobStatus.FAILED
            err_msg = str(exc)
            stderr_tail = getattr(exc, "stderr_tail", "")
            self.job.error_message = err_msg
            self.job.stderr_tail = stderr_tail
            self.signals.failed.emit(self.job.id, err_msg, stderr_tail)


class JobRunner(QObject):
    """Manages queue of conversion jobs and dispatches to QThreadPool."""

    job_added = Signal(ConversionJob)
    job_updated = Signal(str)
    all_completed = Signal()

    def __init__(self, max_threads: int = 4):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(max_threads)
        self.signals = WorkerSignals()
        self.jobs: Dict[str, ConversionJob] = {}
        self._active_count = 0

        # Connect internal worker signals
        self.signals.started.connect(self._on_started)
        self.signals.progress.connect(self._on_progress)
        self.signals.completed.connect(self._on_completed)
        self.signals.failed.connect(self._on_failed)
        self.signals.cancelled.connect(self._on_cancelled)

    def add_job(self, job: ConversionJob) -> str:
        self.jobs[job.id] = job
        self.job_added.emit(job)
        return job.id

    def start_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job or job.status == JobStatus.RUNNING:
            return

        self._active_count += 1
        task = ConversionTask(job, self.signals)
        self.thread_pool.start(task)

    def start_all(self) -> None:
        for job_id, job in list(self.jobs.items()):
            if job.status in (JobStatus.PENDING, JobStatus.FAILED):
                self.start_job(job_id)

    def cancel_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.cancel_requested = True
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                self.job_updated.emit(job_id)

    def clear_completed(self) -> None:
        to_remove = [
            jid for jid, job in self.jobs.items()
            if job.status in (JobStatus.SUCCESS, JobStatus.CANCELLED)
        ]
        for jid in to_remove:
            del self.jobs[jid]
            self.job_updated.emit(jid)

    def _on_started(self, job_id: str) -> None:
        self.job_updated.emit(job_id)

    def _on_progress(self, job_id: str, percent: int) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.progress = percent
        self.job_updated.emit(job_id)

    def _on_completed(self, job_id: str, out_path: str) -> None:
        self._active_count = max(0, self._active_count - 1)
        self.job_updated.emit(job_id)
        if self._active_count == 0:
            self.all_completed.emit()

    def _on_failed(self, job_id: str, msg: str, tail: str) -> None:
        self._active_count = max(0, self._active_count - 1)
        self.job_updated.emit(job_id)
        if self._active_count == 0:
            self.all_completed.emit()

    def _on_cancelled(self, job_id: str) -> None:
        self._active_count = max(0, self._active_count - 1)
        self.job_updated.emit(job_id)
        if self._active_count == 0:
            self.all_completed.emit()
