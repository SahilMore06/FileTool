"""File compression tool for images, video, and PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image

from filetool.core.deps import resolver
from filetool.core.registry import registry
from filetool.core.utils import run_command

logger = logging.getLogger("filetool.tools.compress")


def compress_image(src: Path, dest: Path, quality: int = 65) -> Path:
    """Compress image using Pillow or ImageMagick."""
    ext = src.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        with Image.open(src) as img:
            rgb_img = img.convert("RGB") if img.mode != "RGB" else img
            rgb_img.save(dest, "JPEG", quality=quality, optimize=True)
    elif ext == "png":
        with Image.open(src) as img:
            img.save(dest, "PNG", optimize=True)
    elif ext in ("heic", "avif"):
        magick = resolver.get_tool_path("magick")
        cmd = [magick, str(src), "-quality", str(quality), str(dest)]
        res = run_command(cmd)
        if not res.success:
            raise RuntimeError(f"Image compression failed: {res.stderr_tail()}")
    else:
        with Image.open(src) as img:
            img.save(dest, optimize=True)
    return dest


def compress_video(src: Path, dest: Path, crf: int = 28) -> Path:
    """Compress video using ffmpeg with efficient H.264 CRF encoding."""
    ffmpeg = resolver.get_tool_path("ffmpeg")
    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(dest),
    ]
    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"Video compression failed: {res.stderr_tail()}")
    return dest


def compress_pdf(src: Path, dest: Path, setting: str = "/ebook") -> Path:
    """
    Compress PDF using Ghostscript pdfwrite.
    Settings: /screen (72 dpi, smallest), /ebook (150 dpi), /printer (300 dpi).
    """
    gs = resolver.get_tool_path("gs")
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={dest}",
        str(src),
    ]
    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"PDF compression failed: {res.stderr_tail()}")
    return dest


def compress_file(src: Path, dest: Path, **kwargs) -> Path:
    """Detect format category and compress accordingly."""
    ext = src.suffix.lower().lstrip(".")
    cat = registry.get_category_for_ext(ext)

    if cat == "Images":
        quality = kwargs.get("quality", 65)
        return compress_image(src, dest, quality=quality)
    if cat == "Video":
        crf = kwargs.get("crf", 28)
        return compress_video(src, dest, crf=crf)
    if cat == "PDF" or ext == "pdf":
        setting = kwargs.get("setting", "/ebook")
        return compress_pdf(src, dest, setting=setting)

    raise ValueError(f"Compression not supported for category {cat} (.{ext})")
