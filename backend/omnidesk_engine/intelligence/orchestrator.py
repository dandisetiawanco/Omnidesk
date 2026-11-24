from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from omnidesk_engine.automation import (
    apps,
    browser,
    clipboard,
    desktop_control,
    documents,
    filesystem,
    spreadsheet,
    vision,
)
from omnidesk_engine.config import EngineConfig
from omnidesk_engine.db import Database
from omnidesk_engine.intelligence.planner import TaskPlanner
from omnidesk_engine.schemas import (
    ActionStep,
    ApprovalRequest,
    RiskLevel,
    StepStatus,
    TaskArtifact,
    TaskRun,
    TaskStatus,
    utc_now_iso,
)
from omnidesk_engine.security.policy import SlidingWindowRateLimiter, redact_sensitive_text


class _ExecutionRuntime:
    def __init__(self) -> None:
        self.cancel_event = asyncio.Event()
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.approval_event = asyncio.Event()
        self.approval_granted: bool | None = None
        self.bg_task: asyncio.Task[None] | None = None


class TaskOrchestrator:
    """Async execution engine with approval gating, pause/resume, emergency stop, and SSE streaming."""

    def __init__(self, config: EngineConfig, db: Database, planner: TaskPlanner) -> None:
        self.config = config
        self.db = db
        self.planner = planner
        self._runtimes: dict[str, _ExecutionRuntime] = {}
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._rate_limiter = SlidingWindowRateLimiter(config.max_tasks_per_minute, 60.0)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def _broadcast(self, event_type: str, task: TaskRun) -> None:
        payload = {"type": event_type, "task": task.model_dump()}
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def active_task_ids(self) -> list[str]:
        return [
            tid
            for tid, rt in self._runtimes.items()
            if rt.bg_task is not None and not rt.bg_task.done()
        ]

    async def start_task(
        self,
        prompt: str,
        target_directory: str | None = None,
        dry_run_only: bool = False,
        provider_id: str | None = None,
    ) -> TaskRun:
        self._rate_limiter.check_and_record()
        title, steps, source, scope = await self.planner.build_plan(
            prompt=prompt,
            target_directory=target_directory,
            dry_run_only=dry_run_only,
            preferred_provider=provider_id,
        )
        return await self.start_preplanned_task(
            prompt=prompt,
            title=title,
            steps=steps,
            planner_source=source,
            target_scope=scope,
        )

    async def start_preplanned_task(
        self,
        prompt: str,
        title: str,
        steps: list[ActionStep],
        planner_source: str,
        target_scope: str | None = None,
    ) -> TaskRun:
        if len(steps) > self.config.max_task_steps:
            raise ValueError(f"Plan exceeds maximum allowed steps ({self.config.max_task_steps}).")

        task = TaskRun(
            id=f"tsk-{uuid.uuid4().hex[:10]}",
            prompt=redact_sensitive_text(prompt),
            title=title,
            status=TaskStatus.RUNNING,
            planner_source=planner_source,
            target_scope=target_scope,
            steps=steps,
        )
        self.db.save_task(task)
        self.db.add_audit("task", "created", f"Started task '{title}' ({len(steps)} steps).", task_id=task.id)
        self._broadcast("task_created", task)

        rt = _ExecutionRuntime()
        self._runtimes[task.id] = rt
        rt.bg_task = asyncio.create_task(self._run_loop(task.id, rt))
        return task

    def pause_task(self, task_id: str) -> TaskRun:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError("Task not found.")
        rt = self._runtimes.get(task_id)
        if rt and task.status == TaskStatus.RUNNING:
            rt.pause_event.clear()
            task.status = TaskStatus.PAUSED
            self.db.save_task(task)
            self._broadcast("task_paused", task)
        return task

    def resume_task(self, task_id: str) -> TaskRun:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError("Task not found.")
        rt = self._runtimes.get(task_id)
        if rt and task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.RUNNING
            self.db.save_task(task)
            rt.pause_event.set()
            self._broadcast("task_resumed", task)
        return task

    def cancel_task(self, task_id: str, reason: str = "Stopped by user.") -> TaskRun:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError("Task not found.")
        rt = self._runtimes.get(task_id)
        if rt:
            rt.cancel_event.set()
            rt.pause_event.set()
            rt.approval_granted = False
            rt.approval_event.set()
        if task.status in (TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.AWAITING_APPROVAL, TaskStatus.PLANNING):
            task.status = TaskStatus.CANCELLED
            task.error = reason
            task.pending_approval = None
            for st in task.steps:
                if st.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.AWAITING_APPROVAL):
                    st.status = StepStatus.CANCELLED
            self.db.save_task(task)
            self.db.add_audit("control", "cancel_task", reason, task_id=task.id)
            self._broadcast("task_cancelled", task)
        return task

    def emergency_stop_all(self) -> list[str]:
        stopped: list[str] = []
        for tid in list(self._runtimes.keys()):
            task = self.db.get_task(tid)
            if task and task.status in (
                TaskStatus.RUNNING,
                TaskStatus.PAUSED,
                TaskStatus.AWAITING_APPROVAL,
                TaskStatus.PLANNING,
            ):
                self.cancel_task(tid, reason="Emergency stop triggered by user.")
                stopped.append(tid)
        self.db.add_audit("control", "emergency_stop", f"Emergency stop halted {len(stopped)} active task(s).")
        return stopped

    def decide_approval(self, task_id: str, approved: bool, note: str | None = None) -> TaskRun:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError("Task not found.")
        if not task.pending_approval or task.pending_approval.status != "pending":
            raise ValueError("Task does not have a pending approval request.")

        task.pending_approval.status = "approved" if approved else "denied"
        self.db.add_audit(
            "approval",
            "approved" if approved else "denied",
            f"{task.pending_approval.title}" + (f" ({note})" if note else ""),
            risk=task.pending_approval.risk.value,
            task_id=task.id,
        )
        rt = self._runtimes.get(task_id)
        if rt:
            rt.approval_granted = approved
            rt.approval_event.set()
        self.db.save_task(task)
        self._broadcast("approval_decided", task)
        return task

    def _allowed_roots_for_task(self, task: TaskRun) -> list[str] | None:
        settings = self.db.get_settings()
        roots = list(settings.scoped_directories)
        if task.target_scope and Path(task.target_scope).exists():
            roots.append(task.target_scope)
        return roots if roots else None

    def _build_approval_preview(
        self,
        task: TaskRun,
        step: ActionStep,
        context: dict[str, Any],
    ) -> ApprovalRequest:
        dry_run_items: list[str] = []
        scope = str(step.parameters.get("directory") or step.parameters.get("url") or step.parameters.get("app_name") or "Local Desktop")

        if step.tool == "filesystem.apply_organization":
            plan = context.get("organization_plan") or {}
            moves = plan.get("moves", [])
            for m in moves[:12]:
                dry_run_items.append(
                    f"Move '{m['file_name']}' -> {m['category']}/{Path(m['dest_path']).name}"
                )
            if len(moves) > 12:
                dry_run_items.append(f"...and {len(moves) - 12} more file(s).")
            dry_run_items.append("Deletions: 0 files will be deleted.")
            summary = f"Approve moving {len(moves)} file(s) into category folders inside {scope}. Every move is journaled for undo."
        elif step.tool == "spreadsheet.generate_report":
            dry_run_items.append(f"Create formatted Excel report (.xlsx) inside {scope}")
            dry_run_items.append("Sheets: Summary, Organized Files, Potential Duplicates")
            summary = f"Approve creating an Excel (.xlsx) report inside {scope}."
        elif step.tool == "documents.generate_summary":
            dry_run_items.append(f"Create Markdown summary inside {scope}")
            summary = f"Approve writing a Markdown summary report inside {scope}."
        elif step.tool == "browser.navigate_and_extract":
            dry_run_items.append(f"Open Chromium headless session to {scope}")
            dry_run_items.append("Read page title, text excerpt, and links without submitting forms.")
            summary = f"Approve navigating Playwright Chromium to {scope}."
        elif step.tool == "apps.launch":
            dry_run_items.append(f"Launch native application: {scope}")
            summary = f"Approve opening native desktop application '{scope}'."
        elif step.tool == "apps.open_document":
            app_name = str(step.parameters.get("app_name", "TextEdit"))
            file_path = str(step.parameters.get("file_path", ""))
            dry_run_items.append(f"Open verified document '{Path(file_path).name}' in {app_name}")
            dry_run_items.append(f"Target file: {file_path}")
            summary = f"Approve opening '{Path(file_path).name}' inside external app '{app_name}'."
        elif step.tool == "desktop.click_element":
            app_name = str(step.parameters.get("app_name", ""))
            el_name = str(step.parameters.get("element_name", ""))
            dry_run_items.append(f"Verify '{app_name}' is frontmost and click semantic element '{el_name}'")
            summary = f"Approve target-verified Accessibility click on '{el_name}' in '{app_name}'."
        elif step.tool == "desktop.type_text":
            app_name = str(step.parameters.get("app_name", ""))
            dry_run_items.append(f"Verify '{app_name}' is frontmost (non-secure field) and type bounded text")
            summary = f"Approve controlled text entry into '{app_name}'."
        else:
            dry_run_items.append(f"Execute tool '{step.tool}' on target '{scope}'.")
            summary = f"Approve executing '{step.title}'."

        return ApprovalRequest(
            id=f"apr-{uuid.uuid4().hex[:8]}",
            task_id=task.id,
            step_id=step.id,
            title=step.title,
            summary=summary,
            risk=step.risk,
            reversible=step.reversible,
            scope=scope,
            dry_run_items=dry_run_items,
        )

    async def _execute_step(
        self,
        task: TaskRun,
        step: ActionStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_roots = self._allowed_roots_for_task(task)
        p = step.parameters

        if step.tool == "filesystem.inspect_directory":
            res = await asyncio.to_thread(
                filesystem.inspect_directory,
                p["directory"],
                allowed_roots,
                bool(p.get("include_subdirectories", False)),
            )
            context["inspection"] = res
            return {
                "directory": res["directory"],
                "total_files": res["total_files"],
                "total_bytes": res["total_bytes"],
                "categories": res["categories"],
                "duplicate_group_count": res["duplicate_group_count"],
                "duplicate_file_count": res["duplicate_file_count"],
                "duplicates": res["duplicates"],
            }

        if step.tool == "filesystem.plan_organization":
            plan = await asyncio.to_thread(
                filesystem.plan_organization,
                p["directory"],
                allowed_roots,
            )
            context["organization_plan"] = plan
            context["inspection"] = plan["inspection"]
            return {
                "directory": plan["directory"],
                "planned_move_count": plan["planned_move_count"],
                "deletions_count": 0,
                "categories": plan["categories"],
                "duplicate_group_count": len(plan["duplicate_groups"]),
                "sample_moves": [
                    f"{m['file_name']} -> {m['category']}/{Path(m['dest_path']).name}"
                    for m in plan["moves"][:8]
                ],
            }

        if step.tool == "filesystem.apply_organization":
            plan = context.get("organization_plan")
            if not plan:
                plan = await asyncio.to_thread(filesystem.plan_organization, p["directory"], allowed_roots)
                context["organization_plan"] = plan
                context["inspection"] = plan["inspection"]
            res = await asyncio.to_thread(
                filesystem.apply_organization,
                self.db,
                task.id,
                step.id,
                p["directory"],
                plan["moves"],
                allowed_roots,
            )
            context["moved_files"] = res["moved"]
            return {
                "moved_count": res["moved_count"],
                "skipped_count": res["skipped_count"],
                "deletions_count": 0,
                "verified": res["verified"],
            }

        if step.tool == "spreadsheet.generate_report":
            inspection = context.get("inspection")
            if not inspection:
                inspection = await asyncio.to_thread(
                    filesystem.inspect_directory, p["directory"], allowed_roots, True
                )
            moved = context.get("moved_files", [])
            res = await asyncio.to_thread(
                spreadsheet.generate_organization_workbook,
                self.db,
                task.id,
                step.id,
                p["directory"],
                inspection,
                moved,
                p.get("report_filename"),
                allowed_roots,
            )
            task.artifacts.append(
                TaskArtifact(label=res["file_name"], path=res["report_path"], kind="xlsx")
            )
            return res

        if step.tool == "filesystem.create_directory":
            return await asyncio.to_thread(
                filesystem.create_directory,
                self.db,
                task.id,
                step.id,
                p["directory"],
                p["folder_name"],
                allowed_roots,
            )

        if step.tool == "filesystem.rename_file":
            return await asyncio.to_thread(
                filesystem.rename_file,
                self.db,
                task.id,
                step.id,
                p["directory"],
                p["old_name"],
                p["new_name"],
                allowed_roots,
            )

        if step.tool == "filesystem.search_documents":
            res = await asyncio.to_thread(
                filesystem.search_documents,
                p["directory"],
                p["query"],
                allowed_roots,
            )
            context["search_results"] = res
            return res

        if step.tool == "documents.generate_summary":
            sections: list[tuple[str, str]] = []
            if "search_results" in context:
                sr = context["search_results"]
                lines = [
                    f"- `{m['name']}` ({m['category']}, {m['match_type']})"
                    + (f": {m['snippet']}" if m.get("snippet") else "")
                    for m in sr["matches"]
                ]
                sections.append(
                    ("Matches", "\n".join(lines) if lines else "No matching documents found.")
                )
            if "web_result" in context:
                wr = context["web_result"]
                sections.append(("Source", f"URL: {wr['url']}\nTitle: {wr['title']}"))
                sections.append(("Extracted Excerpt", wr.get("text_excerpt", "")))
            if not sections:
                sections.append(("Summary", f"Completed OmniDesk task '{task.title}'."))
            res = await asyncio.to_thread(
                documents.generate_markdown_report,
                self.db,
                task.id,
                step.id,
                p["directory"],
                p.get("title", task.title),
                sections,
                p.get("filename"),
                allowed_roots,
            )
            task.artifacts.append(
                TaskArtifact(label=res["file_name"], path=res["report_path"], kind="markdown")
            )
            return res

        if step.tool == "apps.launch":
            return await asyncio.to_thread(apps.launch_application, p["app_name"])

        if step.tool == "apps.list_running":
            running = await asyncio.to_thread(desktop_control.list_running_apps)
            return {"count": len(running), "apps": [a["name"] for a in running]}

        if step.tool == "apps.open_document":
            return await asyncio.to_thread(
                desktop_control.open_document_in_app,
                p["app_name"],
                p["file_path"],
                allowed_roots,
            )

        if step.tool == "desktop.inspect_accessibility":
            settings = self.db.get_settings()
            return await asyncio.to_thread(
                desktop_control.inspect_accessibility_tree,
                p.get("app_name"),
                settings.excluded_apps,
            )

        if step.tool == "desktop.click_element":
            settings = self.db.get_settings()
            return await asyncio.to_thread(
                desktop_control.click_semantic_element,
                p["app_name"],
                p["element_name"],
                settings.excluded_apps,
                p.get("role", "button"),
            )

        if step.tool == "desktop.type_text":
            settings = self.db.get_settings()
            return await asyncio.to_thread(
                desktop_control.type_text_into_target,
                p["app_name"],
                p["text"],
                settings.excluded_apps,
            )

        if step.tool == "browser.navigate_and_extract":
            res = await browser.navigate_and_extract(
                p["url"], selector=p.get("selector"), timeout_ms=20000
            )
            context["web_result"] = res
            return res

        if step.tool == "browser.prepare_form":
            return await browser.prepare_form(p["url"], p.get("fields", {}))

        if step.tool == "clipboard.read":
            return await asyncio.to_thread(clipboard.read_clipboard)

        if step.tool == "clipboard.write":
            return await asyncio.to_thread(clipboard.write_clipboard, str(p.get("text", "")))

        if step.tool == "vision.capture_window":
            settings = self.db.get_settings()
            return await asyncio.to_thread(vision.capture_opt_in_snapshot, settings.excluded_apps)

        raise PermissionError(
            f"Tool '{step.tool}' is blocked by OmniDesk's deny-by-default security policy."
        )

    async def _run_loop(self, task_id: str, rt: _ExecutionRuntime) -> None:
        started = time.monotonic()
        context: dict[str, Any] = {}

        try:
            task = self.db.get_task(task_id)
            if not task:
                return

            for step in task.steps:
                if rt.cancel_event.is_set():
                    break
                await rt.pause_event.wait()
                if rt.cancel_event.is_set():
                    break

                if step.risk in (RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED_SYSTEM):
                    step.status = StepStatus.FAILED
                    step.error = "Blocked by OmniDesk deny-by-default security policy."
                    task.status = TaskStatus.FAILED
                    task.error = step.error
                    self.db.save_task(task)
                    self._broadcast("task_failed", task)
                    return

                if step.requires_approval:
                    approval = self._build_approval_preview(task, step, context)
                    step.status = StepStatus.AWAITING_APPROVAL
                    task.status = TaskStatus.AWAITING_APPROVAL
                    task.pending_approval = approval
                    self.db.save_task(task)
                    self._broadcast("approval_requested", task)

                    rt.approval_event.clear()
                    rt.approval_granted = None
                    await rt.approval_event.wait()

                    if rt.cancel_event.is_set():
                        return
                    if not rt.approval_granted:
                        step.status = StepStatus.SKIPPED
                        step.error = "Denied by user."
                        task.pending_approval = None
                        task.status = TaskStatus.CANCELLED
                        task.error = f"Execution stopped: user denied '{step.title}'."
                        self.db.save_task(task)
                        self._broadcast("task_cancelled", task)
                        return

                    task.pending_approval = None
                    task.status = TaskStatus.RUNNING

                step.status = StepStatus.RUNNING
                step.started_at = utc_now_iso()
                self.db.save_task(task)
                self._broadcast("step_started", task)

                try:
                    result = await asyncio.wait_for(
                        self._execute_step(task, step, context),
                        timeout=self.config.step_timeout_seconds,
                    )
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.finished_at = utc_now_iso()
                except Exception as exc:
                    step.status = StepStatus.FAILED
                    step.error = redact_sensitive_text(str(exc))
                    step.finished_at = utc_now_iso()
                    task.status = TaskStatus.FAILED
                    task.error = step.error
                    task.duration_ms = int((time.monotonic() - started) * 1000)
                    self.db.save_task(task)
                    self.db.add_audit("task", "step_failed", f"{step.title}: {step.error}", task_id=task.id)
                    self._broadcast("task_failed", task)
                    return

                self.db.save_task(task)
                self._broadcast("step_completed", task)

            if rt.cancel_event.is_set():
                return

            journal = self.db.get_journal_entries(task.id)
            task.can_undo = len(journal) > 0
            task.status = TaskStatus.COMPLETED
            task.duration_ms = int((time.monotonic() - started) * 1000)
            completed_count = sum(1 for s in task.steps if s.status == StepStatus.COMPLETED)
            artifact_note = (
                f" Generated {len(task.artifacts)} artifact(s)."
                if task.artifacts
                else ""
            )
            task.summary = f"Completed {completed_count}/{len(task.steps)} verified step(s).{artifact_note}"
            self.db.save_task(task)
            self.db.add_audit("task", "completed", task.summary, task_id=task.id)
            self._broadcast("task_completed", task)
        finally:
            self._runtimes.pop(task_id, None)


def create_flagship_demo_sandbox(base_dir: Path) -> dict[str, Any]:
    """Creates a realistic, reproducible folder of real files (including byte-identical duplicates)
    so users can run the flagship organization & Excel report demo without touching personal files.
    """
    demo_dir = (base_dir / "flagship-downloads-demo").resolve()
    if demo_dir.exists():
        import shutil

        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True, exist_ok=True)

    invoice_bytes = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n% Sample Quarterly Invoice Q4\n"
    (demo_dir / "Q4_Invoice_2026.pdf").write_bytes(invoice_bytes)
    (demo_dir / "Q4_Invoice_2026_copy.pdf").write_bytes(invoice_bytes)  # Intentional exact duplicate

    budget_csv = "Department,Budget_USD,Actual_USD\nEngineering,42000,39850\nOperations,18500,17900\n"
    (demo_dir / "Team_Budget_2026.csv").write_text(budget_csv, encoding="utf-8")

    notes_md = "# Release Checklist\n\n- Verify cross-platform builds\n- Confirm zero plaintext secrets\n"
    (demo_dir / "Release_Notes.md").write_text(notes_md, encoding="utf-8")
    (demo_dir / "Release_Notes_backup.md").write_text(notes_md, encoding="utf-8")  # Intentional duplicate

    (demo_dir / "automation_script.py").write_text("print('OmniDesk demo file')\n", encoding="utf-8")
    (demo_dir / "archive_snapshot.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    # Create a real minimal PNG image using Pillow
    from PIL import Image

    img = Image.new("RGB", (64, 64), color=(17, 22, 31))
    img.save(demo_dir / "Product_Diagram.png", format="PNG")

    return {
        "directory": str(demo_dir),
        "file_count": 8,
        "expected_duplicate_groups": 2,
        "prompt": (
            f"Organize the files in {demo_dir} by category, identify possible duplicates, "
            "and generate an Excel report without deleting anything."
        ),
    }


def create_external_app_demo_sandbox(base_dir: Path) -> dict[str, Any]:
    """Creates a dedicated non-sensitive sandbox folder for external application automation testing."""
    import platform

    demo_dir = (base_dir / "external-app-demo").resolve()
    demo_dir.mkdir(parents=True, exist_ok=True)
    app_name = "TextEdit" if platform.system() == "Darwin" else ("Notepad" if platform.system() == "Windows" else "Text Editor")
    return {
        "directory": str(demo_dir),
        "app_name": app_name,
        "prompt": (
            f"Create an automation brief in {demo_dir}, open it in {app_name}, "
            "and inspect accessibility state."
        ),
    }
