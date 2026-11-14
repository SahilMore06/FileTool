# Terms and Conditions

Last updated: November 2026

By installing or using **Fluxora** on macOS, you agree to the terms below alongside the [MIT License](LICENSE) and the [Privacy Policy](PRIVACY.md).

## 1. Open-Source License

Fluxora is open-source software licensed under the MIT License (Copyright (c) 2026 SahilMore06). Subject to the license notice, you may use, copy, modify, merge, publish, and distribute the software free of charge.

## 2. Offline Local Operation

All conversions, compression, media trimming, document exports, and metadata removal happen locally on your Mac. Fluxora does not host cloud servers, require an account, or send your files off your device.

## 3. File Safety and Backups

- By default, Fluxora keeps source files untouched and writes new outputs beside each source using numeric suffixes (`name (1).ext`).
- Turning on **Overwrite Existing Output Files** or **Delete Original After Success** in Settings permanently modifies or removes files after conversion. You are responsible for keeping backups of critical files before enabling destructive options.

## 4. macOS System Integrations

- When **Enable Finder Drag Wheel** is on, Fluxora observes modifier key taps with a passive Quartz `CGEventTap` (`kCGEventFlagsChanged`) and reads `NSDragPboard` URLs only while a drag is in progress.
- When **Launch at Login** is enabled, Fluxora writes a local user LaunchAgent at `~/Library/LaunchAgents/com.fluxora.app.plist`.

## 5. Third-Party Conversion Tools

Fluxora invokes local open-source command-line engines when installed on your Mac (such as `ffmpeg`, `magick`, `pandoc`, `pdftoppm`, `gs`, `7zz`, and LibreOffice). Each third-party binary remains governed by its own license.

## 6. No Warranty and Limitation of Liability

AS PROVIDED IN THE MIT LICENSE, THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM THE USE OF THE SOFTWARE.
