import React, { useState } from "react";
import { ChevronDown, OctagonX, Play, ShieldAlert, TerminalSquare } from "lucide-react";
import type { TaskRun } from "@omnidesk/shared-schemas";
import { BrandMark } from "./BrandMark";
import { StatusTag } from "./StatusTag";

interface FloatingAssistantProps {
  activeTask: TaskRun | null;
  onStartTask: (prompt: string) => Promise<void>;
  onOpenOperator: () => void;
  onOpenApproval: () => void;
  onEmergencyStop: () => Promise<void>;
}

export const FloatingAssistant: React.FC<FloatingAssistantProps> = ({
  activeTask,
  onStartTask,
  onOpenOperator,
  onOpenApproval,
  onEmergencyStop,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [quickPrompt, setQuickPrompt] = useState("");
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (quickPrompt.trim().length < 2) return;
    setSending(true);
    try {
      await onStartTask(quickPrompt.trim());
      setQuickPrompt("");
      setExpanded(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="floating-assistant-wrap" aria-label="Floating OmniDesk Assistant">
      {expanded && (
        <section className="floating-assistant-card" aria-label="Quick assistant panel">
          <div className="flex-row justify-between">
            <div className="flex-row">
              <BrandMark size={20} />
              <strong style={{ fontSize: 13.5 }}>OmniDesk Assistant</strong>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-label="Minimize floating assistant"
              onClick={() => setExpanded(false)}
            >
              <ChevronDown size={16} aria-hidden="true" />
            </button>
          </div>

          {activeTask ? (
            <div className="panel-subtle list-stack" style={{ gap: 8, padding: 10 }}>
              <div className="flex-row justify-between">
                <span className="text-sm" style={{ fontWeight: 600 }}>
                  {activeTask.title}
                </span>
                <StatusTag
                  tone={activeTask.status === "awaiting_approval" ? "warning" : "accent"}
                  label={activeTask.status.replace(/_/g, " ")}
                />
              </div>
              <div className="flex-row flex-wrap">
                {activeTask.status === "awaiting_approval" ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ minHeight: 30, fontSize: 12 }}
                    onClick={() => {
                      setExpanded(false);
                      onOpenApproval();
                    }}
                  >
                    <ShieldAlert size={13} aria-hidden="true" />
                    <span>Review Approval</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn"
                    style={{ minHeight: 30, fontSize: 12 }}
                    onClick={() => {
                      setExpanded(false);
                      onOpenOperator();
                    }}
                  >
                    <TerminalSquare size={13} aria-hidden="true" />
                    <span>View Timeline</span>
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ minHeight: 30, fontSize: 12 }}
                  onClick={() => void onEmergencyStop()}
                >
                  <OctagonX size={13} aria-hidden="true" />
                  <span>Stop</span>
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted">
              Run a quick command from any workspace view. Modifying actions always require
              approval.
            </p>
          )}

          <form onSubmit={handleSubmit} className="flex-row">
            <label htmlFor="floating-assistant-input" className="visually-hidden">
              Quick OmniDesk task
            </label>
            <input
              id="floating-assistant-input"
              className="input"
              type="text"
              placeholder="Ask OmniDesk to operate a task..."
              value={quickPrompt}
              onChange={(e) => setQuickPrompt(e.target.value)}
            />
            <button
              type="submit"
              className="btn btn-primary btn-icon"
              aria-label="Run quick task"
              disabled={sending || quickPrompt.trim().length < 2}
            >
              <Play size={14} aria-hidden="true" />
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        className="floating-assistant-pill"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        <BrandMark size={18} />
        <span>
          {activeTask
            ? activeTask.status === "awaiting_approval"
              ? "Approval Waiting"
              : "Operator Active"
            : "Assistant"}
        </span>
      </button>
    </div>
  );
};
