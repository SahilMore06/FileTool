# Contributing

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests after making changes:

```bash
.venv/bin/pytest -v
```

For headless environments where Cocoa display access is unavailable, run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
```

## Code Organization

- `filetool/core/engines/`: Conversion handlers that register `(src_ext, dest_ext)` edges with the global `registry`. Each engine defines option metadata and handles subprocess failures with clear error tails.
- `filetool/core/tools/`: Single-step operations (`compress`, `resize`, `crop`, `trim`, `split`, `merge`, `metadata`).
- `filetool/platform/`: macOS-only PyObjC/Quartz code. Keep AppKit/Quartz calls guarded so non-Cocoa test runs stay safe.
- `filetool/ui/`: Modular PySide6 views styled exclusively through design tokens in `filetool/ui/styles.py` (supporting both Light and Dark mode without hardcoded widget colors or emoji icons).

## Guidelines

1. Keep all processing offline and local; do not introduce network requests or external analytics.
2. Preserve non-destructive defaults (`get_unique_output_path`) unless overwrite is explicitly selected by the user.
3. Add or update pytest coverage in `tests/` when adding converters, tools, or UI workflows.
