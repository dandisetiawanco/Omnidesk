# Troubleshooting

Common issues and direct resolutions for local development and runtime operation.

## 1. "Local Operator Engine Unreachable" on Startup

- Verify that the Python virtual environment exists inside `backend/.venv`:
  ```bash
  uv sync --directory backend --python 3.12 --extra dev
  ```
- Confirm no stale process is holding port `17420`:
  ```bash
  lsof -i :17420
  ```
- Note: OmniDesk automatically falls back to another free `127.0.0.1` port if `17420` is occupied, and passes the port and session token to the webview over Tauri IPC.

## 2. Ollama Shows "Runtime missing" or "Stopped"

- Confirm `ollama` is installed and executable:
  ```bash
  ollama --version
  ```
- On macOS, OmniDesk checks `PATH`, `/usr/local/bin/ollama`, `/opt/homebrew/bin/ollama`, `~/.local/bin/ollama`, and `/Applications/Ollama.app/Contents/Resources/ollama`.
- Click **Start Local Ollama** in the **Models** view, or start it manually with RAM-conscious defaults:
  ```bash
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=2m ollama serve
  ```
- If memory feels tight on an 8 GB RAM machine, set **Context Limit** to `1024` or `2048` in **Models > Advanced routing & context settings** and click **Unload from RAM** when finished.

## 3. macOS Accessibility Permission Not Updating

- Grant permission to the running host binary in `System Settings > Privacy & Security > Accessibility`.
- In OmniDesk **Settings**, click **Refresh Permissions** to re-query `AXIsProcessTrusted` live without restarting.
- **Screen Recording** is optional and deferred. Do not enable it unless you specifically plan to use manual single-shot snapshots in Live Workspace.

## 4. Cloud Provider Calls Are Not Running

- Verify two conditions:
  1. An API key is saved in **Models** and **Test & Discover Models** reports `Ready`.
  2. **Settings > Privacy Mode** is switched from **Local-only** to **Cloud-assisted**. In **Local-only** mode, cloud calls are intentionally blocked.

## 5. Playwright Browser Tasks Fail With Missing Executable

Install Playwright's Chromium binary into the local cache once:

```bash
backend/.venv/bin/playwright install chromium
```

## 6. Linux Build or Wayland Limitations

- Missing GTK/WebKit headers during `cargo build` or `pnpm dev:desktop`: install `libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf libsecret-1-dev libatspi2.0-dev`.
- On **Wayland**, global window titles, screen capture, and synthetic keyboard injection are restricted by the compositor by design. OmniDesk reports this transparently and uses AT-SPI2 / XDG Desktop Portals rather than unsafe workarounds.
