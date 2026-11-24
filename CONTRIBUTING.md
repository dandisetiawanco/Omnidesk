# Contributing to OmniDesk

Contributions are welcome across native platform adapters (especially Windows 10/11 and Linux X11/Wayland hardware verification), automation executors, local/cloud AI provider reliability, Workflow Studio usability, security hardening, and documentation.

## Engineering Guidelines

1. **Keep platform code isolated**: Place OS-specific Rust implementations in `apps/desktop/src-tauri/src/platform/` (`macos.rs`, `windows.rs`, `linux.rs`) and Python OS adapters in `backend/omnidesk_engine/automation/desktop_control.py` and `capabilities.py`.
2. **Preserve security invariants**: Any new tool must declare an explicit `ToolPolicy` in `backend/omnidesk_engine/security/policy.py` with accurate risk tier, approval requirement, and reversibility status. Never label a non-reversible operation as undoable.
3. **Never commit secrets or user data**: Do not store API keys, session tokens, `.env` files, `.db` files, or machine-specific paths in code, tests, or fixtures.
4. **Report platform support honestly**: Mark untested OS functionality as `implemented_untested` or `experimental` until verified on actual target hardware.
5. **Maintain Omni Glass & accessibility standards**: Keep WCAG AA contrast ratios in both Light and Dark themes, preserve keyboard navigation (`Tab`, `Enter`, `Space`, `Escape`), and respect `prefers-reduced-motion` and Performance Mode.

## Local Verification Before Opening a Pull Request

```bash
pnpm typecheck
pnpm test:schemas
pnpm test:web
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -v
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

## Pull Request Process

1. Fork `https://github.com/dandisetiawanco/Omnidesk` and create a descriptive feature or fix branch.
2. Keep pull requests focused and include unit tests for backend policies, provider logic, or schema updates.
3. Fill out the pull request template with what changed, how it was verified, and which operating system/architecture you tested on.
