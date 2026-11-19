# Privacy Policy

Fluxora runs offline on your Mac. Your files never leave your machine.

## Data collection

- Fluxora makes zero network requests for conversions, updates, telemetry, crash reports, or usage analytics.
- Fluxora does not set cookies, collect identifiers, or transmit file names, file contents, or conversion history to any server.

## Local storage on macOS

- Preferences (theme mode, accent preset, modifier trigger keys, menu-bar mode, output directory, overwrite flag, and delete-original option) are saved locally in macOS `QSettings` (`Fluxora` / `Fluxora`).
- Optional `Launch at Login` writes a user LaunchAgent plist at `~/Library/LaunchAgents/com.fluxora.app.plist` and removes it when switched off.
- Converted files are saved beside each source file by default (or to your chosen local output directory) with numeric suffixes (`name (1).ext`) unless overwrite mode is enabled.

## Finder Drag Wheel

When enabled, `MacDragMonitor` queries macOS Quartz input state (`CGEventSourceButtonState`, `CGEventSourceFlagsState`, and `CGEventSourceKeyState` for Escape/Return/arrow wheel navigation) together with `NSEvent.mouseLocation` and `NSDragPboard` file URLs only while a file drag or wheel overlay is active. It does not install an input event tap, log keystrokes, or record typing, passwords, or screen contents. Permission behavior on clean macOS accounts is tracked in [docs/TRADEMARK_AND_PERMISSIONS_CHECK.md](docs/TRADEMARK_AND_PERMISSIONS_CHECK.md).
