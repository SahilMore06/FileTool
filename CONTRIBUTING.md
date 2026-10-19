# Contributing to FileTool 🍊

Thank you for your interest in contributing to **FileTool**!

FileTool is a 100% offline macOS desktop utility inspired by Tangerine for Mac. We welcome contributions that maintain our core principles:
1. **100% Offline & Private**: Zero external network requests, zero telemetry, zero analytics.
2. **High-Performance**: Ultra-low idle CPU (<0.1%), zero UI freezing, multithreaded conversions.
3. **Safe by Default**: Never overwrite or delete user files without explicit consent.

---

## 🛠 Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/SahilMore06/FileTool.git
   cd FileTool
   ```

2. **Automated Setup**:
   Run the setup script to install local Homebrew binaries and create a Python virtual environment:
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

3. **Running in Development**:
   ```bash
   # Launch GUI
   .venv/bin/python app.py

   # Launch CLI
   .venv/bin/python -m filetool.cli --help

   # Run Test Suite
   .venv/bin/pytest tests/ -v
   ```

---

## 🏗 Architecture Overview

- `filetool/core/engines/`: Format converters organized by media category (images, media, office, pdf, spreadsheets, subtitles, archives).
- `filetool/core/tools/`: File utility operations (compress, resize, crop, trim, split, merge, metadata).
- `filetool/platform/`: macOS platform integrations:
  - `mac_drag_monitor.py`: Low-level drag detection state machine using Quartz event sources (`CGEventSourceButtonState`, `CGEventSourceFlagsState`) without Accessibility permissions.
  - `mac_actions.py`: Native macOS integrations (AirDrop, float window, clipboard, terminal).
  - `mac_window.py`: PyObjC window styling and status level management.
- `filetool/ui/wheel/`: Tangerine-style radial wheel overlay:
  - `geometry.py`: Radial angle calculations and concentric ring hit testing.
  - `wheel_painter.py`: Custom QPainter rendering for segments, badges, and animations.
  - `wheel_window.py`: Frameless transparent overlay window controller.
- `filetool/ui/`: Main Qt window, queue table, and preferences dialog.

---

## 📦 Building the Standalone App

To package FileTool into a standalone macOS `.app`, `.dmg`, and `.zip`:
```bash
chmod +x scripts/build_app.sh
./scripts/build_app.sh
```
Outputs:
- `dist/FileTool.app`
- `dist/FileTool.dmg`
- `dist/FileTool.app.zip`

---

## 🧪 Testing Guidelines

Before submitting a Pull Request, ensure all tests pass:
```bash
pytest tests/ -v
```
All new features should include unit tests in the `tests/` directory.
