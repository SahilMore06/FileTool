# Privacy Policy

FileTool runs offline on your Mac. Your files never leave your machine.

## Data collection

- FileTool makes zero network requests for conversions, updates, telemetry, crash reports, or usage analytics.
- FileTool does not set cookies, collect identifiers, or transmit file names, file contents, or conversion history to any server.

## Local storage on macOS

- Preferences (theme mode, accent preset, modifier trigger keys, menu-bar mode, output directory, overwrite flag, and delete-original option) are saved locally in macOS `QSettings` (`FileTool` / `FileTool`).
- Optional `Launch at Login` writes a user LaunchAgent plist at `~/Library/LaunchAgents/com.filetool.app.plist` and removes it when switched off.
- Converted files are saved beside each source file by default (or to your chosen local output directory) with numeric suffixes (`name (1).ext`) unless overwrite mode is enabled.

## Finder Drag Wheel

When enabled, `MacDragMonitor` uses a passive Quartz `CGEventTap` (`kCGEventFlagsChanged`) to watch modifier key taps and reads `NSDragPboard` pasteboard file URLs only while a drag is active. No keystrokes or screen contents are recorded or stored.
