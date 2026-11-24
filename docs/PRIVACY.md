# Privacy Architecture (Local-First Design)

OmniDesk is engineered so your instructions, files, workflows, and execution history remain on your own device by default.

## Data Stored Locally

OmniDesk persists local application state inside your operating system's standard user application data directory (`omnidesk.db`):

- Appearance, theme, Performance Mode, privacy mode, and scoped directory settings.
- Saved Workflow Studio graphs and version metadata.
- Teach Mode demonstration sessions (with password fields and excluded sensitive apps dropped prior to persistence).
- Task execution history, approval decisions, audit events, and SHA-256 file rollback journals.
- Local model endpoints, context limits, and fallback ordering.

API keys are **never** written to `omnidesk.db`, `.env`, JSON files, or log files; they are stored exclusively in your operating system's credential vault (macOS Keychain, Windows Credential Manager, or Linux Secret Service).

You can inspect or delete individual tasks or clear local history from the **Activity** view at any time.

## Telemetry

Telemetry is disabled by default (`telemetry_enabled: false`). OmniDesk contains no third-party analytics SDKs, usage tracking beacons, or background crash uploaders.

## Cloud AI Data Consent

- **Local-only mode (default)**: `ProviderRegistry` blocks all cloud provider requests before any outbound network connection is created. Only local Ollama (`127.0.0.1:11434`) and the built-in deterministic local planner can run.
- **Cloud-assisted mode (opt-in)**: When explicitly enabled in **Settings**, OmniDesk transmits only the task prompt and tool catalog required by the cloud provider you configured.
- **Screenshot consent**: Live Workspace desktop snapshots are strictly single-shot, opt-in actions triggered manually by the user. Screen Recording is optional and deferred on macOS, continuous screen recording does not exist, and snapshots are never forwarded to cloud models unless `cloud_screenshot_consent` is explicitly enabled.

## Sensitive Application and Password Protection

OmniDesk maintains a user-editable list of **Excluded Sensitive Applications** (defaulting to `1Password`, `Bitwarden`, `Keychain Access`, and `KeePassXC`) and sensitive window-title heuristics (`password`, `passcode`, `sign in`, `2fa`, `otp`, `banking`, `checkout`, `wallet`). Accessibility inspection, Teach Mode capture, and controlled input automatically refuse excluded apps and OS password fields (`AXSecureTextField`, `IsPassword`, `ROLE_PASSWORD_TEXT`).
