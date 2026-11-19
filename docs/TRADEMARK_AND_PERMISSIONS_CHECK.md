# Trademark, Name Conflict, and Clean-Account Permissions Check (L6 & L8)

## 1. macOS Clean-Account Permissions Audit (L6)

### Code-Level Findings (Verified 19 November 2026)

`filetool/platform/mac_drag_monitor.py` does **not** create a `CGEventTap`. Instead it uses:
- `Quartz.CGEventSourceButtonState(...)` (left mouse button state)
- `Quartz.CGEventSourceFlagsState(...)` (modifier flags: Shift, Command, Control, Option)
- `Quartz.CGEventSourceKeyState(...)` (Escape, Return, arrow keys while wheel is open)
- `AppKit.NSEvent.mouseLocation()` and `NSPasteboard` (`NSDragPboard`)

### Clean macOS User Account Test Protocol (Manual Sign-Off)

Run on a brand-new standard macOS user account (or Guest account) with **no** prior entries in `System Settings -> Privacy & Security`:

1. Launch Fluxora and open `System Settings -> Privacy & Security -> Accessibility` and `Input Monitoring`.
2. Drag a `.png` file in Finder and tap `Shift`. Record whether macOS triggers any system prompt or silently blocks `CGEventSourceKeyState` / `CGEventSourceFlagsState`.
3. Press `Escape` and arrow keys while the wheel is open. Record whether `CGEventSourceKeyState` works without `Input Monitoring`.
4. Verify zero outbound network sockets while converting a file:
   ```bash
   lsof -i -n -P -p "$(pgrep -f 'filetool|Fluxora')"
   ```
   Expected: zero open TCP/UDP connections.
5. Update status below and reconcile `README.md` / `PRIVACY.md` if any prompt occurs on macOS 13, 14, or 15+.

| macOS Version | Architecture | Accessibility Prompt? | Input Monitoring Prompt? | Drag Trigger Works? | Keyboard Nav Works? | Date / Tester |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| macOS 13+ | Apple Silicon | _Pending clean-user test_ | _Pending clean-user test_ | _Pending_ | _Pending_ | — |
| macOS 13+ | Intel | _Pending clean-user test_ | _Pending clean-user test_ | _Pending_ | _Pending_ | — |

---

## 2. Trademark & Name Conflict Check for "Fluxora" (L8)

### Live Web Collision Check (Observed 19 November 2026)

Public web searches already show multiple active unrelated domains and products using the name **Fluxora**:
- `fluxora.com` — D2C fashion storefront
- `playfluxora.com` — IPTV streaming service
- `fluxora-pulse.com` — browser extension for random video chats
- `fluxora.tech` / `fluxora.studio` / `fluxorafx.com` — digital/dev/creator agencies
- `FLXO` — crypto token ticker labeled Fluxora

Because of these collisions, **"Fluxora"** faces heavy SEO brand dilution AND potential trademark overlap in software classes (Nice Class 9 / Class 42).

### Required Official Registry Searches (Free Self-Check Before Phase 1 Branding)

- [ ] **India IP Trademark Public Search (Class 9 & Class 42):** https://tmrsearch.ipindia.gov.in/tmrpublicsearch/
- [ ] **USPTO Trademark Search (Class 9 & Class 42):** https://tmsearch.uspto.gov/
- [ ] **EUIPO eSearch Plus (Class 9 & Class 42):** https://euipo.europa.eu/eSearch/
- [ ] **Apple Mac App Store & GitHub Search:** Search `"Fluxora"` for existing desktop utilities or Mac software.

### Fallback Name Shortlist (If Class 9 Software Conflict Exists)

Keep a shortlist ready before locking Phase 1 brand assets and Homebrew Cask naming (verify domain + trademark availability before adopting):
- **FluxDeck** (ties directly to the Arc Deck + pipeline concept)
- **LocalFlow / MacFlux**
- **PipeDrop** (emphasizes drop + recipe pipelines)
- **CraftDrop / FileArc**
