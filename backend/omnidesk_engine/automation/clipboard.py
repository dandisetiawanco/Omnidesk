from __future__ import annotations

import platform
import subprocess
from typing import Any

from omnidesk_engine.security.policy import redact_sensitive_text


def read_clipboard() -> dict[str, Any]:
    system = platform.system()
    if system == "Darwin":
        proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        text = proc.stdout
    elif system == "Windows":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        text = proc.stdout
    else:
        text = ""
        for cmd in (["wl-paste", "--no-newline"], ["xclip", "-o", "-selection", "clipboard"]):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    text = proc.stdout
                    break
            except FileNotFoundError:
                continue
    return {
        "length": len(text),
        "preview": redact_sensitive_text(text[:500]),
    }


def write_clipboard(text: str) -> dict[str, Any]:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["pbcopy"], input=text, text=True, check=True, timeout=5)
    elif system == "Windows":
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            check=True,
            timeout=5,
        )
    else:
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            try:
                subprocess.run(cmd, input=text, text=True, check=True, timeout=5)
                break
            except FileNotFoundError:
                continue
    return {"written_chars": len(text)}
