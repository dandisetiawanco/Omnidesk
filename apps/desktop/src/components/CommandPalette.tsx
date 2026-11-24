import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { Command, OctagonX, Play, Search, X } from "lucide-react";
import type { TaskRun, WorkflowDefinition } from "@omnidesk/shared-schemas";
import type { SectionId } from "./Sidebar";
import { attachLightDismissFallback, closeDialogWithTransition } from "../lib/dialog";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (section: SectionId) => void;
  onStartPrompt: (prompt: string) => void;
  onRunWorkflow: (wf: WorkflowDefinition) => void;
  onRunFlagshipDemo: () => void;
  onEmergencyStop: () => void;
  workflows: WorkflowDefinition[];
  activeTask: TaskRun | null;
}

const SECTIONS: Array<{ id: SectionId; label: string; hint: string }> = [
  { id: "home", label: "Home: Command Center", hint: "Start natural-language tasks" },
  { id: "operator", label: "Operator", hint: "Live execution plan and approvals" },
  { id: "live", label: "Live Workspace", hint: "Opt-in desktop context and snapshots" },
  { id: "workflows", label: "Workflow Studio", hint: "Visual node automation editor" },
  { id: "teach", label: "Teach Mode", hint: "Record demonstrations into workflows" },
  { id: "activity", label: "Activity", hint: "Execution history, audit log, and undo" },
  { id: "models", label: "Models", hint: "Configure Ollama, OpenAI, Gemini, Claude" },
  { id: "settings", label: "Settings", hint: "Appearance, privacy, permissions, capabilities" },
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  open,
  onClose,
  onNavigate,
  onStartPrompt,
  onRunWorkflow,
  onRunFlagshipDemo,
  onEmergencyStop,
  workflows,
  activeTask,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      setQuery("");
      dlg.showModal();
      requestAnimationFrame(() => inputRef.current?.focus());
    } else if (!open && dlg.open) {
      void closeDialogWithTransition(dlg);
    }
  }, [open]);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    const onCancel = (e: Event) => {
      e.preventDefault();
      onClose();
    };
    dlg.addEventListener("cancel", onCancel);
    const cleanupOutside = attachLightDismissFallback(dlg, onClose);
    return () => {
      dlg.removeEventListener("cancel", onCancel);
      cleanupOutside();
    };
  }, [onClose]);

  const lower = query.trim().toLowerCase();

  const matchingSections = useMemo(
    () =>
      SECTIONS.filter(
        (s) => !lower || s.label.toLowerCase().includes(lower) || s.hint.toLowerCase().includes(lower)
      ),
    [lower]
  );

  const matchingWorkflows = useMemo(
    () =>
      workflows.filter(
        (w) =>
          !lower ||
          w.name.toLowerCase().includes(lower) ||
          w.description.toLowerCase().includes(lower)
      ),
    [workflows, lower]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    onStartPrompt(query.trim());
    onClose();
  };

  return (
    <dialog
      ref={dialogRef}
      className="glass-dialog"
      aria-labelledby={titleId}
      {...({ closedby: "any" } as Record<string, string>)}
    >
      <div className="dialog-header">
        <div className="flex-row">
          <Command size={17} aria-hidden="true" />
          <h2 id={titleId} className="panel-title">
            Command Palette
          </h2>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label="Close command palette"
          onClick={onClose}
        >
          <X size={17} aria-hidden="true" />
        </button>
      </div>

      <div className="dialog-body">
        <form onSubmit={handleSubmit} className="field">
          <label htmlFor="palette-input" className="visually-hidden">
            Type a command, task, or section name
          </label>
          <div className="flex-row">
            <Search size={16} aria-hidden="true" />
            <input
              ref={inputRef}
              id="palette-input"
              className="input"
              type="search"
              placeholder="Run an AI task or jump to a workflow or section..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {query.trim().length > 2 && (
            <button type="submit" className="btn btn-primary" style={{ alignSelf: "flex-start" }}>
              <Play size={14} aria-hidden="true" />
              <span>Run Task: &quot;{query.trim().slice(0, 48)}&quot;</span>
            </button>
          )}
        </form>

        {activeTask && (
          <div className="panel-subtle flex-row justify-between flex-wrap">
            <div>
              <div className="field-label">Active Execution: {activeTask.title}</div>
              <div className="text-sm text-muted">Status: {activeTask.status.replace(/_/g, " ")}</div>
            </div>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                onEmergencyStop();
                onClose();
              }}
            >
              <OctagonX size={15} aria-hidden="true" />
              <span>Emergency Stop</span>
            </button>
          </div>
        )}

        <div className="list-stack">
          <div className="field-label">Quick Actions</div>
          <button
            type="button"
            className="list-row row-button"
            onClick={() => {
              onRunFlagshipDemo();
              onClose();
            }}
          >
            <div>
              <div style={{ fontWeight: 580 }}>Run Flagship Downloads Organization Demo</div>
              <div className="text-sm text-muted">
                Creates a safe sandbox folder with duplicates, plans moves, and exports an Excel workbook
              </div>
            </div>
            <kbd className="kbd-cap">Demo</kbd>
          </button>
        </div>

        {matchingWorkflows.length > 0 && (
          <div className="list-stack">
            <div className="field-label">Saved Workflows</div>
            {matchingWorkflows.slice(0, 4).map((wf) => (
              <button
                key={wf.id}
                type="button"
                className="list-row row-button"
                onClick={() => {
                  onRunWorkflow(wf);
                  onClose();
                }}
              >
                <div>
                  <div style={{ fontWeight: 580 }}>{wf.name}</div>
                  <div className="text-sm text-muted">v{wf.version} ({wf.source.replace("_", " ")})</div>
                </div>
                <span className="text-sm" style={{ color: "var(--accent-text)", fontWeight: 600 }}>
                  Run
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="list-stack">
          <div className="field-label">Sections</div>
          {matchingSections.map((sec) => (
            <button
              key={sec.id}
              type="button"
              className="list-row row-button"
              onClick={() => {
                onNavigate(sec.id);
                onClose();
              }}
            >
              <div>
                <div style={{ fontWeight: 560 }}>{sec.label}</div>
                <div className="text-sm text-muted">{sec.hint}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </dialog>
  );
};
