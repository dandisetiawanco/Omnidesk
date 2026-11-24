from __future__ import annotations

import uuid
from typing import Any

from omnidesk_engine.automation.apps import get_active_window_context
from omnidesk_engine.db import Database
from omnidesk_engine.schemas import (
    RecordTeachStepRequest,
    TeachEvent,
    TeachSession,
    TeachVariable,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowVariable,
    utc_now_iso,
)
from omnidesk_engine.security.policy import redact_sensitive_text

SECRET_FIELD_HINTS = ("password", "passwd", "passcode", "otp", "2fa", "secret", "api_key", "token", "ssn", "cvv")


class TeachModeEngine:
    """Explicit user-initiated demonstration recorder that synthesizes parameterized workflows.

    Never records silently, never captures passwords or secure input fields, and prefers semantic selectors.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def start_session(self, name: str) -> TeachSession:
        session = TeachSession(
            id=f"tch-{uuid.uuid4().hex[:10]}",
            name=name.strip(),
            status="recording",
            started_at=utc_now_iso(),
        )
        self.db.save_teach_session(session)
        self.db.add_audit("teach_mode", "start_recording", f"User started Teach Mode session '{session.name}'.")
        return session

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
        looks_secret = req.is_secure_field or is_excluded_app or any(h in lower_text for h in SECRET_FIELD_HINTS)

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
            self.db.add_audit("teach_mode", "redacted_step", "Skipped sensitive field during Teach Mode recording.")
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

    def capture_active_app_step(self, session_id: str) -> TeachSession:
        ctx = get_active_window_context()
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
        session = self.db.get_teach_session(session_id)
        if not session:
            raise KeyError("Teach Mode session not found.")
        session.status = "stopped"
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
                    description="Native application target.",
                )
        return list(found.values())

    def convert_to_workflow(self, session_id: str, workflow_name: str | None = None) -> WorkflowDefinition:
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
                edges.append(WorkflowEdge(id=f"te-{prev_id}-{gate_id}", source=prev_id, target=gate_id))
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
        self.db.add_audit("teach_mode", "converted_workflow", f"Created workflow '{wf.name}' ({wf.id}).")
        return wf

    def _event_to_tool_and_config(self, evt: TeachEvent) -> tuple[str, dict[str, Any]]:
        if evt.kind == "file_action":
            op = str(evt.parameters.get("operation", "inspect"))
            directory = "{{target_directory}}" if "directory" in evt.parameters else str(evt.parameters.get("directory", "~/Downloads"))
            if op == "plan":
                return "filesystem.plan_organization", {"directory": directory}
            if op == "organize":
                return "filesystem.apply_organization", {"directory": directory}
            if op == "search":
                return "filesystem.search_documents", {"directory": directory, "query": str(evt.parameters.get("query", ""))}
            return "filesystem.inspect_directory", {"directory": directory}

        if evt.kind == "report_export":
            return "spreadsheet.generate_report", {
                "directory": "{{target_directory}}",
                "report_filename": "{{report_filename}}" if "report_filename" in evt.parameters else "OmniDesk_Teach_Report.xlsx",
            }

        if evt.kind == "browser_navigation":
            return "browser.navigate_and_extract", {"url": "{{target_url}}"}

        if evt.kind == "app_focus":
            return "apps.launch", {"app_name": "{{app_name}}"}

        return "filesystem.inspect_directory", {"directory": "{{target_directory}}"}
