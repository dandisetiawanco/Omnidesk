from __future__ import annotations

import asyncio
import hmac
import json
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from omnidesk_engine import __version__
from omnidesk_engine.automation import apps, capabilities, vision
from omnidesk_engine.config import EngineConfig
from omnidesk_engine.db import Database
from omnidesk_engine.intelligence.orchestrator import TaskOrchestrator, create_flagship_demo_sandbox
from omnidesk_engine.intelligence.planner import TaskPlanner
from omnidesk_engine.mcp.server import handle_mcp_rpc, list_mcp_tools
from omnidesk_engine.providers.registry import ProviderRegistry
from omnidesk_engine.schemas import (
    AppSettings,
    ApprovalDecisionRequest,
    CreateTaskRequest,
    ProviderConfigUpdate,
    RecordTeachStepRequest,
    RunWorkflowRequest,
    StartTeachRequest,
    WorkflowDefinition,
)
from omnidesk_engine.security.credentials import CredentialVault
from omnidesk_engine.security.journal import rollback_task_operations
from omnidesk_engine.workflows.engine import WorkflowRunner, seed_default_workflows
from omnidesk_engine.workflows.teach import TeachModeEngine


def create_app(config: EngineConfig | None = None) -> FastAPI:
    cfg = config or EngineConfig.from_env()
    db = Database(cfg.db_path)
    seed_default_workflows(db)
    vault = CredentialVault()
    providers = ProviderRegistry(db, vault)
    planner = TaskPlanner(providers)
    orchestrator = TaskOrchestrator(cfg, db, planner)
    workflow_runner = WorkflowRunner(db, orchestrator)
    teach_engine = TeachModeEngine(db)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        orchestrator.emergency_stop_all()

    api = FastAPI(
        title="OmniDesk Local Engine",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Strictly restrict origins to Tauri webview and loopback Vite dev server.
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "http://127.0.0.1:1420",
            "http://localhost:1420",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing session authorization token.",
            )
        provided = authorization[7:].strip()
        if not hmac.compare_digest(provided, cfg.session_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session authorization token.",
            )

    @api.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    # --- System & Capabilities ---
    @api.get("/api/system/profile", dependencies=[Depends(require_auth)])
    async def system_profile() -> dict[str, Any]:
        return capabilities.collect_system_profile(vault).model_dump()

    @api.get("/api/system/active-window", dependencies=[Depends(require_auth)])
    async def active_window() -> dict[str, Any]:
        return await asyncio.to_thread(apps.get_active_window_context)

    @api.post("/api/live/snapshot", dependencies=[Depends(require_auth)])
    async def capture_live_snapshot() -> dict[str, Any]:
        settings = db.get_settings()
        db.add_audit("live_workspace", "snapshot_requested", "User triggered single opt-in desktop snapshot.")
        return await asyncio.to_thread(vision.capture_opt_in_snapshot, settings.excluded_apps)

    # --- Settings ---
    @api.get("/api/settings", dependencies=[Depends(require_auth)])
    async def get_settings() -> dict[str, Any]:
        return db.get_settings().model_dump()

    @api.put("/api/settings", dependencies=[Depends(require_auth)])
    async def put_settings(payload: AppSettings) -> dict[str, Any]:
        saved = db.save_settings(payload)
        db.add_audit("settings", "updated", f"Privacy mode: {saved.privacy_mode}, theme: {saved.theme}.")
        return saved.model_dump()

    # --- AI Model Providers ---
    @api.get("/api/providers", dependencies=[Depends(require_auth)])
    async def list_providers(probe: bool = False) -> list[dict[str, Any]]:
        items = await providers.list_providers(probe_network=probe)
        return [p.model_dump() for p in items]

    @api.put("/api/providers/{provider_id}", dependencies=[Depends(require_auth)])
    async def update_provider(provider_id: str, payload: ProviderConfigUpdate) -> dict[str, Any]:
        try:
            updated = await providers.update_provider(provider_id, payload)
            return updated.model_dump()
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/providers/{provider_id}/test", dependencies=[Depends(require_auth)])
    async def test_provider(provider_id: str) -> dict[str, Any]:
        items = await providers.list_providers(probe_network=True)
        for item in items:
            if item.id == provider_id:
                return item.model_dump()
        raise HTTPException(status_code=404, detail="Provider not found.")

    # --- Tasks & Execution Engine ---
    @api.get("/api/tasks", dependencies=[Depends(require_auth)])
    async def list_tasks(limit: int = 40) -> list[dict[str, Any]]:
        return [t.model_dump() for t in db.list_tasks(limit=min(limit, 100))]

    @api.get("/api/tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def get_task(task_id: str) -> dict[str, Any]:
        task = db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        return task.model_dump()

    @api.post("/api/tasks", dependencies=[Depends(require_auth)])
    async def create_task(req: CreateTaskRequest) -> dict[str, Any]:
        try:
            task = await orchestrator.start_task(
                prompt=req.prompt,
                target_directory=req.target_directory,
                dry_run_only=req.dry_run_only,
                provider_id=req.provider_id,
            )
            return task.model_dump()
        except (ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/tasks/{task_id}/approve", dependencies=[Depends(require_auth)])
    async def approve_task(task_id: str, req: ApprovalDecisionRequest) -> dict[str, Any]:
        try:
            task = orchestrator.decide_approval(task_id, approved=req.approved, note=req.note)
            return task.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/api/tasks/{task_id}/pause", dependencies=[Depends(require_auth)])
    async def pause_task(task_id: str) -> dict[str, Any]:
        try:
            return orchestrator.pause_task(task_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/tasks/{task_id}/resume", dependencies=[Depends(require_auth)])
    async def resume_task(task_id: str) -> dict[str, Any]:
        try:
            return orchestrator.resume_task(task_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/tasks/{task_id}/cancel", dependencies=[Depends(require_auth)])
    async def cancel_task(task_id: str) -> dict[str, Any]:
        try:
            return orchestrator.cancel_task(task_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/tasks/{task_id}/undo", dependencies=[Depends(require_auth)])
    async def undo_task(task_id: str) -> dict[str, Any]:
        if not db.get_task(task_id):
            raise HTTPException(status_code=404, detail="Task not found.")
        return await asyncio.to_thread(rollback_task_operations, db, task_id)

    @api.delete("/api/tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def delete_task(task_id: str) -> dict[str, Any]:
        deleted = db.delete_task(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"deleted": True, "task_id": task_id}

    @api.post("/api/emergency-stop", dependencies=[Depends(require_auth)])
    async def emergency_stop() -> dict[str, Any]:
        stopped = orchestrator.emergency_stop_all()
        return {"stopped_task_ids": stopped, "count": len(stopped)}

    @api.post("/api/demo/setup-downloads", dependencies=[Depends(require_auth)])
    async def setup_demo() -> dict[str, Any]:
        res = await asyncio.to_thread(create_flagship_demo_sandbox, cfg.data_dir)
        settings = db.get_settings()
        if res["directory"] not in settings.scoped_directories:
            settings.scoped_directories.append(res["directory"])
            db.save_settings(settings)
        db.add_audit("demo", "setup_flagship_sandbox", f"Created reproducible demo folder at {res['directory']}.")
        return res

    @api.get("/api/events/stream", dependencies=[Depends(require_auth)])
    async def stream_events(request: Request) -> StreamingResponse:
        queue = orchestrator.subscribe()

        async def generator() -> AsyncIterator[str]:
            try:
                yield "event: connected\ndata: {\"status\":\"ready\"}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"event: task_update\ndata: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                orchestrator.unsubscribe(queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    # --- Activity & Audit ---
    @api.get("/api/audit", dependencies=[Depends(require_auth)])
    async def list_audit(limit: int = 100) -> list[dict[str, Any]]:
        return [a.model_dump() for a in db.list_audit(limit=min(limit, 200))]

    @api.delete("/api/history", dependencies=[Depends(require_auth)])
    async def clear_history() -> dict[str, Any]:
        count = db.clear_history()
        return {"cleared_tasks": count}

    # --- Workflows ---
    @api.get("/api/workflows", dependencies=[Depends(require_auth)])
    async def list_workflows() -> list[dict[str, Any]]:
        return [w.model_dump() for w in db.list_workflows()]

    @api.post("/api/workflows", dependencies=[Depends(require_auth)])
    async def save_workflow(wf: WorkflowDefinition) -> dict[str, Any]:
        existing = db.get_workflow(wf.id)
        if existing:
            wf.version = existing.version + 1
        saved = db.save_workflow(wf)
        db.add_audit("workflow", "saved", f"Saved workflow '{saved.name}' v{saved.version}.")
        return saved.model_dump()

    @api.delete("/api/workflows/{wf_id}", dependencies=[Depends(require_auth)])
    async def delete_workflow(wf_id: str) -> dict[str, Any]:
        if not db.delete_workflow(wf_id):
            raise HTTPException(status_code=404, detail="Workflow not found.")
        return {"deleted": True, "id": wf_id}

    @api.post("/api/workflows/{wf_id}/run", dependencies=[Depends(require_auth)])
    async def run_workflow(wf_id: str, req: RunWorkflowRequest) -> dict[str, Any]:
        try:
            task = await workflow_runner.run_workflow(wf_id, req.variables, dry_run=req.dry_run)
            return task.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- Teach Mode ---
    @api.get("/api/teach/sessions", dependencies=[Depends(require_auth)])
    async def list_teach_sessions() -> list[dict[str, Any]]:
        return [s.model_dump() for s in db.list_teach_sessions()]

    @api.post("/api/teach/sessions", dependencies=[Depends(require_auth)])
    async def start_teach_session(req: StartTeachRequest) -> dict[str, Any]:
        return teach_engine.start_session(req.name).model_dump()

    @api.post("/api/teach/sessions/{session_id}/step", dependencies=[Depends(require_auth)])
    async def record_teach_step(session_id: str, req: RecordTeachStepRequest) -> dict[str, Any]:
        try:
            return teach_engine.record_step(session_id, req).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/teach/sessions/{session_id}/capture-window", dependencies=[Depends(require_auth)])
    async def capture_teach_window(session_id: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(teach_engine.capture_active_app_step, session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/teach/sessions/{session_id}/stop", dependencies=[Depends(require_auth)])
    async def stop_teach_session(session_id: str) -> dict[str, Any]:
        try:
            return teach_engine.stop_session(session_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/teach/sessions/{session_id}/convert", dependencies=[Depends(require_auth)])
    async def convert_teach_session(session_id: str, name: str | None = None) -> dict[str, Any]:
        try:
            return teach_engine.convert_to_workflow(session_id, workflow_name=name).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- MCP Interoperability ---
    @api.get("/api/mcp/tools", dependencies=[Depends(require_auth)])
    async def mcp_tools() -> list[dict[str, Any]]:
        return list_mcp_tools()

    @api.post("/mcp", dependencies=[Depends(require_auth)])
    async def mcp_rpc(payload: dict[str, Any]) -> dict[str, Any]:
        return await handle_mcp_rpc(payload, db, vault)

    api.state.config = cfg
    return api


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    cfg = app.state.config
    print(f"OmniDesk Engine listening on http://{cfg.host}:{cfg.port}", file=sys.stderr)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
