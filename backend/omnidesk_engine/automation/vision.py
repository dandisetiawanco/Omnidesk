from __future__ import annotations

import base64
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from omnidesk_engine.automation.apps import get_active_window_context


def capture_opt_in_snapshot(excluded_apps: list[str]) -> dict[str, Any]:
    """Captures a single user-authorized desktop snapshot while enforcing excluded app privacy."""
    ctx = get_active_window_context()
    active_app = ctx.get("app_name", "Unknown")

    if any(ex.lower() in active_app.lower() for ex in excluded_apps):
        return {
            "captured": False,
            "blocked_by_privacy": True,
            "active_window": ctx,
            "message": f"Capture skipped because '{active_app}' is in your excluded sensitive applications list.",
            "image_data_url": None,
        }

    system = platform.system()
    if system == "Darwin":
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            proc = subprocess.run(
                ["screencapture", "-x", "-t", "png", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
                return {
                    "captured": False,
                    "blocked_by_privacy": False,
                    "active_window": ctx,
                    "message": "macOS Screen Recording permission is required for Live Workspace previews.",
                    "image_data_url": None,
                }
            # Resize snapshot to stay memory-conscious on 8 GB Intel systems.
            from PIL import Image

            with Image.open(tmp_path) as img:
                img.thumbnail((1280, 800))
                out_path = tmp_path.with_suffix(".jpg")
                img.convert("RGB").save(out_path, format="JPEG", quality=76)
                encoded = base64.b64encode(out_path.read_bytes()).decode("ascii")
                width, height = img.size
                out_path.unlink(missing_ok=True)
            return {
                "captured": True,
                "blocked_by_privacy": False,
                "active_window": ctx,
                "width": width,
                "height": height,
                "message": "Captured single opt-in desktop snapshot.",
                "image_data_url": f"data:image/jpeg;base64,{encoded}",
            }
        finally:
            tmp_path.unlink(missing_ok=True)

    return {
        "captured": False,
        "blocked_by_privacy": False,
        "active_window": ctx,
        "message": f"Single-shot screen capture on {system} requires OS portal authorization.",
        "image_data_url": None,
    }
