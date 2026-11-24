import React, { useEffect, useState } from "react";
import {
  Circle,
  GitBranch,
  Lock,
  Monitor,
  Play,
  ShieldCheck,
  Square,
  Trash2,
} from "lucide-react";
import type { TeachSession, WorkflowDefinition } from "@omnidesk/shared-schemas";
import { api } from "../lib/api";
import { StatusTag } from "../components/StatusTag";

interface TeachModeViewProps {
  demoDirectory: string | null;
  activeRecording: TeachSession | null;
  onRecordingChange: (session: TeachSession | null) => void;
  onWorkflowCreated: (wf: WorkflowDefinition) => void;
  onOpenInStudio: (wfId: string) => void;
  onTestWorkflow: (wf: WorkflowDefinition) => Promise<void>;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

export const TeachModeView: React.FC<TeachModeViewProps> = ({
  demoDirectory,
  activeRecording,
  onRecordingChange,
  onWorkflowCreated,
  onOpenInStudio,
  onTestWorkflow,
  onNotify,
}) => {
  const [sessions, setSessions] = useState<TeachSession[]>([]);
  const [active, setActive] = useState<TeachSession | null>(activeRecording);
  const [runningApps, setRunningApps] = useState<string[]>([]);
  const [sessionName, setSessionName] = useState("External App & Folder Workflow");
  const [scopeApp, setScopeApp] = useState("");
  const [targetDir, setTargetDir] = useState(demoDirectory || "~/Downloads");
  const [targetUrl, setTargetUrl] = useState("https://example.com");
  const [enableLiveObserver, setEnableLiveObserver] = useState(true);
  const [convertedWf, setConvertedWf] = useState<WorkflowDefinition | null>(null);
  const [busy, setBusy] = useState(false);

  const loadSessions = async () => {
    try {
      const [list, apps] = await Promise.all([api.listTeachSessions(), api.listRunningApps()]);
      setSessions(list);
      setRunningApps(apps.map((a) => a.name).filter((n) => n.toLowerCase() !== "omnidesk"));
      const liveRec = list.find((s) => s.status === "recording") ?? null;
      onRecordingChange(liveRec);
      setActive((prev) => {
        if (liveRec) return liveRec;
        if (prev) return list.find((s) => s.id === prev.id) ?? list[0] ?? null;
        return list[0] ?? null;
      });
    } catch {
      // Handled by parent state.
    }
  };

  useEffect(() => {
    void loadSessions();
  }, []);

  useEffect(() => {
    if (demoDirectory) setTargetDir(demoDirectory);
  }, [demoDirectory]);

  // Poll captured external app / folder transitions live while a Teach Mode session is actively recording.
  useEffect(() => {
    if (active?.status !== "recording") return;
    const timer = setInterval(() => {
      void api.listTeachSessions().then((list) => {
        setSessions(list);
        const refreshed = list.find((s) => s.id === active.id) ?? null;
        if (refreshed) {
          setActive(refreshed);
          onRecordingChange(refreshed.status === "recording" ? refreshed : null);
        }
      });
    }, 1800);
    return () => clearInterval(timer);
  }, [active?.id, active?.status, onRecordingChange]);

  const startRecording = async () => {
    setBusy(true);
    try {
      const created = await api.startTeachSession({
        name: sessionName.trim() || "Recorded Demonstration",
        scope_app: scopeApp || undefined,
        scope_directory: targetDir.trim() || undefined,
        enable_live_observer: enableLiveObserver,
      });
      setActive(created);
      onRecordingChange(created);
      setConvertedWf(null);
      setSessions((prev) => [created, ...prev]);
      onNotify(
        "Teach Mode recording started",
        enableLiveObserver
          ? "Observing permitted external app switches and scoped folder changes."
          : "Manual semantic step capture active.",
        "info"
      );
    } catch (err) {
      onNotify("Could not start recording", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusy(false);
    }
  };

  const recordStep = async (
    kind: "app_focus" | "file_action" | "browser_navigation" | "ui_semantic_click" | "report_export",
    summary: string,
    selector: string,
    parameters: Record<string, unknown>,
    isSecureField = false
  ) => {
    if (!active || active.status !== "recording") return;
    setBusy(true);
    try {
      const updated = await api.recordTeachStep(active.id, {
        kind,
        summary,
        selector,
        parameters,
        is_secure_field: isSecureField,
      });
      setActive(updated);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (err) {
      onNotify("Could not record step", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusy(false);
    }
  };

  const removeStep = async (eventId: string) => {
    if (!active) return;
    try {
      const updated = await api.deleteTeachStep(active.id, eventId);
      setActive(updated);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (err) {
      onNotify("Could not remove step", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const captureCurrentApp = async () => {
    if (!active || active.status !== "recording") return;
    setBusy(true);
    try {
      const updated = await api.captureTeachWindow(active.id);
      setActive(updated);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } finally {
      setBusy(false);
    }
  };

  const stopRecording = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const stopped = await api.stopTeachSession(active.id);
      setActive(stopped);
      onRecordingChange(null);
      setSessions((prev) => prev.map((s) => (s.id === stopped.id ? stopped : s)));
      onNotify(
        "Recording stopped",
        `Extracted ${stopped.extracted_variables.length} reusable variable(s).`,
        "success"
      );
    } finally {
      setBusy(false);
    }
  };

  const convertToWorkflow = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const wf = await api.convertTeachSession(active.id, active.name);
      setConvertedWf(wf);
      onWorkflowCreated(wf);
      const updated = { ...active, status: "converted" as const, workflow_id: wf.id };
      setActive(updated);
      onRecordingChange(null);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      onNotify("Reusable workflow created", `Saved '${wf.name}' to Workflow Studio.`, "success");
    } catch (err) {
      onNotify("Conversion failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusy(false);
    }
  };

  const isRecording = active?.status === "recording";

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Teach Mode</h1>
          <p className="page-subtitle">
            Demonstrate a repetitive workflow across permitted external applications and folders,
            inspect semantic steps, and synthesize a reusable approval-gated automation.
          </p>
        </div>
        <StatusTag
          tone={isRecording ? "danger" : "neutral"}
          kind={isRecording ? "warn" : "shield"}
          label={isRecording ? "Recording explicitly active" : "Recorder idle"}
        />
      </div>

      <div className="operator-grid">
        <section className="panel" aria-label="Teach Mode recording workspace">
          <div className="panel-header">
            <h2 className="panel-title">1. Choose Permitted Recording Scope</h2>
          </div>

          <div className="two-col">
            <div className="field">
              <label htmlFor="teach-session-name" className="field-label">
                Workflow Name
              </label>
              <input
                id="teach-session-name"
                className="input"
                value={sessionName}
                disabled={isRecording}
                onChange={(e) => setSessionName(e.target.value)}
              />
            </div>

            <div className="field">
              <label htmlFor="teach-scope-app" className="field-label">
                External Application Scope
              </label>
              <select
                id="teach-scope-app"
                className="select"
                disabled={isRecording}
                value={scopeApp}
                onChange={(e) => setScopeApp(e.target.value)}
              >
                <option value="">Any permitted external app</option>
                {runningApps.map((appName) => (
                  <option key={appName} value={appName}>
                    {appName}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="two-col">
            <div className="field">
              <label htmlFor="teach-dir" className="field-label">
                Scoped Folder to Watch &amp; Parameterize
              </label>
              <input
                id="teach-dir"
                className="input mono"
                disabled={isRecording}
                value={targetDir}
                onChange={(e) => setTargetDir(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="teach-url" className="field-label">
                Web URL Parameter (optional)
              </label>
              <input
                id="teach-url"
                className="input mono"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
              />
            </div>
          </div>

          <div className="flex-row justify-between flex-wrap">
            <label className="flex-row text-sm">
              <input
                type="checkbox"
                checked={enableLiveObserver}
                disabled={isRecording}
                onChange={(e) => setEnableLiveObserver(e.target.checked)}
              />
              <span>
                Observe external app switches &amp; scoped folder changes automatically while
                recording
              </span>
            </label>

            {!isRecording ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => void startRecording()}
              >
                <Circle size={14} aria-hidden="true" />
                <span>Start Recording</span>
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-danger"
                disabled={busy}
                onClick={() => void stopRecording()}
              >
                <Square size={14} aria-hidden="true" />
                <span>Stop Recording</span>
              </button>
            )}
          </div>

          {active?.observer_note && (
            <div className="panel-subtle text-sm text-muted">{active.observer_note}</div>
          )}

          <div className="panel-subtle list-stack" style={{ gap: 10 }}>
            <div className="field-label">
              Explicit Semantic Actions (combine with live external app observation)
            </div>
            <div className="flex-row flex-wrap">
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() =>
                  void recordStep(
                    "file_action",
                    "Inspect folder and hash potential duplicates",
                    "fs://directory/inspect",
                    { operation: "inspect", directory: targetDir }
                  )
                }
              >
                Record: Inspect Folder
              </button>
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() =>
                  void recordStep(
                    "file_action",
                    "Plan category moves without deleting files",
                    "fs://directory/plan",
                    { operation: "plan", directory: targetDir }
                  )
                }
              >
                Record: Plan Category Moves
              </button>
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() =>
                  void recordStep(
                    "report_export",
                    "Export Excel (.xlsx) summary workbook",
                    "excel://workbook/export",
                    { directory: targetDir, report_filename: "Weekly_Audit_Report.xlsx" }
                  )
                }
              >
                Record: Export Excel Report
              </button>
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() =>
                  void recordStep(
                    "browser_navigation",
                    `Extract webpage content from ${targetUrl}`,
                    "dom://document/body",
                    { url: targetUrl }
                  )
                }
              >
                Record: Extract Webpage
              </button>
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() => void captureCurrentApp()}
              >
                <Monitor size={14} aria-hidden="true" />
                <span>Capture Active OS App</span>
              </button>
              <button
                type="button"
                className="btn"
                disabled={!isRecording || busy}
                onClick={() =>
                  void recordStep(
                    "ui_semantic_click",
                    "Password field entry test",
                    "ax://secure-textfield[@role='password']",
                    { value: "example-secret-never-saved" },
                    true
                  )
                }
              >
                <Lock size={14} aria-hidden="true" />
                <span>Verify Password Redaction</span>
              </button>
            </div>
          </div>

          <div className="list-stack" style={{ gap: 10 }}>
            <div className="panel-header">
              <h3 className="panel-title">2. Captured Semantic Steps</h3>
              {active && (
                <span className="text-sm text-muted tabular">
                  {active.events.length} step(s)
                </span>
              )}
            </div>

            {!active || active.events.length === 0 ? (
              <div className="state-box">
                <strong>No demonstration steps captured yet.</strong>
                <p className="text-sm text-muted">
                  Click Start Recording, switch to your target external app (such as TextEdit or
                  Finder) or trigger semantic actions above, then stop to review and synthesize.
                </p>
              </div>
            ) : (
              <ol style={{ listStyle: "none", padding: 0 }} className="list-stack">
                {active.events.map((evt, idx) => (
                  <li key={evt.id} className="list-row">
                    <div style={{ minWidth: 0 }}>
                      <div className="flex-row">
                        <span className="kbd-cap tabular">{idx + 1}</span>
                        <strong>{evt.summary}</strong>
                      </div>
                      <div className="mono text-sm text-muted" style={{ marginTop: 4 }}>
                        Selector: {evt.selector}
                      </div>
                    </div>
                    <div className="flex-row">
                      <StatusTag
                        tone={evt.redacted ? "warning" : "success"}
                        kind={evt.redacted ? "shield" : "check"}
                        label={evt.redacted ? "Redacted secret" : evt.kind.replace(/_/g, " ")}
                      />
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon"
                        aria-label={`Remove recorded step ${idx + 1}`}
                        onClick={() => void removeStep(evt.id)}
                      >
                        <Trash2 size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>

          {active && active.status !== "recording" && active.events.some((e) => !e.redacted) && (
            <div className="panel-subtle list-stack" style={{ gap: 12 }}>
              <h3 className="panel-title">3. Parameterize, Convert &amp; Test Replay</h3>
              {active.extracted_variables.length > 0 && (
                <div className="flex-row flex-wrap">
                  {active.extracted_variables.map((v) => (
                    <StatusTag
                      key={v.name}
                      tone="accent"
                      label={`{{${v.name}}} = ${v.sample_value}`}
                    />
                  ))}
                </div>
              )}
              <div className="flex-row flex-wrap">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() => void convertToWorkflow()}
                >
                  <GitBranch size={15} aria-hidden="true" />
                  <span>Convert to Reusable Workflow</span>
                </button>
                {convertedWf && (
                  <>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => onOpenInStudio(convertedWf.id)}
                    >
                      Edit in Workflow Studio
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => void onTestWorkflow(convertedWf)}
                    >
                      <Play size={14} aria-hidden="true" />
                      <span>Test Dry-Run Replay</span>
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </section>

        <aside className="panel" aria-label="Teach Mode privacy guarantees and sessions">
          <div className="flex-row">
            <ShieldCheck size={17} aria-hidden="true" />
            <h2 className="panel-title">Privacy &amp; Safety Rules</h2>
          </div>
          <ul
            className="text-sm text-muted"
            style={{ paddingInlineStart: 18, display: "flex", flexDirection: "column", gap: 6 }}
          >
            <li>External app observation activates ONLY after you click Start Recording.</li>
            <li>A top banner remains visible with one-click Stop and Emergency Stop integration.</li>
            <li>Passwords, OTP/2FA, payment windows, and excluded apps are never recorded.</li>
            <li>Prefers semantic accessibility &amp; filesystem selectors over pixel coordinates.</li>
          </ul>

          <div className="list-stack" style={{ marginTop: 8 }}>
            <h3 className="field-label">Past Teach Sessions</h3>
            {sessions.length === 0 ? (
              <p className="text-sm text-muted">No sessions recorded yet.</p>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="list-row row-button"
                  onClick={() => setActive(s)}
                >
                  <div>
                    <div style={{ fontWeight: 580 }}>{s.name}</div>
                    <div className="text-sm text-muted tabular">
                      {s.events.length} step(s) | {s.status}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>
      </div>
    </>
  );
};
