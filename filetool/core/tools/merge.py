"""Merging tool for PDFs, images to a single PDF, and videos."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Sequence

from PIL import Image
import pypdf

from filetool.core.deps import resolver
from filetool.core.utils import run_command, safe_temp_dir

logger = logging.getLogger("filetool.tools.merge")


def merge_pdfs(src_files: Sequence[Path], dest: Path) -> Path:
    """Merge multiple PDF documents into a single sequential PDF."""
    if not src_files:
        raise ValueError("Must provide at least one PDF file to merge")

    writer = pypdf.PdfWriter()
    for pdf_path in src_files:
        writer.append(str(pdf_path))

    with open(dest, "wb") as f_out:
        writer.write(f_out)
    writer.close()

    return dest


def merge_images_to_pdf(src_images: Sequence[Path], dest: Path, dpi: int = 300) -> Path:
    """Merge a sequence of image files into a single multi-page PDF document."""
    if not src_images:
        raise ValueError("Must provide at least one image file to merge into PDF")

    loaded_images: List[Image.Image] = []
    try:
        for img_path in src_images:
            im = Image.open(img_path)
            # Composite RGBA onto white RGB
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                alpha = im.convert("RGBA")
                bg = Image.new("RGB", alpha.size, (255, 255, 255))
                bg.paste(alpha, mask=alpha.split()[-1])
                loaded_images.append(bg)
            elif im.mode != "RGB":
                loaded_images.append(im.convert("RGB"))
            else:
                loaded_images.append(im.copy())
            im.close()

        first_img = loaded_images[0]
        remaining = loaded_images[1:] if len(loaded_images) > 1 else []

        first_img.save(
            dest,
            "PDF",
            resolution=float(dpi),
            save_all=True,
            append_images=remaining,
        )
    finally:
        for img in loaded_images:
            img.close()

    return dest


def merge_videos(src_videos: Sequence[Path], dest: Path) -> Path:
    """
    Concatenate multiple video files using ffmpeg concat demuxer.
    """
    if not src_videos:
        raise ValueError("Must provide at least one video to merge")

    ffmpeg = resolver.get_tool_path("ffmpeg")

    with safe_temp_dir(prefix="filetool_concat_") as tmp_dir:
        list_file = tmp_dir / "playlist.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for vid in src_videos:
                # Escape single quotes for ffmpeg concat demuxer
                escaped = str(vid.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(dest),
        ]
        res = run_command(cmd)
        if not res.success or not dest.exists():
            # If stream copy failed (different codecs/resolutions), re-encode
            cmd_reencode = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                str(dest),
            ]
            res_re = run_command(cmd_reencode)
            if not res_re.success or not dest.exists():
                raise RuntimeError(f"Video merge failed: {res_re.stderr_tail()}")

    return dest
