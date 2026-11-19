# Third-Party Software Notices

Fluxora itself is licensed under the [MIT License](LICENSE).

This file inventories third-party Python packages detected in the build environment and external local CLI tools invoked as separate processes (`shell=False`). Regenerate anytime with:

```bash
.venv/bin/python scripts/audit_licenses.py --write-notices THIRD_PARTY_NOTICES.md
```

## License Compliance Notes (Phase 0 Audit)

- **Action tracked for Phase 2 (`pymupdf`):** `pdf2docx` transitively installs `PyMuPDF` (`AGPL-3.0`). Do **not** bundle `PyMuPDF` into a closed or MIT-only binary distribution without removing/replacing `pdf2docx` or shipping under compliant separation. See [docs/LICENSE_REMEDIATION.md](docs/LICENSE_REMEDIATION.md).
- **Qt / PySide6 (`LGPL-3.0-only`):** Dynamically linked under LGPL-3.0 obligations; users can inspect and relink Qt libraries.
- **pillow-heif (`BSD-3-Clause` wrapper):** Prebuilt wheels include `libheif` (`LGPL-3.0`); verify wheel notice compliance before macOS app bundling.
- **External CLI tools:** Invoked strictly via separate subprocesses (`shell=False`) and currently installed separately by the user (e.g., via Homebrew).

## Python Packages

| Package | Version | License | Category |
| :--- | :--- | :--- | :--- |
| `altgraph` | `0.17.5` | MIT | `permissive` |
| `dmgbuild` | `1.6.7` | MIT | `permissive` |
| `ds_store` | `1.3.3` | MIT | `permissive` |
| `et_xmlfile` | `2.0.0` | MIT | `permissive` |
| `filetype` | `1.2.0` | MIT | `permissive` |
| `fire` | `0.7.1` | Apache-2.0 | `permissive` |
| `fonttools` | `4.67.0` | MIT | `permissive` |
| `iniconfig` | `2.3.1` | MIT | `permissive` |
| `lxml` | `6.1.3` | BSD-3-Clause | `permissive` |
| `mac_alias` | `2.2.3` | MIT | `permissive` |
| `macholib` | `1.16.4` | MIT | `permissive` |
| `numpy` | `2.5.4` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | `permissive` |
| `opencv-python-headless` | `5.0.0.93` | Apache 2.0 | `permissive` |
| `openpyxl` | `3.1.5` | MIT | `permissive` |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause | `permissive` |
| `pandas` | `3.0.6` | OSI Approved :: BSD License | `permissive` |
| `pdf2docx` | `0.5.13` | MIT | `permissive` |
| `pillow` | `13.0.0` | MIT-CMU | `permissive` |
| `pillow_heif` | `1.8.1` | BSD-3-Clause | `permissive` |
| `pip` | `26.2.1` | MIT | `permissive` |
| `pluggy` | `1.7.0` | MIT | `permissive` |
| `Pygments` | `2.21.0` | BSD-2-Clause | `permissive` |
| `pyinstaller` | `6.22.3` | GPL-2.0-or-later WITH Bootloader-exception (build tool only) | `build-exception` |
| `pyinstaller-hooks-contrib` | `2026.8` | Apache-2.0 OR GPL-2.0-only (build tool only) | `build-exception` |
| `pymupdf` | `1.28.2` | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License | `strong-copyleft` |
| `pyobjc-core` | `12.2.2` | MIT | `permissive` |
| `pyobjc-framework-Cocoa` | `12.2.2` | MIT | `permissive` |
| `pyobjc-framework-Quartz` | `12.2.2` | MIT | `permissive` |
| `pypdf` | `6.21.1` | BSD-3-Clause | `permissive` |
| `PySide6` | `6.12.0` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `PySide6_Addons` | `6.12.0` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `PySide6_Essentials` | `6.12.0` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `PySide6_Pdf` | `6.12.0.140` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `PySide6_WebEngine` | `6.12.0.140` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `pytest` | `9.1.1` | MIT | `permissive` |
| `python-dateutil` | `2.9.0.post0` | OSI Approved :: BSD License; OSI Approved :: Apache Software License | `permissive` |
| `python-docx` | `1.2.0` | MIT | `permissive` |
| `python-pptx` | `1.0.2` | MIT | `permissive` |
| `setuptools` | `84.0.0` | MIT | `permissive` |
| `shiboken6` | `6.12.0` | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `weak-copyleft` |
| `six` | `1.17.0` | MIT | `permissive` |
| `termcolor` | `3.3.0` | MIT | `permissive` |
| `typing_extensions` | `4.16.0` | PSF-2.0 | `permissive` |
| `xlsxwriter` | `3.2.9` | BSD-2-Clause | `permissive` |

## External CLI Binaries (Separate Subprocesses)

| Binary | Upstream Project | License | Invocation | Phase 2 Direction | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ffmpeg / ffprobe` | FFmpeg | LGPL-2.1+ or GPL-2.0+ (depends on build flags) | External subprocess (shell=False) | Bundle documented LGPL-only build or prefer AVFoundation for common codecs. | https://ffmpeg.org/download.html |
| `gs` | Ghostscript | AGPL-3.0-only / Artifex Commercial | External subprocess (shell=False) | Replace default PDF compression with native PDFKit/Quartz; keep Ghostscript optional user-installed. | https://ghostscript.com/releases/gsdnld.html |
| `pandoc` | Pandoc | GPL-2.0-or-later | External subprocess (shell=False) | Keep separate unmodified executable with source offer/notices or optional user install. | https://github.com/jgm/pandoc |
| `pdftoppm / pdftotext` | Poppler | GPL-2.0-only / GPL-3.0-only | External subprocess (shell=False) | Prefer native macOS PDFKit rendering/extraction; keep Poppler optional user-installed. | https://poppler.freedesktop.org/ |
| `soffice` | LibreOffice | MPL-2.0 | External subprocess (shell=False) | Keep optional user-installed external process; never bundle inside DMG. | https://www.libreoffice.org/download/download-libreoffice/ |
| `magick` | ImageMagick | ImageMagick (Apache-2.0 compatible) | External subprocess (shell=False) | Prefer native macOS ImageIO + Pillow; keep ImageMagick optional. | https://github.com/ImageMagick/ImageMagick |
| `7zz` | 7-Zip | LGPL-2.1+ with unRAR restriction | External subprocess (shell=False) | Audit unRAR restriction before bundling; use Python stdlib zipfile/tarfile by default. | https://www.7-zip.org/download.html |
