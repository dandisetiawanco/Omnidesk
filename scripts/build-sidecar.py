#!/usr/bin/env python3
"""Builds a self-contained OmniDesk backend sidecar binary for Tauri bundling.

End users receive a single native desktop installer (.dmg, .msi, .exe, .deb, .rpm, .AppImage)
without needing Python, uv, Rust, Node.js, or pnpm installed.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def detect_rust_target_triple() -> str:
    try:
        out = subprocess.check_output(["rustc", "-vV"], text=True, timeout=10)
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if sys_name == "darwin":
        return f"{arch}-apple-darwin"
    if sys_name == "windows":
        return f"{arch}-pc-windows-msvc"
    return f"{arch}-unknown-linux-gnu"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle OmniDesk Python engine as a Tauri sidecar.")
    parser.add_argument("--target", help="Explicit Rust target triple (e.g. aarch64-apple-darwin)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"
    entry_script = backend_dir / "omnidesk_engine" / "sidecar_entry.py"
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)

    target_triple = args.target or detect_rust_target_triple()
    ext = ".exe" if "windows" in target_triple else ""
    output_name = f"omnidesk-engine-{target_triple}"
    final_binary = binaries_dir / f"{output_name}{ext}"

    venv_py = (
        backend_dir / ".venv" / "Scripts" / "python.exe"
        if platform.system() == "Windows"
        else backend_dir / ".venv" / "bin" / "python"
    )
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    build_dir = repo_root / "build" / "sidecar"
    dist_dir = build_dir / "dist"
    work_dir = build_dir / "work"
    spec_dir = build_dir / "spec"
    build_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        python_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        output_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(backend_dir),
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "keyring.backends.macOS",
        "--hidden-import",
        "keyring.backends.Windows",
        "--hidden-import",
        "keyring.backends.SecretService",
        str(entry_script),
    ]

    print(f"Building sidecar binary for {target_triple} using {python_exe}...")
    subprocess.run(cmd, cwd=str(backend_dir), check=True, env={**os.environ, "PYTHONPATH": str(backend_dir)})

    built_artifact = dist_dir / f"{output_name}{ext}"
    if not built_artifact.exists():
        raise FileNotFoundError(f"Expected PyInstaller artifact missing: {built_artifact}")

    shutil.copy2(built_artifact, final_binary)
    if ext == "":
        final_binary.chmod(0o755)

    print(f"Bundled sidecar ready at: {final_binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
