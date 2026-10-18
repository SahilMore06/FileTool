"""Image conversion engine supporting JPG, PNG, WebP, HEIC, TIFF, AVIF, BMP, PDF, and SVG."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from PIL import Image
import pillow_heif

# Register HEIF opener with Pillow for seamless reading of .heic files
pillow_heif.register_heif_opener()

from filetool.core.deps import resolver
from filetool.core.registry import Converter, OptionDefinition, registry
from filetool.core.utils import run_command, safe_temp_dir

logger = logging.getLogger("filetool.engines.images")

# Input formats supported
IMAGE_INPUT_FORMATS = ("jpg", "jpeg", "png", "webp", "heic", "tiff", "tif", "avif", "bmp", "svg")

# Target output formats supported
IMAGE_OUTPUT_FORMATS = ("jpg", "jpeg", "png", "webp", "heic", "tiff", "avif", "bmp", "pdf")

IMAGE_OPTIONS = {
    "quality": OptionDefinition(
        name="quality",
        label="Image Quality",
        type=int,
        default=85,
        min_value=1,
        max_value=100,
        description="Compression quality for lossy formats (JPG, WebP, AVIF, HEIC)",
    ),
    "dpi": OptionDefinition(
        name="dpi",
        label="Resolution DPI",
        type=int,
        default=300,
        min_value=72,
        max_value=1200,
        description="Target DPI for PDF and SVG rasterization",
    ),
}


def _flatten_transparency(img: Image.Image) -> Image.Image:
    """Composite RGBA/transparency onto a clean white RGB background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alpha_img = img.convert("RGBA")
        background = Image.new("RGB", alpha_img.size, (255, 255, 255))
        background.paste(alpha_img, mask=alpha_img.split()[-1])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def convert_image(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """
    Convert an image from src to dest format using Pillow, ImageMagick, or sips.
    """
    quality = int(options.get("quality", 85))
    dpi = int(options.get("dpi", 300))
    in_ext = src.suffix.lower().lstrip(".")
    out_ext = dest.suffix.lower().lstrip(".")

    # Case 1: SVG as input format
    if in_ext == "svg":
        magick_path = resolver.get_tool_path("magick")
        # For rasterizing SVG, set density for high DPI fidelity
        cmd = [magick_path, "-density", str(dpi), str(src)]
        if out_ext in ("jpg", "jpeg"):
            cmd.extend(["-background", "white", "-flatten", "-quality", str(quality)])
        elif out_ext in ("webp", "avif", "heic"):
            cmd.extend(["-quality", str(quality)])
        cmd.append(str(dest))

        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"SVG conversion failed: {res.stderr_tail()}")
        return dest

    # Case 2: AVIF output format
    if out_ext == "avif":
        magick_path = resolver.get_tool_path("magick")
        cmd = [magick_path, str(src), "-quality", str(quality), str(dest)]
        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"AVIF conversion failed: {res.stderr_tail()}")
        return dest

    # Case 3: HEIC output format
    if out_ext in ("heic", "heif"):
        # ImageMagick or macOS sips
        magick_path = resolver.resolve("magick")
        if magick_path:
            cmd = [str(magick_path), str(src), "-quality", str(quality), str(dest)]
            res = run_command(cmd)
            if res.success and dest.exists():
                return dest
        # Fallback to macOS native sips
        sips_path = resolver.get_tool_path("sips")
        cmd = [sips_path, "-s", "format", "heic", str(src), "--out", str(dest)]
        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"HEIC conversion failed: {res.stderr_tail()}")
        return dest

    # Case 4: AVIF input format to other formats via ImageMagick
    if in_ext == "avif":
        magick_path = resolver.get_tool_path("magick")
        cmd = [magick_path, str(src)]
        if out_ext in ("jpg", "jpeg", "bmp"):
            cmd.extend(["-background", "white", "-flatten", "-quality", str(quality)])
        elif out_ext in ("webp",):
            cmd.extend(["-quality", str(quality)])
        cmd.append(str(dest))
        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"AVIF reading failed: {res.stderr_tail()}")
        return dest

    # Case 5: PDF output format from image
    if out_ext == "pdf":
        with Image.open(src) as img:
            rgb_img = _flatten_transparency(img)
            rgb_img.save(dest, "PDF", resolution=float(dpi))
        return dest

    # Case 6: Standard Pillow formats (JPG, PNG, WebP, TIFF, BMP)
    with Image.open(src) as img:
        # Normalize format name for Pillow
        save_kwargs: Dict[str, Any] = {}

        if out_ext in ("jpg", "jpeg"):
            pillow_format = "JPEG"
            img = _flatten_transparency(img)
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
            save_kwargs["dpi"] = (dpi, dpi)
        elif out_ext == "png":
            pillow_format = "PNG"
            save_kwargs["optimize"] = True
            save_kwargs["dpi"] = (dpi, dpi)
        elif out_ext == "webp":
            pillow_format = "WEBP"
            save_kwargs["quality"] = quality
        elif out_ext in ("tiff", "tif"):
            pillow_format = "TIFF"
            save_kwargs["dpi"] = (dpi, dpi)
        elif out_ext == "bmp":
            pillow_format = "BMP"
            img = _flatten_transparency(img)
        else:
            pillow_format = out_ext.upper()

        img.save(dest, format=pillow_format, **save_kwargs)

    return dest


def register_image_converters() -> None:
    """Register all image conversion combinations in the central registry."""
    for out_ext in ("jpg", "png", "webp", "heic", "tiff", "avif", "bmp", "pdf"):
        # Collect compatible input formats (excluding same-format)
        valid_inputs = tuple(
            fmt for fmt in IMAGE_INPUT_FORMATS
            if fmt != out_ext and not (fmt in ("jpg", "jpeg") and out_ext in ("jpg", "jpeg"))
        )

        conv = Converter(
            id=f"images_to_{out_ext}",
            name=f"Images to {out_ext.upper()}",
            input_formats=valid_inputs,
            output_format=out_ext,
            category="Images",
            convert_fn=convert_image,
            options=IMAGE_OPTIONS,
            required_tools=("magick",) if out_ext in ("avif", "heic") else (),
            description=f"Convert images ({', '.join(valid_inputs)}) to {out_ext.upper()}",
        )
        registry.register(conv)


# Automatically register on import
register_image_converters()
