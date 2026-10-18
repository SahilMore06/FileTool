"""Image resize and image/PDF rotation tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image
import pypdf

logger = logging.getLogger("filetool.tools.resize")


def resize_image(
    src: Path,
    dest: Path,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale_percent: Optional[float] = None,
) -> Path:
    """
    Resize image dimensions preserving aspect ratio if only one dimension is supplied.
    """
    with Image.open(src) as img:
        orig_w, orig_h = img.size

        if scale_percent is not None:
            new_w = max(1, int(orig_w * (scale_percent / 100.0)))
            new_h = max(1, int(orig_h * (scale_percent / 100.0)))
        elif width is not None and height is not None:
            new_w, new_h = width, height
        elif width is not None:
            new_w = width
            new_h = max(1, int(orig_h * (width / orig_w)))
        elif height is not None:
            new_h = height
            new_w = max(1, int(orig_w * (height / orig_h)))
        else:
            raise ValueError("Must provide width, height, or scale_percent")

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized.save(dest)

    return dest


def rotate_image(src: Path, dest: Path, degrees: int = 90) -> Path:
    """Rotate image clockwise by specified degrees (e.g. 90, 180, 270)."""
    with Image.open(src) as img:
        # Pillow rotate is counter-clockwise by default, so use -degrees to rotate clockwise
        rotated = img.rotate(-degrees, expand=True)
        rotated.save(dest)
    return dest


def rotate_pdf(src: Path, dest: Path, degrees: int = 90) -> Path:
    """Rotate all pages of a PDF document clockwise."""
    reader = pypdf.PdfReader(str(src))
    writer = pypdf.PdfWriter()

    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)

    with open(dest, "wb") as f_out:
        writer.write(f_out)

    return dest
