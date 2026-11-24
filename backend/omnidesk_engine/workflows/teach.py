from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from omnidesk_engine.automation import desktop_control
from omnidesk_engine.db import Database
from omnidesk_engine.schemas import (
    RecordTeachStepRequest,
    StartTeachRequest,
    TeachEvent,
    TeachSession,
    TeachVariable,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowVariable,
    utc_now_iso,
)
from omnidesk_engine.security.policy import redact_sensitive_text, validate_scoped_directory

SECRET_FIELD_HINTS = (
    "password",
    "passwd",
    "passcode",
    "otp",
    "2fa",
    "secret",
    "api_key",
    "token",
    "ssn",
    "cvv",
    "payment",
    "credit card",
)


class TeachModeEngine:
    """Explicit user-initiated demonstration recorder supporting authorized external app & folder observation.

    Never records silently, never captures passwords or secure input fields, and prefers semantic selectors.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self._observer_tasks: dict[str, asyncio.Task[None]] = {}

    def start_session(self, req: StartTeachRequest) -> TeachSession:
        ax_ok = desktop_control.macos_accessibility_trusted()
        note_parts = []
        if req.scope_app:
            note_parts.append(f"Scoped to external app '{req.scope_app}'.")
        else:
            note_parts.append("Observing permitted external app transitions.")
        if req.scope_directory:
            note_parts.append(f"Watching scoped folder '{req.scope_directory}' for file actions.")
        if not ax_ok:
            note_parts.append(
                "Grant macOS Accessibility permission to also observe fine-grained window titles and UI elements."
            )

        session = TeachSession(
            id=f"tch-{uuid.uuid4().hex[:10]}",
            name=req.name.strip(),
            status="recording",
            started_at=utc_now_iso(),
            scope_app=req.scope_app.strip() if req.scope_app else None,
            scope_directory=req.scope_directory.strip() if req.scope_directory else None,
            observer_active=req.enable_live_observer,
            observer_note=" ".join(note_parts),
        )
        self.db.save_teach_session(session)
        self.db.add_audit(
            "teach_mode",
            "start_recording",
            f"User started Teach Mode session '{session.name}' (scope_app={session.scope_app or 'any'}).",
        )
        if req.enable_live_observer:
            try:
                loop = asyncio.get_running_loop()
                self._observer_tasks[session.id] = loop.create_task(
                    self._observe_external_loop(session.id)
                )
            except RuntimeError:
                pass
        return session

    async def _observe_external_loop(self, session_id: str) -> None:
        """Polls permitted OS frontmost app transitions & scoped folder file changes at a low 1.5s cadence."""
        last_app = ""
        last_title = ""
        known_files: set[str] | None = None

        session = self.db.get_teach_session(session_id)
        if session and session.scope_directory:
            try:
                scoped_dir = validate_scoped_directory(session.scope_directory)
                known_files = {p.name for p in scoped_dir.iterdir() if not p.name.startswith(".")}
            except Exception:
                known_files = None

        try:
            while True:
                await asyncio.sleep(1.5)
                current = self.db.get_teach_session(session_id)
                if not current or current.status != "recording":
                    break

                settings = self.db.get_settings()
                front = await asyncio.to_thread(desktop_control.get_frontmost_application)
                app_name = str(front.get("app_name") or "")
                win_title = str(front.get("window_title") or "")

                # Ignore OmniDesk itself when observing external desktop interactions.
                if app_name and app_name.lower() not in ("omnidesk", "unknown"):
                    scope_ok = not current.scope_app or current.scope_app.lower() in app_name.lower()
                    if scope_ok and (app_name != last_app or (front.get("accessibility_granted") and win_title != last_title)):
                        last_app = app_name
                        last_title = win_title
                        sensitive = desktop_control.is_excluded_or_sensitive(
                            app_name, win_title, settings.excluded_apps
                        )
                        if sensitive:
                            self.record_step(
                                session_id,
                                RecordTeachStepRequest(
                                    kind="ui_semantic_click",
                                    summary="Sensitive application or login window skipped",
                                    selector="redacted://sensitive-window",
                                    app_name=app_name,
                                    parameters={},
                                    is_secure_field=True,
                                ),
                            )
                        else:
                            title_suffix = (
                                f" ({win_title[:48]})"
                                if front.get("accessibility_granted") and win_title
                                else ""
                            )
                            self.record_step(
                                session_id,
                                RecordTeachStepRequest(
                                    kind="app_focus",
                                    summary=f"Switch to external app '{app_name}'{title_suffix}",
                                    selector=f"ax://application[@name='{app_name}']",
                                    app_name=app_name,
                                    parameters={"app_name": app_name},
                                ),
                            )

                # Observe real file creations inside user's explicitly scoped folder.
                if current.scope_directory and known_files is not None:
                    try:
                        scoped_dir = validate_scoped_directory(current.scope_directory)
                        now_files = {p.name for p in scoped_dir.iterdir() if not p.name.startswith(".")}
                        added = sorted(now_files - known_files)
                        known_files = now_files
                        for fname in added[:5]:
                            self.record_step(
                                session_id,
                                RecordTeachStepRequest(
                                    kind="file_action",
                                    summary=f"Detected new file '{fname}' in scoped folder",
                                    selector=f"fs://file[@name='{fname}']",
                                    parameters={
                                        "operation": "inspect",
                                        "directory": str(scoped_dir),
                                        "file_name": fname,
                                    },
                                ),
                            )
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        finally:
            self._observer_tasks.pop(session_id, None)

    def stop_all_observers(self) -> None:
        for sid, task in list(self._observer_tasks.items()):
            task.cancel()
            sess = self.db.get_teach_session(sid)
            if sess and sess.status == "recording":
                sess.status = "stopped"
                sess.observer_active = False
                sess.stopped_at = utc_now_iso()
                self.db.save_teach_session(sess)
        self._observer_tasks.clear()

    def record_step(self, session_id: str, req: RecordTeachStepRequest) -> TeachSession:
        session = self.db.get_teach_session(session_id)
        if not session:
            raise KeyError("Teach Mode session not found.")
        if session.status != "recording":
            raise ValueError("Teach Mode session is not currently recording.")

        settings = self.db.get_settings()
        is_excluded_app = bool(
            req.app_name and any(ex.lower() in req.app_name.lower() for ex in settings.excluded_apps)
        )
        lower_text = f"{req.summary} {req.selector}".lower()
        looks_secret = (
            req.is_secure_field
            or is_excluded_app
            or any(h in lower_text for h in SECRET_FIELD_HINTS)
        )

        if looks_secret:
            event = TeachEvent(
                id=f"evt-{uuid.uuid4().hex[:8]}",
                kind="redacted_secret",
                summary="Sensitive or secure field skipped automatically by Teach Mode privacy filter.",
                selector="redacted://secure-field",
                app_name=None,
                parameters={},
                redacted=True,
            )
            self.db.add_audit(
                "teach_mode", "redacted_step", "Skipped sensitive field during Teach Mode recording."
            )
        else:
            clean_params = {
                k: redact_sensitive_text(str(v)) if isinstance(v, str) else v
                for k, v in req.parameters.items()
            }
            event = TeachEvent(
                id=f"evt-{uuid.uuid4().hex[:8]}",
                kind=req.kind,
                summary=redact_sensitive_text(req.summary),
                selector=req.selector,
                app_name=req.app_name,
                parameters=clean_params,
                redacted=False,
            )

        session.events.append(event)
        self.db.save_teach_session(session)
        return session

    def delete_step(self, session_id: str, event_id: str) -> TeachSession:
        session = self.db.get_teach_session(session_id)
        if not session:
            raise KeyError("Teach Mode session not found.")
        session.events = [e for e in session.events if e.id != event_id]
        session.extracted_variables = self._extract_variables(session.events)
        self.db.save_teach_session(session)
        return session

    def capture_active_app_step(self, session_id: str) -> TeachSession:
        ctx = desktop_control.get_frontmost_application()
        app_name = ctx.get("app_name", "Unknown")
        return self.record_step(
            session_id,
            RecordTeachStepRequest(
                kind="app_focus",
                summary=f"Switch to application '{app_name}'",
                selector=f"ax://application[@name='{app_name}']",
                app_name=app_name,
                parameters={"app_name": app_name},
            ),
        )

    def stop_session(self, session_id: str) -> TeachSession:
        task = self._observer_tasks.pop(session_id, None)
        if task:
            task.cancel()
        session = self.db.get_teach_session(session_id)
        if not session:
            raise KeyError("Teach Mode session not found.")
        session.status = "stopped"
        session.observer_active = False
        session.stopped_at = utc_now_iso()
        session.extracted_variables = self._extract_variables(session.events)
        self.db.save_teach_session(session)
        self.db.add_audit(
            "teach_mode",
            "stop_recording",
            f"Stopped Teach Mode '{session.name}' with {len(session.events)} step(s).",
        )
        return session

    def _extract_variables(self, events: list[TeachEvent]) -> list[TeachVariable]:
        found: dict[str, TeachVariable] = {}
        for evt in events:
            if evt.redacted:
                continue
            if "directory" in evt.parameters and "target_directory" not in found:
                found["target_directory"] = TeachVariable(
                    name="target_directory",
                    sample_value=str(evt.parameters["directory"]),
                    description="Directory path parameterized from demonstration.",
                )
            if "url" in evt.parameters and "target_url" not in found:
                found["target_url"] = TeachVariable(
                    name="target_url",
                    sample_value=str(evt.parameters["url"]),
                    description="Webpage URL parameterized from demonstration.",
                )
            if "report_filename" in evt.parameters and "report_filename" not in found:
                found["report_filename"] = TeachVariable(
                    name="report_filename",
                    sample_value=str(evt.parameters["report_filename"]),
                    description="Report output filename.",
                )
            if "app_name" in evt.parameters and "app_name" not in found:
                found["app_name"] = TeachVariable(
                    name="app_name",
                    sample_value=str(evt.parameters["app_name"]),
                    description="Native external application target.",
                )
        return list(found.values())

    def convert_to_workflow(
        self, session_id: str, workflow_name: str | None = None
    ) -> WorkflowDefinition:
        session = self.db.get_teach_session(session_id)
        if not session:
            raise KeyError("Teach Mode session not found.")
        if session.status == "recording":
            session = self.stop_session(session_id)

        usable = [e for e in session.events if not e.redacted]
        if not usable:
            raise ValueError("No recordable non-sensitive steps were captured in this session.")

        nodes: list[WorkflowNode] = [
            WorkflowNode(
                id="t-start",
                type="trigger",
                label="Manual / Reusable Trigger",
                x=60,
                y=120,
                config={"source_session": session.id},
            )
        ]
        edges: list[WorkflowEdge] = []
        prev_id = "t-start"
        x_cursor = 300.0
        y_cursor = 120.0

        for idx, evt in enumerate(usable):
            tool, config = self._event_to_tool_and_config(evt)
            needs_gate = tool in (
                "filesystem.apply_organization",
                "spreadsheet.generate_report",
                "browser.navigate_and_extract",
                "apps.launch",
                "apps.open_document",
            )
            if needs_gate:
                gate_id = f"t-gate-{idx}"
                nodes.append(
                    WorkflowNode(
                        id=gate_id,
                        type="approval",
                        label=f"Approve: {evt.summary[:30]}",
                        x=x_cursor,
                        y=y_cursor,
                        config={"require_explicit_approval": True},
                    )
                )
                edges.append(
                    WorkflowEdge(id=f"te-{prev_id}-{gate_id}", source=prev_id, target=gate_id)
                )
                prev_id = gate_id
                x_cursor += 250.0
                if x_cursor > 860:
                    x_cursor = 300.0
                    y_cursor += 150.0

            nid = f"t-act-{idx}"
            nodes.append(
                WorkflowNode(
                    id=nid,
                    type="action",
                    label=evt.summary[:56],
                    tool=tool,
                    x=x_cursor,
                    y=y_cursor,
                    config=config,
                )
            )
            edges.append(WorkflowEdge(id=f"te-{prev_id}-{nid}", source=prev_id, target=nid))
            prev_id = nid
            x_cursor += 250.0
            if x_cursor > 860:
                x_cursor = 300.0
                y_cursor += 150.0

        wf = WorkflowDefinition(
            id=f"wf-teach-{uuid.uuid4().hex[:8]}",
            name=(workflow_name or session.name).strip(),
            description=f"Synthesized from Teach Mode demonstration '{session.name}' ({len(usable)} semantic step(s)).",
            version=1,
            source="teach_mode",
            variables=[
                WorkflowVariable(
                    name=v.name,
                    default_value=v.sample_value,
                    description=v.description,
                )
                for v in session.extracted_variables
            ],
            max_loop_iterations=25,
            nodes=nodes,
            edges=edges,
        )
        self.db.save_workflow(wf)
        session.status = "converted"
        session.workflow_id = wf.id
        self.db.save_teach_session(session)
        self.db.add_audit(
            "teach_mode", "converted_workflow", f"Created workflow '{wf.name}' ({wf.id})."
        )
        return wf

    def _event_to_tool_and_config(self, evt: TeachEvent) -> tuple[str, dict[str, Any]]:
        if evt.kind == "file_action":
            op = str(evt.parameters.get("operation", "inspect"))
            directory = (
                "{{target_directory}}"
                if "directory" in evt.parameters
                else str(evt.parameters.get("directory", "~/Downloads"))
            )
            if op == "plan":
                return "filesystem.plan_organization", {"directory": directory}
            if op == "organize":
                return "filesystem.apply_organization", {"directory": directory}
            if op == "search":
                return "filesystem.search_documents", {
                    "directory": directory,
                    "query": str(evt.parameters.get("query", "")),
                }
            return "filesystem.inspect_directory", {"directory": directory}

        if evt.kind == "report_export":
            return "spreadsheet.generate_report", {
                "directory": "{{target_directory}}",
                "report_filename": (
                    "{{report_filename}}"
                    if "report_filename" in evt.parameters
                    else "OmniDesk_Teach_Report.xlsx"
                ),
            }

        if evt.kind == "browser_navigation":
            return "browser.navigate_and_extract", {"url": "{{target_url}}"}

        if evt.kind == "app_focus":
            return "apps.launch", {"app_name": "{{app_name}}"}

        return "filesystem.inspect_directory", {"directory": "{{target_directory}}"}
