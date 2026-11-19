# Fluxora

**Open-source, offline file conversion and automation for macOS 13+.** Convert 266 format pairs locally from the desktop batch window, CLI, Docker container, or Finder drag overlay — with zero cloud uploads or telemetry.

[![Website](https://img.shields.io/badge/website-fluxora.live-F28A32)](https://fluxora.live/)
[![CI](https://github.com/SahilMore06/Fluxora/actions/workflows/ci.yml/badge.svg)](https://github.com/SahilMore06/Fluxora/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/SahilMore06/Fluxora?label=download)](https://github.com/SahilMore06/Fluxora/releases/latest)
[![GitHub Package](https://img.shields.io/badge/ghcr.io-fluxora-24292F?logo=docker&logoColor=white)](https://github.com/SahilMore06/Fluxora/pkgs/container/fluxora)
[![Platform](https://img.shields.io/badge/macOS-13%2B%20(Apple%20Silicon%20%26%20Intel)-222325)](#download-and-installation)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-E87410)](LICENSE)

[Website](https://fluxora.live/) · [Showcase](#launch-showcase) · [Why Fluxora](#why-fluxora) · [Download](#download-and-installation) · [Drag Wheel](#finder-drag-wheel) · [Desktop App](#desktop-window-and-onboarding) · [Quick Tools](#quick-tools-and-native-actions) · [Supported Formats](#supported-formats-and-backends) · [CLI](#command-line-interface) · [Architecture](#architecture-and-project-layout)

---

Fluxora combines a native PySide6 desktop batch converter, a scriptable CLI, a multi-arch Linux Docker image, and a non-activating macOS Finder drag overlay. Every conversion runs locally on your machine through Pillow, FFmpeg, ImageMagick, Ghostscript, Pandoc, LibreOffice, and 7-Zip, with zero outbound network calls verified by automated tests ([Privacy Policy](PRIVACY.md) · [Third-Party Notices](THIRD_PARTY_NOTICES.md)).

<a id="launch-showcase"></a>

![Fluxora offline macOS file converter and batch workflow showcase](docs/assets/fluxora_showcase.webp)

---

![Fluxora Finder drag overlay in light and dark mode](docs/assets/drag_wheel_showcase.png)

## Why Fluxora

| Common File Workflow Problem | How Fluxora Handles It |
| :--- | :--- |
| **Sensitive Files Leaving Your Mac** | Documents, images, video, and archives convert strictly locally with zero telemetry, accounts, or outbound networking (enforced in CI via AST checks). |
| **Web Converter Limits & Subscription Gates** | Unlimited offline batch processing under the [MIT License](LICENSE) on both Apple Silicon and Intel Macs. |
| **Repetitive Manual Conversions** | Run single or batch jobs from the desktop queue, `fluxora` terminal CLI, or headless Docker container (`ghcr.io/sahilmore06/fluxora`). |
| **Transparent macOS Input Scope** | Queries Quartz state APIs (`CGEventSourceButtonState`, `CGEventSourceFlagsState`, `CGEventSourceKeyState`) and `NSDragPboard` only while dragging — zero keystroke logging. |
| **Accidental Overwrites** | Preserves originals by default and writes numbered outputs (`report (1).pdf`) unless overwrite is turned on in Settings. |

## Download and Installation

### Option 1: Download Pre-Built macOS App

Download the latest packaged application bundle from [fluxora.live](https://fluxora.live/) or [GitHub Releases](https://github.com/SahilMore06/Fluxora/releases/latest):

| Package | Direct Download | Target | Notes |
| :--- | :--- | :--- | :--- |
| **macOS Disk Image** | [Download `Fluxora.dmg`](https://github.com/SahilMore06/Fluxora/releases/latest/download/Fluxora.dmg) | macOS 13+ | Open `Fluxora.dmg` and drag `Fluxora` into the `Applications` folder shortcut |
| **Standalone ZIP** | [Download `Fluxora.app.zip`](https://github.com/SahilMore06/Fluxora/releases/latest/download/Fluxora.app.zip) | macOS 13+ | Extract and move `Fluxora.app` into `/Applications` |
| **Checksums** | [View `SHA256SUMS.txt` & Release Notes](https://github.com/SahilMore06/Fluxora/releases/latest) | All builds | Verify downloads via `shasum -a 256 -c SHA256SUMS.txt` |

<div align="center">
  <img src="docs/assets/dmg_installer_showcase.webp" alt="Fluxora macOS Drag-to-Applications DMG Installer" width="680" />
</div>

#### First-Launch Setup on macOS

1. Open `Fluxora.dmg` and drag `Fluxora.app` onto the `Applications` folder shortcut (or move `Fluxora.app` into `/Applications`).
2. Because open-source builds use ad-hoc code signing rather than paid Apple Developer notarization, macOS Gatekeeper prompts on first launch. Open it by right-clicking `Fluxora.app` and selecting **Open**, or run:

   ```bash
   xattr -cr /Applications/Fluxora.app
   ```

3. On first boot, Fluxora plays an interactive starter setup sequence that checks installed local engines, demonstrates Force Touch drag-wheel haptics, and asks you to confirm the offline [Privacy Policy](PRIVACY.md) and [Terms and Conditions](TERMS.md).
4. Python engines (`Pillow`, `pillow-heif`, `pypdf`, `pdf2docx`, `python-pptx`, `openpyxl`, `pandas`, archive/subtitle handlers) work immediately out of the box. Install optional Homebrew packages to unlock video, audio, vector PDF compression, EPUB/DOCX markup, and LibreOffice conversions:

   ```bash
   brew install ffmpeg imagemagick pandoc poppler ghostscript sevenzip
   brew install --cask libreoffice
   ```

### Option 2: Install from Source

Requires macOS 13+ (Apple Silicon or Intel), Python 3.12+, and [Homebrew](https://brew.sh):

```bash
git clone https://github.com/SahilMore06/Fluxora.git && cd Fluxora && ./scripts/setup.sh
```

`scripts/setup.sh` installs the Homebrew conversion tools above, configures `.venv` with Python 3.12, and installs Fluxora in editable mode with test and build dependencies.

Manual virtual environment setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Option 3: Docker / GitHub Packages (Headless CLI)

Multi-arch container images (`linux/amd64` and `linux/arm64`) package the `fluxora` CLI with Python engines and local converters (`ffmpeg`, `imagemagick`, `pandoc`, `poppler`, `ghostscript`, `7-Zip`, and headless `LibreOffice`):

```bash
docker pull ghcr.io/sahilmore06/fluxora:latest

# Convert files in the current directory without installing local tools
docker run --rm -v "$PWD:/work" ghcr.io/sahilmore06/fluxora:latest photo.png --to jpg --quality 90
```

## Finder Drag Wheel

Begin dragging one or more files or folders in Finder and press a modifier key to open the radial wheel centered at the pointer:

| Modifier Key | Wheel Mode | Available Operations |
| :--- | :--- | :--- |
| `Shift` | **Convert** | Context-filtered target formats compatible with every selected item, expanding into an outer `MORE...` ring when over six formats match |
| `Command` | **Quick Tools** | Format-aware tools (`Compress`, `Resize`, `Rotate`, `Crop`, `Trim`, `Split`, `Merge`, `Metadata`, `To PDF`) |
| `Control` | **macOS Actions** | Native OS actions (`AirDrop`, `Float`, `Copy`, `Move`, `Copy Path`, `Open in Terminal`) |

### Engineering Details

- **Quartz Drag State Detection**: `MacDragMonitor` polls `NSPasteboard` (`NSDragPboard`) change counts dynamically (20 Hz idle, 60 Hz during primary mouse drags) alongside Quartz `CGEventSource` state queries (`CGEventSourceButtonState`, `CGEventSourceFlagsState`, `CGEventSourceKeyState`). See [docs/TRADEMARK_AND_PERMISSIONS_CHECK.md](docs/TRADEMARK_AND_PERMISSIONS_CHECK.md) for clean-account permission tracking.
- **Non-Activating Overlay**: The wheel runs inside an `NSWindow` at `NSStatusWindowLevel` across all Spaces and full-screen apps so Finder retains active drag focus.
- **Force Touch Haptics & Audio**: Supported MacBook trackpads receive `NSHapticFeedbackManager` ticks (`alignment` across petal boundaries and theme switches, `level_change` on click and job completion) synchronized with subtle `NSSound` cues.
- **Non-Destructive Defaults**: New files are written next to the source item with incremental numeric suffixes (`report (1).pdf`) unless overwrite or a custom output folder is enabled in Settings.

## Desktop Window and Onboarding

### Batch Queue, Encoding Controls, and History

Drop individual files or nested folders into the main window to assign per-file or bulk output formats (`Convert all to`), tune JPEG/WebP/HEIC/AVIF quality, H.264/VP9 CRF and video resolution (`original`, `1080p`, `720p`, `480p`), audio bitrate, or PDF render DPI, and execute conversions concurrently on a `QThreadPool`.

![Fluxora desktop conversion queue in light mode](docs/assets/main_window_light.png)

Completed conversions appear in the **History** tab with single-click `Reveal in Finder`, `Copy Path`, and `Open in Terminal` actions. An animated menu-bar status popover (`tray_popover.py`) keeps drag monitoring status, quick drop, and app toggles accessible from the macOS menu bar.

![Fluxora dark theme settings and tool preferences](docs/assets/main_window_dark.png)

### Theming, Accessibility, and First-Boot Tour

- **Light & Dark Design Tokens**: Centralized token stylesheets in `filetool/ui/styles.py` meet WCAG AA text contrast across Light and Dark modes with four accent presets (`Amber`, `Ocean`, `Emerald`, `Graphite`).
- **Reduced Motion**: Animations and transitions respect `prefers-reduced-motion` system settings.
- **Starter Tour & Settings Validation**: Settings validates duplicate trigger modifiers and missing custom output directories, manages `Launch at Login` via a user LaunchAgent, inspects local binary health, and lets you replay the animated starter setup or review Privacy and Terms anytime.

## Quick Tools and Native Actions

| Category | Action | Backend / Behavior |
| :--- | :--- | :--- |
| **Compression** | `Compress` | Images via Pillow quality optimization; video via FFmpeg H.264 CRF; PDFs via Ghostscript (`/ebook`, `/screen`, `/printer`) |
| **Geometry** | `Resize`, `Rotate`, `Crop` | Aspect-preserving dimension scaling and margin crop via Pillow; image and multi-page PDF rotation via Pillow and `pypdf` |
| **Time & Pages** | `Trim`, `Split`, `Merge` | Media clipping and concatenation via `ffmpeg`; PDF page splitting and multi-file merge via `pypdf` |
| **Privacy Tool** | `Metadata` Strip | Removes EXIF, GPS, IPTC, and container metadata tags via Pillow and `ffmpeg -map_metadata -1` |
| **macOS Actions** | `AirDrop`, `Float`, `Copy`, `Move`, `Path`, `Terminal` | Native `NSSharingService` AirDrop sheet, always-on-top floating preview window, Finder pasteboard copy/move, clipboard path copy, and Terminal launch |
| **Finder Service** | `Convert with Fluxora` | Installs as a macOS Quick Action in `~/Library/Services` |

## Supported Formats and Backends

Fluxora registers **266 conversion pairs** across **47 input extensions**, **39 output formats**, and **9 categories** (browse the searchable matrix at [fluxora.live/formats](https://fluxora.live/formats), or step-by-step guides for [HEIC to JPG](https://fluxora.live/convert/heic-to-jpg), [MOV to MP4](https://fluxora.live/convert/mov-to-mp4), [PDF to DOCX](https://fluxora.live/convert/pdf-to-docx), [Compress PDF](https://fluxora.live/convert/compress-pdf), and [Strip Metadata](https://fluxora.live/convert/strip-exif-metadata)).

| Category | Pairs | Input Extensions | Output Formats | Local Backends |
| :--- | :---: | :--- | :--- | :--- |
| **Images** | 72 | `avif`, `bmp`, `heic`, `jpeg`, `jpg`, `png`, `svg`, `tif`, `tiff`, `webp` | `avif`, `bmp`, `heic`, `jpg`, `pdf`, `png`, `tiff`, `webp` | Pillow, `pillow-heif`, ImageMagick (`magick`), macOS `sips` |
| **Audio** | 63 | `aif`, `aiff`, `flac`, `m4a`, `mp3`, `ogg`, `opus`, `wav`, `wma` | `aiff`, `flac`, `m4a`, `mp3`, `ogg`, `opus`, `wav`, `wma` | FFmpeg (`ffmpeg`, `ffprobe`) |
| **Video** | 49 | `avi`, `gif`, `mkv`, `mov`, `mp4`, `webm`, `wmv` | `avi`, `gif`, `mkv`, `mov`, `mp3`, `mp4`, `webm`, `wmv` | FFmpeg (`ffmpeg`) |
| **Documents** | 31 | `docx`, `epub`, `html`, `md`, `rtf`, `txt` | `docx`, `epub`, `html`, `md`, `pdf`, `rtf`, `txt` | Pandoc, LibreOffice (`soffice`) |
| **Spreadsheets** | 21 | `csv`, `ods`, `tsv`, `xls`, `xlsx` | `csv`, `ods`, `pdf`, `tsv`, `xlsx` | `pandas`, `openpyxl`, LibreOffice (`soffice`) |
| **Archives** | 12 | `gz`, `rar` (extract), `tar`, `tgz`, `zip` | `gz`, `tar`, `zip` | 7-Zip (`7zz`), Python `zipfile` and `tarfile` |
| **PDF** | 8 | `pdf` | `docx`, `epub`, `jpg`, `md`, `png`, `pptx`, `txt`, `xlsx` | `pypdf`, `pdf2docx`, `python-pptx`, Poppler (`pdftoppm`, `pdftotext`), Pandoc |
| **Slides** | 6 | `ppt`, `pptx` | `jpg`, `pdf`, `png` | LibreOffice (`soffice`), Poppler (`pdftoppm`) |
| **Subtitles** | 4 | `srt`, `vtt` | `srt`, `txt`, `vtt` | Built-in Python subtitle parser |

### External Binary Lookup Order

`ToolResolver` searches the packaged bundle (`Contents/Resources/bin`), repo `resources/bin`, Apple Silicon Homebrew (`/opt/homebrew/bin`), Intel Homebrew (`/usr/local/bin`), `/usr/bin`, and `/Applications/LibreOffice.app/Contents/MacOS`, so standalone `.app` launches from Finder resolve tools reliably even without an interactive shell `$PATH`.

## Command-Line Interface

Full flag reference and multi-arch Docker examples are also hosted at [fluxora.live/cli](https://fluxora.live/cli).

### Desktop App Options

```bash
# Standard launch (triggers first-boot starter animation and Terms acceptance if unset)
.venv/bin/python app.py

# Start minimized in the macOS menu bar
.venv/bin/python -m filetool.app --daemon

# Replay the animated starter sequence and haptic wheel intro
.venv/bin/python app.py --intro

# Reset saved onboarding acceptance state before launch
.venv/bin/python app.py --reset-onboarding
```

### Batch CLI Conversion

```bash
# Convert a single file with explicit quality settings
fluxora photo.heic --to jpg --quality 90 --out-dir ./converted

# Transcode video with target CRF and resolution scaling
fluxora clip.mov --to mp4 --crf 22 --resolution 1080p

# Show compatible output formats for a file and verify tool availability
fluxora report.pdf --list-formats

# Inspect local CLI dependency health
fluxora --check-deps
```

Available conversion flags: `--to`, `--out-dir`, `--overwrite`, `--quality` (1 to 100), `--dpi` (default 300), `--bitrate` (`128k`/`192k`/`256k`/`320k`), `--crf` (0 to 51), `--resolution` (`original`, `1080p`, `720p`, `480p`), `--list-formats`, and `--check-deps`. When calling without activating `.venv`, substitute `.venv/bin/python -m filetool.cli`.

### Finder Quick Action & Packaging

```bash
# Install "Convert with Fluxora" into ~/Library/Services
./scripts/install_quick_action.sh

# Build signed Fluxora.app, Fluxora.app.zip, Fluxora.dmg, and SHA256SUMS.txt
./scripts/build_app.sh
```

## Privacy and Safety Guarantees

- **Zero Outbound Network Calls**: No updates, analytics, crash telemetry, cookies, or account logins exist in the codebase ([Privacy Policy](PRIVACY.md)).
- **Subprocess Safety**: External binaries run strictly with argument arrays (`shell=False`) and clean temporary staging directories deleted after each job.
- **Local Persistence**: Preferences store locally in macOS `QSettings` (`Fluxora` / `Fluxora`) and logs write to `~/Library/Logs/Fluxora/fluxora.log`. Optional `Launch at Login` writes only `~/Library/LaunchAgents/com.fluxora.app.plist`.

## Architecture and Project Layout

Detailed technical notes and visual system maps live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):

- [System Architecture Diagram](docs/diagrams/filetool_architecture.svg)
- [Radial Drag and Drop Flow](docs/diagrams/filetool_interaction_flow.svg)

```text
filetool/
  app.py                Menu-bar coordinator, onboarding gate, drag polling, and CLI flags
  cli.py                Command-line conversion and dependency diagnostics (`fluxora` / `filetool`)
  core/
    deps.py             Local CLI resolver across app bundles, Homebrew, and macOS paths
    image_ops.py        Non-destructive image compression and resize helpers
    legal.py            Bundled offline Privacy Policy and Terms & Conditions renderer
    registry.py         Format compatibility graph and engine lookup (`266` pairs)
    runner.py           `QThreadPool` parallel job execution with progress and cancellation
    utils.py            `shell=False` subprocess runner and unique output path resolver
    engines/            Adapters for archives, images, media, office, pandoc, pdf, sheets, subtitles
    tools/              Compress, crop, merge, metadata strip, resize, split, and trim
  platform/
    mac_actions.py      AirDrop, floating preview, clipboard/Finder actions, LaunchAgent, haptics, sound
    mac_drag_monitor.py Quartz `CGEventSource` state polling + `NSDragPboard` drag state machine
    mac_window.py       Non-activating `NSStatusWindowLevel` overlay bridge
  ui/
    components.py       Animated emblem, vector icons, Force Touch switches, URL helpers
    dropzone.py         Recursive file and folder drop target
    history_panel.py    Completed jobs list with Reveal, Copy Path, and Terminal actions
    job_list.py         Conversion queue rows and stderr diagnostics viewer
    main_window.py      Primary desktop window (`Convert`, `History`, `Settings`)
    onboarding.py       Starter install animation, haptic wheel sandbox, and legal consent
    options_panel.py    Quality, CRF, resolution, bitrate, and DPI controls
    settings_page.py    Persistent `QSettings`, validation, accent swatches, and dependency view
    styles.py           WCAG AA Light/Dark design tokens and QSS generator
    tray_popover.py     Animated macOS menu-bar status card and quick-drop actions
    wheel/              Radial overlay geometry, painter, springs, and window
scripts/                Homebrew setup, PyInstaller `.dmg`/`.zip` builder, Quick Action installer
tests/                  Pytest suite across engines, CLI, dependencies, drag monitor, wheel, and UI
docs/                   Architecture docs, SVG/HTML system diagrams, and showcase captures
```

## Testing and Contributing

Run the full test suite sequentially (so headless `soffice` conversions do not contend on LibreOffice user-profile locks):

```bash
.venv/bin/pytest -v
```

Run headless without a Cocoa display session:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/LICENSE_REMEDIATION.md](docs/LICENSE_REMEDIATION.md), [SECURITY.md](SECURITY.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [PRIVACY.md](PRIVACY.md), and [TERMS.md](TERMS.md) for contributor workflows, license notices, security practices, and policy terms.

Visit [fluxora.live](https://fluxora.live/), star the repository, or open bug reports and format requests in [GitHub Issues](https://github.com/SahilMore06/Fluxora/issues) to help shape Fluxora 2.0.

## License

Released under the [MIT License](LICENSE).
