import React, { useEffect, useState } from "react";
import { ExternalLink, FolderPlus, Save, ShieldCheck, Trash2 } from "lucide-react";
import type { AppSettings, SystemProfile } from "@omnidesk/shared-schemas";
import { api } from "../lib/api";
import { BrandMark } from "../components/BrandMark";
import { StatusTag } from "../components/StatusTag";
import { resolveSystemScheme } from "../lib/theme";
import { openOsPermissionPane, pickScopedDirectory } from "../lib/tauri";

interface SettingsViewProps {
  settings: AppSettings;
  profile: SystemProfile | null;
  onSaveSettings: (next: AppSettings) => Promise<void>;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  settings,
  profile,
  onSaveSettings,
  onNotify,
}) => {
  const [draft, setDraft] = useState<AppSettings>(settings);
  const [newDir, setNewDir] = useState("");
  const [newExcluded, setNewExcluded] = useState("");
  const [mcpCount, setMcpCount] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  useEffect(() => {
    api
      .listMcpTools()
      .then((list) => setMcpCount(list.length))
      .catch(() => setMcpCount(null));
  }, []);

  const conn = api.getConnectionInfo();
  const resolvedSystem = resolveSystemScheme();

  const saveAll = async (override?: AppSettings) => {
    setSaving(true);
    try {
      await onSaveSettings(override ?? draft);
      onNotify("Settings saved", "Preferences persisted locally in SQLite.", "success");
    } catch (err) {
      onNotify("Failed to save settings", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setSaving(false);
    }
  };

  const addScopedDirectory = async (browse = false) => {
    const val = browse ? await pickScopedDirectory() : newDir.trim();
    if (!val) return;
    if (!draft.scoped_directories.includes(val)) {
      const next = { ...draft, scoped_directories: [...draft.scoped_directories, val] };
      setDraft(next);
      setNewDir("");
      await saveAll(next);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">
            Control appearance, hardware performance mode, local-first privacy boundaries,
            permissions, and live platform diagnostics.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={saving}
          onClick={() => void saveAll()}
        >
          <Save size={15} aria-hidden="true" />
          <span>{saving ? "Saving..." : "Save Changes"}</span>
        </button>
      </div>

      <div className="two-col">
        <section className="panel" aria-label="Appearance and performance">
          <h2 className="panel-title">Appearance &amp; Hardware Performance</h2>

          <fieldset
            style={{
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "12px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <legend className="field-label" style={{ paddingInline: 6 }}>
              Color Scheme
            </legend>
            {(
              [
                { value: "system", label: `System (currently ${resolvedSystem})` },
                { value: "light", label: "Light (Silver Frost)" },
                { value: "dark", label: "Dark (Obsidian Graphite)" },
              ] as const
            ).map((opt) => (
              <label key={opt.value} className="flex-row">
                <input
                  type="radio"
                  name="theme-choice"
                  checked={draft.theme === opt.value}
                  onChange={() => {
                    const next = { ...draft, theme: opt.value };
                    setDraft(next);
                    void saveAll(next);
                  }}
                />
                <span>{opt.label}</span>
              </label>
            ))}
          </fieldset>

          <label className="flex-row" style={{ alignItems: "flex-start" }}>
            <input
              type="checkbox"
              checked={draft.performance_mode}
              onChange={(e) => {
                const next = { ...draft, performance_mode: e.target.checked };
                setDraft(next);
                void saveAll(next);
              }}
            />
            <span>
              <strong>Performance Mode (Intel &amp; lower-powered devices)</strong>
              <br />
              <span className="text-sm text-muted">
                Disables translucent glass blur filters and reduces UI transitions to lower GPU
                and memory overhead.
              </span>
            </span>
          </label>

          <div className="field">
            <label htmlFor="settings-shortcut" className="field-label">
              Global Command Palette Shortcut
            </label>
            <input
              id="settings-shortcut"
              className="input mono"
              value={draft.global_shortcut}
              onChange={(e) => setDraft({ ...draft, global_shortcut: e.target.value })}
            />
            <span className="field-hint">
              In-window shortcut Cmd/Ctrl+K is always active without conflicting with OS bindings.
            </span>
          </div>
        </section>

        <section className="panel" aria-label="Privacy and data retention">
          <h2 className="panel-title">Privacy, Consent &amp; Storage</h2>

          <div className="field">
            <label htmlFor="privacy-mode-select" className="field-label">
              AI Execution Privacy Mode
            </label>
            <select
              id="privacy-mode-select"
              className="select"
              value={draft.privacy_mode}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  privacy_mode: e.target.value as "local_only" | "cloud_assisted",
                })
              }
            >
              <option value="local_only">Local-only (no cloud AI transmission)</option>
              <option value="cloud_assisted">Cloud-assisted (requires configured provider)</option>
            </select>
          </div>

          <label className="flex-row" style={{ alignItems: "flex-start" }}>
            <input
              type="checkbox"
              checked={draft.cloud_screenshot_consent}
              disabled={draft.privacy_mode === "local_only"}
              onChange={(e) =>
                setDraft({ ...draft, cloud_screenshot_consent: e.target.checked })
              }
            />
            <span>
              Allow transmitting explicit desktop snapshots to configured cloud vision models
            </span>
          </label>

          <div className="field">
            <label htmlFor="retention-days" className="field-label">
              Local History Retention (days)
            </label>
            <input
              id="retention-days"
              className="input tabular"
              type="number"
              min={1}
              max={365}
              value={draft.data_retention_days}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  data_retention_days: Math.min(365, Math.max(1, Number(e.target.value) || 30)),
                })
              }
            />
          </div>

          <div className="flex-row text-sm text-muted">
            <ShieldCheck size={15} aria-hidden="true" />
            <span>Telemetry: Disabled ({draft.telemetry_enabled ? "On" : "Off by default"}).</span>
          </div>
        </section>
      </div>

      <div className="two-col">
        <section className="panel" aria-label="Scoped directories">
          <h2 className="panel-title">Approved Scoped Directories</h2>
          <p className="text-sm text-muted">
            Restrict file automation to explicit directories. Protected system and credential
            paths (~/.ssh, /System, /etc) are always blocked.
          </p>
          <div className="flex-row">
            <label htmlFor="new-scoped-dir" className="visually-hidden">
              Add scoped directory path
            </label>
            <input
              id="new-scoped-dir"
              className="input mono"
              placeholder="/path/to/workspace"
              value={newDir}
              onChange={(e) => setNewDir(e.target.value)}
            />
            <button type="button" className="btn" onClick={() => void addScopedDirectory(false)}>
              Add
            </button>
            <button type="button" className="btn" onClick={() => void addScopedDirectory(true)}>
              <FolderPlus size={14} aria-hidden="true" />
              <span>Browse</span>
            </button>
          </div>
          {draft.scoped_directories.length === 0 ? (
            <p className="text-sm text-muted">
              No custom root allowlist configured yet. OmniDesk validates every user-selected task
              folder against protected system exclusions.
            </p>
          ) : (
            <div className="list-stack">
              {draft.scoped_directories.map((dir) => (
                <div key={dir} className="list-row">
                  <span className="mono text-sm truncate">{dir}</span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-icon"
                    aria-label={`Remove scoped directory ${dir}`}
                    onClick={() => {
                      const next = {
                        ...draft,
                        scoped_directories: draft.scoped_directories.filter((d) => d !== dir),
                      };
                      setDraft(next);
                      void saveAll(next);
                    }}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel" aria-label="Sensitive application exclusions">
          <h2 className="panel-title">Excluded Sensitive Applications</h2>
          <p className="text-sm text-muted">
            Live Workspace and Teach Mode automatically skip these applications.
          </p>
          <div className="flex-row">
            <label htmlFor="new-excluded-app" className="visually-hidden">
              Add excluded application name
            </label>
            <input
              id="new-excluded-app"
              className="input"
              placeholder="Password manager or banking app"
              value={newExcluded}
              onChange={(e) => setNewExcluded(e.target.value)}
            />
            <button
              type="button"
              className="btn"
              onClick={() => {
                const trimmed = newExcluded.trim();
                if (!trimmed || draft.excluded_apps.includes(trimmed)) return;
                const next = { ...draft, excluded_apps: [...draft.excluded_apps, trimmed] };
                setDraft(next);
                setNewExcluded("");
                void saveAll(next);
              }}
            >
              Add
            </button>
          </div>
          <div className="flex-row flex-wrap">
            {draft.excluded_apps.map((appName) => (
              <span key={appName} className="status-tag" data-tone="neutral">
                <span>{appName}</span>
                <button
                  type="button"
                  className="btn-ghost"
                  style={{ border: "none", padding: "0 2px", fontWeight: 700 }}
                  aria-label={`Remove ${appName} from exclusions`}
                  onClick={() => {
                    const next = {
                      ...draft,
                      excluded_apps: draft.excluded_apps.filter((a) => a !== appName),
                    };
                    setDraft(next);
                    void saveAll(next);
                  }}
                >
                  x
                </button>
              </span>
            ))}
          </div>
        </section>
      </div>

      <section className="panel" aria-label="Platform capabilities registry">
        <div className="panel-header">
          <h2 className="panel-title">Platform Capabilities &amp; Diagnostics</h2>
          <StatusTag
            tone={conn.authenticated ? "success" : "warning"}
            kind="shield"
            label={conn.authenticated ? "Authenticated Loopback IPC" : "Local session"}
          />
        </div>

        {profile ? (
          <>
            <div className="panel-subtle text-sm mono">
              Host: {profile.os_name} {profile.os_version} ({profile.arch}) | CPU:{" "}
              {profile.cpu_model} ({profile.cpu_cores} cores) | RAM: {profile.memory_total_gb} GB |
              GPU: {profile.gpu_name} | Engine: {conn.baseUrl}
              {mcpCount !== null ? ` | MCP Tools: ${mcpCount}` : ""}
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <caption className="visually-hidden">Detected platform capabilities</caption>
                <thead>
                  <tr>
                    <th scope="col">Capability</th>
                    <th scope="col">Maturity</th>
                    <th scope="col">Runtime Status</th>
                    <th scope="col">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.capabilities.map((cap) => (
                    <tr key={cap.id}>
                      <td style={{ fontWeight: 580 }}>{cap.name}</td>
                      <td className="text-sm">
                        <StatusTag
                          tone={cap.maturity === "implemented_tested" ? "accent" : "neutral"}
                          label={(cap.maturity ?? "implemented_tested").replace(/_/g, " ")}
                        />
                      </td>
                      <td>
                        <StatusTag
                          tone={
                            cap.status === "available"
                              ? "success"
                              : cap.status === "permission_required" || cap.status === "experimental"
                                ? "warning"
                                : "neutral"
                          }
                          label={cap.status.replace(/_/g, " ")}
                        />
                      </td>
                      <td className="text-sm">
                        <div>{cap.detail}</div>
                        {cap.status === "permission_required" && cap.id.startsWith("macos.") && (
                          <button
                            type="button"
                            className="btn"
                            style={{ marginTop: 6, minHeight: 28, fontSize: 12 }}
                            onClick={async () => {
                              const pane =
                                cap.id === "macos.screen_capture"
                                  ? "screen_recording"
                                  : "accessibility";
                              const msg = await openOsPermissionPane(pane);
                              if (!msg) await api.openPermissionSettings(pane);
                              onNotify("Opened macOS System Settings", `Review ${pane.replace("_", " ")} permission.`, "info");
                            }}
                          >
                            <ExternalLink size={12} aria-hidden="true" />
                            <span>Open System Settings</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted">Capability registry loading...</p>
        )}
      </section>

      <section className="panel" aria-label="About OmniDesk">
        <div className="flex-row justify-between flex-wrap">
          <div className="flex-row" style={{ gap: 12 }}>
            <BrandMark size={34} />
            <div>
              <h2 className="panel-title">OmniDesk v0.1.0</h2>
              <p className="text-sm text-muted">
                Universal AI Computer Operator. Apache-2.0 Open-Source Release.
              </p>
            </div>
          </div>
          <div className="text-sm text-muted">Built by NGOPREK DIGITAL</div>
        </div>
      </section>
    </>
  );
};
