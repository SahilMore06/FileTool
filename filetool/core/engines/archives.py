"""Archive management engine supporting ZIP, TAR, GZIP create/extract, and RAR extract."""

from __future__ import annotations

import logging
import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict

from filetool.core.deps import resolver
from filetool.core.registry import Converter, OptionDefinition, registry
from filetool.core.utils import run_command, safe_temp_dir

logger = logging.getLogger("filetool.engines.archives")

ARCHIVE_INPUTS = ("zip", "tar", "gz", "tgz", "rar")
ARCHIVE_OUTPUTS = ("zip", "tar", "gz")

ARCHIVE_OPTIONS = {
    "compression_level": OptionDefinition(
        name="compression_level",
        label="Compression Level",
        type=int,
        default=5,
        min_value=0,
        max_value=9,
        description="7-Zip / archive compression level (0-9, default 5)",
    ),
}


def extract_archive(src: Path, dest_dir: Path) -> Path:
    """Extract an archive (ZIP, TAR, GZ, RAR) into destination directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    in_ext = src.suffix.lower().lstrip(".")

    # Prefer 7zz if available (handles all formats including RAR)
    sevenzip = resolver.resolve("7zz")
    if sevenzip:
        cmd = [str(sevenzip), "x", "-y", f"-o{dest_dir}", str(src)]
        res = run_command(cmd)
        if res.success:
            return dest_dir

    # Fallbacks using standard python libraries
    if in_ext == "zip":
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(dest_dir)
        return dest_dir

    if in_ext in ("tar", "gz", "tgz"):
        mode = "r:gz" if in_ext in ("gz", "tgz") else "r:*"
        with tarfile.open(src, mode) as tf:
            tf.extractall(dest_dir)
        return dest_dir

    if in_ext == "rar":
        raise RuntimeError("Extracting RAR files requires 7zz. Please install sevenzip: `brew install sevenzip`")

    raise ValueError(f"Unsupported archive format: .{in_ext}")


def create_archive(src_path: Path, dest_archive: Path, options: Dict[str, Any]) -> Path:
    """Create an archive (ZIP, TAR, GZ) from a file or folder."""
    out_ext = dest_archive.suffix.lower().lstrip(".")
    level = str(options.get("compression_level", 5))

    sevenzip = resolver.resolve("7zz")
    if sevenzip:
        # Determine 7zz format flag
        type_flag = "-tzip" if out_ext == "zip" else ("-ttar" if out_ext == "tar" else "-tgzip")
        cmd = [str(sevenzip), "a", type_flag, f"-mx={level}", str(dest_archive)]
        if src_path.is_dir():
            cmd.append(f"{src_path}/*")
        else:
            cmd.append(str(src_path))
        res = run_command(cmd)
        if res.success and dest_archive.exists():
            return dest_archive

    # Python library fallbacks
    if out_ext == "zip":
        with zipfile.ZipFile(dest_archive, "w", zipfile.ZIP_DEFLATED) as zf:
            if src_path.is_dir():
                for root, _, files in os.walk(src_path):
                    for file in files:
                        p = Path(root) / file
                        zf.write(p, p.relative_to(src_path))
            else:
                zf.write(src_path, src_path.name)
        return dest_archive

    if out_ext in ("tar", "gz"):
        mode = "w:gz" if out_ext == "gz" else "w"
        with tarfile.open(dest_archive, mode) as tf:
            if src_path.is_dir():
                for root, _, files in os.walk(src_path):
                    for file in files:
                        p = Path(root) / file
                        tf.add(p, arcname=str(p.relative_to(src_path)))
            else:
                tf.add(src_path, arcname=src_path.name)
        return dest_archive

    raise ValueError(f"Unsupported target archive type: .{out_ext}")


def convert_archive(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """
    Convert an archive from one container format to another (e.g. RAR to ZIP, TAR to GZ, ZIP to TAR).
    Extracts to a clean temporary directory and repacks into target format.
    """
    with safe_temp_dir(prefix="filetool_repack_") as tmp_dir:
        extract_archive(src, tmp_dir)
        create_archive(tmp_dir, dest, options)

    if not dest.exists():
        raise RuntimeError(f"Archive repackaging failed from {src.name} to {dest.name}")
    return dest


def register_archive_converters() -> None:
    """Register archive converters."""
    for out_ext in ARCHIVE_OUTPUTS:
        valid_inputs = tuple(fmt for fmt in ARCHIVE_INPUTS if fmt != out_ext)
        registry.register(
            Converter(
                id=f"archive_to_{out_ext}",
                name=f"Archive to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Archives",
                convert_fn=convert_archive,
                options=ARCHIVE_OPTIONS,
                required_tools=("7zz",),
                description=f"Repack archives ({', '.join(valid_inputs)}) to {out_ext.upper()}",
            )
        )


# Automatically register on import
register_archive_converters()
