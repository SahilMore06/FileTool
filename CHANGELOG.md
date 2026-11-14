# Changelog

All notable changes to Fluxora are documented in this file.

## [1.1.1] - 2026-11-14

### Added
- Multi-arch headless CLI container image (`ghcr.io/sahilmore06/fluxora` for `linux/amd64` and `linux/arm64`) published to GitHub Packages via `Dockerfile` and `.github/workflows/packages.yml`.
- Native macOS Drag-to-Applications `.dmg` installer (`dmgbuild`) featuring an `Applications` folder shortcut (`/Applications` symlink) and a custom HiDPI (`1x`/`2x`) installer background.

### Changed
- Rebranded application identity, repository, macOS `.app`/`.dmg` packaging, and launch showcase to **Fluxora – Intelligent File Conversion & Productivity Suite** (`github.com/SahilMore06/Fluxora`).
- Upgraded GitHub README showcase to crisp native `1920x1080` inline Animated WebP (removing downloadable `.mp4`/`.gif` showcase links from the repository).

### Fixed
- Stabilized `test_onboarding_starter_animation_haptic_sandbox_and_consent` on macOS CI runners with Accessibility Reduce Motion active.
- Corrected `MacDragMonitor` idle polling documentation to `20 Hz` (`INTERVAL_IDLE_MS = 50`).

## [1.1.0] - 2026-11-14

### Added
- Animated first-boot starter sequence (`OnboardingWindow`, `_StarterInstallCanvas`) with local engine verification and spring recoil feedback.
- Interactive Force Touch drag-wheel sandbox (`_HapticWheelSandbox`) with live `Shift`, `Command`, and `Control` modifier switching and Light/Dark preset preview.
- Bundled offline Legal Consent flow ([PRIVACY.md](PRIVACY.md), [TERMS.md](TERMS.md), `filetool/core/legal.py`) triggered automatically on first launch (`--intro`, `--reset-onboarding` CLI flags, plus Settings replay card).
- Force Touch trackpad haptics (`NSHapticFeedbackManager` `generic`, `alignment`, `level_change`) and optional system sound cues (`NSSound`, disabled under `offscreen` Qt).
- Redesigned Light and Dark token palette meeting WCAG AA contrast (`filetool/ui/styles.py`), radial emblem artwork, and animated menu-bar status popover (`tray_popover.py`).
- GitHub Community Health documentation (`SECURITY.md`, `CODE_OF_CONDUCT.md`, pull request template) and automated GitHub Actions macOS `.dmg` / `.app.zip` release workflow.

### Fixed
- Settings validation for duplicate modifier keys and unverified custom output directory paths.
- Compressed documentation showcase PNG assets without quality degradation.
- GitHub Actions CI workflow installing `--cask libreoffice` with `QT_QPA_PLATFORM=offscreen` so all 162 tests pass cleanly on macOS runners.

## [1.0.0] - 2026-10-19

### Added
- Cursor-tracking radial drag wheel for Finder (`Shift` Convert, `Command` Quick Tools, `Control` macOS Actions) without Accessibility permissions.
- PySide6 batch conversion window with `QThreadPool` runner, History panel, Settings persistence, and encoding options.
- 266 conversion pairs across 47 input formats and 39 outputs through Pillow, FFmpeg, ImageMagick, Ghostscript, Pandoc, LibreOffice, and 7-Zip.
- Full CLI interface (`fluxora` / `filetool`), macOS Finder Quick Action installer, and PyInstaller `.app` / `.dmg` build script.
