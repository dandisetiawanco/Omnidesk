# Platform Support Matrix

OmniDesk uses a shared core with isolated platform adapters. This document honestly distinguishes what is **tested on real hardware**, **implemented and CI-validated**, **experimental**, and **planned**.

## Operating Systems

| Platform | Architecture | Build Status | Runtime Validation Status | Native Glass Material |
| --- | --- | --- | --- | --- |
| macOS 13+ (tested on macOS 15.8.3) | Intel x86_64 | Tested locally | Tested locally (Rust shell, Python engine, Playwright, Keychain, Flagship Demo) | Native `NSVisualEffectView` vibrancy |
| macOS 13+ | Apple Silicon (arm64) | Configured in CI | Pending Apple Silicon hardware validation | Native `NSVisualEffectView` vibrancy |
| Windows 10 / 11 | x64 | Configured in CI (`msi`, `nsis`) | Pending native Windows host testing | Windows 11 Mica / Windows 10 Acrylic fallback |
| Linux (Ubuntu, Fedora, Debian) | x64 | Configured in CI (`deb`, `rpm`, `appimage`) | Pending native Linux desktop testing | Compositor blur (KDE/Hyprland) or crisp solid fallback |

## Capability Matrix

| Capability | macOS | Windows | Linux (X11) | Linux (Wayland) |
| --- | --- | --- | --- | --- |
| Scoped File Inspection & SHA-256 Duplicate Detection | Implemented & Tested | Implemented | Implemented | Implemented |
| Dry-Run File Organization & SHA-256 Undo Journal | Implemented & Tested | Implemented | Implemented | Implemented |
| Formatted Excel (`.xlsx`) & Markdown Reporting | Implemented & Tested | Implemented | Implemented | Implemented |
| Playwright Chromium Browser Automation | Implemented & Tested | Implemented | Implemented | Implemented |
| Native Application Launching | Implemented (`open -a`) | Implemented (`explorer.exe`) | Implemented (`gtk-launch`/`xdg-open`) | Implemented (`gtk-launch`/`xdg-open`) |
| Secure Credential Storage | Implemented (Keychain) | Implemented (Credential Manager) | Implemented (Secret Service) | Implemented (Secret Service) |
| Accessibility Tree Inspection | Permission-gated (`AXIsProcessTrusted`) | Experimental (UIA adapter) | Experimental (AT-SPI) | Portal / Compositor gated |
| Opt-In Single-Shot Screen Snapshot | Permission-gated (`CGPreflightScreenCaptureAccess`) | Planned (DXGI / Graphics Capture) | Experimental | Portal-only (XDG Desktop Portal) |
| Global Synthetic Input Injection | Permission-gated (Planned) | Experimental (UIA) | Experimental | Intentionally unsupported without compositor portal |

## Platform Limitations & Honest Boundaries

- **macOS**: Accessibility, Screen Recording, and Automation (Apple Events) permissions are controlled strictly by macOS TCC. OmniDesk checks status read-only and guides users to System Settings instead of attempting bypasses.
- **Linux Wayland**: Wayland compositors isolate global screen capture, window titles, and synthetic input injection by design. OmniDesk detects Wayland sessions separately from X11, reports restricted capabilities honestly, and uses compositor-approved XDG Desktop Portals rather than workarounds.
- **Hardware Performance**: On Intel laptops and lower-powered machines (such as 8 GB RAM dual/quad-core devices), enabling **Performance Mode** in Settings disables backdrop blur filters and collapses non-essential motion to reduce GPU/RAM overhead.
