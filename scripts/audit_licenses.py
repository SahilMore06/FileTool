#!/usr/bin/env python3
"""Python and external binary license inventory + CI policy gate for Fluxora."""

from __future__ import annotations

import argparse
import importlib.metadata as md
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

# First-party editable distributions in local environments
FIRST_PARTY_NAMES: Set[str] = {"fluxora", "filetool"}

# Build-only tools (not linked into the runtime Python app)
BUILD_EXCEPTION_PACKAGES: Dict[str, str] = {
    "pyinstaller": "GPL-2.0-or-later WITH Bootloader-exception (build tool only)",
    "pyinstaller-hooks-contrib": "Apache-2.0 OR GPL-2.0-only (build tool only)",
}

# Temporary Phase 0 allowlist ONLY for pre-existing transitive copyleft dependencies
# tracked for removal/replacement in Phase 2 (see docs/LICENSE_REMEDIATION.md).
DEFAULT_ALLOWED_STRONG_COPYLEFT: Set[str] = {"pymupdf"}

EXTERNAL_BINARIES: List[Dict[str, str]] = [
    {
        "binary": "ffmpeg / ffprobe",
        "project": "FFmpeg",
        "license": "LGPL-2.1+ or GPL-2.0+ (depends on build flags)",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Bundle documented LGPL-only build or prefer AVFoundation for common codecs.",
        "source_url": "https://ffmpeg.org/download.html",
    },
    {
        "binary": "gs",
        "project": "Ghostscript",
        "license": "AGPL-3.0-only / Artifex Commercial",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Replace default PDF compression with native PDFKit/Quartz; keep Ghostscript optional user-installed.",
        "source_url": "https://ghostscript.com/releases/gsdnld.html",
    },
    {
        "binary": "pandoc",
        "project": "Pandoc",
        "license": "GPL-2.0-or-later",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Keep separate unmodified executable with source offer/notices or optional user install.",
        "source_url": "https://github.com/jgm/pandoc",
    },
    {
        "binary": "pdftoppm / pdftotext",
        "project": "Poppler",
        "license": "GPL-2.0-only / GPL-3.0-only",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Prefer native macOS PDFKit rendering/extraction; keep Poppler optional user-installed.",
        "source_url": "https://poppler.freedesktop.org/",
    },
    {
        "binary": "soffice",
        "project": "LibreOffice",
        "license": "MPL-2.0",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Keep optional user-installed external process; never bundle inside DMG.",
        "source_url": "https://www.libreoffice.org/download/download-libreoffice/",
    },
    {
        "binary": "magick",
        "project": "ImageMagick",
        "license": "ImageMagick (Apache-2.0 compatible)",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Prefer native macOS ImageIO + Pillow; keep ImageMagick optional.",
        "source_url": "https://github.com/ImageMagick/ImageMagick",
    },
    {
        "binary": "7zz",
        "project": "7-Zip",
        "license": "LGPL-2.1+ with unRAR restriction",
        "invocation": "External subprocess (shell=False)",
        "phase2_plan": "Audit unRAR restriction before bundling; use Python stdlib zipfile/tarfile by default.",
        "source_url": "https://www.7-zip.org/download.html",
    },
]


def _extract_license_text(dist: md.Distribution) -> str:
    name_norm = (dist.metadata.get("Name") or "").strip().lower()
    if name_norm in FIRST_PARTY_NAMES:
        return "MIT (first-party)"
    if name_norm in BUILD_EXCEPTION_PACKAGES:
        return BUILD_EXCEPTION_PACKAGES[name_norm]

    expr = (dist.metadata.get("License-Expression") or "").strip()
    if expr:
        return expr

    classifiers = [
        c.split("License :: ", 1)[1].strip()
        for c in (dist.metadata.get_all("Classifier") or [])
        if c.startswith("License :: ")
    ]
    raw_license = (dist.metadata.get("License") or "").strip()
    first_line = raw_license.splitlines()[0].strip() if raw_license else ""

    if first_line and first_line.lower() not in {"unknown", "dual license", "other/proprietary license"}:
        if len(first_line) <= 100:
            return first_line
        return first_line[:97] + "..."

    if classifiers:
        return "; ".join(classifiers)

    return first_line or "UNKNOWN"


def classify_license(license_text: str) -> str:
    """Classify a license string into permissive, weak-copyleft, build-exception, strong-copyleft, or unknown."""
    text = (license_text or "").strip()
    if not text or text.upper() == "UNKNOWN":
        return "unknown"
    lower = text.lower()

    if "build tool only" in lower or "bootloader-exception" in lower:
        return "build-exception"

    # Strong copyleft must be checked before permissive substrings (except explicit dual/LGPL OR choices)
    if "affero" in lower or "agpl" in lower:
        return "strong-copyleft"

    # Dual-licensed with permissive option (e.g. "Apache-2.0 OR GPL-2.0") or LGPL OR GPL
    if "lgpl" in lower or "lesser general public" in lower or "mpl" in lower or "mozilla public" in lower:
        return "weak-copyleft"

    permissive_markers = (
        "mit",
        "bsd",
        "apache",
        "psf",
        "python software foundation",
        "isc",
        "zlib",
        "cc0",
        "0bsd",
        "unlicense",
        "hpnd",
        "first-party",
    )
    has_gpl = "gpl" in lower or "general public license" in lower
    has_permissive = any(marker in lower for marker in permissive_markers)

    if has_gpl and not (" or " in lower and has_permissive):
        return "strong-copyleft"
    if has_permissive:
        return "permissive"
    return "unknown"


def collect_python_licenses() -> List[Dict[str, str]]:
    """Collect normalized license records for every installed Python distribution."""
    seen: Dict[str, Dict[str, str]] = {}
    for dist in md.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if not name:
            continue
        key = name.lower()
        lic = _extract_license_text(dist)
        category = classify_license(lic)
        seen[key] = {
            "name": name,
            "version": dist.version or "unknown",
            "license": lic,
            "category": category,
        }
    return sorted(seen.values(), key=lambda r: r["name"].lower())


def check_policy(
    records: Iterable[Dict[str, str]],
    allowed_strong_copyleft: Optional[Set[str]] = None,
) -> List[str]:
    """Return policy violation messages for unknown or unapproved strong-copyleft packages."""
    allowed = {
        name.lower()
        for name in (
            DEFAULT_ALLOWED_STRONG_COPYLEFT
            if allowed_strong_copyleft is None
            else allowed_strong_copyleft
        )
    }
    violations: List[str] = []
    for rec in records:
        name = rec["name"]
        cat = rec["category"]
        lic = rec["license"]
        if cat == "unknown":
            violations.append(f"UNKNOWN license: {name}=={rec['version']} ({lic})")
        elif cat == "strong-copyleft" and name.lower() not in allowed:
            violations.append(f"UNAPPROVED strong-copyleft: {name}=={rec['version']} ({lic})")
    return violations


def render_third_party_notices(records: List[Dict[str, str]]) -> str:
    """Render THIRD_PARTY_NOTICES.md from live Python packages and external binary table."""
    lines: List[str] = [
        "# Third-Party Software Notices",
        "",
        "Fluxora itself is licensed under the [MIT License](LICENSE).",
        "",
        "This file inventories third-party Python packages detected in the build environment and external local CLI tools invoked as separate processes (`shell=False`). Regenerate anytime with:",
        "",
        "```bash",
        ".venv/bin/python scripts/audit_licenses.py --write-notices THIRD_PARTY_NOTICES.md",
        "```",
        "",
        "## License Compliance Notes (Phase 0 Audit)",
        "",
        "- **Action tracked for Phase 2 (`pymupdf`):** `pdf2docx` transitively installs `PyMuPDF` (`AGPL-3.0`). Do **not** bundle `PyMuPDF` into a closed or MIT-only binary distribution without removing/replacing `pdf2docx` or shipping under compliant separation. See [docs/LICENSE_REMEDIATION.md](docs/LICENSE_REMEDIATION.md).",
        "- **Qt / PySide6 (`LGPL-3.0-only`):** Dynamically linked under LGPL-3.0 obligations; users can inspect and relink Qt libraries.",
        "- **pillow-heif (`BSD-3-Clause` wrapper):** Prebuilt wheels include `libheif` (`LGPL-3.0`); verify wheel notice compliance before macOS app bundling.",
        "- **External CLI tools:** Invoked strictly via separate subprocesses (`shell=False`) and currently installed separately by the user (e.g., via Homebrew).",
        "",
        "## Python Packages",
        "",
        "| Package | Version | License | Category |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for rec in records:
        if rec["name"].lower() in FIRST_PARTY_NAMES:
            continue
        lic_safe = rec["license"].replace("|", "\\|")
        lines.append(f"| `{rec['name']}` | `{rec['version']}` | {lic_safe} | `{rec['category']}` |")

    lines.extend(
        [
            "",
            "## External CLI Binaries (Separate Subprocesses)",
            "",
            "| Binary | Upstream Project | License | Invocation | Phase 2 Direction | Source |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for item in EXTERNAL_BINARIES:
        lines.append(
            f"| `{item['binary']}` | {item['project']} | {item['license']} | "
            f"{item['invocation']} | {item['phase2_plan']} | {item['source_url']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Fluxora Python and external tool licenses.")
    parser.add_argument("--check", action="store_true", help="Fail non-zero if license policy violations exist.")
    parser.add_argument("--strict", action="store_true", help="Disallow all strong-copyleft packages including Phase 0 allowlist.")
    parser.add_argument("--write-notices", type=Path, default=None, help="Write THIRD_PARTY_NOTICES.md to path.")
    args = parser.parse_args(argv)

    records = collect_python_licenses()
    if args.write_notices is not None:
        args.write_notices.write_text(render_third_party_notices(records), encoding="utf-8")
        print(f"Wrote {args.write_notices} ({len(records)} Python distributions scanned).")

    if args.check or args.write_notices is None:
        allowed = set() if args.strict else DEFAULT_ALLOWED_STRONG_COPYLEFT
        violations = check_policy(records, allowed_strong_copyleft=allowed)
        if violations:
            print("License policy violations detected:", file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
            return 1
        print(f"License audit passed ({len(records)} distributions checked; Phase 0 allowlist={sorted(allowed)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
