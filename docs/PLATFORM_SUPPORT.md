# Platform Support Matrix

OmniDesk uses a shared application core with isolated OS platform adapters and a bundled backend sidecar distribution architecture. This matrix distinguishes what is **tested locally on real hardware** from what is **implemented and CI-packaged pending native host hardware verification**.

## Operating Systems & Universal Distribution

| Platform | Architecture | Packaging Targets | Runtime Validation Status | Native Glass Material |
| --- | --- | --- | --- | --- |
| macOS 13+ (verified on macOS 15.8.3) | Intel x86_64 | `.dmg`, `.app` + bundled sidecar | Verified locally (Tauri 2 shell, Python engine, Ollama `qwen2.5:1.5b`, Accessibility tree, Keychain, Playwright, Flagship Demo) | Native `NSVisualEffectView` (`UnderWindowBackground`) |
| macOS 13+ | Apple Silicon (arm64) | `.dmg`, `.app` + bundled sidecar | CI target configured; pending Apple Silicon host verification | Native `NSVisualEffectView` |
| Windows 10 / 11 | x64 & ARM64 | `.msi`, NSIS `.exe` + bundled sidecar | Adapter implemented; pending native Windows host verification | Windows 11 Mica / Windows 10 Acrylic / solid fallback |
| Linux (Ubuntu, Fedora, Debian) | x64 & ARM64 | `.deb`, `.rpm`, `.AppImage` + bundled sidecar | Adapter implemented; pending native Linux host verification | Compositor blur (KDE/Hyprland/Sway) or solid fallback |

End-user release installers package the Python operator engine as a self-contained sidecar binary (`scripts/build-sidecar.py` + `tauri.release.conf.json`), so end users do not need Python, uv, Rust, Node.js, or pnpm installed.

## Capability Matrix

| Capability | macOS | Windows 10/11 | Linux (X11) | Linux (Wayland) |
| --- | --- | --- | --- | --- |
| Local LLM (`Ollama` + `qwen2.5:1.5b`) | Implemented & Verified | Implemented (untested) | Implemented (untested) | Implemented (untested) |
| Cloud AI (Gemini, OpenAI, Anthropic, Compatible) | Implemented & Verified (unit/API) | Implemented | Implemented | Implemented |
| Scoped File Inspection, Undo Journal & Excel Reports | Implemented & Verified | Implemented | Implemented | Implemented |
| Playwright Chromium Browser Automation | Implemented & Verified | Implemented | Implemented | Implemented |
| Native App Launch & Window Discovery | Verified (`lsappinfo`, `open -a`) | Implemented (`User32`, `Start-Process`, `SetForegroundWindow`) | Implemented (`wmctrl`, `xdotool`, `gtk-launch`) | Implemented (`AT-SPI2`, `gtk-launch`, `xdg-open`) |
| Accessibility Tree & Semantic UI Interaction | Verified (`AXIsProcessTrusted` + System Events) | Implemented (`UIAutomationClient` Invoke/Toggle/Value) | Implemented (`AT-SPI2` Action/EditableText) | Implemented (`AT-SPI2`, respecting compositor isolation) |
| Secure Credential Storage | Verified (macOS Keychain) | Implemented (Credential Manager) | Implemented (D-Bus Secret Service) | Implemented (D-Bus Secret Service) |
| Screen Capture (Optional / Deferred) | Deferred & optional (`CGPreflightScreenCaptureAccess`) | Deferred & optional | Deferred & optional | Portal-gated (XDG Desktop Portal only) |

## Honest Platform Boundaries

- **macOS**: Accessibility and Automation permissions are managed strictly by macOS TCC. Screen Recording is optional and deferred; semantic Accessibility automation does not require Screen Recording.
- **Windows**: Full Win32 + UIA (`UIAutomationClient`) implementation is in place (including password control skipping via `IsPassword`), and requires verification on physical Windows 10 and Windows 11 devices before marking runtime-verified.
- **Linux Wayland**: Wayland compositors intentionally isolate global window titles, screen capture, and synthetic input injection. OmniDesk detects Wayland vs X11 explicitly, uses AT-SPI2 and XDG Desktop Portals where permitted, and refuses unauthorized global key injection on Wayland.
- **Resource Constraints**: On 8 GB RAM systems, OmniDesk defaults local Ollama inference to `num_ctx=2048`, `OLLAMA_MAX_LOADED_MODELS=1`, and `keep_alive=2m`, with one-click RAM unloading from Models.
