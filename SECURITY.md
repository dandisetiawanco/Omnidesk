# Security Policy

Security is a foundational design requirement in OmniDesk, not an optional feature.

## Core Security Controls

1. **Deny-by-default permissions**: Every tool belongs to an explicit risk tier (`read_only`, `reversible_modification`, `sensitive_access`, `external_communication`, `destructive`, `privileged_system`). Unregistered tools default to `privileged_system` and are blocked.
2. **Mandatory human confirmation**: Moving or creating files, generating reports, launching native applications, accessing the clipboard, or opening external browser URLs pause for explicit approval with a dry-run preview.
3. **Authenticated loopback transport**: The local FastAPI engine binds strictly to `127.0.0.1` and requires a per-session 256-bit cryptographically random Bearer token (`OMNIDESK_SESSION_TOKEN`) validated in constant time (`hmac.compare_digest`). Tokens are passed via child process environment variables, never via CLI arguments or query parameters.
4. **Zero plaintext credentials**: Provider API keys are stored exclusively in the host operating system credential store (macOS Keychain, Windows Credential Manager, Linux Secret Service). Keys are never written to `.env`, SQLite, JSON config files, frontend bundles, or logs.
5. **Scoped filesystem boundaries**: Every path is resolved via `Path.resolve()` to prevent symlink and `..` traversal escapes. Protected directories (`/System`, `/etc`, `/usr`, `/bin`, `/sbin`, `~/.ssh`, `~/.aws`, `~/.gnupg`, `C:\Windows\System32`) are unconditionally denied.
6. **Prompt-injection isolation**: Filenames, document contents, and Playwright webpage excerpts are treated strictly as untrusted data, scanned for injection patterns, redacted for secrets, and wrapped in non-instructional delimiters before any model call.
7. **Strict Tauri capabilities & CSP**: `tauri.conf.json` enforces `script-src 'self'`, `object-src 'none'`, and least-privilege plugin permissions without exposing arbitrary shell execution to the webview.
8. **No silent surveillance or privilege elevation**: OmniDesk never requests administrator/root privileges by default, never installs hidden background keyloggers, and never bypasses macOS TCC or Linux Wayland portal restrictions.
9. **Bounded execution & Emergency Stop**: Every task enforces step caps, per-step timeouts, sliding-window rate limits, bounded workflow loop counts (`<= 100`), and an always-reachable Emergency Stop trigger.

## Reporting a Vulnerability

If you discover a security issue in OmniDesk, please report it privately to the maintainers at NGOPREK DIGITAL rather than opening a public issue with exploit details. Include reproduction steps, affected operating system, and impact assessment so we can verify and release a fix promptly.
