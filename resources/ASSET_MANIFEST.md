# Fluxora Resource & Asset Provenance Manifest (L7)

Every bundled asset shipped under `resources/` and every runtime visual/audio/font resource used by Fluxora is tracked below so provenance and licensing stay auditable.

## Bundled Files in `resources/`

| File | Size | SHA-256 | Origin / Author | License | Phase 1 Status |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `resources/Fluxora.icns` | 307,275 bytes | `d2677960081bf66bdbbfbd629e5671fe5f8c41797cba4d63d848407606baa783` | Generated programmatically for Fluxora by repository author (`SahilMore06`) | MIT (first-party) | Replace with original Fluxora 2.0 emblem in Phase 1 (`6.3`) |

## Runtime UI Icons, Sounds, and Fonts

| Asset Type | Implementation Location | Source / Provider | License / Terms | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **App Vector Icons** | `filetool/ui/components.py` (`draw_vector_icon`, `create_brand_pixmap`) | Hand-coded `QPainterPath` geometry in repo | MIT (first-party) | No third-party SVG/PNG packs bundled. |
| **Wheel Symbols (macOS)** | `filetool/ui/wheel/wheel_painter.py` (`SYMBOL_MAP`) | macOS system `NSImage` SF Symbols lookup at runtime with `QPainter` vector fallback | Apple macOS system runtime API only | Per Apple SF Symbols license, **never** extract or embed SF Symbols glyphs in website or marketing assets. Replace with custom Fluxora 2.0 vector set in Phase 1 (`6.3`). |
| **Audio Cues** | `filetool/platform/mac_actions.py` | macOS built-in `NSSound` system cues (`Tink`, `Pop`, etc.) | Apple macOS system runtime API | No audio files redistributed in `resources/`. |
| **Typography** | `filetool/ui/styles.py`, `filetool/core/legal.py` | System UI fonts (`.AppleSystemUIFont`, `Helvetica Neue`, `SF Mono`) | System-installed OS fonts | Zero font binaries redistributed in `resources/`. |

## Maintenance Rule

`tests/test_compliance.py` fails automatically if any new file is added to `resources/` without a corresponding entry in this manifest.
