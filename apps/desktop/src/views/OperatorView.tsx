import React, { useState } from "react";
import {
  FileSpreadsheet,
  OctagonX,
  Pause,
  Play,
  ShieldAlert,
  Square,
  Undo2,
} from "lucide-react";
import type { TaskRun } from "@omnidesk/shared-schemas";
import { StatusTag } from "../components/StatusTag";

interface OperatorViewProps {
  tasks: TaskRun[];
  selectedTaskId: string | null;
  onSelectTask: (id: string) => void;
  onStartTask: (prompt: string, targetDir?: string) => Promise<void>;
  onOpenApproval: (task: TaskRun) => void;
  onPause: (taskId: string) => Promise<void>;
  onResume: (taskId: string) => Promise<void>;
  onCancel: (taskId: string) => Promise<void>;
  onUndo: (taskId: string) => Promise<void>;
  onEmergencyStop: () => Promise<void>;
  onRunFlagshipDemo: () => Promise<void>;
}

export const OperatorView: React.FC<OperatorViewProps> = ({
  tasks,
  selectedTaskId,
  onSelectTask,
  onStartTask,
  onOpenApproval,
  onPause,
  onResume,
  onCancel,
  onUndo,
  onEmergencyStop,
  onRunFlagshipDemo,
}) => {
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const selected =
    tasks.find((t) => t.id === selectedTaskId) ?? tasks[0] ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      await onStartTask(prompt.trim());
      setPrompt("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Operator</h1>
          <p className="page-subtitle">
            Structured execution plans, live step verification, explicit permission gates, and
            journaled recovery controls.
          </p>
        </div>
        <div className="flex-row">
          <button type="button" className="btn" onClick={() => void onRunFlagshipDemo()}>
            Run Flagship Demo
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void onEmergencyStop()}>
            <OctagonX size={15} aria-hidden="true" />
            <span>Emergency Stop</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="panel">
        <div className="field">
          <label htmlFor="operator-prompt" className="field-label">
            New Operator Instruction
          </label>
          <div className="flex-row">
            <input
              id="operator-prompt"
              className="input"
              type="text"
              placeholder="Enter a task (file organization, document search, webpage inspection, app launch)..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button type="submit" className="btn btn-primary" disabled={submitting || !prompt.trim()}>
              <Play size={15} aria-hidden="true" />
              <span>{submitting ? "Starting..." : "Execute"}</span>
            </button>
          </div>
        </div>
      </form>

      {!selected ? (
        <div className="state-box">
          <strong>No active or recorded executions yet.</strong>
          <p className="text-sm text-muted">
            Submit an instruction above or launch the Flagship Downloads Organization Demo to
            inspect the real-time execution plan and approval timeline.
          </p>
          <button type="button" className="btn btn-primary" onClick={() => void onRunFlagshipDemo()}>
            Run Flagship Folder Demo
          </button>
        </div>
      ) : (
        <div className="operator-grid">
          <section className="panel" aria-label="Execution plan and step timeline">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">{selected.title}</h2>
                <p className="text-sm text-muted">
                  Planner: <span className="mono">{selected.planner_source}</span>
                  {selected.duration_ms != null ? ` | Duration: ${selected.duration_ms} ms` : ""}
                </p>
              </div>
              <div className="flex-row flex-wrap">
                <StatusTag
                  tone={
                    selected.status === "completed"
                      ? "success"
                      : selected.status === "awaiting_approval"
                        ? "warning"
                        : selected.status === "failed" || selected.status === "cancelled"
                          ? "danger"
                          : "accent"
                  }
                  label={selected.status.replace(/_/g, " ")}
                />
                {selected.status === "running" && (
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onPause(selected.id)}
                  >
                    <Pause size={14} aria-hidden="true" />
                    <span>Pause</span>
                  </button>
                )}
                {selected.status === "paused" && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void onResume(selected.id)}
                  >
                    <Play size={14} aria-hidden="true" />
                    <span>Resume</span>
                  </button>
                )}
                {["running", "paused", "awaiting_approval"].includes(selected.status) && (
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => void onCancel(selected.id)}
                  >
                    <Square size={14} aria-hidden="true" />
                    <span>Stop</span>
                  </button>
                )}
                {selected.can_undo && !selected.undone && (
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onUndo(selected.id)}
                  >
                    <Undo2 size={14} aria-hidden="true" />
                    <span>Undo File Changes</span>
                  </button>
                )}
              </div>
            </div>

            {selected.pending_approval && selected.pending_approval.status === "pending" && (
              <div
                className="panel-subtle flex-row justify-between flex-wrap"
                style={{ borderColor: "var(--status-warning-text)" }}
              >
                <div className="flex-row">
                  <ShieldAlert size={18} aria-hidden="true" />
                  <div>
                    <div style={{ fontWeight: 620 }}>
                      Approval required: {selected.pending_approval.title}
                    </div>
                    <div className="text-sm text-muted">{selected.pending_approval.summary}</div>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => onOpenApproval(selected)}
                >
                  Review &amp; Decide
                </button>
              </div>
            )}

            {selected.summary && (
              <div className="panel-subtle">
                <strong>Result Summary:</strong> {selected.summary}
              </div>
            )}

            {selected.error && (
              <div
                className="panel-subtle"
                role="alert"
                style={{
                  background: "var(--status-danger-bg)",
                  color: "var(--status-danger-text)",
                }}
              >
                <strong>Execution Note:</strong> {selected.error}
              </div>
            )}

            <ol
              className="list-stack"
              style={{ listStyle: "none", padding: 0, gap: 10 }}
              aria-label="Execution steps"
            >
              {selected.steps.map((step) => (
                <li key={step.id} className="panel-subtle list-stack" style={{ gap: 8 }}>
                  <div className="flex-row justify-between flex-wrap">
                    <div className="flex-row">
                      <span className="kbd-cap tabular">{step.index + 1}</span>
                      <strong>{step.title}</strong>
                    </div>
                    <div className="flex-row">
                      <StatusTag
                        tone="neutral"
                        label={step.risk.replace(/_/g, " ")}
                      />
                      <StatusTag
                        tone={
                          step.status === "completed"
                            ? "success"
                            : step.status === "awaiting_approval"
                              ? "warning"
                              : step.status === "failed" || step.status === "cancelled"
                                ? "danger"
                                : "accent"
                        }
                        label={step.status.replace(/_/g, " ")}
                      />
                    </div>
                  </div>
                  <div className="text-sm text-muted mono">
                    Tool: {step.tool} | {step.reversible ? "Reversible" : "Non-reversible"}
                  </div>
                  {step.error && (
                    <div className="text-sm" style={{ color: "var(--status-danger-text)" }}>
                      {step.error}
                    </div>
                  )}
                  {step.result && (
                    <details>
                      <summary className="text-sm" style={{ fontWeight: 560 }}>
                        Verified Output
                      </summary>
                      <pre
                        className="mono text-sm"
                        style={{
                          marginTop: 8,
                          padding: 10,
                          borderRadius: "var(--radius-sm)",
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border-subtle)",
                          overflowX: "auto",
                          maxHeight: 240,
                        }}
                      >
                        {JSON.stringify(step.result, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              ))}
            </ol>

            {selected.artifacts.length > 0 && (
              <div className="list-stack">
                <h3 className="field-label">Generated Artifacts</h3>
                {selected.artifacts.map((art) => (
                  <div key={art.path} className="list-row">
                    <div className="flex-row" style={{ minWidth: 0 }}>
                      <FileSpreadsheet size={17} aria-hidden="true" />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600 }}>{art.label}</div>
                        <div className="mono text-sm text-muted" style={{ wordBreak: "break-all" }}>
                          {art.path}
                        </div>
                      </div>
                    </div>
                    <StatusTag tone="success" kind="check" label={art.kind.toUpperCase()} />
                  </div>
                ))}
              </div>
            )}
          </section>

          <aside className="panel" aria-label="Task queue and history">
            <h2 className="panel-title">Executions</h2>
            <div className="list-stack">
              {tasks.map((task) => (
                <button
                  key={task.id}
                  type="button"
                  className="list-row row-button"
                  aria-current={task.id === selected.id ? "true" : undefined}
                  style={{
                    borderColor:
                      task.id === selected.id ? "var(--accent-solid)" : "var(--border-subtle)",
                  }}
                  onClick={() => onSelectTask(task.id)}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 580 }} className="truncate">
                      {task.title}
                    </div>
                    <div className="text-sm text-muted tabular">
                      {task.steps.length} steps | {task.status.replace(/_/g, " ")}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </aside>
        </div>
      )}
    </>
  );
};
