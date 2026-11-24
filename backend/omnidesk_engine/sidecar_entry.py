from __future__ import annotations

import sys

import uvicorn

from omnidesk_engine.main import create_app


def main() -> None:
    app = create_app()
    cfg = app.state.config
    print(f"OmniDesk Sidecar Engine listening on http://{cfg.host}:{cfg.port}", file=sys.stderr)
    uvicorn.run(
        app,
        host=cfg.host,
        port=cfg.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
