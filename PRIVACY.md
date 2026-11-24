# Privacy Policy (Local-First Design)

OmniDesk is engineered to process your data locally by default.

## Stored Locally on Your Device

OmniDesk writes local operational data to your operating system's application data directory (`omnidesk.db`):

- Appearance, privacy, and scoped directory preferences.
- Saved Workflow Studio definitions and version history.
- Teach Mode semantic step sessions (with passwords and secure fields stripped before storage).
- Execution history, approval audit entries, and reversible file operation journals.
- Local model URLs and role assignments (never API secrets, which live only in your OS Keychain / Credential Manager / Secret Service).

You can inspect individual history records or wipe local execution and audit history at any time from the **Activity** view.

## Telemetry

Telemetry is **disabled by default** (`telemetry_enabled: false`). OmniDesk does not collect analytics, usage fingerprints, or background crash uploads.

## Cloud AI Usage and Consent

- In **Local-only mode** (default), OmniDesk never transmits prompts, filenames, documents, or snapshots to external cloud AI providers.
- In **Cloud-assisted mode**, OmniDesk sends only the task context required by the provider you explicitly configured (OpenAI, Google Gemini, Anthropic Claude, or a custom OpenAI-compatible endpoint).
- Desktop snapshots in **Live Workspace** run only when you explicitly authorize and trigger a single capture. They are never streamed continuously, never sent to cloud models without explicit `cloud_screenshot_consent`, and automatically skip applications listed in your **Excluded Sensitive Applications** list (such as 1Password, Bitwarden, Keychain Access, and KeePassXC).
