# Fluxora 2.0 License Audit & Remediation Decisions (L5)

> **Disclaimer:** This is an engineering compliance inventory prepared during Phase 0 (`19 November 2026`). Have a qualified open-source licensing advisor review final binary packaging before distributing bundled third-party binaries in Phase 2.

## Decision Matrix for Copyleft & Restricted Components

| Component | License | Current Status (v1.1.1) | Decision for Fluxora 2.0 | Phase 2 Action |
| :--- | :--- | :--- | :--- | :--- |
| **`pymupdf` (via `pdf2docx`)** | **AGPL-3.0** / Commercial | Installed as a runtime Python dependency in `pyproject.toml` (`pdf2docx>=0.5.8`) | **Remove from bundled core / make optional** | Remove `pdf2docx` from default `pyproject.toml` dependencies and PyInstaller bundle; offer optional user-installed plugin or replace PDF->DOCX with a permissive converter. |
| **Ghostscript (`gs`)** | **AGPL-3.0** / Commercial | External subprocess (`filetool/core/tools/compress.py`) | **Replace default / keep optional external** | Use native macOS `PDFKit` / Quartz filters for built-in PDF compression; keep `gs` strictly as an optional user-installed binary. |
| **Poppler (`pdftoppm`, `pdftotext`)** | **GPL-2.0 / GPL-3.0** | External subprocess (`filetool/core/engines/pdf.py`, `office.py`) | **Replace default / keep optional external** | Prefer native macOS `PDFKit` page rasterization and text extraction; keep Poppler optional and never link in-process. |
| **Pandoc (`pandoc`)** | **GPL-2.0-or-later** | External subprocess (`filetool/core/engines/pandoc_docs.py`) | **Keep separate optional binary** | Run only as an unmodified separate process; provide upstream source link and GPL notice if ever distributed, or keep optional user install. |
| **FFmpeg (`ffmpeg`, `ffprobe`)** | **LGPL-2.1+ or GPL-2.0+** | External subprocess (`filetool/core/engines/media.py`, tools) | **Bundle LGPL-only build or use `AVFoundation`** | Never bundle a `--enable-gpl` Homebrew build (`libx264` is GPL). In Phase 2, either use macOS `AVFoundation` / VideoToolbox (`h264_videotoolbox`) or bundle a verified `--disable-gpl` LGPL FFmpeg build with exact configure flags and source offer published. |
| **LibreOffice (`soffice`)** | **MPL-2.0** | External subprocess (`filetool/core/engines/office.py`, `sheets.py`) | **Keep optional external** | Never bundle inside `Fluxora.dmg`; keep as user-installed optional Office engine. |
| **7-Zip (`7zz`)** | **LGPL-2.1+ with unRAR restriction** | External subprocess (`filetool/core/engines/archives.py`) | **Keep stdlib default / audit before bundling** | Use Python stdlib `zipfile`/`tarfile`/`gzip` by default; do not bundle `7zz` unless the unRAR license clause is resolved or a non-unRAR build is verified. |
| **PySide6 / shiboken6** | **LGPL-3.0-only** | Runtime GUI framework | **Keep (LGPL compliant)** | Preserve dynamic shared libraries in bundle, include LGPL-3.0 notice in `THIRD_PARTY_NOTICES.md`, and strip unused modules (`PySide6_WebEngine`, `PySide6_Pdf`) in Phase 2. |
| **pillow-heif (`libheif`)** | **BSD-3-Clause** (wheel bundles `libheif` **LGPL-3.0**) | Runtime image HEIC/AVIF adapter | **Prefer native macOS `ImageIO` in Phase 2** | Native macOS `ImageIO` handles HEIC/AVIF natively with zero extra binary size; keep `pillow-heif` notices documented while used. |

## CI Enforcement

- `scripts/audit_licenses.py --check` runs automatically in `.github/workflows/ci.yml` and `tests/test_compliance.py`.
- Any **new** `AGPL`/`GPL` or `UNKNOWN` package immediately fails CI.
- Once `pdf2docx`/`pymupdf` is removed in Phase 2, clear `DEFAULT_ALLOWED_STRONG_COPYLEFT` in `scripts/audit_licenses.py` and switch CI to `--strict`.
