# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :--- |
| `1.1.x` | Yes |
| `1.0.x` | Security fixes applied on `1.1.x` |

## Security Model

Fluxora is built for local execution on macOS:

- **Offline Execution**: Zero outbound HTTP requests, update checks, telemetry beacons, or analytics collectors.
- **No Shell Interpolation**: External CLI engines (`ffmpeg`, `magick`, `pandoc`, `pdftoppm`, `gs`, `soffice`, `7zz`) execute strictly with argument lists (`shell=False`).
- **Passive Drag Detection**: `MacDragMonitor` uses a passive Quartz `CGEventTap` (`kCGEventFlagsChanged`) and `NSDragPboard` change counts without requiring Accessibility permissions or recording keyboard text.
- **Non-Destructive Defaults**: Source files stay untouched and existing targets append numeric increments (`name (1).ext`) unless overwrite or delete-after-success is explicitly switched on in Settings.

## Reporting a Vulnerability

If you discover a security bug or unsafe subprocess handling, please report it privately through [GitHub Security Advisories](https://github.com/SahilMore06/Fluxora/security/advisories/new) instead of opening a public issue with exploit details. Include steps to reproduce and affected versions.
