"""Same-format image operations (resize, compress) used by the Quick Wheel.

These complement the format-to-format converters in the registry, which
deliberately exclude same-format conversions. Originals are never modified;
callers pass a fresh destination path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from PIL import Image

# Formats Pillow can both read and write losslessly-enough for these ops
SUPPORTED_EXTS = {"jpg", "jpeg", "png", "webp", "tiff", "tif", "bmp"}

_PIL_FORMAT = {
    "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
    "tiff": "TIFF", "tif": "TIFF", "bmp": "BMP",
}

OPERATION_SUFFIX = {"resize": "resized", "compress": "compressed"}


def supports(path: Path | str) -> bool:
    """Return True if resize/compress can be applied to this file."""
    return Path(path).suffix.lower().lstrip(".") in SUPPORTED_EXTS


def _save(img: Image.Image, dest: Path, quality: int) -> None:
    ext = dest.suffix.lower().lstrip(".")
    fmt = _PIL_FORMAT.get(ext, ext.upper())
    kwargs: Dict[str, Any] = {}
    if fmt == "JPEG":
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        kwargs.update(quality=quality, optimize=True, progressive=True)
    elif fmt == "WEBP":
        kwargs.update(quality=quality, method=6)
    elif fmt == "PNG":
        kwargs.update(optimize=True)
        if quality < 60 and img.mode in ("RGB", "RGBA"):
            # Lossy palette quantization for meaningful PNG compression
            img = img.quantize(colors=max(16, int(256 * quality / 100)))
    elif fmt == "TIFF":
        kwargs.update(compression="tiff_lzw")
    img.save(dest, format=fmt, **kwargs)


def resize_image(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Resize ``src`` into ``dest``.

    Options: width, height (px), keep_aspect (bool, default True: fit inside
    the box without distortion), quality (1-100).
    """
    width = int(options.get("width") or 0)
    height = int(options.get("height") or 0)
    keep_aspect = bool(options.get("keep_aspect", True))
    quality = int(options.get("quality", 90))
    if width <= 0 and height <= 0:
        raise ValueError("Resize requires a width or height")

    from PIL import Image

    with Image.open(src) as img:
        img.load()
        w0, h0 = img.size
        if keep_aspect:
            sx = width / w0 if width > 0 else float("inf")
            sy = height / h0 if height > 0 else float("inf")
            scale = min(sx, sy)
            new_size = (max(1, round(w0 * scale)), max(1, round(h0 * scale)))
        else:
            new_size = (width or w0, height or h0)
        out = img.resize(new_size, Image.Resampling.LANCZOS)
        _save(out, dest, quality)
    return dest


def compress_image(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Re-encode ``src`` into ``dest`` at the requested quality (1-100)."""
    from PIL import Image

    quality = int(options.get("quality", 75))
    with Image.open(src) as img:
        img.load()
        _save(img, dest, quality)
    return dest


OPERATIONS = {"resize": resize_image, "compress": compress_image}
