"""Metadata stripping tool for privacy (Images, Video, PDF)."""

from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image
import pypdf

from filetool.core.deps import resolver
from filetool.core.registry import registry
from filetool.core.utils import run_command

logger = logging.getLogger("filetool.tools.metadata")


def strip_image_metadata(src: Path, dest: Path) -> Path:
    """Remove EXIF, GPS coordinates, camera model, and IPTC from image."""
    magick = resolver.resolve("magick")
    if magick:
        cmd = [str(magick), str(src), "-strip", str(dest)]
        res = run_command(cmd)
        if res.success and dest.exists():
            return dest

    # Pillow fallback: load raw image data without EXIF info dict
    with Image.open(src) as img:
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(list(img.getdata()))
        clean_img.save(dest)

    return dest


def strip_video_metadata(src: Path, dest: Path) -> Path:
    """Remove metadata tags from audio/video containers."""
    ffmpeg = resolver.get_tool_path("ffmpeg")
    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-map_metadata", "-1",
        "-c", "copy",
        str(dest),
    ]
    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"Video metadata stripping failed: {res.stderr_tail()}")
    return dest


def strip_pdf_metadata(src: Path, dest: Path) -> Path:
    """Remove metadata title, author, producer, and creation date from PDF."""
    reader = pypdf.PdfReader(str(src))
    writer = pypdf.PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Empty metadata
    writer.add_metadata({})

    with open(dest, "wb") as f_out:
        writer.write(f_out)

    return dest


def strip_metadata(src: Path, dest: Path) -> Path:
    """Detect file type and strip metadata accordingly."""
    ext = src.suffix.lower().lstrip(".")
    cat = registry.get_category_for_ext(ext)

    if cat == "Images":
        return strip_image_metadata(src, dest)
    if cat in ("Video", "Audio"):
        return strip_video_metadata(src, dest)
    if cat == "PDF" or ext == "pdf":
        return strip_pdf_metadata(src, dest)

    raise ValueError(f"Metadata stripping not supported for category {cat} (.{ext})")
