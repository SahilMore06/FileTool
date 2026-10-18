#!/usr/bin/env bash
# ==============================================================================
# FileTool - Automated Setup Script for macOS (Apple Silicon / Intel)
# Installs all local CLI tools via Homebrew and configures Python environment.
# All tools run completely offline. No telemetry or network calls at runtime.
# ==============================================================================

set -euo pipefail

echo "============================================================"
echo "          Installing FileTool Dependencies for macOS        "
echo "============================================================"

# 1. Check for Homebrew
if command -v brew >/dev/null 2>&1; then
    BREW_BIN=$(command -v brew)
elif [[ -x "/opt/homebrew/bin/brew" ]]; then
    BREW_BIN="/opt/homebrew/bin/brew"
elif [[ -x "/usr/local/bin/brew" ]]; then
    BREW_BIN="/usr/local/bin/brew"
else
    echo "Error: Homebrew is required but not installed."
    echo "Install it from https://brew.sh or run:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

echo "✔ Found Homebrew at: ${BREW_BIN}"

# 2. Install external CLI dependencies
echo ""
echo "--> Installing local external conversion binaries..."
FORMULAE=(
    ffmpeg
    imagemagick
    pandoc
    poppler
    ghostscript
    sevenzip
)

for pkg in "${FORMULAE[@]}"; do
    if "${BREW_BIN}" list --formula | grep -q "^${pkg}\$"; then
        echo "  ✔ ${pkg} is already installed"
    else
        echo "  -> Installing ${pkg}..."
        "${BREW_BIN}" install "${pkg}"
    fi
done

# Install LibreOffice cask for office conversions (DOCX/PPTX to PDF)
if "${BREW_BIN}" list --cask | grep -q "^libreoffice\$" || [[ -d "/Applications/LibreOffice.app" ]]; then
    echo "  ✔ LibreOffice is already installed"
else
    echo "  -> Installing LibreOffice cask..."
    "${BREW_BIN}" install --cask libreoffice || echo "Warning: LibreOffice install via Homebrew failed; please download manually if needed."
fi

# 3. Locate Python 3.12
echo ""
echo "--> Setting up Python 3.12 environment..."
PYTHON_BIN=""
for candidate in python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
        VER=$("${candidate}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ "${VER}" == "3.12" || "${VER}" == "3.11" || "${VER}" == "3.13" ]]; then
            PYTHON_BIN=$(command -v "${candidate}")
            break
        fi
    fi
done

if [[ -z "${PYTHON_BIN}" ]]; then
    echo "Python 3.12 not found. Installing via Homebrew..."
    "${BREW_BIN}" install python@3.12
    PYTHON_BIN="/opt/homebrew/bin/python3.12"
fi

echo "✔ Using Python: ${PYTHON_BIN} ($("${PYTHON_BIN}" --version))"

# 4. Create virtual environment
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment in .venv..."
    "${PYTHON_BIN}" -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

echo ""
echo "============================================================"
echo "✔ Setup Complete!"
echo "Run GUI:    .venv/bin/python app.py"
echo "Run CLI:    .venv/bin/python -m filetool.cli --help"
echo "Run Tests:  .venv/bin/pytest tests/ -v"
echo "============================================================"
