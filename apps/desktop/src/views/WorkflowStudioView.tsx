import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Download,
  Play,
  Plus,
  Redo2,
  Save,
  Trash2,
  Undo2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { WorkflowDefinition, WorkflowNode } from "@omnidesk/shared-schemas";
import { StatusTag } from "../components/StatusTag";

interface WorkflowStudioViewProps {
  workflows: WorkflowDefinition[];
  initialWorkflowId: string | null;
  onSaveWorkflow: (wf: WorkflowDefinition) => Promise<WorkflowDefinition>;
  onDeleteWorkflow: (id: string) => Promise<void>;
  onRunWorkflow: (wf: WorkflowDefinition, vars: Record<string, string>, dryRun: boolean) => Promise<void>;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

const NODE_TOOLS = [
  "filesystem.inspect_directory",
  "filesystem.plan_organization",
  "filesystem.apply_organization",
  "spreadsheet.generate_report",
  "filesystem.search_documents",
  "documents.generate_summary",
  "browser.navigate_and_extract",
  "apps.launch",
];

const NODE_KINDS: Array<{ type: WorkflowNode["type"]; label: string }> = [
  { type: "trigger", label: "Trigger" },
  { type: "action", label: "Action" },
  { type: "condition", label: "Condition" },
  { type: "loop", label: "Bounded Loop" },
  { type: "approval", label: "Human Approval" },
  { type: "variable", label: "Variable" },
  { type: "error_handler", label: "Error Handler" },
];

export const WorkflowStudioView: React.FC<WorkflowStudioViewProps> = ({
  workflows,
  initialWorkflowId,
  onSaveWorkflow,
  onDeleteWorkflow,
  onRunWorkflow,
  onNotify,
}) => {
  const [selectedWfId, setSelectedWfId] = useState<string>(
    initialWorkflowId || workflows[0]?.id || ""
  );
  const [draft, setDraft] = useState<WorkflowDefinition | null>(null);
  const [history, setHistory] = useState<WorkflowDefinition[]>([]);
  const [future, setFuture] = useState<WorkflowDefinition[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.75);
  const [pan, setPan] = useState({ x: 8, y: 8 });
  const [varInputs, setVarInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const draggingNodeRef = useRef<{ id: string; startX: number; startY: number; origX: number; origY: number } | null>(null);
  const panningRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);

  useEffect(() => {
    const chosen =
      workflows.find((w) => w.id === (initialWorkflowId || selectedWfId)) ?? workflows[0] ?? null;
    if (chosen) {
      setSelectedWfId(chosen.id);
      setDraft(structuredClone(chosen));
      setHistory([]);
      setFuture([]);
      setSelectedNodeId(chosen.nodes[0]?.id ?? null);
      const defaults: Record<string, string> = {};
      for (const v of chosen.variables) defaults[v.name] = v.default_value;
      setVarInputs(defaults);
    }
  }, [workflows, initialWorkflowId]);

  const commitDraft = useCallback(
    (updater: (current: WorkflowDefinition) => WorkflowDefinition) => {
      setDraft((prev) => {
        if (!prev) return prev;
        const next = updater(structuredClone(prev));
        setHistory((h) => [...h.slice(-29), prev]);
        setFuture([]);
        return next;
      });
    },
    []
  );

  const handleUndo = useCallback(() => {
    setHistory((h) => {
      if (h.length === 0 || !draft) return h;
      const previous = h[h.length - 1];
      setFuture((f) => [draft, ...f]);
      setDraft(previous);
      return h.slice(0, -1);
    });
  }, [draft]);

  const handleRedo = useCallback(() => {
    setFuture((f) => {
      if (f.length === 0 || !draft) return f;
      const next = f[0];
      setHistory((h) => [...h, draft]);
      setDraft(next);
      return f.slice(1);
    });
  }, [draft]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        if (document.activeElement?.tagName === "INPUT" || document.activeElement?.tagName === "TEXTAREA") {
          return;
        }
        e.preventDefault();
        if (e.shiftKey) handleRedo();
        else handleUndo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleUndo, handleRedo]);

  const selectWorkflow = (wf: WorkflowDefinition) => {
    setSelectedWfId(wf.id);
    setDraft(structuredClone(wf));
    setHistory([]);
    setFuture([]);
    setSelectedNodeId(wf.nodes[0]?.id ?? null);
    const defaults: Record<string, string> = {};
    for (const v of wf.variables) defaults[v.name] = v.default_value;
    setVarInputs(defaults);
  };

  const createNewWorkflow = () => {
    const id = `wf-custom-${Date.now().toString(36)}`;
    const now = new Date().toISOString();
    const blank: WorkflowDefinition = {
      id,
      name: "Untitled Automation Workflow",
      description: "Custom multi-step workflow created in Workflow Studio.",
      version: 1,
      source: "manual",
      variables: [
        {
          name: "target_directory",
          default_value: "~/Downloads",
          description: "Scoped folder for file operations",
        },
      ],
      max_loop_iterations: 20,
      nodes: [
        {
          id: "n-trigger",
          type: "trigger",
          label: "Manual Trigger",
          x: 60,
          y: 120,
          config: {},
        },
        {
          id: "n-inspect",
          type: "action",
          label: "Inspect Scoped Folder",
          tool: "filesystem.inspect_directory",
          x: 330,
          y: 120,
          config: { directory: "{{target_directory}}" },
        },
      ],
      edges: [{ id: "e-init", source: "n-trigger", target: "n-inspect" }],
      created_at: now,
      updated_at: now,
    };
    setSelectedWfId(id);
    setDraft(blank);
    setHistory([]);
    setFuture([]);
    setSelectedNodeId("n-inspect");
    setVarInputs({ target_directory: "~/Downloads" });
  };

  const addNode = (kind: WorkflowNode["type"]) => {
    if (!draft) return;
    const id = `node-${Date.now().toString(36)}`;
    const last = draft.nodes[draft.nodes.length - 1];
    const newNode: WorkflowNode = {
      id,
      type: kind,
      label:
        kind === "approval"
          ? "Human Approval Gate"
          : kind === "loop"
            ? "Bounded Loop (max 10)"
            : kind === "condition"
              ? "Check Condition"
              : kind === "error_handler"
                ? "Error Recovery"
                : kind === "variable"
                  ? "Set Variable"
                  : kind === "trigger"
                    ? "Trigger"
                    : "New Action Step",
      tool: kind === "action" ? "filesystem.inspect_directory" : undefined,
      x: last ? Math.min(last.x + 240, 860) : 80,
      y: last ? (last.x > 640 ? last.y + 135 : last.y) : 120,
      config: kind === "action" ? { directory: "{{target_directory}}" } : {},
    };
    commitDraft((cur) => {
      cur.nodes.push(newNode);
      if (last) {
        cur.edges.push({ id: `e-${last.id}-${id}`, source: last.id, target: id });
      }
      return cur;
    });
    setSelectedNodeId(id);
  };

  const nudgeSelectedNode = (dx: number, dy: number) => {
    if (!selectedNodeId) return;
    commitDraft((cur) => {
      const target = cur.nodes.find((n) => n.id === selectedNodeId);
      if (target) {
        target.x = Math.max(16, Math.round(target.x + dx));
        target.y = Math.max(16, Math.round(target.y + dy));
      }
      return cur;
    });
  };

  const removeSelectedNode = () => {
    if (!selectedNodeId) return;
    commitDraft((cur) => {
      cur.nodes = cur.nodes.filter((n) => n.id !== selectedNodeId);
      cur.edges = cur.edges.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId);
      return cur;
    });
    setSelectedNodeId(null);
  };

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await onSaveWorkflow(draft);
      setDraft(structuredClone(saved));
      onNotify("Workflow saved", `${saved.name} is now at version v${saved.version}.`, "success");
    } catch (err) {
      onNotify("Save failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setSaving(false);
    }
  };

  const exportJson = () => {
    if (!draft) return;
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${draft.id}-v${draft.version}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const selectedNode = useMemo(
    () => draft?.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [draft, selectedNodeId]
  );

  const nodeMap = useMemo(() => {
    const map = new Map<string, WorkflowNode>();
    for (const n of draft?.nodes ?? []) map.set(n.id, n);
    return map;
  }, [draft]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Workflow Studio</h1>
          <p className="page-subtitle">
            Compose, version, and test reusable desktop automations with explicit approval gates
            and bounded loop safety.
          </p>
        </div>
        <div className="flex-row flex-wrap">
          <button type="button" className="btn" onClick={createNewWorkflow}>
            <Plus size={15} aria-hidden="true" />
            <span>New Workflow</span>
          </button>
          <button
            type="button"
            className="btn"
            disabled={!draft}
            onClick={exportJson}
          >
            <Download size={15} aria-hidden="true" />
            <span>Export JSON</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!draft || saving}
            onClick={() => void handleSave()}
          >
            <Save size={15} aria-hidden="true" />
            <span>{saving ? "Saving..." : "Save Version"}</span>
          </button>
        </div>
      </div>

      <div className="panel" style={{ padding: "12px 16px" }}>
        <div className="flex-row flex-wrap justify-between">
          <div className="flex-row flex-wrap">
            <label htmlFor="wf-picker" className="field-label">
              Workflow:
            </label>
            <select
              id="wf-picker"
              className="select"
              style={{ width: "auto", minWidth: 240 }}
              value={draft?.id ?? ""}
              onChange={(e) => {
                const found = workflows.find((w) => w.id === e.target.value);
                if (found) selectWorkflow(found);
              }}
            >
              {workflows.map((wf) => (
                <option key={wf.id} value={wf.id}>
                  {wf.name} (v{wf.version})
                </option>
              ))}
              {draft && !workflows.some((w) => w.id === draft.id) && (
                <option value={draft.id}>{draft.name} (unsaved)</option>
              )}
            </select>
            {draft && (
              <StatusTag tone="neutral" label={`v${draft.version} | ${draft.source.replace("_", " ")}`} />
            )}
          </div>

          <div className="flex-row flex-wrap">
            <button
              type="button"
              className="btn btn-icon"
              aria-label="Undo canvas edit"
              disabled={history.length === 0}
              onClick={handleUndo}
            >
              <Undo2 size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="btn btn-icon"
              aria-label="Redo canvas edit"
              disabled={future.length === 0}
              onClick={handleRedo}
            >
              <Redo2 size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="btn btn-icon"
              aria-label="Zoom out"
              onClick={() => setZoom((z) => Math.max(0.55, Number((z - 0.1).toFixed(2))))}
            >
              <ZoomOut size={15} aria-hidden="true" />
            </button>
            <span className="text-sm tabular" style={{ minWidth: 42, textAlign: "center" }}>
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              className="btn btn-icon"
              aria-label="Zoom in"
              onClick={() => setZoom((z) => Math.min(1.5, Number((z + 0.1).toFixed(2))))}
            >
              <ZoomIn size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setZoom(1);
                setPan({ x: 16, y: 16 });
              }}
            >
              Reset View
            </button>
          </div>
        </div>
      </div>

      {!draft ? (
        <div className="state-box">
          <strong>No workflow selected.</strong>
          <button type="button" className="btn btn-primary" onClick={createNewWorkflow}>
            Create First Workflow
          </button>
        </div>
      ) : (
        <div className="studio-grid">
          <section className="panel" aria-label="Visual workflow canvas">
            <div className="flex-row flex-wrap">
              <span className="field-label">Add node:</span>
              {NODE_KINDS.map((k) => (
                <button
                  key={k.type}
                  type="button"
                  className="btn"
                  style={{ minHeight: 30, fontSize: 12, paddingInline: 10 }}
                  onClick={() => addNode(k.type)}
                >
                  + {k.label}
                </button>
              ))}
            </div>

            <div
              className="canvas-viewport"
              onPointerDown={(e) => {
                if ((e.target as HTMLElement).closest(".wf-node")) return;
                panningRef.current = {
                  startX: e.clientX,
                  startY: e.clientY,
                  origX: pan.x,
                  origY: pan.y,
                };
              }}
              onPointerMove={(e) => {
                if (draggingNodeRef.current) {
                  const { id, startX, startY, origX, origY } = draggingNodeRef.current;
                  const nx = Math.max(12, Math.round(origX + (e.clientX - startX) / zoom));
                  const ny = Math.max(12, Math.round(origY + (e.clientY - startY) / zoom));
                  setDraft((prev) =>
                    prev
                      ? {
                          ...prev,
                          nodes: prev.nodes.map((n) => (n.id === id ? { ...n, x: nx, y: ny } : n)),
                        }
                      : prev
                  );
                } else if (panningRef.current) {
                  const { startX, startY, origX, origY } = panningRef.current;
                  setPan({ x: origX + (e.clientX - startX), y: origY + (e.clientY - startY) });
                }
              }}
              onPointerUp={() => {
                draggingNodeRef.current = null;
                panningRef.current = null;
              }}
            >
              <div
                className="canvas-stage"
                style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
              >
                <svg
                  width="1400"
                  height="800"
                  style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
                  aria-hidden="true"
                >
                  {draft.edges.map((edge) => {
                    const src = nodeMap.get(edge.source);
                    const dst = nodeMap.get(edge.target);
                    if (!src || !dst) return null;
                    const x1 = src.x + 214;
                    const y1 = src.y + 34;
                    const x2 = dst.x;
                    const y2 = dst.y + 34;
                    const midX = (x1 + x2) / 2;
                    return (
                      <g key={edge.id}>
                        <path
                          d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                          fill="none"
                          stroke="var(--border-control)"
                          strokeWidth="2"
                        />
                        {edge.label && (
                          <text
                            x={midX}
                            y={(y1 + y2) / 2 - 6}
                            fill="var(--text-secondary)"
                            fontSize="11"
                            textAnchor="middle"
                          >
                            {edge.label}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </svg>

                {draft.nodes.map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    className="wf-node"
                    data-kind={node.type}
                    data-selected={selectedNodeId === node.id ? "true" : "false"}
                    style={{ left: node.x, top: node.y }}
                    onClick={() => setSelectedNodeId(node.id)}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      setSelectedNodeId(node.id);
                      draggingNodeRef.current = {
                        id: node.id,
                        startX: e.clientX,
                        startY: e.clientY,
                        origX: node.x,
                        origY: node.y,
                      };
                    }}
                  >
                    <div className="text-sm text-muted" style={{ textTransform: "capitalize" }}>
                      {node.type.replace("_", " ")}
                    </div>
                    <div style={{ fontWeight: 600, marginTop: 2 }}>{node.label}</div>
                    {node.tool && (
                      <div className="mono text-sm text-muted truncate" style={{ marginTop: 4 }}>
                        {node.tool}
                      </div>
                    )}
                  </button>
                ))}
              </div>

              {/* Minimap overview */}
              <div className="minimap" aria-hidden="true">
                <svg width="140" height="76" viewBox="0 0 1100 500">
                  {draft.nodes.map((n) => (
                    <rect
                      key={n.id}
                      x={n.x}
                      y={n.y}
                      width="170"
                      height="52"
                      rx="10"
                      fill={selectedNodeId === n.id ? "var(--accent-solid)" : "var(--border-control)"}
                    />
                  ))}
                </svg>
              </div>
            </div>

            <div className="flex-row justify-between flex-wrap">
              <div className="flex-row flex-wrap">
                <button
                  type="button"
                  className="btn"
                  onClick={() => void onRunWorkflow(draft, varInputs, true)}
                >
                  <Play size={14} aria-hidden="true" />
                  <span>Test Dry-Run</span>
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void onRunWorkflow(draft, varInputs, false)}
                >
                  <Play size={14} aria-hidden="true" />
                  <span>Execute Workflow</span>
                </button>
              </div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void onDeleteWorkflow(draft.id)}
              >
                <Trash2 size={14} aria-hidden="true" />
                <span>Delete Workflow</span>
              </button>
            </div>
          </section>

          <aside className="panel" aria-label="Workflow and node inspector">
            <h2 className="panel-title">Inspector</h2>

            <div className="field">
              <label htmlFor="wf-name" className="field-label">
                Workflow Name
              </label>
              <input
                id="wf-name"
                className="input"
                value={draft.name}
                onChange={(e) => commitDraft((c) => ({ ...c, name: e.target.value }))}
              />
            </div>

            <div className="field">
              <label htmlFor="wf-loop-cap" className="field-label">
                Maximum Loop Iterations (1 to 100)
              </label>
              <input
                id="wf-loop-cap"
                className="input tabular"
                type="number"
                min={1}
                max={100}
                value={draft.max_loop_iterations}
                onChange={(e) =>
                  commitDraft((c) => ({
                    ...c,
                    max_loop_iterations: Math.min(100, Math.max(1, Number(e.target.value) || 1)),
                  }))
                }
              />
            </div>

            {draft.variables.length > 0 && (
              <div className="panel-subtle list-stack" style={{ gap: 10 }}>
                <div className="field-label">Run Variables</div>
                {draft.variables.map((v) => (
                  <div key={v.name} className="field">
                    <label htmlFor={`var-${v.name}`} className="text-sm mono">
                      {`{{${v.name}}}`}
                    </label>
                    <input
                      id={`var-${v.name}`}
                      className="input mono"
                      value={varInputs[v.name] ?? v.default_value}
                      onChange={(e) =>
                        setVarInputs((prev) => ({ ...prev, [v.name]: e.target.value }))
                      }
                    />
                  </div>
                ))}
              </div>
            )}

            {selectedNode ? (
              <div className="panel-subtle list-stack" style={{ gap: 10 }}>
                <div className="flex-row justify-between">
                  <span className="field-label">Selected Node</span>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ minHeight: 28, paddingInline: 8 }}
                    onClick={removeSelectedNode}
                  >
                    Remove
                  </button>
                </div>

                <div className="field">
                  <label htmlFor="node-label" className="text-sm">
                    Label
                  </label>
                  <input
                    id="node-label"
                    className="input"
                    value={selectedNode.label}
                    onChange={(e) =>
                      commitDraft((c) => {
                        const n = c.nodes.find((item) => item.id === selectedNode.id);
                        if (n) n.label = e.target.value;
                        return c;
                      })
                    }
                  />
                </div>

                {selectedNode.type === "action" && (
                  <div className="field">
                    <label htmlFor="node-tool" className="text-sm">
                      Automation Tool
                    </label>
                    <select
                      id="node-tool"
                      className="select mono"
                      value={selectedNode.tool || NODE_TOOLS[0]}
                      onChange={(e) =>
                        commitDraft((c) => {
                          const n = c.nodes.find((item) => item.id === selectedNode.id);
                          if (n) n.tool = e.target.value;
                          return c;
                        })
                      }
                    >
                      {NODE_TOOLS.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Accessible non-drag positioning controls (WCAG 2.5.7) */}
                <div>
                  <div className="text-sm text-muted" style={{ marginBottom: 6 }}>
                    Position ({Math.round(selectedNode.x)}, {Math.round(selectedNode.y)})
                  </div>
                  <div className="flex-row">
                    <button
                      type="button"
                      className="btn btn-icon"
                      aria-label="Move node left"
                      onClick={() => nudgeSelectedNode(-24, 0)}
                    >
                      <ArrowLeft size={14} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="btn btn-icon"
                      aria-label="Move node up"
                      onClick={() => nudgeSelectedNode(0, -24)}
                    >
                      <ArrowUp size={14} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="btn btn-icon"
                      aria-label="Move node down"
                      onClick={() => nudgeSelectedNode(0, 24)}
                    >
                      <ArrowDown size={14} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="btn btn-icon"
                      aria-label="Move node right"
                      onClick={() => nudgeSelectedNode(24, 0)}
                    >
                      <ArrowRight size={14} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted">Select a node on the canvas to edit its properties.</p>
            )}
          </aside>
        </div>
      )}
    </>
  );
};
