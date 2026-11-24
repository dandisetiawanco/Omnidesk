# Changelog

All notable changes to OmniDesk are documented in this file.

## [0.1.0] - 2026-11-24 (Developer Preview)

### Added

- **Cross-platform monorepo architecture**: Tauri 2 native desktop shell (Rust), React 19 + TypeScript + Vite frontend, Zod shared contracts (`packages/shared-schemas`), and Python 3.12 + FastAPI + SQLite local operator engine.
- **Omni Glass design system**: 4-tier adaptive material hierarchy (macOS `NSVisualEffectView`, Windows 11 Mica / Windows 10 Acrylic, Linux compositor or solid fallback), WCAG AA verified Light and Dark themes, reduced-motion support, and Performance Mode.
- **Local AI inference via Ollama**: Automatic runtime detection, on-demand service startup, model pull with live progress tracking, one-click RAM unloading (`keep_alive: 0`), configurable context limits (`num_ctx=2048` default on 8 GB hosts), and verified local structured JSON planning with `qwen2.5:1.5b` (`Q4_K_M`, ~986 MB).
- **Cloud AI provider integrations**: Real API clients for Google Gemini, OpenAI, Anthropic Claude (native `submit_plan` tool calling), and OpenAI-compatible endpoints with dynamic model discovery, capability tagging, SSE streaming previews, request cancellation, configurable fallback priority, and token/cost tracking.
- **Strict plan validation & deterministic fallback**: Outside-the-model validation rejecting unregistered tools, destructive actions, and incomplete parameters, with transparent fallback to the built-in local deterministic planner.
- **Deny-by-default security architecture**: Six risk tiers, mandatory dry-run approval dialogs, scoped directory validation with symlink/traversal protection, prompt-injection isolation, OS secure credential vault storage, authenticated loopback IPC (256-bit CSPRNG Bearer token), SHA-256 operation journal with Undo rollback, and global Emergency Stop.
- **Native desktop automation & cross-platform adapters**:
  - macOS Intel x64 verified (`AXIsProcessTrusted` + System Events semantic tree inspection, `lsappinfo`, `open -a`, Keychain; Screen Recording deferred/optional).
  - Windows 10/11 adapter implemented (`UIAutomationClient`, Win32 `User32`, `Start-Process`, `SetForegroundWindow`, Credential Manager, Mica/Acrylic detection; pending host runtime testing).
  - Linux X11 & Wayland adapter implemented (`AT-SPI2`, D-Bus XDG Portals, `wmctrl`/`xdotool` on X11, transparent Wayland isolation, Secret Service; pending host runtime testing).
- **Workflow Studio & Teach Mode**: Interactive visual DAG editor (pan, zoom, minimap, keyboard positioning, undo/redo, bounded loops capped at 100 iterations, versioned JSON export) and explicit opt-in demonstration recorder with automatic password/excluded-app redaction.
- **Floating Assistant & Command Palette**: Persistent floating quick-operator panel, `Cmd/Ctrl+K` command palette, system tray menu, and `CommandOrControl+Shift+Space` global shortcut.
- **Universal distribution architecture**: PyInstaller standalone backend sidecar builder (`scripts/build-sidecar.py`) and 6-target GitHub Actions cross-platform build matrix (macOS Intel/ARM64, Windows x64/ARM64, Linux x64/ARM64).
