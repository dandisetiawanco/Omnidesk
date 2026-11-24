from __future__ import annotations

import platform
import re
import subprocess
from typing import Any

SAFE_APP_NAME_RE = re.compile(r"^[A-Za-z0-9 ._+-]{1,80}$")


def validate_app_name(app_name: str) -> str:
    clean = app_name.strip()
    if not SAFE_APP_NAME_RE.match(clean) or ".." in clean:
        raise ValueError(f"Application name '{app_name}' contains disallowed characters.")
    return clean


def launch_application(app_name: str) -> dict[str, Any]:
    clean = validate_app_name(app_name)
    system = platform.system()

    if system == "Darwin":
        proc = subprocess.run(["open", "-a", clean], capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"macOS could not open '{clean}'.")
        return {"app_name": clean, "platform": "macOS", "launched": True}

    if system == "Windows":
        proc = subprocess.run(["explorer.exe", clean], capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"Windows could not launch '{clean}'.")
        return {"app_name": clean, "platform": "Windows", "launched": True}

    for launcher in ("gtk-launch", "xdg-open"):
        try:
            proc = subprocess.run([launcher, clean], capture_output=True, text=True, timeout=15)
            if proc.returncode == 0:
                return {"app_name": clean, "platform": "Linux", "launched": True}
        except FileNotFoundError:
            continue
    raise RuntimeError(f"Linux desktop launcher could not open '{clean}'.")


def get_active_window_context() -> dict[str, Any]:
    system = platform.system()
    if system == "Darwin":
        try:
            proc = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of first application process whose frontmost is true',
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {
                    "platform": "macOS",
                    "app_name": proc.stdout.strip(),
                    "status": "ok",
                    "note": "Queried on demand via System Events.",
                }
            return {
                "platform": "macOS",
                "app_name": "Permission required",
                "status": "permission_required",
                "note": "Authorize Automation / Accessibility in macOS System Settings.",
            }
        except Exception as exc:
            return {
                "platform": "macOS",
                "app_name": "Unavailable",
                "status": "error",
                "note": str(exc),
            }

    if system == "Linux":
        import os

        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return {
                "platform": "Linux (Wayland)",
                "app_name": "Isolated by Wayland compositor",
                "status": "unsupported",
                "note": "Wayland restricts global window queries without a compositor portal.",
            }
        return {
            "platform": "Linux (X11)",
            "app_name": "X11 desktop session",
            "status": "experimental",
            "note": "Use AT-SPI or xdotool when installed.",
        }

    return {
        "platform": system,
        "app_name": "Active desktop window",
        "status": "experimental",
        "note": "Windows UIA foreground inspection requires Windows host runtime.",
    }
