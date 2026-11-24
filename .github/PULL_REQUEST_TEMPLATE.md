## Summary

- What does this pull request change?
- Why is this change needed?

## Platform & Verification

- [ ] Tested locally on target OS: *(specify macOS / Windows / Linux, architecture, and display server)*
- [ ] `pnpm typecheck`
- [ ] `pnpm test:schemas` and `pnpm test:web`
- [ ] `PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -v`
- [ ] `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml`

## Security & Design Checklist

- [ ] No API keys, session tokens, `.db` files, or machine-specific paths included
- [ ] Any new tool registers an explicit `ToolPolicy` risk tier, approval requirement, and reversibility flag
- [ ] Platform capabilities report verified vs untested status honestly
- [ ] UI changes preserve WCAG AA contrast in Light and Dark themes and keyboard accessibility
