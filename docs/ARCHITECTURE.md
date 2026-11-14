# Fluxora Architecture

Fluxora separates platform-native macOS integration, format/tool execution engines, and the PySide6 desktop interface into three layers.

Diagrams:
- [System Architecture Diagram](diagrams/filetool_architecture.svg)
- [Radial Drag & Drop Flow](diagrams/filetool_interaction_flow.svg)

## 1. Platform Layer (`filetool/platform/`)

- **`mac_drag_monitor.py`**: Runs an adaptive Qt timer polling loop (20 Hz idle, 60 Hz active button press) paired with a Quartz `CGEventTap` (`kCGEventFlagsChanged` / `KeyDown`). Drag detection monitors `NSPasteboard` change counts (`NSDragPboard`) while the primary mouse button moves past a threshold, fetching file URLs without needing Accessibility permissions.
- **`mac_window.py`**: Configures the wheel overlay as a frameless, non-activating `NSWindow` (`NSStatusWindowLevel`) that joins all Spaces and full-screen apps so Finder never loses drag focus. Guards non-Cocoa QPA platforms safely for headless testing.
- **`mac_actions.py`**: Bridges Finder Reveal, AirDrop sharing (`NSSharingService`), always-on-top floating preview windows, clipboard file copy, terminal launch, AppKit `NSSound`, `NSHapticFeedbackManager`, and macOS user notifications.

## 2. Core Engine (`filetool/core/`)

- **`registry.py`**: Maps supported `(in_ext, out_ext)` pairs to converter functions and option definitions across all engines.
- **`deps.py`**: Locates external CLI tools (`ffmpeg`, `magick`, `gs`, `soffice`, `pandoc`, `7zz`) across standard macOS and Homebrew paths (`PATH`, `/opt/homebrew/bin`, `/usr/local/bin`).
- **`runner.py`**: Dispatches `ConversionJob` tasks onto `QThreadPool` workers with cancellation flags, progress signals, and safe path resolution.
- **`image_ops.py`**: Handles same-format resize and compression via Pillow without modifying source files.
- **`engines/` & `tools/`**: Modular adapters for images, audio/video, office documents, PDFs, spreadsheets, subtitles, archives, cropping, trimming, splitting, merging, and metadata stripping.

## 3. UI Layer (`filetool/ui/`)

- **Main Desktop App (`main_window.py` & panels)**:
  - `main_window.py` provides a single compact toolbar (`Convert`, `History`, `Settings`), collapsible `options_panel.py`, `DropZone` -> `JobListWidget` transition, and footer actions (`bulk_combo`, `Clear Done`, `Convert All`).
  - `history_panel.py`, `settings_page.py`, and `tray_popover.py` handle completed outputs, persistent `QSettings` preferences, and the animated menu-bar card using centralized tokens from `styles.py` and the shared emblem/icons from `components.py`.
- **Radial Wheel (`ui/wheel/`)**:
  - `geometry.py` computes curved petal regions and `atan2` hit-testing across primary and secondary rings.
  - `wheel_painter.py` draws segments, SF Symbols, center hub progress, and drop feedback at 60 FPS.
  - `wheel_window.py` connects mouse and keyboard input to `JobRunner`, `execute_wheel_tool`, and native macOS actions.
