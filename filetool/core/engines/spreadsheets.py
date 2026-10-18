"""Spreadsheet conversion engine supporting XLSX, XLS, ODS, CSV, TSV, and PDF."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from filetool.core.deps import resolver
from filetool.core.registry import Converter, registry
from filetool.core.utils import run_command, safe_temp_dir

logger = logging.getLogger("filetool.engines.spreadsheets")

# Formats
SPREADSHEET_INPUT_FORMATS = ("xlsx", "xls", "ods", "csv", "tsv")
SPREADSHEET_OUTPUT_FORMATS = ("xlsx", "ods", "csv", "tsv", "pdf")


def convert_spreadsheet(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """
    Convert spreadsheet files between XLSX, XLS, ODS, CSV, TSV, and PDF.
    Combines pandas / openpyxl with LibreOffice headless.
    """
    in_ext = src.suffix.lower().lstrip(".")
    out_ext = dest.suffix.lower().lstrip(".")

    # Case 1: Conversion to PDF via LibreOffice headless
    if out_ext == "pdf":
        soffice = resolver.get_tool_path("soffice")
        with safe_temp_dir(prefix="filetool_sheet_pdf_") as tmp_dir:
            cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_dir), str(src)]
            res = run_command(cmd, timeout=90.0)
            expected_pdf = tmp_dir / f"{src.stem}.pdf"
            if not expected_pdf.exists():
                raise RuntimeError(f"Spreadsheet to PDF conversion failed: {res.stderr_tail()}")
            shutil.copy2(expected_pdf, dest)
        return dest

    # Case 2: Conversion to ODS via LibreOffice headless
    if out_ext == "ods":
        soffice = resolver.get_tool_path("soffice")
        with safe_temp_dir(prefix="filetool_sheet_ods_") as tmp_dir:
            cmd = [soffice, "--headless", "--convert-to", "ods", "--outdir", str(tmp_dir), str(src)]
            res = run_command(cmd, timeout=90.0)
            expected_ods = tmp_dir / f"{src.stem}.ods"
            if not expected_ods.exists():
                raise RuntimeError(f"Spreadsheet to ODS conversion failed: {res.stderr_tail()}")
            shutil.copy2(expected_ods, dest)
        return dest

    # Case 3: Read input into pandas DataFrame
    if in_ext == "csv":
        df = pd.read_csv(src)
    elif in_ext == "tsv":
        df = pd.read_csv(src, sep="\t")
    elif in_ext == "xlsx":
        df = pd.read_excel(src, engine="openpyxl")
    elif in_ext in ("xls", "ods"):
        # Use LibreOffice to convert to temporary CSV first to ensure flawless parsing
        soffice = resolver.get_tool_path("soffice")
        with safe_temp_dir(prefix="filetool_sheet_read_") as tmp_dir:
            cmd = [soffice, "--headless", "--convert-to", "csv", "--outdir", str(tmp_dir), str(src)]
            res = run_command(cmd, timeout=90.0)
            expected_csv = tmp_dir / f"{src.stem}.csv"
            if not expected_csv.exists():
                raise RuntimeError(f"Failed parsing spreadsheet format .{in_ext}: {res.stderr_tail()}")
            df = pd.read_csv(expected_csv)
    else:
        df = pd.read_csv(src)

    # Case 4: Write output from DataFrame
    if out_ext == "csv":
        df.to_csv(dest, index=False)
    elif out_ext == "tsv":
        df.to_csv(dest, sep="\t", index=False)
    elif out_ext == "xlsx":
        df.to_excel(dest, index=False, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported spreadsheet output format: .{out_ext}")

    return dest


def register_spreadsheet_converters() -> None:
    """Register all spreadsheet conversions."""
    for out_ext in ("xlsx", "ods", "csv", "tsv", "pdf"):
        valid_inputs = tuple(fmt for fmt in SPREADSHEET_INPUT_FORMATS if fmt != out_ext)
        needs_soffice = out_ext in ("ods", "pdf") or any(f in ("xls", "ods") for f in valid_inputs)

        registry.register(
            Converter(
                id=f"sheet_to_{out_ext}",
                name=f"Spreadsheet to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Spreadsheets",
                convert_fn=convert_spreadsheet,
                required_tools=("soffice",) if needs_soffice else (),
                description=f"Convert spreadsheet to {out_ext.upper()}",
            )
        )


# Automatically register on import
register_spreadsheet_converters()
