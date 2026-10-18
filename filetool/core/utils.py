"""Utility functions for safe filesystem operations, subprocess execution, and logging."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Sequence

LOG_DIR = Path.home() / "Library" / "Logs" / "FileTool"
LOG_FILE = LOG_DIR / "filetool.log"

logger = logging.getLogger("filetool")


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure logging to ~/Library/Logs/FileTool/filetool.log and stderr."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
        )

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def get_unique_output_path(target_path: Path | str) -> Path:
    """
    Ensure the target file does not overwrite an existing file.
    If 'report.pdf' exists, generates 'report (1).pdf', 'report (2).pdf', etc.
    """
    path = Path(target_path).resolve()
    if not path.exists():
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


@contextmanager
def safe_temp_dir(prefix: str = "filetool_") -> Generator[Path, None, None]:
    """
    Context manager creating a temporary directory that is guaranteed
    to be cleaned up even on conversion errors or termination.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    cmd: list[str]

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def stderr_tail(self, max_lines: int = 15) -> str:
        """Return the last N lines of stderr for clean user-facing error reporting."""
        lines = self.stderr.strip().splitlines()
        if not lines:
            return ""
        return "\n".join(lines[-max_lines:])


def run_command(
    args: Sequence[str | Path],
    cwd: Path | str | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """
    Execute a local tool safely through subprocess without shell=True.
    Safely stringifies arguments, handles unicode, and captures stdout/stderr.
    """
    cmd = [str(arg) for arg in args]
    cwd_str = str(cwd) if cwd else None

    # Merge custom env or pass current environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    logger.debug("Executing command: %s (cwd=%s)", cmd, cwd_str)

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd_str,
            timeout=timeout,
            env=run_env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result = CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmd=cmd,
        )
        if not result.success:
            logger.warning(
                "Command failed with code %d: %s\nStderr tail:\n%s",
                proc.returncode,
                cmd,
                result.stderr_tail(5),
            )
        return result
    except subprocess.TimeoutExpired as exc:
        stdout_str = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr_str = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        logger.error("Command timed out after %s seconds: %s", timeout, cmd)
        return CommandResult(
            returncode=-1,
            stdout=stdout_str,
            stderr=f"Command timed out after {timeout} seconds.\n{stderr_str}",
            cmd=cmd,
        )
    except Exception as exc:
        logger.error("Error running command %s: %s", cmd, exc, exc_info=True)
        return CommandResult(
            returncode=-1,
            stdout="",
            stderr=str(exc),
            cmd=cmd,
        )
