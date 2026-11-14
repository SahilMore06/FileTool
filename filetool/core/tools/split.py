"""File splitting tool for PDF (by pages) and Video (by duration)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from filetool.core.deps import resolver
from filetool.core.utils import run_command

logger = logging.getLogger("filetool.tools.split")


def split_pdf_by_pages(
    src: Path,
    dest_dir: Path,
    ranges: Optional[List[Tuple[int, int]]] = None,
) -> List[Path]:
    """
    Split PDF document into separate PDF files.
    If ranges is provided (e.g. [(1, 2), (3, 5)]), extracts those 1-indexed page ranges.
    Otherwise, extracts each individual page into 'stem_page_1.pdf', 'stem_page_2.pdf', etc.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    import pypdf

    reader = pypdf.PdfReader(str(src))
    total_pages = len(reader.pages)
    output_files: List[Path] = []

    if ranges:
        for idx, (start_p, end_p) in enumerate(ranges, start=1):
            s = max(0, start_p - 1)
            e = min(total_pages, end_p)
            if s >= e:
                continue
            writer = pypdf.PdfWriter()
            for p in range(s, e):
                writer.add_page(reader.pages[p])

            target = dest_dir / f"{src.stem}_part_{idx}.pdf"
            with open(target, "wb") as f_out:
                writer.write(f_out)
            output_files.append(target)
    else:
        for p_num in range(total_pages):
            writer = pypdf.PdfWriter()
            writer.add_page(reader.pages[p_num])
            target = dest_dir / f"{src.stem}_page_{p_num + 1}.pdf"
            with open(target, "wb") as f_out:
                writer.write(f_out)
            output_files.append(target)

    return output_files


def split_video_by_time(
    src: Path,
    dest_dir: Path,
    segment_duration_seconds: float = 30.0,
) -> List[Path]:
    """
    Split a video into segments of fixed duration using ffmpeg segment muxer.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = resolver.get_tool_path("ffmpeg")
    out_pattern = dest_dir / f"{src.stem}_part_%03d{src.suffix}"

    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-c", "copy",
        "-map", "0",
        "-segment_time", str(segment_duration_seconds),
        "-f", "segment",
        "-reset_timestamps", "1",
        str(out_pattern),
    ]

    res = run_command(cmd)
    if not res.success:
        raise RuntimeError(f"Video splitting failed: {res.stderr_tail()}")

    prefix = f"{src.stem}_part_"
    segments = sorted(
        p for p in dest_dir.iterdir()
        if p.is_file() and p.name.startswith(prefix) and p.suffix == src.suffix
    )
    return segments
