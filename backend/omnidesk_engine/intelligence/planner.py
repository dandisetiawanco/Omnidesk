from __future__ import annotations

import platform
import re
import uuid
from pathlib import Path
from typing import Any

from omnidesk_engine.providers.registry import ProviderRegistry
from omnidesk_engine.schemas import ActionStep, RiskLevel, TokenUsage
from omnidesk_engine.security.policy import TOOL_POLICIES, get_tool_policy

URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


def _extract_target_directory(prompt: str, explicit_dir: str | None) -> str:
    if explicit_dir and explicit_dir.strip():
        return str(Path(explicit_dir).expanduser().resolve())
    lower = prompt.lower()
    home = Path.home()
    if "downloads" in lower:
        return str((home / "Downloads").resolve())
    if "desktop" in lower:
        return str((home / "Desktop").resolve())
    if "documents" in lower:
        return str((home / "Documents").resolve())
    return str((home / "Downloads").resolve())


def _extract_app_name(prompt: str) -> str:
    match = re.search(r"(?:open|launch|start)\s+(?:the\s+)?([A-Za-z0-9 ._+-]{2,40})", prompt, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip().rstrip(".,!?")
        for stop in (" app", " application", " for me"):
            if candidate.lower().endswith(stop):
                candidate = candidate[: -len(stop)].strip()
        if candidate:
            return candidate
    return "Calculator"


def _resolve_external_app_name(lower_prompt: str) -> str:
    if "textedit" in lower_prompt:
        return "TextEdit"
    if "notepad" in lower_prompt:
        return "Notepad"
    if "text editor" in lower_prompt:
        return "Text Editor"
    system = platform.system()
    if system == "Darwin":
        return "TextEdit"
    if system == "Windows":
        return "Notepad"
    return "Text Editor"


def _make_step(
    index: int,
    title: str,
    tool: str,
    parameters: dict[str, Any],
    force_approval: bool = False,
) -> ActionStep:
    policy = get_tool_policy(tool)
    return ActionStep(
        id=f"stp-{uuid.uuid4().hex[:8]}",
        index=index,
        title=title,
        tool=tool,
        risk=policy.risk,
        requires_approval=policy.requires_approval or force_approval,
        reversible=policy.reversible,
        parameters=parameters,
    )


class TaskPlanner:
    """Decomposes natural-language tasks into typed, policy-validated execution plans."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self.providers = providers

    async def build_plan(
        self,
        prompt: str,
        target_directory: str | None = None,
        dry_run_only: bool = False,
        preferred_provider: str | None = None,
    ) -> tuple[str, list[ActionStep], str, str | None, TokenUsage | None, str | None]:
        clean_prompt = prompt.strip()
        lower = clean_prompt.lower()

        # Refuse unsafe direct shell or silent destructive requests explicitly via policy tier.
        if any(kw in lower for kw in ("rm -rf", "format drive", "delete system", "wipe disk")):
            step = _make_step(
                0,
                "Blocked destructive request",
                "system.shell_command",
                {"reason": "OmniDesk blocks destructive system-wide commands under deny-by-default policy."},
                force_approval=True,
            )
            return "Blocked Unsafe Request", [step], "security_policy_guard", None, None, None

        # Attempt configured local/cloud model provider; validate every returned tool & required parameter strictly.
        catalog = [
            {"tool": p.tool, "risk": p.risk.value, "description": p.description}
            for p in TOOL_POLICIES.values()
            if p.risk not in (RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED_SYSTEM)
        ]
        llm_plan, source, usage, fallback_note = await self.providers.complete_json_plan(
            clean_prompt, catalog, preferred_provider=preferred_provider
        )
        if llm_plan and llm_plan.get("steps"):
            validated_steps: list[ActionStep] = []
            rejected_reasons: list[str] = []
            resolved_dir = _extract_target_directory(clean_prompt, target_directory)

            for idx, raw_step in enumerate(llm_plan["steps"][:12]):
                if not isinstance(raw_step, dict):
                    rejected_reasons.append("non-object step")
                    continue
                tool_name = str(raw_step.get("tool", ""))
                if tool_name not in TOOL_POLICIES:
                    rejected_reasons.append(f"unknown tool '{tool_name}'")
                    continue
                policy = get_tool_policy(tool_name)
                if policy.risk in (RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED_SYSTEM):
                    rejected_reasons.append(f"blocked risky tool '{tool_name}'")
                    continue
                params = raw_step.get("parameters") if isinstance(raw_step.get("parameters"), dict) else {}
                # Normalize missing directory/url/app parameters safely or reject incomplete plans.
                if tool_name.startswith("filesystem.") or tool_name in ("spreadsheet.generate_report", "documents.generate_summary"):
                    params["directory"] = target_directory or params.get("directory") or resolved_dir
                if tool_name == "filesystem.search_documents" and not params.get("query"):
                    rejected_reasons.append("missing search query")
                    continue
                if tool_name == "browser.navigate_and_extract":
                    url_m = URL_RE.search(clean_prompt)
                    params["url"] = params.get("url") or (url_m.group(0) if url_m else None)
                    if not params["url"]:
                        rejected_reasons.append("missing browser url")
                        continue
                if tool_name == "apps.launch" and not params.get("app_name"):
                    params["app_name"] = _extract_app_name(clean_prompt)
                if tool_name == "apps.open_document":
                    if not params.get("app_name") or not params.get("file_path"):
                        rejected_reasons.append("apps.open_document missing app_name or file_path")
                        continue
                    creates_doc_earlier = any(s.tool == "documents.generate_summary" for s in validated_steps)
                    if not creates_doc_earlier and not Path(str(params["file_path"])).expanduser().exists():
                        rejected_reasons.append("apps.open_document references non-existent file without prior generation")
                        continue
                if tool_name == "desktop.click_element" and (not params.get("app_name") or not params.get("element_name")):
                    rejected_reasons.append("desktop.click_element missing app_name or element_name")
                    continue
                if tool_name == "desktop.type_text" and (not params.get("app_name") or not params.get("text")):
                    rejected_reasons.append("desktop.type_text missing app_name or text")
                    continue
                if tool_name == "filesystem.apply_organization" and not any(
                    s.tool == "filesystem.plan_organization" for s in validated_steps
                ):
                    rejected_reasons.append("filesystem.apply_organization requires prior dry-run plan step")
                    continue
                if dry_run_only and tool_name in ("filesystem.apply_organization", "spreadsheet.generate_report"):
                    continue
                validated_steps.append(
                    _make_step(
                        len(validated_steps),
                        str(raw_step.get("title") or tool_name),
                        tool_name,
                        params,
                    )
                )

            # Reject lightweight-model plans that dropped all actionable steps or mixed unknown tools.
            if validated_steps and not rejected_reasons:
                title = str(llm_plan.get("title") or clean_prompt[:72])
                return title, validated_steps, source, target_directory or resolved_dir, usage, None
            if rejected_reasons:
                fallback_note = (
                    f"Model plan from {source} rejected by policy validation ({', '.join(rejected_reasons[:3])}); "
                    "switched to deterministic local fallback."
                )

        # Deterministic local structured planner (clearly labeled fallback when model unavailable or rejected).
        # 1. Reproducible external application automation (create brief + open in native app + verify)
        if any(
            kw in lower
            for kw in (
                "textedit",
                "text editor",
                "notepad",
                "external app",
                "external-app-demo",
                "accessibility tree",
                "accessibility state",
                "inspect window",
            )
        ):
            directory = _extract_target_directory(clean_prompt, target_directory)
            app_name = _resolve_external_app_name(lower)
            if "accessibility" in lower and "brief" not in lower and "create" not in lower:
                steps = [
                    _make_step(0, "List visible running GUI applications", "apps.list_running", {}),
                    _make_step(
                        1,
                        "Inspect frontmost window and OS accessibility tree",
                        "desktop.inspect_accessibility",
                        {},
                    ),
                ]
                return "Inspect Active App & Accessibility", steps, "local_deterministic_planner", None, usage, fallback_note

            brief_file = str(Path(directory) / "OmniDesk_Automation_Brief.txt")
            steps = [
                _make_step(0, "Verify running desktop applications before launch", "apps.list_running", {}),
                _make_step(
                    1,
                    "Generate verified automation brief document in sandbox",
                    "documents.generate_summary",
                    {
                        "directory": directory,
                        "title": "OmniDesk External Application Automation Brief",
                        "filename": "OmniDesk_Automation_Brief.txt",
                    },
                    force_approval=True,
                ),
                _make_step(
                    2,
                    f"Open verified brief in native {app_name} application",
                    "apps.open_document",
                    {"app_name": app_name, "file_path": brief_file, "directory": directory},
                    force_approval=True,
                ),
                _make_step(
                    3,
                    f"Verify {app_name} window & accessibility state",
                    "desktop.inspect_accessibility",
                    {"app_name": app_name},
                ),
            ]
            return f"External App Automation ({app_name})", steps, "local_deterministic_planner", directory, usage, fallback_note

        # 2. Flagship file organization + duplicate scan + Excel/Markdown report
        if any(kw in lower for kw in ("organize", "sort files", "categorize", "duplicate", "excel", "spreadsheet")):
            directory = _extract_target_directory(clean_prompt, target_directory)
            wants_excel = any(kw in lower for kw in ("excel", "xlsx", "spreadsheet", "report"))
            steps = [
                _make_step(
                    0,
                    "Inspect files and verify SHA-256 duplicates",
                    "filesystem.inspect_directory",
                    {"directory": directory},
                ),
                _make_step(
                    1,
                    "Build dry-run category organization plan (zero deletions)",
                    "filesystem.plan_organization",
                    {"directory": directory},
                ),
            ]
            if not dry_run_only:
                steps.append(
                    _make_step(
                        2,
                        "Move files into category folders with undo journal",
                        "filesystem.apply_organization",
                        {"directory": directory},
                        force_approval=True,
                    )
                )
            if wants_excel:
                steps.append(
                    _make_step(
                        len(steps),
                        "Generate formatted Excel (.xlsx) organization report",
                        "spreadsheet.generate_report",
                        {"directory": directory},
                        force_approval=True,
                    )
                )
            return f"Organize {Path(directory).name} & Report", steps, "local_deterministic_planner", directory, usage, fallback_note

        # 3. Browser navigation / extraction / form prep
        url_match = URL_RE.search(clean_prompt)
        if url_match or any(kw in lower for kw in ("browse", "website", "webpage", "url", "playwright")):
            url = url_match.group(0).rstrip(".,)") if url_match else "https://example.com"
            steps = [
                _make_step(
                    0,
                    f"Navigate and inspect {url}",
                    "browser.navigate_and_extract",
                    {"url": url},
                    force_approval=True,
                )
            ]
            if target_directory and any(kw in lower for kw in ("report", "summary", "save")):
                steps.append(
                    _make_step(
                        1,
                        "Save extracted web summary report",
                        "documents.generate_summary",
                        {"directory": target_directory, "title": f"Web Summary: {url}"},
                        force_approval=True,
                    )
                )
            return f"Browser Research: {url[:44]}", steps, "local_deterministic_planner", url, usage, fallback_note

        # 4. Document search & extraction
        if any(kw in lower for kw in ("search", "find files", "find documents", "extract")):
            directory = _extract_target_directory(clean_prompt, target_directory)
            quoted = re.search(r"['\"]([^'\"]{2,60})['\"]", clean_prompt)
            query = quoted.group(1) if quoted else clean_prompt.split()[-1].strip(".,?!")
            steps = [
                _make_step(
                    0,
                    f"Search documents for '{query}'",
                    "filesystem.search_documents",
                    {"directory": directory, "query": query},
                ),
                _make_step(
                    1,
                    "Generate Markdown search report",
                    "documents.generate_summary",
                    {"directory": directory, "title": f"Document Search Report ({query})"},
                    force_approval=True,
                ),
            ]
            return f"Search Documents in {Path(directory).name}", steps, "local_deterministic_planner", directory, usage, fallback_note

        # 5. Native application launching
        if any(kw in lower for kw in ("open ", "launch ", "start ")):
            app_name = _extract_app_name(clean_prompt)
            steps = [
                _make_step(
                    0,
                    f"Launch native application '{app_name}'",
                    "apps.launch",
                    {"app_name": app_name},
                    force_approval=True,
                )
            ]
            return f"Launch {app_name}", steps, "local_deterministic_planner", app_name, usage, fallback_note

        # 6. Safe fallback: inspect scoped directory without modifying anything
        directory = _extract_target_directory(clean_prompt, target_directory)
        steps = [
            _make_step(
                0,
                f"Inspect directory {Path(directory).name}",
                "filesystem.inspect_directory",
                {"directory": directory},
            )
        ]
        return clean_prompt[:72], steps, "local_deterministic_planner", directory, usage, fallback_note
