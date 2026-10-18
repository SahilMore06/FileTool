"""Image cropping tool."""

from __future__ import annotations

from pathlib import Path
from PIL import Image


def crop_image(src: Path, dest: Path, left: int, top: int, right: int, bottom: int) -> Path:
    """
    Crop an image to the specified bounding box (left, top, right, bottom).
    """
    with Image.open(src) as img:
        w, h = img.size
        # Clamp to bounds
        clamped_left = max(0, min(left, w))
        clamped_top = max(0, min(top, h))
        clamped_right = max(clamped_left + 1, min(right, w))
        clamped_bottom = max(clamped_top + 1, min(bottom, h))

        cropped = img.crop((clamped_left, clamped_top, clamped_right, clamped_bottom))
        cropped.save(dest)

    return dest
