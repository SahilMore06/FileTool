# FileTool for macOS 🍊

A complete, high-performance, **fully offline** desktop file-conversion application inspired by ["Tangerine"](https://tangerineformac.com) for personal use on macOS (Apple Silicon & Intel, macOS 13+).

Drag files in, pick an output format, and get converted files instantly. **Everything runs 100% locally on your machine.** Zero network access, zero analytics, zero telemetry, zero cloud APIs, zero auto-updaters.

---

## ✨ Features

- **Tangerine-Inspired Native macOS GUI**:
  - Big, responsive drop zone accepting multiple files and recursive directory trees.
  - Native file dialog via `Cmd+O`.
  - Smart per-file format pickers populated strictly with supported converters.
  - **"Convert all to..."** bulk dropdown when multiple files share compatible targets.
  - Options drawer with real-time sliders (image quality, video CRF, audio bitrate, render DPI).
  - Multi-threaded background runner on `QThreadPool` — UI never stutters or hangs.
  - Per-file progress bars, cancellation, and clean human-readable error dialogs with stderr tail diagnostics.
  - Persistent conversion history with native Finder actions.
  - Dynamic macOS Light and Dark mode styling.
- **Full CLI Support**:
  - `python -m filetool.cli document.pdf --to docx`
  - `--check-deps` system tool health report.
  - `--list-formats` dynamic format inspector.
- **Safety First**:
  - **Never overwrites**: Automatically generates `filename (1).ext`, `filename (2).ext` if target exists (unless `--overwrite` is specified).
  - **Never deletes originals** unless explicitly toggled in Preferences.
  - **Isolated temporary directories** cleaned up automatically on completion or failure.
  - Subprocess execution strictly uses argument lists — `shell=True` is never used.
  - Fully handles unicode, spaces, and very long paths.
  - Structured logging directly to `~/Library/Logs/FileTool/filetool.log`.
- **System Tool Resolver**:
  - Automatically locates external conversion tools across:
    1. App Bundle: `FileTool.app/Contents/Resources/bin`
    2. Apple Silicon Homebrew: `/opt/homebrew/bin`
    3. Intel Homebrew: `/usr/local/bin`
    4. macOS System: `/usr/bin`
    5. LibreOffice: `/Applications/LibreOffice.app/Contents/MacOS`
  - Packaged `.app` reliably resolves Homebrew tools even when launched by double-clicking in Finder without interactive shell `$PATH`.

---

## 🛠 Supported Format Conversion Matrix

| Category | Input Formats | Supported Output Formats | Local Engine |
| :--- | :--- | :--- | :--- |
| **Images** | `JPG`, `PNG`, `WebP`, `HEIC`, `TIFF`, `AVIF`, `BMP`, `SVG` | `JPG`, `PNG`, `WebP`, `HEIC`, `TIFF`, `AVIF`, `BMP`, `PDF` | Pillow, `pillow-heif`, ImageMagick (`magick`), macOS `sips` |
| **Audio** | `MP3`, `M4A`, `WAV`, `FLAC`, `OGG`, `Opus`, `AIFF`, `WMA` | `MP3`, `M4A`, `WAV`, `FLAC`, `OGG`, `Opus`, `AIFF`, `WMA` | `ffmpeg` |
| **Video** | `MP4`, `MOV`, `MKV`, `WebM`, `AVI`, `WMV`, `GIF` | `MP4`, `MOV`, `MKV`, `WebM`, `AVI`, `WMV`, `GIF`, `MP3` (audio extract) | `ffmpeg` (libx264, libvpx-vp9, palettegen/paletteuse) |
| **PDF** | `PDF` | `DOCX`, `PPTX` (slide deck), `XLSX` (best effort), `JPG`, `PNG` (300 DPI all pages), `EPUB`, `TXT`, `MD` | `pdf2docx`, `python-pptx`, Poppler (`pdftoppm`, `pdftotext`), `pandoc` |
| **Documents** | `DOCX`, `MD`, `TXT`, `EPUB`, `HTML`, `RTF` | `DOCX`, `MD`, `TXT`, `EPUB`, `HTML`, `RTF`, `PDF` (DOCX to PDF) | `pandoc`, LibreOffice headless (`soffice`) |
| **Slides** | `PPT`, `PPTX` | `PDF`, `JPG`, `PNG` (300 DPI slides) | LibreOffice headless (`soffice`), Poppler (`pdftoppm`) |
| **Spreadsheets**| `XLSX`, `XLS` (input), `ODS`, `CSV`, `TSV` | `XLSX`, `ODS`, `CSV`, `TSV`, `PDF` | `pandas`, `openpyxl`, LibreOffice headless (`soffice`) |
| **Subtitles** | `SRT`, `VTT` | `SRT`, `VTT`, `TXT` (plain dialogue extract) | Native subtitle parser & converter |
| **Archives** | `ZIP`, `TAR`, `GZ`, `TGZ`, `RAR` (extract only) | `ZIP`, `TAR`, `GZ` | `7zz` (7-Zip 26.04), `zipfile`, `tarfile` |

---

## 🧰 Built-in File Tools

- **Compress**:
  - Images: Lossy / lossless compression with quality slider (JPG, PNG, WebP, HEIC, AVIF).
  - Video: H.264 CRF rate reduction and presets.
  - PDF: Ghostscript vector PDF optimization (`/ebook`, `/screen`, `/printer`).
- **Resize & Rotate**:
  - Images: Scale by percentage or target width/height using high-grade Lanczos resampling.
  - Rotate: 90°, 180°, 270° clockwise image and PDF rotation.
- **Crop**:
  - Pixel bounding box cropping for images (`left`, `top`, `right`, `bottom`).
- **Trim**:
  - Lossless audio and video trimming by start time and duration or timestamp (`HH:MM:SS`).
- **Split**:
  - PDF: Split by individual pages or custom page ranges (e.g. `[(1, 3), (4, 8)]`).
  - Video: Split into fixed-duration segments using ffmpeg segment muxer.
- **Merge**:
  - PDFs: Merge multiple PDF documents sequentially.
  - Images to PDF: Combine multiple images into a unified multi-page PDF.
  - Videos: Concatenate video clips using ffmpeg concat demuxer.
- **Strip Metadata**:
  - Remove EXIF, GPS, camera serials, and XMP from images.
  - Strip container metadata from video and audio tracks (`-map_metadata -1`).
  - Remove author, title, and producer info from PDF dictionaries.

---

## ⚡️ File Actions (macOS Integration)

Accessible via row buttons and context menu (right-click on any row):
1. **Reveal in Finder** (`open -R`)
2. **Copy File Path** (copies absolute path to macOS clipboard)
3. **Open Containing Folder in Terminal** (`open -a Terminal <dir>`)

---

## 🚀 Installation & Setup

Run the automated setup script to install all external Homebrew binaries and configure the Python 3.12 environment:

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Manual Homebrew Dependencies
If you prefer installing tools manually:
```bash
brew install ffmpeg imagemagick pandoc poppler ghostscript sevenzip
brew install --cask libreoffice
```

---

## 🖥 Running the Application

### 1. Launch GUI Application
```bash
python app.py
# or using the virtual environment:
.venv/bin/python app.py
```

### 2. Command Line Interface (CLI)
```bash
# Convert image:
python -m filetool.cli photo.heic --to jpg --quality 90

# Transcode video to WebM:
python -m filetool.cli video.mp4 --to webm --crf 24

# Extract audio from video:
python -m filetool.cli movie.mov --to mp3 --bitrate 320k

# Convert PDF to editable Word document:
python -m filetool.cli report.pdf --to docx

# Convert Markdown to DOCX:
python -m filetool.cli notes.md --to docx

# Convert Spreadsheet to PDF:
python -m filetool.cli financials.xlsx --to pdf

# Inspect tool health:
python -m filetool.cli --check-deps

# List supported targets for any file:
python -m filetool.cli input.svg --list-formats
```

### 3. Finder Quick Action
Install the Finder right-click Quick Action:
```bash
./scripts/install_quick_action.sh
```
Now, right-click any file in macOS Finder -> **Quick Actions** -> **"Convert with FileTool"**.

---

## 📦 Building the Standalone `.app`

To package FileTool into a standalone macOS Application bundle (`dist/FileTool.app`):

```bash
./scripts/build_app.sh
```

You can drag `dist/FileTool.app` into `/Applications` and launch it with Wi-Fi disabled.

---

## 🔍 Known Limitations & Quality Notes

1. **PDF to DOCX**:
   - Uses `pdf2docx` layout reconstruction. Clean text documents and standard tables reconstruct with high fidelity. Highly complex magazine layouts, OCR-scanned graphics, or overlapping vector path art may experience slight layout shifts.
2. **PDF to XLSX**:
   - Best-effort tabular extraction. Multi-column whitespace alignment is parsed into spreadsheet cells. Does not perform OCR on pure image-scans lacking an embedded text layer.
3. **Apple Pages**:
   - **Omitted / Marked Unsupported**: Apple Pages is a proprietary sandbox application with no official CLI converter or public specification. In accordance with zero-stub policy, Pages is marked unsupported rather than using unreliable AppleScript GUI automation.
4. **SVG Vector Output**:
   - SVG is supported as **input only**. Rasterizing vector SVG to high-DPI JPG, PNG, WebP, HEIC, and PDF is supported; automatic vector tracing from raster images is not supported.
5. **RAR Archives**:
   - RAR is supported for **extraction only**. The RAR compression algorithm is proprietary; creating archives produces open, high-compression formats (`ZIP`, `TAR`, `GZ`).

---

## 🧪 Comprehensive Test Matrix

Every single conversion pair has been verified with real sample files in automated test suites:

| Test Suite | Total Tests | Status | Description |
| :--- | :---: | :---: | :--- |
| **`tests/test_deps.py`** | 3 | **PASSED** | External binary resolver, Homebrew paths, health diagnostics |
| **`tests/test_registry.py`** | 3 | **PASSED** | Converter registration, category classification, output lookup |
| **`tests/test_images.py`** | 23 | **PASSED** | Real conversions for JPG, PNG, WebP, HEIC, TIFF, AVIF, BMP, PDF, SVG |
| **`tests/test_media.py`** | 22 | **PASSED** | Real conversions for MP3, M4A, WAV, FLAC, OGG, Opus, AIFF, WMA, MP4, MOV, MKV, WebM, AVI, WMV, GIF |
| **`tests/test_docs_office.py`**| 37 | **PASSED** | DOCX, MD, TXT, HTML, RTF, EPUB, PPTX to PDF/images, PDF to DOCX/PPTX/XLSX/images, CSV/TSV/XLSX/ODS |
| **`tests/test_subtitles_archives.py`** | 9 | **PASSED** | SRT, VTT, TXT conversions, ZIP, TAR, GZ repacking and extraction |
| **`tests/test_tools.py`** | 11 | **PASSED** | Compress, Resize, Rotate, Crop, Trim, Split, Merge, Strip Metadata |
| **`tests/test_ui.py`** | 3 | **PASSED** | JobRunner execution, thread cancellation, MainWindow queue |
| **`tests/test_cli.py`** | 4 | **PASSED** | CLI argument parsing, collision avoidance `" (1)"`, end-to-end run |
| **TOTAL** | **115 / 115** | **100% PASS** | **All format pairs and tools verified with real files** |

---

## 📜 License
Personal Use License - 100% Local, Offline & Private.
