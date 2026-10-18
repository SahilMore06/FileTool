"""Tests for File Tools: Compress, Resize, Crop, Rotate, Trim, Split, Merge, and Strip Metadata."""

from __future__ import annotations

from pathlib import Path
from PIL import Image
import pypdf
import pytest

from filetool.core.tools.compress import compress_image, compress_pdf, compress_video
from filetool.core.tools.crop import crop_image
from filetool.core.tools.merge import merge_images_to_pdf, merge_pdfs, merge_videos
from filetool.core.tools.metadata import strip_image_metadata, strip_pdf_metadata, strip_video_metadata
from filetool.core.tools.resize import resize_image, rotate_image, rotate_pdf
from filetool.core.tools.split import split_pdf_by_pages, split_video_by_time
from filetool.core.tools.trim import trim_media


def test_compress_image(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.jpg"
    dest = tmp_path / "compressed.jpg"
    out = compress_image(src, dest, quality=40)
    assert out.exists()
    assert out.stat().st_size > 0


def test_compress_video(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.mp4"
    dest = tmp_path / "compressed.mp4"
    out = compress_video(src, dest, crf=32)
    assert out.exists()
    assert out.stat().st_size > 0


def test_compress_pdf(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.pdf"
    dest = tmp_path / "compressed.pdf"
    out = compress_pdf(src, dest, setting="/ebook")
    assert out.exists()
    assert out.stat().st_size > 0


def test_resize_and_rotate_image(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.png"
    dest_resize = tmp_path / "resized.png"
    out_resize = resize_image(src, dest_resize, width=32, height=32)
    with Image.open(out_resize) as img:
        assert img.size == (32, 32)

    dest_rotate = tmp_path / "rotated.png"
    out_rotate = rotate_image(src, dest_rotate, degrees=90)
    assert out_rotate.exists()


def test_rotate_pdf(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.pdf"
    dest = tmp_path / "rotated.pdf"
    out = rotate_pdf(src, dest, degrees=90)
    assert out.exists()
    reader = pypdf.PdfReader(str(out))
    assert reader.pages[0].rotation == 90


def test_crop_image(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.png"
    dest = tmp_path / "cropped.png"
    out = crop_image(src, dest, 10, 10, 40, 40)
    with Image.open(out) as img:
        assert img.size == (30, 30)


def test_trim_media(samples_dir: Path, tmp_path: Path):
    # Trim audio
    src_audio = samples_dir / "sample.wav"
    dest_audio = tmp_path / "trimmed.wav"
    out_audio = trim_media(src_audio, dest_audio, start_time=0.1, duration=0.2)
    assert out_audio.exists()

    # Trim video
    src_video = samples_dir / "sample.mp4"
    dest_video = tmp_path / "trimmed.mp4"
    out_video = trim_media(src_video, dest_video, start_time=0.1, duration=0.2)
    assert out_video.exists()


def test_split_pdf(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.pdf"
    dest_dir = tmp_path / "pdf_split"
    parts = split_pdf_by_pages(src, dest_dir)
    assert len(parts) >= 1
    for p in parts:
        assert p.exists()


def test_split_video(samples_dir: Path, tmp_path: Path):
    src = samples_dir / "sample.mp4"
    dest_dir = tmp_path / "video_split"
    parts = split_video_by_time(src, dest_dir, segment_duration_seconds=0.25)
    assert len(parts) >= 1
    for p in parts:
        assert p.exists()


def test_merge_tools(samples_dir: Path, tmp_path: Path):
    # 1. Merge PDFs
    pdf1 = samples_dir / "sample.pdf"
    dest_merged_pdf = tmp_path / "merged.pdf"
    out_pdf = merge_pdfs([pdf1, pdf1], dest_merged_pdf)
    assert out_pdf.exists()
    reader = pypdf.PdfReader(str(out_pdf))
    assert len(reader.pages) == 2 * len(pypdf.PdfReader(str(pdf1)).pages)

    # 2. Merge Images to PDF
    img1 = samples_dir / "sample.png"
    img2 = samples_dir / "sample.jpg"
    dest_imgs_pdf = tmp_path / "images_to_pdf.pdf"
    out_img_pdf = merge_images_to_pdf([img1, img2], dest_imgs_pdf)
    assert out_img_pdf.exists()
    reader2 = pypdf.PdfReader(str(out_img_pdf))
    assert len(reader2.pages) == 2

    # 3. Merge Videos
    vid1 = samples_dir / "sample.mp4"
    dest_merged_vid = tmp_path / "merged.mp4"
    out_vid = merge_videos([vid1, vid1], dest_merged_vid)
    assert out_vid.exists()


def test_strip_metadata(samples_dir: Path, tmp_path: Path):
    src_img = samples_dir / "sample.jpg"
    dest_img = tmp_path / "stripped.jpg"
    out_img = strip_image_metadata(src_img, dest_img)
    assert out_img.exists()

    src_vid = samples_dir / "sample.mp4"
    dest_vid = tmp_path / "stripped.mp4"
    out_vid = strip_video_metadata(src_vid, dest_vid)
    assert out_vid.exists()

    src_pdf = samples_dir / "sample.pdf"
    dest_pdf = tmp_path / "stripped.pdf"
    out_pdf = strip_pdf_metadata(src_pdf, dest_pdf)
    assert out_pdf.exists()
