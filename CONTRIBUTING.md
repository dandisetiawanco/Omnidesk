# Contributing to OmniDesk

Contributions are welcome across platform adapters, automation tools, workflow nodes, security hardening, and documentation.

## Development Standards

1. **Isolate platform code**: Keep macOS, Windows, and Linux implementations behind `apps/desktop/src-tauri/src/platform/` and avoid leaking OS assumptions into shared UI or orchestration logic.
2. **Preserve security boundaries**: Every new automation tool must register an explicit `ToolPolicy` entry in `backend/omnidesk_engine/security/policy.py` with accurate risk tier, approval requirement, and reversibility flag. Never claim an irreversible action can be undone.
3. **Zero plaintext secrets**: Never store tokens or API keys in config files, SQLite, logs, or test fixtures committed to Git.
4. **Honest capabilities**: Never mark an unimplemented or unsupported platform feature as available.
5. **Accessibility & Omni Glass quality**: Verify WCAG AA contrast ratios in both Light and Dark modes, keyboard navigation (`Tab`, `Enter`, `Space`, `Escape`), and responsive reflow before opening a pull request.

## Verification Checklist Before Opening a PR

```bash
pnpm typecheck
pnpm test:schemas
pnpm test:web
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -v
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```
