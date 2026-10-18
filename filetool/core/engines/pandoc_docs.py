"""Document conversion engine supporting DOCX, Markdown, TXT, EPUB, HTML, RTF via Pandoc and LibreOffice."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from filetool.core.deps import resolver
from filetool.core.registry import Converter, OptionDefinition, registry
from filetool.core.utils import run_command, safe_temp_dir

logger = logging.getLogger("filetool.engines.pandoc_docs")

# Document formats supported by Pandoc
DOC_FORMATS = ("docx", "md", "markdown", "txt", "epub", "html", "htm", "rtf")

PANDOC_INPUT_MAP = {
    "docx": "docx",
    "md": "markdown",
    "markdown": "markdown",
    "txt": "markdown",
    "epub": "epub",
    "html": "html",
    "htm": "html",
    "rtf": "rtf",
}

PANDOC_OUTPUT_MAP = {
    "docx": "docx",
    "md": "markdown",
    "markdown": "markdown",
    "txt": "plain",
    "epub": "epub",
    "html": "html",
    "htm": "html",
    "rtf": "rtf",
}


def convert_pandoc_document(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Convert documents between DOCX, MD, TXT, EPUB, HTML, RTF using local Pandoc."""
    pandoc = resolver.get_tool_path("pandoc")
    in_ext = src.suffix.lower().lstrip(".")
    out_ext = dest.suffix.lower().lstrip(".")

    from_format = PANDOC_INPUT_MAP.get(in_ext, in_ext)
    to_format = PANDOC_OUTPUT_MAP.get(out_ext, out_ext)

    cmd = [pandoc, str(src), "-f", from_format, "-t", to_format, "-o", str(dest)]

    # Standalone output (with proper HTML/RTF/EPUB headers)
    if out_ext in ("html", "htm", "rtf", "epub"):
        cmd.append("-s")

    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"Pandoc conversion failed ({src.name} -> {dest.name}): {res.stderr_tail()}")
    return dest


def convert_docx_to_pdf(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Convert DOCX to PDF using LibreOffice headless."""
    soffice = resolver.get_tool_path("soffice")

    with safe_temp_dir(prefix="filetool_docx_pdf_") as tmp_dir:
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(tmp_dir),
            str(src),
        ]
        res = run_command(cmd, timeout=60.0)
        expected_pdf = tmp_dir / f"{src.stem}.pdf"
        if not expected_pdf.exists():
            raise RuntimeError(f"DOCX to PDF conversion failed: {res.stderr_tail()}")
        shutil.copy2(expected_pdf, dest)

    return dest


def register_document_converters() -> None:
    """Register all document conversions."""
    # Register Pandoc document conversions
    for out_ext in ("docx", "md", "txt", "epub", "html", "rtf"):
        valid_inputs = tuple(
            fmt for fmt in ("docx", "md", "txt", "epub", "html", "rtf")
            if fmt != out_ext
        )
        registry.register(
            Converter(
                id=f"doc_to_{out_ext}",
                name=f"Document to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Documents",
                convert_fn=convert_pandoc_document,
                required_tools=("pandoc",),
                description=f"Convert document formats to {out_ext.upper()} via Pandoc",
            )
        )

    # Register DOCX to PDF via LibreOffice
    registry.register(
        Converter(
            id="docx_to_pdf",
            name="DOCX to PDF",
            input_formats=("docx",),
            output_format="pdf",
            category="Documents",
            convert_fn=convert_docx_to_pdf,
            required_tools=("soffice",),
            description="Convert DOCX document to PDF via headless LibreOffice",
        )
    )


# Automatically register on import
register_document_converters()
