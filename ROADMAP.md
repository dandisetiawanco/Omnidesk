# Roadmap

OmniDesk is currently an early-stage Developer Preview (`v0.1.0`) with a verified local macOS Intel x64 runtime and implemented cross-platform adapters. The roadmap below reflects genuine engineering priorities without speculative delivery dates.

## Near-Term Hardware Verification

- **Native Windows 10 and Windows 11 verification**: End-to-end runtime testing of Windows UI Automation (`UIAutomationClient`), Win32 foreground tracking, Credential Manager, Mica/Acrylic materials, high-DPI scaling, and bundled `.msi` / NSIS `.exe` installers on x64 and ARM64 hosts.
- **Native Linux X11 and Wayland verification**: End-to-end testing of AT-SPI2 semantic interaction, D-Bus XDG Desktop Portals, Secret Service (GNOME Keyring / KWallet), tray behavior, and `.deb` / `.rpm` / `.AppImage` packages on Ubuntu, Fedora, and Debian (x64 and ARM64).
- **Apple Silicon (`arm64`) verification**: Hardware testing of universal/arm64 macOS `.dmg` bundles, native Metal acceleration for local Ollama models, and TCC permission flows.

## Core Operator Capabilities

- **Advanced semantic desktop interaction**: Deeper multi-level accessibility selectors, structured window state verification, and broader application control patterns across native toolkits.
- **Expanded Teach Mode recording and replay**: Richer semantic event synthesis, interactive parameter editing, step-level assertions, and deterministic replay diagnostics.
- **Improved local model planning**: Better tool-calling reliability and constrained JSON decoding for compact quantized local models (0.5B to 7B) alongside lower cold-start latency.
- **Optional visual understanding**: Opt-in vision-assisted element disambiguation for apps with incomplete accessibility trees, gated strictly by explicit user consent and excluded-app rules.

## Ecosystem, Packaging, and Quality

- **Workflow portability**: Import/export schema validation, shareable workflow packs with explicit permission manifests, and template libraries.
- **Signed and notarized distribution packages**: Automated Apple Developer ID notarization, Windows Authenticode code signing, and reproducible checksum verification.
- **Accessibility and performance improvements**: Continued WCAG AA contrast auditing, full keyboard operability in Workflow Studio, and lower idle memory overhead on 8 GB RAM machines.
