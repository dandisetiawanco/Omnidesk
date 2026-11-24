# Installation and Development Setup

OmniDesk is currently distributed from source as an early-stage Developer Preview (`v0.1.0`). Signed public desktop installers have not been published yet.

## System Requirements

| Component | Requirement | Notes |
| --- | --- | --- |
| Operating System | macOS 13+ (tested on macOS 15.8.3 Intel x86_64), Windows 10/11, or Linux (Ubuntu/Debian/Fedora) | See [PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md) for verified vs untested status |
| Memory | 8 GB RAM minimum (16 GB recommended for larger local models) | Default local context limit automatically scales to `2048` on 8 GB hosts |
| Node.js & pnpm | Node.js `>= 20` and `pnpm >= 9` | Frontend build and workspace orchestration |
| Python & uv | Python `3.11` to `3.13` and `uv` | Local operator engine virtual environment |
| Rust Toolchain | Stable Rust + Cargo (`rustup`) | Native Tauri 2 desktop shell |
| Linux System Libraries | `libwebkit2gtk-4.1-dev`, `libappindicator3-dev`, `librsvg2-dev`, `patchelf`, `libsecret-1-dev`, `libatspi2.0-dev` | Required on Ubuntu/Debian before building Tauri |

## 1. Clone the Repository

```bash
git clone https://github.com/dandisetiawanco/Omnidesk.git
cd Omnidesk
```

## 2. Install Frontend and Workspace Dependencies

```bash
pnpm install
```

## 3. Set Up the Python Operator Engine

```bash
uv sync --directory backend --python 3.12 --extra dev
```

To enable real Playwright browser automation, install Chromium once:

```bash
backend/.venv/bin/playwright install chromium
```

## 4. Launch the Native Desktop Application

```bash
pnpm dev:desktop
```

This starts Vite (`http://127.0.0.1:1420`), compiles and launches the native Tauri 2 shell (`apps/desktop/src-tauri`), and spawns the authenticated local FastAPI engine on `127.0.0.1:17420` (falling back to a free loopback port if `17420` is busy).

## 5. Set Up Local AI with Ollama (Recommended Offline Option)

1. Install **Ollama** from the official release for your OS (https://ollama.com/download or GitHub Releases).
2. Pull a lightweight quantized instruction model suited for 8 GB RAM systems:

```bash
ollama pull qwen2.5:1.5b
```

3. Open the **Models** view inside OmniDesk. Ollama is detected automatically; you can start the local runtime on demand, adjust `num_ctx`, select `qwen2.5:1.5b`, run a live streaming test, or click **Unload from RAM** at any time.

## 6. Optional Cloud AI Setup

1. Open **Models** and select **Google Gemini**, **OpenAI**, **Anthropic Claude**, or **OpenAI-Compatible Endpoint**.
2. Paste your API key and click **Save Configuration** (keys are saved only to your OS Keychain, Windows Credential Manager, or Linux Secret Service).
3. Click **Test & Discover Models** to verify live connectivity.
4. Open **Settings** and switch Privacy Mode from **Local-only** to **Cloud-assisted** when you explicitly want cloud models to plan tasks.

## 7. Platform Permissions

- **macOS**: Grant **Accessibility** in `System Settings > Privacy & Security > Accessibility` to inspect native application UI trees and perform approved semantic interactions. **Screen Recording** is optional and deferred; core features work without enabling it.
- **Windows**: Standard user privileges are sufficient for UI Automation and scoped file workflows.
- **Linux**: Enable desktop accessibility (`org.a11y.Bus` / AT-SPI2) for semantic UI inspection. On Wayland, global capture and synthetic input remain isolated by the compositor unless explicitly authorized through XDG Desktop Portals.

## 8. Building a Standalone Local Package (Optional)

To test building a self-contained backend sidecar and native desktop bundle on your current machine:

```bash
uv sync --directory backend --python 3.12 --extra bundle
backend/.venv/bin/python scripts/build-sidecar.py
pnpm --filter @omnidesk/desktop tauri build --config src-tauri/tauri.release.conf.json
```
