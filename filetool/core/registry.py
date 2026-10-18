"""Converter registry, metadata schemas, and format capability lookups."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from filetool.core.deps import resolver

logger = logging.getLogger("filetool.registry")


@dataclass
class OptionDefinition:
    name: str
    label: str
    type: type  # int, str, float, bool
    default: Any
    choices: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""


@dataclass
class Converter:
    id: str
    name: str
    input_formats: Tuple[str, ...]
    output_format: str
    category: str
    convert_fn: Callable[[Path, Path, Dict[str, Any]], Path]
    options: Dict[str, OptionDefinition] = field(default_factory=dict)
    required_tools: Tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def is_available(self) -> bool:
        """Return True if all external tools required by this converter exist on the system."""
        for tool in self.required_tools:
            if not resolver.resolve(tool):
                return False
        return True


class ConverterRegistry:
    """Central registry of all file conversion engines."""

    def __init__(self) -> None:
        self._converters: List[Converter] = []
        # Fast lookup map: (normalized_in_ext, normalized_out_ext) -> Converter
        self._lookup: Dict[Tuple[str, str], Converter] = {}
        # Extension to category mapping
        self._ext_to_category: Dict[str, str] = {}

    def register(self, converter: Converter) -> None:
        """Register a converter instance."""
        self._converters.append(converter)
        out_ext = converter.output_format.lower().lstrip(".")
        for in_ext in converter.input_formats:
            norm_in = in_ext.lower().lstrip(".")
            key = (norm_in, out_ext)
            if key in self._lookup:
                logger.debug(
                    "Overriding converter for %s -> %s with %s",
                    norm_in,
                    out_ext,
                    converter.id,
                )
            self._lookup[key] = converter
            if norm_in not in self._ext_to_category:
                self._ext_to_category[norm_in] = converter.category

    def get_converter(self, in_ext: str, out_ext: str) -> Optional[Converter]:
        """Look up a converter for the given input and output extensions."""
        norm_in = in_ext.lower().lstrip(".")
        norm_out = out_ext.lower().lstrip(".")
        return self._lookup.get((norm_in, norm_out))

    def list_outputs(self, in_ext: str, available_only: bool = False) -> List[str]:
        """
        Return a sorted list of supported output formats for a given input format.
        If available_only=True, filters out converters missing required tools.
        """
        norm_in = in_ext.lower().lstrip(".")
        outputs = set()
        for (src, dest), conv in self._lookup.items():
            if src == norm_in:
                if not available_only or conv.is_available():
                    outputs.add(dest)
        return sorted(outputs)

    def is_supported(self, in_ext: str, out_ext: str) -> bool:
        """Check if conversion between format pair is supported."""
        return self.get_converter(in_ext, out_ext) is not None

    def get_category_for_ext(self, ext: str) -> str:
        """Return detected category name (Images, Audio, Video, Documents, etc.)."""
        norm = ext.lower().lstrip(".")
        if norm in self._ext_to_category:
            return self._ext_to_category[norm]

        # Common defaults
        image_exts = {"jpg", "jpeg", "png", "webp", "heic", "tiff", "tif", "avif", "bmp", "svg"}
        audio_exts = {"mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "aif", "wma"}
        video_exts = {"mp4", "mov", "mkv", "webm", "avi", "wmv", "gif"}
        doc_exts = {"docx", "md", "markdown", "txt", "epub", "html", "htm", "rtf", "pdf"}
        slide_exts = {"ppt", "pptx"}
        sheet_exts = {"xlsx", "xls", "ods", "csv", "tsv"}
        sub_exts = {"srt", "vtt"}
        arch_exts = {"zip", "tar", "gz", "tgz", "rar"}

        if norm in image_exts:
            return "Images"
        if norm in audio_exts:
            return "Audio"
        if norm in video_exts:
            return "Video"
        if norm in slide_exts:
            return "Slides"
        if norm in sheet_exts:
            return "Spreadsheets"
        if norm in sub_exts:
            return "Subtitles"
        if norm in arch_exts:
            return "Archives"
        if norm in doc_exts:
            return "Documents"
        return "Other"

    def all_converters(self) -> List[Converter]:
        return list(self._converters)

    def all_supported_pairs(self) -> List[Tuple[str, str, str]]:
        """Return list of (in_ext, out_ext, category) for all registered pairs."""
        pairs = []
        for (src, dest), conv in sorted(self._lookup.items()):
            pairs.append((src, dest, conv.category))
        return pairs


# Global registry singleton
registry = ConverterRegistry()
