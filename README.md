# OmniDesk

**Your computer. Powered by intelligence.**

OmniDesk is an independent, local-first, cross-platform desktop application that turns natural-language instructions and user demonstrations into verified, permission-gated computer operations across macOS, Windows, and Linux.

## What OmniDesk Does Today (v0.1.0)

- **Natural-language task orchestration**: Decomposes desktop, file, document, and browser tasks into structured, policy-validated execution plans instead of executing unconstrained model text.
- **Flagship folder organization & Excel reporting**: Inspects scoped directories, verifies potential duplicates via byte-size grouping plus SHA-256 content hashes, previews every proposed move, requires explicit user approval, preserves zero-deletion guarantees, records an operation journal for SHA-256-verified rollback, and exports formatted multi-sheet `.xlsx` workbooks.
- **Teach Mode (flagship feature)**: Explicitly records permitted semantic demonstration steps (never silent background recording, automatically dropping passwords and excluded apps), extracts reusable variables, and synthesizes versioned Workflow Studio graphs.
- **Workflow Studio**: Interactive node-based automation editor supporting pan, zoom, minimap, keyboard/pointer node positioning, undo/redo, bounded loops (capped at 100 iterations), human approval gates, versioned JSON export, and dry-run testing.
- **Playwright browser automation**: Real DOM navigation, content extraction with prompt-injection isolation, and form preparation without automatic external form submission.
- **Deny-by-default security architecture**: Six risk tiers, mandatory approval modals with dry-run previews, protected system directory exclusions, OS secure credential vault storage (macOS Keychain, Windows Credential Manager, Linux Secret Service), authenticated loopback IPC with per-session 256-bit bearer tokens, and instant Emergency Stop.
- **Omni Glass design system**: Platform-adaptive materials (macOS vibrancy, Windows Mica/Acrylic, Linux compositor or solid fallback), WCAG AA verified Light and Dark themes, reduced-motion support, and Performance Mode for Intel and lower-powered devices.

## Product Screenshots

Screenshots captured from the running OmniDesk desktop application on macOS 15.8.3 (x86_64):

- Command Center (Dark & Light Omni Glass themes): `docs/screenshots/home-dark.png`, `docs/screenshots/home-light.png`
- Flagship Downloads Demo Approval Gate & Operator Timeline: `docs/screenshots/operator-approval.png`
- Workflow Studio Visual Editor: `docs/screenshots/workflow-studio.png`
- Teach Mode Demonstration Recorder: `docs/screenshots/teach-mode.png`

## Quick Start (Development)

### Prerequisites

- Node.js 20+ and pnpm 9+
- Python 3.11 to 3.13 and `uv`
- Rust stable toolchain (for the native Tauri 2 desktop shell)

### Install Dependencies

```bash
pnpm install
uv sync --directory backend --python 3.12 --extra dev
```

### Run Automated Verification Suites

```bash
pnpm test:schemas
pnpm test:web
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -v
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

### Launch the Desktop Application

```bash
pnpm dev:desktop
```

Or build production bundles for the current host OS:

```bash
pnpm build:desktop
```

## Architecture & Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): Process boundaries, authenticated IPC, platform adapters, and AI pipeline.
- [DESIGN.md](DESIGN.md): Omni Glass design language, WCAG AA contrast verification, and material rules.
- [SECURITY.md](SECURITY.md): Threat model, deny-by-default permission tiers, credential storage, and vulnerability disclosure.
- [PRIVACY.md](PRIVACY.md): Local-first storage policy, cloud consent controls, redaction, and retention.
- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md): Honest capability matrix (implemented, experimental, planned).
- [docs/SIGNING_AND_NOTARIZATION.md](docs/SIGNING_AND_NOTARIZATION.md): Release signing and packaging setup for macOS, Windows, and Linux.
- [docs/LICENSE_DECISION.md](docs/LICENSE_DECISION.md): Rationale for Apache-2.0 licensing.
- [CONTRIBUTING.md](CONTRIBUTING.md): Development workflow and contribution guidelines.
- [CHANGELOG.md](CHANGELOG.md): Release history.

## License & Attribution

Licensed under the [Apache License 2.0](LICENSE).

Created by NGOPREK DIGITAL.
