import { z } from "zod";

export const RiskLevelSchema = z.enum([
  "read_only",
  "reversible_modification",
  "sensitive_access",
  "external_communication",
  "destructive",
  "privileged_system",
]);
export type RiskLevel = z.infer<typeof RiskLevelSchema>;

export const CapabilityStatusSchema = z.enum([
  "available",
  "permission_required",
  "not_installed",
  "experimental",
  "unsupported",
]);
export type CapabilityStatus = z.infer<typeof CapabilityStatusSchema>;

export const CapabilityMaturitySchema = z.enum([
  "implemented_tested",
  "implemented_untested",
  "experimental",
  "unsupported",
]);

export const CapabilityEntrySchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.enum(["os", "automation", "vision", "browser", "ai_runtime", "security"]),
  status: CapabilityStatusSchema,
  maturity: CapabilityMaturitySchema.optional(),
  detail: z.string(),
  platform_note: z.string().optional(),
});
export type CapabilityEntry = z.infer<typeof CapabilityEntrySchema>;

export const SystemProfileSchema = z.object({
  os_name: z.string(),
  os_version: z.string(),
  arch: z.string(),
  cpu_model: z.string(),
  cpu_cores: z.number().int().nonnegative(),
  memory_total_gb: z.number().nonnegative(),
  gpu_name: z.string(),
  desktop_environment: z.string(),
  display_server: z.string(),
  displays: z.array(
    z.object({
      name: z.string(),
      width: z.number().int().nonnegative(),
      height: z.number().int().nonnegative(),
      scale_factor: z.number().positive(),
    })
  ),
  glass_material: z.enum(["macos_vibrancy", "windows_mica", "linux_compositor", "solid_fallback"]),
  capabilities: z.array(CapabilityEntrySchema),
});
export type SystemProfile = z.infer<typeof SystemProfileSchema>;

export const ProviderIdSchema = z.enum([
  "openai",
  "gemini",
  "anthropic",
  "ollama",
  "openai_compatible",
]);
export type ProviderId = z.infer<typeof ProviderIdSchema>;

export const ProviderStatusSchema = z.object({
  id: ProviderIdSchema,
  label: z.string(),
  kind: z.enum(["local", "cloud", "custom"]),
  configured: z.boolean(),
  reachable: z.boolean(),
  status_detail: z.string(),
  base_url: z.string().optional(),
  masked_key: z.string().optional(),
  available_models: z.array(z.string()),
  model_capabilities: z.record(z.array(z.string())).optional(),
  selected_models: z.object({
    planning: z.string().optional(),
    vision: z.string().optional(),
    lightweight: z.string().optional(),
  }),
});
export type ProviderStatus = z.infer<typeof ProviderStatusSchema>;

export const StepStatusSchema = z.enum([
  "pending",
  "awaiting_approval",
  "running",
  "completed",
  "failed",
  "skipped",
  "cancelled",
]);
export type StepStatus = z.infer<typeof StepStatusSchema>;

export const TaskStatusSchema = z.enum([
  "planning",
  "awaiting_approval",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
]);
export type TaskStatus = z.infer<typeof TaskStatusSchema>;

export const ActionStepSchema = z.object({
  id: z.string(),
  index: z.number().int().nonnegative(),
  title: z.string(),
  tool: z.string(),
  risk: RiskLevelSchema,
  requires_approval: z.boolean(),
  reversible: z.boolean(),
  status: StepStatusSchema,
  parameters: z.record(z.unknown()),
  preview: z.record(z.unknown()).optional(),
  result: z.record(z.unknown()).optional(),
  error: z.string().optional(),
  started_at: z.string().optional(),
  finished_at: z.string().optional(),
});
export type ActionStep = z.infer<typeof ActionStepSchema>;

export const ApprovalRequestSchema = z.object({
  id: z.string(),
  task_id: z.string(),
  step_id: z.string(),
  title: z.string(),
  summary: z.string(),
  risk: RiskLevelSchema,
  reversible: z.boolean(),
  scope: z.string(),
  dry_run_items: z.array(z.string()),
  status: z.enum(["pending", "approved", "denied", "expired"]),
  created_at: z.string(),
});
export type ApprovalRequest = z.infer<typeof ApprovalRequestSchema>;

export const TaskRunSchema = z.object({
  id: z.string(),
  prompt: z.string(),
  title: z.string(),
  status: TaskStatusSchema,
  planner_source: z.string(),
  target_scope: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  duration_ms: z.number().int().nonnegative().optional(),
  summary: z.string().optional(),
  error: z.string().optional(),
  can_undo: z.boolean(),
  undone: z.boolean(),
  steps: z.array(ActionStepSchema),
  pending_approval: ApprovalRequestSchema.optional().nullable(),
  artifacts: z.array(
    z.object({
      label: z.string(),
      path: z.string(),
      kind: z.string(),
    })
  ),
});
export type TaskRun = z.infer<typeof TaskRunSchema>;

export const WorkflowNodeSchema = z.object({
  id: z.string(),
  type: z.enum([
    "trigger",
    "action",
    "condition",
    "loop",
    "approval",
    "variable",
    "error_handler",
  ]),
  label: z.string(),
  tool: z.string().optional(),
  x: z.number(),
  y: z.number(),
  config: z.record(z.unknown()),
});
export type WorkflowNode = z.infer<typeof WorkflowNodeSchema>;

export const WorkflowEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  label: z.string().optional(),
});
export type WorkflowEdge = z.infer<typeof WorkflowEdgeSchema>;

export const WorkflowDefinitionSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.number().int().positive(),
  source: z.enum(["manual", "teach_mode", "template"]),
  variables: z.array(
    z.object({
      name: z.string(),
      default_value: z.string(),
      description: z.string(),
    })
  ),
  max_loop_iterations: z.number().int().positive().max(100),
  nodes: z.array(WorkflowNodeSchema),
  edges: z.array(WorkflowEdgeSchema),
  created_at: z.string(),
  updated_at: z.string(),
});
export type WorkflowDefinition = z.infer<typeof WorkflowDefinitionSchema>;

export const TeachEventSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  kind: z.enum([
    "app_focus",
    "file_action",
    "browser_navigation",
    "ui_semantic_click",
    "report_export",
    "redacted_secret",
  ]),
  summary: z.string(),
  selector: z.string(),
  app_name: z.string().optional(),
  parameters: z.record(z.unknown()),
  redacted: z.boolean(),
});
export type TeachEvent = z.infer<typeof TeachEventSchema>;

export const TeachSessionSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(["recording", "stopped", "converted"]),
  started_at: z.string(),
  stopped_at: z.string().optional().nullable(),
  scope_app: z.string().optional().nullable(),
  scope_directory: z.string().optional().nullable(),
  observer_active: z.boolean().optional(),
  observer_note: z.string().optional().nullable(),
  events: z.array(TeachEventSchema),
  extracted_variables: z.array(
    z.object({
      name: z.string(),
      sample_value: z.string(),
      description: z.string(),
    })
  ),
  workflow_id: z.string().optional().nullable(),
});
export type TeachSession = z.infer<typeof TeachSessionSchema>;

export const AppSettingsSchema = z.object({
  theme: z.enum(["system", "light", "dark"]),
  performance_mode: z.boolean(),
  privacy_mode: z.enum(["local_only", "cloud_assisted"]),
  cloud_screenshot_consent: z.boolean(),
  data_retention_days: z.number().int().min(1).max(365),
  excluded_apps: z.array(z.string()),
  scoped_directories: z.array(z.string()),
  global_shortcut: z.string(),
  onboarding_completed: z.boolean(),
  telemetry_enabled: z.boolean(),
});
export type AppSettings = z.infer<typeof AppSettingsSchema>;
