"""CLI interface for FileTool (python -m filetool.cli input.heic --to jpg)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is at sys.path[0] and filetool directory is not in sys.path
# to avoid shadowing the standard library 'platform' module
_filetool_dir = str(Path(__file__).resolve().parent)
_project_root = str(Path(__file__).resolve().parent.parent)
if _filetool_dir in sys.path:
    sys.path.remove(_filetool_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Ensure all engines are loaded and registered
import filetool.core.engines.archives  # noqa: F401
import filetool.core.engines.images  # noqa: F401
import filetool.core.engines.media  # noqa: F401
import filetool.core.engines.office  # noqa: F401
import filetool.core.engines.pandoc_docs  # noqa: F401
import filetool.core.engines.pdf  # noqa: F401
import filetool.core.engines.spreadsheets  # noqa: F401
import filetool.core.engines.subtitles  # noqa: F401
from filetool.core.deps import check_dependencies, format_dependency_report
from filetool.core.registry import registry
from filetool.core.utils import get_unique_output_path, setup_logging


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="filetool",
        description="Native offline file conversion for macOS (Apple Silicon).",
    )

    parser.add_argument("input_file", nargs="?", type=str, help="Path to input file to convert")
    parser.add_argument("--to", dest="output_format", type=str, help="Target output format extension (e.g. jpg, mp4)")
    parser.add_argument("--out-dir", dest="out_dir", type=str, default=None, help="Output directory (defaults to source folder)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing target file instead of appending (1)")
    parser.add_argument("--quality", type=int, default=85, help="Image quality (1-100, default 85)")
    parser.add_argument("--dpi", type=int, default=300, help="PDF / rasterization DPI (default 300)")
    parser.add_argument("--bitrate", type=str, default="192k", help="Audio bitrate (128k, 192k, 256k, 320k)")
    parser.add_argument("--crf", type=int, default=23, help="Video CRF quality (0-51, default 23)")
    parser.add_argument("--resolution", type=str, default="original", choices=["original", "1080p", "720p", "480p"])
    parser.add_argument("--check-deps", action="store_true", help="Display external tool dependency health report")
    parser.add_argument("--list-formats", action="store_true", help="List supported target formats for input file")

    parsed = parser.parse_args(args)
    setup_logging()

    if parsed.check_deps:
        print(format_dependency_report())
        missing = [s for s in check_dependencies().values() if not s.available]
        return 1 if missing else 0

    if not parsed.input_file:
        parser.print_help()
        return 0

    src_path = Path(parsed.input_file).resolve()
    if not src_path.is_file():
        print(f"Error: Input file '{parsed.input_file}' does not exist.", file=sys.stderr)
        return 1

    in_ext = src_path.suffix.lower().lstrip(".")

    if parsed.list_formats:
        outputs = registry.list_outputs(in_ext)
        if not outputs:
            print(f"No conversions registered for .{in_ext}")
        else:
            print(f"Available output formats for .{in_ext}:")
            for out in outputs:
                conv = registry.get_converter(in_ext, out)
                avail_str = "✔ available" if conv and conv.is_available() else "✖ missing tool"
                print(f"  - {out.upper():8s} [{avail_str}]")
        return 0

    if not parsed.output_format:
        outputs = registry.list_outputs(in_ext)
        print(f"Error: Missing --to format. Supported outputs for .{in_ext}: {', '.join(outputs)}", file=sys.stderr)
        return 1

    out_ext = parsed.output_format.lower().lstrip(".")
    conv = registry.get_converter(in_ext, out_ext)
    if not conv:
        print(f"Error: Conversion from .{in_ext} to .{out_ext} is not supported.", file=sys.stderr)
        return 1

    if not conv.is_available():
        missing = [tool for tool in conv.required_tools if not filetool.core.deps.resolver.resolve(tool)]
        print(f"Error: Required tool(s) missing: {', '.join(missing)}", file=sys.stderr)
        return 1

    # Determine destination path
    out_dir = Path(parsed.out_dir).resolve() if parsed.out_dir else src_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target_dest = out_dir / f"{src_path.stem}.{out_ext}"

    if not parsed.overwrite:
        target_dest = get_unique_output_path(target_dest)

    options = {
        "quality": parsed.quality,
        "dpi": parsed.dpi,
        "bitrate": parsed.bitrate,
        "crf": parsed.crf,
        "resolution": parsed.resolution,
        "audio_bitrate": parsed.bitrate,
    }

    print(f"Converting: {src_path.name} -> {target_dest.name} ...", end=" ", flush=True)
    try:
        result_path = conv.convert_fn(src_path, target_dest, options)
        print("DONE ✔")
        print(f"Output saved to: {result_path}")
        return 0
    except Exception as exc:
        print("FAILED ✖", file=sys.stderr)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
