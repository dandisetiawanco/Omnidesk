import React, { useEffect, useState } from "react";
import { RefreshCw, Trash2, Undo2 } from "lucide-react";
import type { TaskRun } from "@omnidesk/shared-schemas";
import { api, type AuditEntry } from "../lib/api";
import { StatusTag } from "../components/StatusTag";

interface ActivityViewProps {
  tasks: TaskRun[];
  onRefresh: () => Promise<void>;
  onOpenTask: (taskId: string) => void;
  onUndoTask: (taskId: string) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  onClearHistory: () => Promise<void>;
}

export const ActivityView: React.FC<ActivityViewProps> = ({
  tasks,
  onRefresh,
  onOpenTask,
  onUndoTask,
  onDeleteTask,
  onClearHistory,
}) => {
  const [tab, setTab] = useState<"tasks" | "audit">("tasks");
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const loadAudit = async () => {
    setLoadingAudit(true);
    try {
      setAudit(await api.listAudit());
    } finally {
      setLoadingAudit(false);
    }
  };

  useEffect(() => {
    if (tab === "audit") {
      void loadAudit();
    }
  }, [tab]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Activity</h1>
          <p className="page-subtitle">
            Local auditable execution history, approval decisions, and verifiable recovery actions.
          </p>
        </div>
        <div className="flex-row flex-wrap">
          <button
            type="button"
            className="btn"
            onClick={() => {
              void onRefresh();
              if (tab === "audit") void loadAudit();
            }}
          >
            <RefreshCw size={15} aria-hidden="true" />
            <span>Refresh</span>
          </button>
          {confirmClear ? (
            <>
              <button type="button" className="btn" onClick={() => setConfirmClear(false)}>
                Keep History
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={async () => {
                  await onClearHistory();
                  setAudit([]);
                  setConfirmClear(false);
                }}
              >
                Confirm Delete Local History
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={tasks.length === 0 && audit.length === 0}
              onClick={() => setConfirmClear(true)}
            >
              <Trash2 size={15} aria-hidden="true" />
              <span>Clear Local History</span>
            </button>
          )}
        </div>
      </div>

      <div role="tablist" aria-label="Activity views" className="flex-row">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "tasks"}
          className={tab === "tasks" ? "btn btn-primary" : "btn"}
          onClick={() => setTab("tasks")}
        >
          Executed Tasks ({tasks.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "audit"}
          className={tab === "audit" ? "btn btn-primary" : "btn"}
          onClick={() => setTab("audit")}
        >
          Security &amp; Permission Audit Log
        </button>
      </div>

      {tab === "tasks" ? (
        tasks.length === 0 ? (
          <div className="state-box">
            <strong>No local execution history.</strong>
            <p className="text-sm text-muted">
              Every completed, paused, or cancelled task is saved to your local SQLite database
              and can be inspected or deleted here.
            </p>
          </div>
        ) : (
          <div className="table-wrap panel" style={{ padding: 0 }}>
            <table className="data-table">
              <caption className="visually-hidden">Local task execution history</caption>
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">Status</th>
                  <th scope="col">Timestamp</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Recovery</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div style={{ fontWeight: 580 }}>{task.title}</div>
                      <div className="text-sm text-muted">
                        {task.summary || task.error || `${task.steps.length} planned step(s)`}
                      </div>
                    </td>
                    <td>
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
                    </td>
                    <td className="tabular text-sm">
                      {new Date(task.created_at).toLocaleString()}
                    </td>
                    <td className="tabular text-sm">
                      {task.duration_ms != null ? `${task.duration_ms} ms` : "In progress"}
                    </td>
                    <td className="text-sm">
                      {task.undone ? (
                        <StatusTag tone="neutral" label="Rolled back" />
                      ) : task.can_undo ? (
                        <button
                          type="button"
                          className="btn"
                          style={{ minHeight: 30, fontSize: 12 }}
                          onClick={() => void onUndoTask(task.id)}
                        >
                          <Undo2 size={13} aria-hidden="true" />
                          <span>Undo</span>
                        </button>
                      ) : (
                        <span className="text-muted">Read-only / N/A</span>
                      )}
                    </td>
                    <td>
                      <div className="flex-row">
                        <button
                          type="button"
                          className="btn"
                          style={{ minHeight: 30, fontSize: 12 }}
                          onClick={() => onOpenTask(task.id)}
                        >
                          Inspect
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-icon"
                          aria-label={`Delete history entry ${task.title}`}
                          onClick={() => void onDeleteTask(task.id)}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : loadingAudit ? (
        <div className="state-box">
          <strong>Loading local audit log...</strong>
        </div>
      ) : audit.length === 0 ? (
        <div className="state-box">
          <strong>No security audit events recorded yet.</strong>
          <p className="text-sm text-muted">
            Permission approvals, provider key updates, Teach Mode recordings, and rollbacks are
            logged locally here.
          </p>
        </div>
      ) : (
        <div className="table-wrap panel" style={{ padding: 0 }}>
          <table className="data-table">
            <caption className="visually-hidden">Security and permission audit log</caption>
            <thead>
              <tr>
                <th scope="col">Timestamp</th>
                <th scope="col">Category</th>
                <th scope="col">Action</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((entry) => (
                <tr key={entry.id}>
                  <td className="tabular text-sm">{new Date(entry.timestamp).toLocaleString()}</td>
                  <td>
                    <StatusTag tone="neutral" label={entry.category} />
                  </td>
                  <td className="mono text-sm">{entry.action}</td>
                  <td className="text-sm">{entry.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};
