import React, { useEffect, useState } from "react";
import {
  AppWindow,
  FolderOpen,
  GitBranch,
  Globe,
  Play,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import type {
  AppSettings,
  ProviderStatus,
  SystemProfile,
  TaskRun,
  WorkflowDefinition,
} from "@omnidesk/shared-schemas";
import { StatusTag } from "../components/StatusTag";
import { api } from "../lib/api";
import { pickScopedDirectory } from "../lib/tauri";

interface HomeViewProps {
  profile: SystemProfile | null;
  providers: ProviderStatus[];
  settings: AppSettings;
  tasks: TaskRun[];
  workflows: WorkflowDefinition[];
  demoDirectory: string | null;
  onStartTask: (
    prompt: string,
    targetDir?: string,
    dryRun?: boolean,
    providerId?: string,
    attachedApp?: string,
    attachedUrl?: string
  ) => Promise<void>;
  onRunFlagshipDemo: () => Promise<void>;
  onRunExternalAppDemo: () => Promise<void>;
  onOpenTask: (taskId: string) => void;
  onRunWorkflow: (wf: WorkflowDefinition) => Promise<void>;
  onNavigateModels: () => void;
  onNavigateStudio: () => void;
}

const SUGGESTED_ACTIONS = [
  {
    label: "Organize folder & export Excel report",
    prompt:
      "Organize the files in my folder by category, identify possible duplicates, and generate an Excel report without deleting anything.",
  },
  {
    label: "External app brief in TextEdit",
    prompt:
      "Create an automation brief in my sandbox folder, open it in TextEdit, and inspect accessibility state.",
  },
  {
    label: "Inspect active app accessibility tree",
    prompt: "Inspect active window accessibility tree and running GUI applications.",
  },
  {
    label: "Extract webpage with Playwright",
    prompt: "Browse https://example.com and extract the main content and links.",
  },
];

export const HomeView: React.FC<HomeViewProps> = ({
  profile,
  providers,
  settings,
  tasks,
  workflows,
  demoDirectory,
  onStartTask,
  onRunFlagshipDemo,
  onRunExternalAppDemo,
  onOpenTask,
  onRunWorkflow,
  onNavigateModels,
  onNavigateStudio,
}) => {
  const [prompt, setPrompt] = useState("");
  const [targetDir, setTargetDir] = useState(demoDirectory ?? "");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [attachedApp, setAttachedApp] = useState("");
  const [attachedUrl, setAttachedUrl] = useState("");
  const [showContextBar, setShowContextBar] = useState(false);
  const [runningApps, setRunningApps] = useState<string[]>([]);
  const [dryRunOnly, setDryRunOnly] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (demoDirectory && !targetDir) setTargetDir(demoDirectory);
  }, [demoDirectory, targetDir]);

  useEffect(() => {
    if (!showContextBar) return;
    api
      .listRunningApps()
      .then((list) => setRunningApps(list.map((a) => a.name)))
      .catch(() => {});
  }, [showContextBar]);

  const activeTask = tasks.find((t) =>
    ["running", "paused", "awaiting_approval", "planning"].includes(t.status)
  );
  const configuredProviders = providers.filter((p) => p.configured || p.reachable);

  const handleBrowse = async () => {
    const picked = await pickScopedDirectory();
    if (picked) setTargetDir(picked);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim().length < 2) {
      setFormError("Describe a desktop, file, or browser task before running.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await onStartTask(
        prompt.trim(),
        targetDir.trim() || undefined,
        dryRunOnly,
        selectedProvider || undefined,
        attachedApp.trim() || undefined,
        attachedUrl.trim() || undefined
      );
      setPrompt("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not start task.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Command Center</h1>
          <p className="page-subtitle">
            Your computer. Powered by intelligence. Plan, verify, and approve real desktop, file,
            and browser operations from one workspace.
          </p>
        </div>
        <div className="flex-row flex-wrap">
          <button
            type="button"
            className="btn"
            disabled={submitting}
            onClick={() => void onRunExternalAppDemo()}
          >
            <AppWindow size={15} aria-hidden="true" />
            <span>External App Demo</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={submitting}
            onClick={() => void onRunFlagshipDemo()}
          >
            <Play size={15} aria-hidden="true" />
            <span>Run Flagship Folder Demo</span>
          </button>
        </div>
      </div>

      <div className="home-composer-grid">
        <section className="panel panel-composer" aria-label="Natural language task composer">
          <div className="panel-header">
            <h2 className="panel-title">Start an Operator Task</h2>
            <div className="flex-row flex-wrap">
              <label htmlFor="home-model-select" className="visually-hidden">
                Planner model provider
              </label>
              <select
                id="home-model-select"
                className="select"
                style={{ width: "auto", minHeight: 30, padding: "2px 10px", fontSize: 12.5 }}
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
              >
                <option value="">Planner: Auto (Local-first)</option>
                {configuredProviders.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
              <StatusTag
                tone={settings.privacy_mode === "local_only" ? "success" : "accent"}
                kind="shield"
                label={settings.privacy_mode === "local_only" ? "Local-only" : "Cloud-assisted"}
              />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="list-stack" style={{ gap: 14 }} noValidate>
            <div className="field">
              <label htmlFor="home-command-input" className="field-label">
                Task instruction
              </label>
              <textarea
                id="home-command-input"
                className="textarea"
                placeholder="Example: Organize the files in my Downloads folder by category, identify possible duplicates, and generate an Excel report without deleting anything."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                aria-invalid={formError ? "true" : undefined}
                aria-describedby={formError ? "home-command-error" : "home-command-hint"}
              />
              <span id="home-command-hint" className="field-hint">
                File mutations, app launches, and external URLs pause for explicit dry-run
                approval.
              </span>
              {formError && (
                <p id="home-command-error" role="alert" style={{ color: "var(--status-danger-text)" }}>
                  {formError}
                </p>
              )}
            </div>

            <div className="field">
              <label htmlFor="home-scope-dir" className="field-label">
                Scoped target directory (optional)
              </label>
              <div className="flex-row">
                <input
                  id="home-scope-dir"
                  className="input mono"
                  type="text"
                  placeholder={demoDirectory || "~/Downloads"}
                  value={targetDir}
                  onChange={(e) => setTargetDir(e.target.value)}
                />
                <button type="button" className="btn" onClick={() => void handleBrowse()}>
                  <FolderOpen size={15} aria-hidden="true" />
                  <span>Browse</span>
                </button>
                <button
                  type="button"
                  className="btn"
                  aria-expanded={showContextBar}
                  onClick={() => setShowContextBar((v) => !v)}
                >
                  <span>Attach Context</span>
                </button>
              </div>
            </div>

            {showContextBar && (
              <div className="panel-subtle two-col" style={{ gap: 12 }}>
                <div className="field">
                  <label htmlFor="ctx-app" className="text-sm flex-row">
                    <AppWindow size={13} aria-hidden="true" />
                    <span>Target Desktop App</span>
                  </label>
                  <select
                    id="ctx-app"
                    className="select"
                    value={attachedApp}
                    onChange={(e) => setAttachedApp(e.target.value)}
                  >
                    <option value="">None attached</option>
                    {runningApps.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="ctx-url" className="text-sm flex-row">
                    <Globe size={13} aria-hidden="true" />
                    <span>Reference URL</span>
                  </label>
                  <input
                    id="ctx-url"
                    className="input mono"
                    type="url"
                    placeholder="https://example.com"
                    value={attachedUrl}
                    onChange={(e) => setAttachedUrl(e.target.value)}
                  />
                </div>
              </div>
            )}

            <div className="flex-row justify-between flex-wrap">
              <label className="flex-row text-sm">
                <input
                  type="checkbox"
                  checked={dryRunOnly}
                  onChange={(e) => setDryRunOnly(e.target.checked)}
                />
                <span>Dry-run inspection only (do not move files)</span>
              </label>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                <TerminalSquare size={15} aria-hidden="true" />
                <span>{submitting ? "Planning..." : "Plan & Execute"}</span>
              </button>
            </div>
          </form>

          <div className="list-stack" style={{ gap: 8 }}>
            <div className="field-label">Suggested Actions</div>
            <div className="flex-row flex-wrap">
              {SUGGESTED_ACTIONS.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className="btn"
                  style={{ fontSize: 12.5, minHeight: 32 }}
                  onClick={() => setPrompt(item.prompt)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </section>

        <aside className="panel" aria-label="Device and model readiness">
          <div className="panel-header">
            <h2 className="panel-title">Device &amp; Runtime Status</h2>
            <StatusTag tone="success" kind="check" label="Engine online" />
          </div>

          {profile ? (
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "auto minmax(0, 1fr)",
                gap: "8px 14px",
                fontSize: 13,
              }}
            >
              <dt className="text-muted">System</dt>
              <dd className="tabular">
                {profile.os_name} {profile.os_version} ({profile.arch})
              </dd>
              <dt className="text-muted">Hardware</dt>
              <dd className="tabular">
                {profile.cpu_cores} logical cores, {profile.memory_total_gb} GB RAM
              </dd>
              <dt className="text-muted">Material</dt>
              <dd>{profile.glass_material.replace(/_/g, " ")}</dd>
              <dt className="text-muted">Display</dt>
              <dd>{profile.display_server}</dd>
            </dl>
          ) : (
            <p className="text-muted text-sm">Loading hardware and capability profile...</p>
          )}

          <div className="panel-subtle list-stack" style={{ gap: 8 }}>
            <div className="flex-row justify-between">
              <span className="field-label">Model Availability</span>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ minHeight: 28, paddingInline: 8 }}
                onClick={onNavigateModels}
              >
                Configure
              </button>
            </div>
            {configuredProviders.length > 0 ? (
              configuredProviders.map((p) => (
                <div key={p.id} className="flex-row justify-between text-sm">
                  <span>{p.label}</span>
                  <StatusTag
                    tone={p.reachable ? "success" : "accent"}
                    label={p.reachable ? "Reachable" : "Key stored"}
                  />
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">
                No external AI provider configured yet. Local deterministic planner is active for
                file, report, browser, and native app operations.
              </p>
            )}
          </div>

          {activeTask && (
            <div className="panel-subtle list-stack" style={{ gap: 8 }}>
              <div className="flex-row justify-between">
                <span className="field-label">Active Execution</span>
                <StatusTag tone="warning" kind="clock" label={activeTask.status.replace(/_/g, " ")} />
              </div>
              <div className="text-sm">{activeTask.title}</div>
              <button
                type="button"
                className="btn"
                onClick={() => onOpenTask(activeTask.id)}
              >
                Open in Operator
              </button>
            </div>
          )}

          <div className="flex-row text-sm text-muted">
            <ShieldCheck size={15} aria-hidden="true" />
            <span>Deny-by-default permissions active on all mutations.</span>
          </div>
        </aside>
      </div>

      <div className="home-lower-grid">
        <section className="panel" aria-label="Recent tasks">
          <div className="panel-header">
            <h2 className="panel-title">Recent Executions</h2>
            <span className="text-sm text-muted tabular">{tasks.length} recorded locally</span>
          </div>
          {tasks.length === 0 ? (
            <div className="state-box">
              <strong>No tasks executed yet.</strong>
              <p className="text-sm text-muted">
                Run the Flagship Folder Demo or External App Demo above to inspect verified
                execution history here.
              </p>
            </div>
          ) : (
            <div className="list-stack">
              {tasks.slice(0, 5).map((task) => (
                <button
                  key={task.id}
                  type="button"
                  className="list-row row-button"
                  onClick={() => onOpenTask(task.id)}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 580 }} className="truncate">
                      {task.title}
                    </div>
                    <div className="text-sm text-muted tabular">
                      {new Date(task.created_at).toLocaleString()}
                      {task.duration_ms != null ? ` | ${task.duration_ms} ms` : ""}
                    </div>
                  </div>
                  <StatusTag
                    tone={
                      task.status === "completed"
                        ? "success"
                        : task.status === "failed" || task.status === "cancelled"
                          ? "danger"
                          : task.status === "awaiting_approval"
                            ? "warning"
                            : "accent"
                    }
                    label={task.status.replace(/_/g, " ")}
                  />
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel" aria-label="Saved workflows">
          <div className="panel-header">
            <h2 className="panel-title">Saved Workflows</h2>
            <button type="button" className="btn btn-ghost" onClick={onNavigateStudio}>
              <GitBranch size={15} aria-hidden="true" />
              <span>Open Studio</span>
            </button>
          </div>
          {workflows.length === 0 ? (
            <div className="state-box">
              <strong>No workflows saved.</strong>
              <p className="text-sm text-muted">
                Create a reusable graph in Workflow Studio or record one in Teach Mode.
              </p>
            </div>
          ) : (
            <div className="list-stack">
              {workflows.slice(0, 5).map((wf) => (
                <div key={wf.id} className="list-row">
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 580 }} className="truncate">
                      {wf.name}
                    </div>
                    <div className="text-sm text-muted">
                      v{wf.version} | {wf.nodes.length} nodes | {wf.source.replace("_", " ")}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onRunWorkflow(wf)}
                  >
                    Run
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
};
