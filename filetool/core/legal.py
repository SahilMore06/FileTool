"""Structured offline Privacy Policy and Terms & Conditions content for FileTool."""

from __future__ import annotations

from html import escape
from typing import Dict, List, Tuple

LEGAL_VERSION = "1.0"

PRIVACY_HIGHLIGHTS: List[Tuple[str, str]] = [
    ("100% Local Processing", "Every image, audio, video, PDF, and archive runs on your Mac. Zero uploads."),
    ("Zero Telemetry or Ads", "No analytics SDKs, no crash uploads, no tracking identifiers, and no cookies."),
    ("No Accessibility Spying", "Drag Wheel checks NSDragPboard during active drags only; no keystrokes are logged."),
]

TERMS_HIGHLIGHTS: List[Tuple[str, str]] = [
    ("MIT Open-Source License", "Free to use, modify, and share under Copyright (c) 2026 SahilMore06."),
    ("Non-Destructive Defaults", "Outputs are saved with unique names (name (1).ext) unless you turn on Overwrite."),
    ("Provided \"AS IS\"", "Keep backups of important files before batch conversion or turning on Delete Original."),
]

PRIVACY_SECTIONS: List[Tuple[str, List[str]]] = [
    (
        "Offline by Architecture",
        [
            "FileTool executes every conversion, compression, resize, split, merge, and metadata strip strictly on your Mac.",
            "FileTool makes zero network requests for conversions, updates, telemetry, crash reports, or usage analytics.",
            "FileTool sets no cookies, collects no device or user identifiers, and transmits no filenames or conversion history to any server.",
        ],
    ),
    (
        "Local Preferences and Disk Storage",
        [
            "Settings (appearance theme, accent color, wheel trigger keys, menu-bar mode, output directory, overwrite flag, and legal acceptance) are stored locally in macOS QSettings under the FileTool domain.",
            "Turning on Launch at Login creates ~/Library/LaunchAgents/com.filetool.app.plist locally on your account and removes it when turned off.",
            "Converted outputs are written beside each source file by default, or to your chosen local output directory.",
        ],
    ),
    (
        "Finder Drag Wheel Privacy Scope",
        [
            "When Finder Drag Wheel is enabled, MacDragMonitor uses a passive Quartz CGEventTap (kCGEventFlagsChanged) to notice Shift, Command, Control, or Option taps during drags.",
            "It reads NSDragPboard file URLs only while an active drag is detected, without requiring Accessibility permission, and never records typing, passwords, or screen contents.",
        ],
    ),
]

TERMS_SECTIONS: List[Tuple[str, List[str]]] = [
    (
        "1. Open-Source MIT License",
        [
            "FileTool is licensed under the MIT License (Copyright (c) 2026 SahilMore06). You may use, copy, modify, merge, publish, and distribute the software subject to the MIT License notice in LICENSE.",
        ],
    ),
    (
        "2. File Safety and User Responsibility",
        [
            "Default settings keep original source files intact and avoid overwriting existing outputs by adding numeric suffixes such as name (1).ext.",
            "Optional settings such as Overwrite Existing Output Files or Delete Original After Success alter or remove files once conversion succeeds. Back up important data before enabling those options.",
        ],
    ),
    (
        "3. Local Third-Party Engines",
        [
            "FileTool orchestrates local tools installed on your Mac including Pillow, ffmpeg, ImageMagick (magick), Pandoc, Poppler (pdftoppm, pdftotext), Ghostscript (gs), 7-Zip (7zz), and LibreOffice (soffice).",
            "Each third-party engine remains subject to its own open-source license and system availability.",
        ],
    ),
    (
        "4. Warranty Disclaimer",
        [
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM OR IN CONNECTION WITH THE SOFTWARE.",
        ],
    ),
]


def render_legal_html(doc_key: str, tokens: Dict[str, str]) -> str:
    """Render styled HTML for either ``'privacy'`` or ``'terms'`` using theme tokens."""
    if doc_key == "privacy":
        title = "FileTool Privacy Policy"
        lead = "Your files never leave your Mac. Zero uploads, zero telemetry, zero tracking."
        highlights = PRIVACY_HIGHLIGHTS
        sections = PRIVACY_SECTIONS
    else:
        title = "FileTool Terms & Conditions"
        lead = "MIT open-source terms, local file safety defaults, and \"AS IS\" software notice."
        highlights = TERMS_HIGHLIGHTS
        sections = TERMS_SECTIONS

    fg = tokens["text_primary"]
    fg2 = tokens["text_secondary"]
    accent_text = tokens["accent_text"]
    border = tokens["border"]

    blocks: List[str] = [
        f"<div style='font-family: \".AppleSystemUIFont\", \"Helvetica Neue\", sans-serif; color: {fg}; line-height: 1.55;'>",
        f"<h2 style='margin: 0 0 4px 0; font-size: 16px; font-weight: 700; color: {fg};'>{escape(title)}</h2>",
        f"<p style='margin: 0 0 12px 0; font-size: 12.5px; color: {fg2};'>{escape(lead)}</p>",
        f"<div style='border-bottom: 1px solid {border}; padding-bottom: 10px; margin-bottom: 12px;'>",
    ]
    for h_title, h_desc in highlights:
        blocks.append(
            f"<p style='margin: 0 0 6px 0; font-size: 12px; color: {fg};'>"
            f"<span style='font-weight: 700; color: {accent_text};'>{escape(h_title)}:</span> "
            f"{escape(h_desc)}</p>"
        )
    blocks.append("</div>")

    for heading, paragraphs in sections:
        blocks.append(
            f"<h3 style='margin: 12px 0 5px 0; font-size: 13px; font-weight: 700; color: {fg};'>{escape(heading)}</h3>"
        )
        for para in paragraphs:
            blocks.append(
                f"<p style='margin: 0 0 7px 0; font-size: 12px; color: {fg2};'>{escape(para)}</p>"
            )

    blocks.append("</div>")
    return "".join(blocks)
