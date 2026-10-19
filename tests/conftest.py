"""Pytest fixtures and sample media generators for real format testing."""

from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
from PIL import Image
import pillow_heif

# Enable HEIF opener
pillow_heif.register_heif_opener()

import sys
from PySide6.QtWidgets import QApplication

from filetool.core.deps import resolver
from filetool.core.utils import run_command


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="session")
def samples_dir(tmp_path_factory) -> Path:
    """Generate real, valid sample files for each image, audio, and video type."""
    sample_dir = tmp_path_factory.mktemp("samples")

    # 1. Base Image generation
    base_png = sample_dir / "sample.png"
    img = Image.new("RGB", (64, 64), color=(220, 80, 50))
    img.save(base_png, "PNG")

    base_jpg = sample_dir / "sample.jpg"
    img.save(base_jpg, "JPEG", quality=90)

    base_webp = sample_dir / "sample.webp"
    img.save(base_webp, "WEBP", quality=90)

    base_bmp = sample_dir / "sample.bmp"
    img.save(base_bmp, "BMP")

    base_tiff = sample_dir / "sample.tiff"
    img.save(base_tiff, "TIFF")

    # SVG sample
    base_svg = sample_dir / "sample.svg"
    base_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        '<rect width="64" height="64" fill="coral"/>'
        '<circle cx="32" cy="32" r="20" fill="white"/>'
        '</svg>',
        encoding="utf-8",
    )

    # HEIC sample (using ImageMagick or sips)
    base_heic = sample_dir / "sample.heic"
    magick = resolver.resolve("magick")
    sips = resolver.resolve("sips")
    if magick:
        run_command([str(magick), str(base_png), str(base_heic)])
    elif sips:
        run_command([str(sips), "-s", "format", "heic", str(base_png), "--out", str(base_heic)])

    # AVIF sample (using ImageMagick)
    base_avif = sample_dir / "sample.avif"
    if magick:
        run_command([str(magick), str(base_png), str(base_avif)])

    # 2. Base Audio generation using ffmpeg
    ffmpeg = resolver.get_tool_path("ffmpeg")
    base_wav = sample_dir / "sample.wav"
    run_command([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", str(base_wav)])

    base_mp3 = sample_dir / "sample.mp3"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "libmp3lame", "-b:a", "128k", str(base_mp3)])

    base_m4a = sample_dir / "sample.m4a"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "aac", "-b:a", "128k", str(base_m4a)])

    base_flac = sample_dir / "sample.flac"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "flac", str(base_flac)])

    base_ogg = sample_dir / "sample.ogg"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-ac", "2", "-c:a", "vorbis", "-strict", "-2", str(base_ogg)])

    base_opus = sample_dir / "sample.opus"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "libopus", "-b:a", "96k", str(base_opus)])

    base_aiff = sample_dir / "sample.aiff"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "pcm_s16be", str(base_aiff)])

    base_wma = sample_dir / "sample.wma"
    run_command([ffmpeg, "-y", "-i", str(base_wav), "-c:a", "wmav2", str(base_wma)])

    # 3. Base Video generation using ffmpeg
    base_mp4 = sample_dir / "sample.mp4"
    run_command([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=0.5:size=160x120:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(base_mp4),
    ])

    base_mov = sample_dir / "sample.mov"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-c:v", "copy", "-c:a", "copy", str(base_mov)])

    base_mkv = sample_dir / "sample.mkv"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-c:v", "copy", "-c:a", "copy", str(base_mkv)])

    base_webm = sample_dir / "sample.webm"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-c:v", "libvpx-vp9", "-c:a", "libopus", str(base_webm)])

    base_avi = sample_dir / "sample.avi"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-c:v", "mpeg4", "-c:a", "libmp3lame", str(base_avi)])

    base_wmv = sample_dir / "sample.wmv"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-c:v", "wmv2", "-c:a", "wmav2", str(base_wmv)])

    base_gif = sample_dir / "sample.gif"
    run_command([ffmpeg, "-y", "-i", str(base_mp4), "-vf", "fps=10,scale=160:-1", str(base_gif)])

    # 4. Document samples via Pandoc
    pandoc = resolver.get_tool_path("pandoc")
    base_md = sample_dir / "sample.md"
    base_md.write_text("# Sample Document\n\nThis is test text for Pandoc document conversions.\n", encoding="utf-8")

    base_txt = sample_dir / "sample.txt"
    base_txt.write_text("Plain text sample file content.\n", encoding="utf-8")

    base_html = sample_dir / "sample.html"
    base_html.write_text("<!DOCTYPE html><html><body><h1>Sample</h1><p>Test HTML body</p></body></html>\n", encoding="utf-8")

    base_docx = sample_dir / "sample.docx"
    run_command([pandoc, str(base_md), "-o", str(base_docx)])

    base_rtf = sample_dir / "sample.rtf"
    run_command([pandoc, str(base_md), "-s", "-o", str(base_rtf)])

    base_epub = sample_dir / "sample.epub"
    run_command([pandoc, str(base_md), "-o", str(base_epub)])

    # 5. Office & Slides samples
    soffice = resolver.get_tool_path("soffice")
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "Slide 1 Title"
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Slide 2 Content"
    base_pptx = sample_dir / "sample.pptx"
    prs.save(str(base_pptx))

    # 6. PDF sample (generated with text + table from docx via LibreOffice)
    base_pdf = sample_dir / "sample.pdf"
    run_command([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(sample_dir), str(base_docx)])

    # 7. Spreadsheet samples
    base_csv = sample_dir / "sample.csv"
    base_csv.write_text("Item,Quantity,Price\nWidget A,10,19.99\nWidget B,5,49.50\n", encoding="utf-8")

    base_tsv = sample_dir / "sample.tsv"
    base_tsv.write_text("Item\tQuantity\tPrice\nWidget A\t10\t19.99\nWidget B\t5\t49.50\n", encoding="utf-8")

    import pandas as pd
    df_sample = pd.read_csv(base_csv)
    base_xlsx = sample_dir / "sample.xlsx"
    df_sample.to_excel(base_xlsx, index=False, engine="openpyxl")

    base_ods = sample_dir / "sample.ods"
    run_command([soffice, "--headless", "--convert-to", "ods", "--outdir", str(sample_dir), str(base_xlsx)])

    # 8. Subtitle samples
    base_srt = sample_dir / "sample.srt"
    base_srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello and welcome.\n\n2\n00:00:04,000 --> 00:00:06,000\nEnjoy the video!\n",
        encoding="utf-8",
    )

    base_vtt = sample_dir / "sample.vtt"
    base_vtt.write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.500\nHello and welcome.\n\n2\n00:00:04.000 --> 00:00:06.000\nEnjoy the video!\n",
        encoding="utf-8",
    )

    # 9. Archive samples
    import zipfile
    import tarfile

    base_zip = sample_dir / "sample.zip"
    with zipfile.ZipFile(base_zip, "w") as zf:
        zf.writestr("test_in_zip.txt", "Archive payload")

    base_tar = sample_dir / "sample.tar"
    with tarfile.open(base_tar, "w") as tf:
        tar_entry = sample_dir / "tmp_entry.txt"
        tar_entry.write_text("Archive payload")
        tf.add(tar_entry, arcname="test_in_tar.txt")
        tar_entry.unlink()

    base_gz = sample_dir / "sample.gz"
    with tarfile.open(base_gz, "w:gz") as tf:
        tar_entry = sample_dir / "tmp_entry2.txt"
        tar_entry.write_text("Archive payload")
        tf.add(tar_entry, arcname="test_in_gz.txt")
        tar_entry.unlink()

    return sample_dir
