"""Converter registry, metadata schemas, and format capability lookups."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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


_IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "webp", "heic", "tiff", "tif", "avif", "bmp", "svg"})
_AUDIO_EXTS = frozenset({"mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "aif", "wma"})
_VIDEO_EXTS = frozenset({"mp4", "mov", "mkv", "webm", "avi", "wmv", "gif"})
_DOC_EXTS = frozenset({"docx", "md", "markdown", "txt", "epub", "html", "htm", "rtf", "pdf"})
_SLIDE_EXTS = frozenset({"ppt", "pptx"})
_SHEET_EXTS = frozenset({"xlsx", "xls", "ods", "csv", "tsv"})
_SUB_EXTS = frozenset({"srt", "vtt"})
_ARCH_EXTS = frozenset({"zip", "tar", "gz", "tgz", "rar"})


class ConverterRegistry:
    """Central registry of all file conversion engines."""

    def __init__(self) -> None:
        self._converters: List[Converter] = []
        # Fast lookup map: (normalized_in_ext, normalized_out_ext) -> Converter
        self._lookup: Dict[Tuple[str, str], Converter] = {}
        # Indexed output map: normalized_in_ext -> {normalized_out_ext: Converter}
        self._by_input: Dict[str, Dict[str, Converter]] = {}
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
            self._by_input.setdefault(norm_in, {})[out_ext] = converter
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
        dest_map = self._by_input.get(norm_in)
        if not dest_map:
            return []
        if not available_only:
            return sorted(dest_map.keys())
        return sorted(dest for dest, conv in dest_map.items() if conv.is_available())

    def is_supported(self, in_ext: str, out_ext: str) -> bool:
        """Check if conversion between format pair is supported."""
        return self.get_converter(in_ext, out_ext) is not None

    def get_category_for_ext(self, ext: str) -> str:
        """Return detected category name (Images, Audio, Video, Documents, etc.)."""
        norm = ext.lower().lstrip(".")
        cached_cat = self._ext_to_category.get(norm)
        if cached_cat is not None:
            return cached_cat

        if norm in _IMAGE_EXTS:
            return "Images"
        if norm in _AUDIO_EXTS:
            return "Audio"
        if norm in _VIDEO_EXTS:
            return "Video"
        if norm in _SLIDE_EXTS:
            return "Slides"
        if norm in _SHEET_EXTS:
            return "Spreadsheets"
        if norm in _SUB_EXTS:
            return "Subtitles"
        if norm in _ARCH_EXTS:
            return "Archives"
        if norm in _DOC_EXTS:
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
