"""Subtitle conversion engine supporting SRT, VTT, and TXT."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from filetool.core.registry import Converter, registry

logger = logging.getLogger("filetool.engines.subtitles")

SUBTITLE_FORMATS = ("srt", "vtt", "txt")


@dataclass
class SubtitleCue:
    index: str
    start: str
    end: str
    text: str


def _parse_srt(content: str) -> List[SubtitleCue]:
    """Parse SubRip (.srt) subtitle text."""
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", content.strip())
    cues = []

    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        # Look for the line containing '-->'
        time_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_idx = idx
                break

        if time_idx == -1:
            continue

        cue_idx = lines[0].strip() if time_idx > 0 else str(len(cues) + 1)
        time_parts = lines[time_idx].split("-->")
        start = time_parts[0].strip()
        end = time_parts[1].strip().split()[0]  # strip any inline styling tags
        text = "\n".join(lines[time_idx + 1:])

        cues.append(SubtitleCue(index=cue_idx, start=start, end=end, text=text))

    return cues


def _parse_vtt(content: str) -> List[SubtitleCue]:
    """Parse WebVTT (.vtt) subtitle text."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Strip WEBVTT header and any NOTE comments
    lines = content.split("\n")
    cleaned_lines = []
    skip_header = True

    for line in lines:
        if skip_header:
            if line.startswith("WEBVTT"):
                continue
            if line.strip() == "":
                skip_header = False
                continue
        cleaned_lines.append(line)

    cleaned_content = "\n".join(cleaned_lines)
    blocks = re.split(r"\n\s*\n", cleaned_content.strip())
    cues = []

    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        time_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_idx = idx
                break

        if time_idx == -1:
            continue

        cue_idx = lines[0].strip() if time_idx > 0 else str(len(cues) + 1)
        time_parts = lines[time_idx].split("-->")
        start = time_parts[0].strip()
        end = time_parts[1].strip().split()[0]
        text = "\n".join(lines[time_idx + 1:])

        cues.append(SubtitleCue(index=cue_idx, start=start, end=end, text=text))

    return cues


def _time_srt_to_vtt(ts: str) -> str:
    """Convert SRT timestamp (00:01:20,000) to VTT (00:01:20.000)."""
    return ts.replace(",", ".")


def _time_vtt_to_srt(ts: str) -> str:
    """Convert VTT timestamp (00:01:20.000) to SRT (00:01:20,000)."""
    # If hours are omitted (e.g. 01:20.000), add 00:
    parts = ts.split(":")
    if len(parts) == 2:
        ts = f"00:{ts}"
    return ts.replace(".", ",")


def convert_subtitles(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Convert between SRT, VTT, and plain TXT."""
    in_ext = src.suffix.lower().lstrip(".")
    out_ext = dest.suffix.lower().lstrip(".")
    raw_content = src.read_text(encoding="utf-8", errors="replace")

    cues = _parse_vtt(raw_content) if in_ext == "vtt" else _parse_srt(raw_content)

    if out_ext == "txt":
        # Extract purely spoken dialogue, removing duplicates
        dialogue = []
        for cue in cues:
            clean_text = re.sub(r"<[^>]+>", "", cue.text).strip()
            if clean_text and (not dialogue or dialogue[-1] != clean_text):
                dialogue.append(clean_text)
        dest.write_text("\n".join(dialogue) + "\n", encoding="utf-8")
        return dest

    if out_ext == "srt":
        blocks = []
        for idx, cue in enumerate(cues, start=1):
            start = _time_vtt_to_srt(cue.start)
            end = _time_vtt_to_srt(cue.end)
            blocks.append(f"{idx}\n{start} --> {end}\n{cue.text}")
        dest.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return dest

    if out_ext == "vtt":
        blocks = ["WEBVTT\n"]
        for idx, cue in enumerate(cues, start=1):
            start = _time_srt_to_vtt(cue.start)
            end = _time_srt_to_vtt(cue.end)
            blocks.append(f"{idx}\n{start} --> {end}\n{cue.text}")
        dest.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return dest

    raise ValueError(f"Unsupported subtitle conversion {in_ext} -> {out_ext}")


def register_subtitle_converters() -> None:
    """Register all subtitle conversions."""
    for out_ext in ("srt", "vtt", "txt"):
        valid_inputs = tuple(fmt for fmt in ("srt", "vtt") if fmt != out_ext)
        registry.register(
            Converter(
                id=f"subtitle_to_{out_ext}",
                name=f"Subtitles to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Subtitles",
                convert_fn=convert_subtitles,
                description=f"Convert subtitles to {out_ext.upper()}",
            )
        )


# Automatically register on import
register_subtitle_converters()
