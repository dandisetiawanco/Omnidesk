from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_MODIFICATION = "reversible_modification"
    SENSITIVE_ACCESS = "sensitive_access"
    EXTERNAL_COMMUNICATION = "external_communication"
    DESTRUCTIVE = "destructive"
    PRIVILEGED_SYSTEM = "privileged_system"


class StepStatus(str, Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CapabilityEntry(BaseModel):
    id: str
    name: str
    category: Literal["os", "automation", "vision", "browser", "ai_runtime", "security"]
    status: Literal["available", "permission_required", "not_installed", "experimental", "unsupported"]
    maturity: Literal[
        "implemented_tested",
        "implemented_untested",
        "experimental",
        "unsupported",
    ] = "implemented_tested"
    detail: str
    platform_note: str | None = None


class DisplayInfo(BaseModel):
    name: str
    width: int
    height: int
    scale_factor: float


class SystemProfile(BaseModel):
    os_name: str
    os_version: str
    arch: str
    cpu_model: str
    cpu_cores: int
    memory_total_gb: float
    gpu_name: str
    desktop_environment: str
    display_server: str
    displays: list[DisplayInfo]
    glass_material: Literal["macos_vibrancy", "windows_mica", "linux_compositor", "solid_fallback"]
    capabilities: list[CapabilityEntry]


class SelectedModels(BaseModel):
    planning: str | None = None
    vision: str | None = None
    lightweight: str | None = None


class TokenUsage(BaseModel):
    provider_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    latency_ms: int = 0


class ProviderStatus(BaseModel):
    id: Literal["openai", "gemini", "anthropic", "ollama", "openai_compatible"]
    label: str
    kind: Literal["local", "cloud", "custom"]
    configured: bool
    reachable: bool
    runtime_installed: bool = True
    status_detail: str
    base_url: str | None = None
    masked_key: str | None = None
    primary_model: str | None = None
    context_limit: int = 2048
    available_models: list[str] = Field(default_factory=list)
    loaded_models: list[str] = Field(default_factory=list)
    model_capabilities: dict[str, list[str]] = Field(default_factory=dict)
    selected_models: SelectedModels = Field(default_factory=SelectedModels)


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = None
    clear_key: bool = False
    base_url: str | None = None
    primary_model: str | None = None
    context_limit: int | None = Field(default=None, ge=512, le=32768)
    selected_models: SelectedModels | None = None


class ActionStep(BaseModel):
    id: str
    index: int
    title: str
    tool: str
    risk: RiskLevel
    requires_approval: bool
    reversible: bool
    status: StepStatus = StepStatus.PENDING
    parameters: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class ApprovalRequest(BaseModel):
    id: str
    task_id: str
    step_id: str
    title: str
    summary: str
    risk: RiskLevel
    reversible: bool
    scope: str
    dry_run_items: list[str] = Field(default_factory=list)
    status: Literal["pending", "approved", "denied", "expired"] = "pending"
    created_at: str = Field(default_factory=utc_now_iso)


class TaskArtifact(BaseModel):
    label: str
    path: str
    kind: str


class TaskRun(BaseModel):
    id: str
    prompt: str
    title: str
    status: TaskStatus
    planner_source: str
    target_scope: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    duration_ms: int | None = None
    summary: str | None = None
    error: str | None = None
    can_undo: bool = False
    undone: bool = False
    steps: list[ActionStep] = Field(default_factory=list)
    pending_approval: ApprovalRequest | None = None
    artifacts: list[TaskArtifact] = Field(default_factory=list)
    usage: TokenUsage | None = None
    fallback_note: str | None = None


class CreateTaskRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    target_directory: str | None = None
    dry_run_only: bool = False
    provider_id: str | None = None
    attached_app: str | None = None
    attached_url: str | None = None


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    note: str | None = None


class WorkflowVariable(BaseModel):
    name: str
    default_value: str
    description: str


class WorkflowNode(BaseModel):
    id: str
    type: Literal[
        "trigger",
        "action",
        "condition",
        "loop",
        "approval",
        "variable",
        "error_handler",
    ]
    label: str
    tool: str | None = None
    x: float
    y: float
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    version: int = 1
    source: Literal["manual", "teach_mode", "template"] = "manual"
    variables: list[WorkflowVariable] = Field(default_factory=list)
    max_loop_iterations: int = Field(default=25, ge=1, le=100)
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class RunWorkflowRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False


class TeachEvent(BaseModel):
    id: str
    timestamp: str = Field(default_factory=utc_now_iso)
    kind: Literal[
        "app_focus",
        "file_action",
        "browser_navigation",
        "ui_semantic_click",
        "report_export",
        "redacted_secret",
    ]
    summary: str
    selector: str
    app_name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    redacted: bool = False


class TeachVariable(BaseModel):
    name: str
    sample_value: str
    description: str


class TeachSession(BaseModel):
    id: str
    name: str
    status: Literal["recording", "stopped", "converted"]
    started_at: str = Field(default_factory=utc_now_iso)
    stopped_at: str | None = None
    scope_app: str | None = None
    scope_directory: str | None = None
    observer_active: bool = False
    observer_note: str | None = None
    events: list[TeachEvent] = Field(default_factory=list)
    extracted_variables: list[TeachVariable] = Field(default_factory=list)
    workflow_id: str | None = None


class StartTeachRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scope_app: str | None = None
    scope_directory: str | None = None
    enable_live_observer: bool = True


class RecordTeachStepRequest(BaseModel):
    kind: Literal[
        "app_focus",
        "file_action",
        "browser_navigation",
        "ui_semantic_click",
        "report_export",
    ]
    summary: str
    selector: str
    app_name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_secure_field: bool = False


class AppSettings(BaseModel):
    theme: Literal["system", "light", "dark"] = "system"
    performance_mode: bool = False
    privacy_mode: Literal["local_only", "cloud_assisted"] = "local_only"
    cloud_screenshot_consent: bool = False
    data_retention_days: int = Field(default=30, ge=1, le=365)
    excluded_apps: list[str] = Field(
        default_factory=lambda: ["1Password", "Bitwarden", "Keychain Access", "KeePassXC"]
    )
    scoped_directories: list[str] = Field(default_factory=list)
    global_shortcut: str = "CommandOrControl+Shift+Space"
    onboarding_completed: bool = False
    telemetry_enabled: bool = False
    provider_fallback_order: list[str] = Field(
        default_factory=lambda: ["ollama", "gemini", "openai", "anthropic", "openai_compatible"]
    )
    local_context_limit: int = Field(default=2048, ge=512, le=32768)


class AuditEntry(BaseModel):
    id: str
    timestamp: str
    category: str
    action: str
    detail: str
    risk: str | None = None
    task_id: str | None = None
