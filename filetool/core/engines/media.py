"""Audio and Video conversion engine using local ffmpeg/ffprobe."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from filetool.core.deps import resolver
from filetool.core.registry import Converter, OptionDefinition, registry
from filetool.core.utils import run_command

logger = logging.getLogger("filetool.engines.media")

# Audio formats
AUDIO_FORMATS = ("mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "aif", "wma")

# Video formats
VIDEO_FORMATS = ("mp4", "mov", "mkv", "webm", "avi", "wmv", "gif")

AUDIO_OPTIONS = {
    "bitrate": OptionDefinition(
        name="bitrate",
        label="Audio Bitrate",
        type=str,
        default="192k",
        choices=["128k", "192k", "256k", "320k"],
        description="Target bitrate for lossy audio formats",
    ),
}

VIDEO_OPTIONS = {
    "crf": OptionDefinition(
        name="crf",
        label="Video Quality (CRF)",
        type=int,
        default=23,
        min_value=0,
        max_value=51,
        description="Constant Rate Factor (lower is higher quality, default 23)",
    ),
    "preset": OptionDefinition(
        name="preset",
        label="Encoder Preset",
        type=str,
        default="medium",
        choices=["ultrafast", "fast", "medium", "slow"],
        description="FFmpeg speed/compression tradeoff preset",
    ),
    "resolution": OptionDefinition(
        name="resolution",
        label="Resolution",
        type=str,
        default="original",
        choices=["original", "1080p", "720p", "480p"],
        description="Scale video to specified resolution height while keeping aspect ratio",
    ),
    "audio_bitrate": OptionDefinition(
        name="audio_bitrate",
        label="Audio Bitrate",
        type=str,
        default="192k",
        choices=["128k", "192k", "256k", "320k"],
        description="Target audio bitrate for video audio track",
    ),
}


def _get_resolution_filter(res: str) -> list[str]:
    """Generate scaling video filter if resolution is constrained."""
    if res == "1080p":
        return ["-vf", "scale=-2:1080"]
    if res == "720p":
        return ["-vf", "scale=-2:720"]
    if res == "480p":
        return ["-vf", "scale=-2:480"]
    return []


def convert_audio(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Convert between audio formats using ffmpeg."""
    ffmpeg = resolver.get_tool_path("ffmpeg")
    out_ext = dest.suffix.lower().lstrip(".")
    bitrate = str(options.get("bitrate", "192k"))

    cmd = [ffmpeg, "-y", "-i", str(src)]

    if out_ext == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])
    elif out_ext == "m4a":
        cmd.extend(["-c:a", "aac", "-b:a", bitrate])
    elif out_ext == "wav":
        cmd.extend(["-c:a", "pcm_s16le"])
    elif out_ext == "flac":
        cmd.extend(["-c:a", "flac"])
    elif out_ext == "ogg":
        # Native vorbis requires stereo / 2 channels and strict flag
        cmd.extend(["-c:a", "vorbis", "-ac", "2", "-strict", "-2", "-b:a", bitrate])
    elif out_ext == "opus":
        cmd.extend(["-c:a", "libopus", "-b:a", bitrate])
    elif out_ext in ("aiff", "aif"):
        cmd.extend(["-c:a", "pcm_s16be"])
    elif out_ext == "wma":
        cmd.extend(["-c:a", "wmav2", "-b:a", bitrate])
    else:
        cmd.extend(["-b:a", bitrate])

    cmd.append(str(dest))

    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"Audio conversion failed: {res.stderr_tail()}")
    return dest


def convert_video(src: Path, dest: Path, options: Dict[str, Any]) -> Path:
    """Convert between video formats or extract audio to mp3."""
    ffmpeg = resolver.get_tool_path("ffmpeg")
    out_ext = dest.suffix.lower().lstrip(".")
    crf = str(options.get("crf", 23))
    preset = str(options.get("preset", "medium"))
    resolution = str(options.get("resolution", "original"))
    audio_bitrate = str(options.get("audio_bitrate", "192k"))

    # Case 1: Extract audio to MP3 from Video
    if out_ext == "mp3":
        cmd = [ffmpeg, "-y", "-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", audio_bitrate, str(dest)]
        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"Audio extraction from video failed: {res.stderr_tail()}")
        return dest

    # Case 2: Convert video to GIF
    if out_ext == "gif":
        scale_str = "scale=-2:480:flags=lanczos," if resolution != "original" else "scale=flags=lanczos,"
        filter_str = f"fps=15,{scale_str}split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        cmd = [ffmpeg, "-y", "-i", str(src), "-vf", filter_str, str(dest)]
        res = run_command(cmd)
        if not res.success or not dest.exists():
            raise RuntimeError(f"GIF generation failed: {res.stderr_tail()}")
        return dest

    # Case 3: Convert to standard video container
    cmd = [ffmpeg, "-y", "-i", str(src)]
    cmd.extend(_get_resolution_filter(resolution))

    if out_ext in ("mp4", "mov", "mkv"):
        cmd.extend([
            "-c:v", "libx264",
            "-crf", crf,
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ])
        if out_ext == "mp4":
            cmd.extend(["-movflags", "+faststart"])
    elif out_ext == "webm":
        cmd.extend([
            "-c:v", "libvpx-vp9",
            "-crf", crf,
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", audio_bitrate,
        ])
    elif out_ext == "avi":
        cmd.extend([
            "-c:v", "mpeg4",
            "-q:v", "3",
            "-c:a", "libmp3lame",
            "-b:a", audio_bitrate,
        ])
    elif out_ext == "wmv":
        cmd.extend([
            "-c:v", "wmv2",
            "-q:v", "3",
            "-c:a", "wmav2",
            "-b:a", audio_bitrate,
        ])
    else:
        cmd.extend(["-crf", crf, "-preset", preset])

    cmd.append(str(dest))

    res = run_command(cmd)
    if not res.success or not dest.exists():
        raise RuntimeError(f"Video conversion failed: {res.stderr_tail()}")
    return dest


def register_media_converters() -> None:
    """Register audio and video converters into registry."""
    # Audio to Audio
    for out_ext in ("mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma"):
        valid_inputs = tuple(
            fmt for fmt in AUDIO_FORMATS
            if fmt != out_ext and not (fmt in ("aiff", "aif") and out_ext in ("aiff", "aif"))
        )
        registry.register(
            Converter(
                id=f"audio_to_{out_ext}",
                name=f"Audio to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Audio",
                convert_fn=convert_audio,
                options=AUDIO_OPTIONS,
                required_tools=("ffmpeg",),
                description=f"Transcode audio to {out_ext.upper()} with quality controls",
            )
        )

    # Video to Video
    for out_ext in ("mp4", "mov", "mkv", "webm", "avi", "wmv", "gif"):
        valid_inputs = tuple(fmt for fmt in VIDEO_FORMATS if fmt != out_ext)
        registry.register(
            Converter(
                id=f"video_to_{out_ext}",
                name=f"Video to {out_ext.upper()}",
                input_formats=valid_inputs,
                output_format=out_ext,
                category="Video",
                convert_fn=convert_video,
                options=VIDEO_OPTIONS,
                required_tools=("ffmpeg",),
                description=f"Transcode video to {out_ext.upper()} with CRF quality controls",
            )
        )

    # Video to MP3 (Audio extraction)
    registry.register(
        Converter(
            id="video_to_mp3",
            name="Extract Audio to MP3",
            input_formats=VIDEO_FORMATS,
            output_format="mp3",
            category="Video",
            convert_fn=convert_video,
            options={
                "audio_bitrate": OptionDefinition(
                    name="audio_bitrate",
                    label="Audio Bitrate",
                    type=str,
                    default="192k",
                    choices=["128k", "192k", "256k", "320k"],
                    description="Bitrate of the extracted MP3 audio",
                )
            },
            required_tools=("ffmpeg",),
            description="Extract audio track from video files to MP3",
        )
    )


# Automatically register on import
register_media_converters()
