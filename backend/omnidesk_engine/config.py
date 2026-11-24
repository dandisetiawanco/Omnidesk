from __future__ import annotations

import os
import platform
import secrets
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    env_dir = os.environ.get("OMNIDESK_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "OmniDesk"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "OmniDesk"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / "omnidesk"


@dataclass(frozen=True)
class EngineConfig:
    host: str
    port: int
    session_token: str
    data_dir: Path
    db_path: Path
    max_task_steps: int = 25
    max_workflow_loops: int = 100
    step_timeout_seconds: float = 90.0
    max_tasks_per_minute: int = 20

    @classmethod
    def from_env(cls) -> "EngineConfig":
        data_dir = default_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        token = os.environ.get("OMNIDESK_SESSION_TOKEN", "").strip()
        if len(token) < 24:
            token = secrets.token_hex(32)
        port = int(os.environ.get("OMNIDESK_PORT", "17420"))
        # Always bind loopback only; never expose an unauthenticated LAN socket.
        host = "127.0.0.1"
        return cls(
            host=host,
            port=port,
            session_token=token,
            data_dir=data_dir,
            db_path=data_dir / "omnidesk.db",
        )
