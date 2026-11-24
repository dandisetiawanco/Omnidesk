from __future__ import annotations

import uuid
from typing import Any

from omnidesk_engine.db import Database
from omnidesk_engine.intelligence.orchestrator import TaskOrchestrator
from omnidesk_engine.schemas import (
    ActionStep,
    TaskRun,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowVariable,
)
from omnidesk_engine.security.policy import get_tool_policy


def seed_default_workflows(db: Database) -> None:
    if db.list_workflows():
        return

    flagship = WorkflowDefinition(
        id="wf-flagship-organize",
        name="Organize Folder & Export Excel Report",
        description="Inspects a scoped folder, detects SHA-256 duplicates, requests approval before moving files into categories, and writes an Excel report with zero deletions.",
        version=1,
        source="template",
        variables=[
            WorkflowVariable(
                name="target_directory",
                default_value="~/Downloads",
                description="Scoped folder to inspect and organize.",
            ),
            WorkflowVariable(
                name="report_filename",
                default_value="OmniDesk_Organization_Report.xlsx",
                description="Output Excel workbook filename.",
            ),
        ],
        max_loop_iterations=25,
        nodes=[
            WorkflowNode(
                id="n1",
                type="trigger",
                label="Manual Command Trigger",
                x=60,
                y=120,
                config={"trigger": "manual"},
            ),
            WorkflowNode(
                id="n2",
                type="action",
                label="Inspect Directory & SHA-256 Duplicates",
                tool="filesystem.inspect_directory",
                x=310,
                y=120,
                config={"directory": "{{target_directory}}"},
            ),
            WorkflowNode(
                id="n3",
                type="action",
                label="Build Dry-Run Organization Plan",
                tool="filesystem.plan_organization",
                x=580,
                y=120,
                config={"directory": "{{target_directory}}"},
            ),
            WorkflowNode(
                id="n4",
                type="approval",
                label="Human Approval Gate",
                x=840,
                y=120,
                config={"require_explicit_approval": True},
            ),
            WorkflowNode(
                id="n5",
                type="action",
                label="Apply Category Moves (Journaled)",
                tool="filesystem.apply_organization",
                x=580,
                y=270,
                config={"directory": "{{target_directory}}"},
            ),
            WorkflowNode(
                id="n6",
                type="action",
                label="Export Excel Report (.xlsx)",
                tool="spreadsheet.generate_report",
                x=840,
                y=270,
                config={
                    "directory": "{{target_directory}}",
                    "report_filename": "{{report_filename}}",
                },
            ),
            WorkflowNode(
                id="n7",
                type="error_handler",
                label="Preserve Original Files on Error",
                x=310,
                y=270,
                config={"strategy": "halt_and_offer_rollback"},
            ),
        ],
        edges=[
            WorkflowEdge(id="e1", source="n1", target="n2"),
            WorkflowEdge(id="e2", source="n2", target="n3"),
            WorkflowEdge(id="e3", source="n3", target="n4"),
            WorkflowEdge(id="e4", source="n4", target="n5", label="Approved"),
            WorkflowEdge(id="e5", source="n5", target="n6"),
            WorkflowEdge(id="e6", source="n5", target="n7", label="On Error"),
        ],
    )

    web_research = WorkflowDefinition(
        id="wf-web-research",
        name="Extract Webpage & Save Summary",
        description="Navigates to an approved URL with Playwright Chromium, extracts structured content with prompt-injection isolation, and saves a Markdown summary.",
        version=1,
        source="template",
        variables=[
            WorkflowVariable(
                name="target_url",
                default_value="https://example.com",
                description="Approved HTTP/HTTPS webpage URL.",
            ),
            WorkflowVariable(
                name="output_directory",
                default_value="~/Documents",
                description="Scoped folder for the summary report.",
            ),
        ],
        max_loop_iterations=10,
        nodes=[
            WorkflowNode(id="w1", type="trigger", label="Manual Trigger", x=60, y=130, config={}),
            WorkflowNode(id="w2", type="approval", label="Approve External URL", x=300, y=130, config={}),
            WorkflowNode(
                id="w3",
                type="action",
                label="Navigate & Extract DOM",
                tool="browser.navigate_and_extract",
                x=550,
                y=130,
                config={"url": "{{target_url}}"},
            ),
            WorkflowNode(
                id="w4",
                type="action",
                label="Save Markdown Summary",
                tool="documents.generate_summary",
                x=800,
                y=130,
                config={"directory": "{{output_directory}}", "title": "Webpage Extract"},
            ),
        ],
        edges=[
            WorkflowEdge(id="we1", source="w1", target="w2"),
            WorkflowEdge(id="we2", source="w2", target="w3", label="Approved"),
            WorkflowEdge(id="we3", source="w3", target="w4"),
        ],
    )

    db.save_workflow(flagship)
    db.save_workflow(web_research)


def _interpolate(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for k, v in variables.items():
            out = out.replace(f"{{{{{k}}}}}", v)
        return out
    if isinstance(value, dict):
        return {k: _interpolate(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, variables) for v in value]
    return value


class WorkflowRunner:
    """Compiles a versioned workflow graph into policy-checked ActionSteps and executes via TaskOrchestrator."""

    def __init__(self, db: Database, orchestrator: TaskOrchestrator) -> None:
        self.db = db
        self.orchestrator = orchestrator

    async def run_workflow(
        self,
        workflow_id: str,
        variable_overrides: dict[str, str],
        dry_run: bool = False,
    ) -> TaskRun:
        wf = self.db.get_workflow(workflow_id)
        if not wf:
            raise KeyError(f"Workflow '{workflow_id}' not found.")

        resolved_vars = {v.name: v.default_value for v in wf.variables}
        resolved_vars.update({k: v for k, v in variable_overrides.items() if v is not None and v != ""})

        # Walk graph edges in topological / sequence order with cycle guard.
        node_map = {n.id: n for n in wf.nodes}
        outgoing: dict[str, list[str]] = {}
        incoming_count: dict[str, int] = {n.id: 0 for n in wf.nodes}
        for edge in wf.edges:
            if edge.label == "On Error":
                continue
            outgoing.setdefault(edge.source, []).append(edge.target)
            if edge.target in incoming_count:
                incoming_count[edge.target] += 1

        ordered: list[WorkflowNode] = []
        queue = [n.id for n in wf.nodes if incoming_count.get(n.id, 0) == 0]
        visited: set[str] = set()
        while queue and len(visited) < wf.max_loop_iterations:
            nid = queue.pop(0)
            if nid in visited or nid not in node_map:
                continue
            visited.add(nid)
            ordered.append(node_map[nid])
            for nxt in outgoing.get(nid, []):
                if nxt not in visited:
                    queue.append(nxt)

        for n in wf.nodes:
            if n.id not in visited and n.type == "action":
                ordered.append(n)

        steps: list[ActionStep] = []
        pending_approval_gate = False
        target_scope: str | None = resolved_vars.get("target_directory") or resolved_vars.get("output_directory")

        for node in ordered:
            if node.type == "approval":
                pending_approval_gate = True
                continue
            if node.type != "action" or not node.tool:
                continue
            if dry_run and node.tool in ("filesystem.apply_organization", "spreadsheet.generate_report", "documents.generate_summary"):
                continue
            policy = get_tool_policy(node.tool)
            params = _interpolate(node.config, resolved_vars)
            steps.append(
                ActionStep(
                    id=f"stp-{uuid.uuid4().hex[:8]}",
                    index=len(steps),
                    title=node.label,
                    tool=node.tool,
                    risk=policy.risk,
                    requires_approval=policy.requires_approval or pending_approval_gate,
                    reversible=policy.reversible,
                    parameters=params,
                )
            )
            pending_approval_gate = False

        if not steps:
            raise ValueError("Workflow contains no executable action steps.")

        return await self.orchestrator.start_preplanned_task(
            prompt=f"Run workflow '{wf.name}' (v{wf.version})" + (" [dry-run]" if dry_run else ""),
            title=wf.name + (" (Dry-Run)" if dry_run else ""),
            steps=steps,
            planner_source=f"workflow:{wf.id}:v{wf.version}",
            target_scope=target_scope,
        )
