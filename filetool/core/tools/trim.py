"""Audio and Video trimming tool using ffmpeg."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from filetool.core.deps import resolver
from filetool.core.utils import run_command

logger = logging.getLogger("filetool.tools.trim")


def trim_media(
    src: Path,
    dest: Path,
    start_time: str | float = 0,
    end_time: Optional[str | float] = None,
    duration: Optional[str | float] = None,
    reencode: bool = False,
) -> Path:
    """
    Trim audio or video file by start time and end time / duration.
    start_time/end_time can be seconds (e.g. 5.5) or HH:MM:SS timestamps (e.g. '00:01:30').
    """
    ffmpeg = resolver.get_tool_path("ffmpeg")
    cmd = [ffmpeg, "-y", "-ss", str(start_time), "-i", str(src)]

    if end_time is not None:
        cmd.extend(["-to", str(end_time)])
    elif duration is not None:
        cmd.extend(["-t", str(duration)])

    if not reencode:
        # Fast lossless copy
        cmd.extend(["-c", "copy"])

    cmd.append(str(dest))

    res = run_command(cmd)
    if not res.success or not dest.exists():
        # Fallback to re-encoding if stream copy failed
        logger.info("Direct stream copy failed for trim; retrying with re-encoding")
        cmd_reencode = [ffmpeg, "-y", "-ss", str(start_time), "-i", str(src)]
        if end_time is not None:
            cmd_reencode.extend(["-to", str(end_time)])
        elif duration is not None:
            cmd_reencode.extend(["-t", str(duration)])
        cmd_reencode.append(str(dest))

        res_reencode = run_command(cmd_reencode)
        if not res_reencode.success or not dest.exists():
            raise RuntimeError(f"Trim failed: {res_reencode.stderr_tail()}")

    return dest
