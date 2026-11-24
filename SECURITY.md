# Security Policy

Security is a core architectural boundary in OmniDesk. While no desktop automation software that interacts with local files, browsers, and operating system accessibility APIs can guarantee zero risk, OmniDesk applies layered defense-in-depth controls to keep every action visible, scoped, and user-controlled.

## Implemented Security Controls

1. **Deny-by-default tool policy**: Every executable action must be registered in `backend/omnidesk_engine/security/policy.py` under one of six risk tiers (`read_only`, `reversible_modification`, `sensitive_access`, `external_communication`, `destructive`, `privileged_system`). Unregistered tools default to `privileged_system` and are blocked.
2. **Outside-the-model plan validation**: Structured JSON plans returned by local or cloud AI models are strictly validated before execution. Unknown tools, shell commands, destructive requests, file moves lacking a prior dry-run plan, or incomplete parameters are rejected cleanly.
3. **Mandatory human approval**: Modifying files, generating documents or spreadsheets, launching applications, clicking/typing in external apps, or visiting external URLs pause in `awaiting_approval` with a dry-run preview until explicitly approved by the user.
4. **Authenticated loopback IPC**: The local FastAPI backend binds strictly to `127.0.0.1` and requires a per-session 256-bit cryptographically random Bearer token (`OMNIDESK_SESSION_TOKEN`) verified in constant time (`hmac.compare_digest`). Session tokens are passed via process environment variables, never CLI arguments or URL query strings.
5. **OS credential vault storage**: Cloud provider API keys are stored exclusively in the host operating system credential store (macOS Keychain, Windows Credential Manager, or Linux Secret Service). Keys are never persisted to `.env`, SQLite, JSON config files, frontend storage, or logs.
6. **Scoped filesystem boundaries**: Paths are canonicalized with `Path.resolve()` to block `..` traversal and symlink escapes. Protected system and credential paths (`/System`, `/etc`, `/usr`, `/bin`, `/sbin`, `~/.ssh`, `~/.aws`, `~/.gnupg`, `C:\Windows\System32`) are unconditionally denied.
7. **Sensitive application and password field refusal**: Password managers and sensitive window titles are excluded by default (`1Password`, `Bitwarden`, `Keychain Access`, `KeePassXC`, banking/login/OTP titles). Semantic adapters explicitly skip password inputs (`AXSecureTextField` on macOS, `IsPassword` on Windows UIA, `ROLE_PASSWORD_TEXT` on Linux AT-SPI2).
8. **Prompt-injection isolation**: External filenames, document text, and browser DOM content are treated as untrusted data, scanned for injection cues, redacted for common secret patterns, and separated from planner instructions.
9. **Reversible rollback and Emergency Stop**: Approved file moves record SHA-256 digests in an operation journal for verified rollback. Emergency Stop immediately cancels running tasks, stops Teach Mode observers, and aborts active AI inference connections.
10. **Strict Tauri CSP and platform respect**: `tauri.conf.json` enforces `script-src 'self'` and `object-src 'none'`. OmniDesk does not request administrator/root elevation by default and never bypasses macOS TCC or Linux Wayland security boundaries.

## Reporting a Vulnerability

If you identify a security vulnerability in OmniDesk, please do **not** open a public issue with exploit details. Instead:

- Use GitHub's private vulnerability reporting feature on `https://github.com/dandisetiawanco/Omnidesk/security` (when enabled), or contact the maintainer directly via https://www.dandisetiawan.id/.
- Include clear reproduction steps, affected operating system and architecture, and potential security impact so the issue can be verified and patched responsibly.
