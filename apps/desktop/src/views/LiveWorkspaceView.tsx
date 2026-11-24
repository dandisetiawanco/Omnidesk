import React, { useEffect, useState } from "react";
import { Camera, ExternalLink, EyeOff, Layers, RefreshCw, ShieldCheck } from "lucide-react";
import type { AppSettings, SystemProfile } from "@omnidesk/shared-schemas";
import { api, type AccessibilityTreeResult, type LiveSnapshotResult } from "../lib/api";
import { openOsPermissionPane } from "../lib/tauri";
import { StatusTag } from "../components/StatusTag";

interface LiveWorkspaceViewProps {
  profile: SystemProfile | null;
  settings: AppSettings;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

export const LiveWorkspaceView: React.FC<LiveWorkspaceViewProps> = ({
  profile,
  settings,
  onNotify,
}) => {
  const [authorized, setAuthorized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [runningApps, setRunningApps] = useState<string[]>([]);
  const [targetApp, setTargetApp] = useState("");
  const [activeWindow, setActiveWindow] = useState<{
    platform: string;
    app_name: string;
    window_title?: string;
    accessibility_granted?: boolean;
    status: string;
    note: string;
  } | null>(null);
  const [axResult, setAxResult] = useState<AccessibilityTreeResult | null>(null);
  const [snapshot, setSnapshot] = useState<LiveSnapshotResult | null>(null);

  const loadRunning = async () => {
    try {
      const list = await api.listRunningApps();
      setRunningApps(list.map((a) => a.name));
    } catch {
      // Handled gracefully.
    }
  };

  useEffect(() => {
    void loadRunning();
  }, []);

  const inspectWindow = async () => {
    setLoading(true);
    try {
      const [ctx, ax] = await Promise.all([
        api.getActiveWindow(),
        api.inspectAccessibilityTree(targetApp || undefined),
      ]);
      setActiveWindow(ctx);
      setAxResult(ax);
      await loadRunning();
    } catch (err) {
      onNotify("Active window check failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setLoading(false);
    }
  };

  const captureSingleSnapshot = async () => {
    setLoading(true);
    try {
      const res = await api.captureLiveSnapshot();
      setSnapshot(res);
      setActiveWindow(res.active_window);
      onNotify(
        res.captured ? "Snapshot captured" : "Capture notice",
        res.message,
        res.captured ? "success" : "info"
      );
    } catch (err) {
      onNotify("Snapshot failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setLoading(false);
    }
  };

  const openSystemPermissions = async (pane: "accessibility" | "screen_recording") => {
    try {
      const nativeMsg = await openOsPermissionPane(pane);
      if (!nativeMsg) {
        await api.openPermissionSettings(pane);
      }
      onNotify("Opened OS Settings", `Review ${pane.replace("_", " ")} permission for OmniDesk.`, "info");
    } catch (err) {
      onNotify("Could not open OS settings", err instanceof Error ? err.message : undefined, "error");
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Workspace</h1>
          <p className="page-subtitle">
            Inspect active applications, semantic accessibility trees, and single-shot desktop
            previews with explicit user authorization.
          </p>
        </div>
        <div className="flex-row flex-wrap">
          <button
            type="button"
            className={authorized ? "btn btn-danger" : "btn btn-primary"}
            onClick={() => {
              const next = !authorized;
              setAuthorized(next);
              if (!next) setSnapshot(null);
            }}
          >
            {authorized ? <EyeOff size={15} aria-hidden="true" /> : <Camera size={15} aria-hidden="true" />}
            <span>{authorized ? "Disable Screen Access" : "Authorize On-Demand Capture"}</span>
          </button>
        </div>
      </div>

      <div className="operator-grid">
        <div className="list-stack" style={{ gap: 20 }}>
          <section className="panel" aria-label="Screen context preview">
            <div className="panel-header">
              <h2 className="panel-title">Desktop Context Snapshot</h2>
              <StatusTag
                tone={authorized ? "accent" : "neutral"}
                label={authorized ? "Single-shot ready" : "Capture disabled"}
              />
            </div>

            {!authorized ? (
              <div className="state-box">
                <strong>Screen access is turned off.</strong>
                <p className="text-sm text-muted">
                  Enable on-demand capture above when you want OmniDesk to inspect a single desktop
                  snapshot. Applications in your privacy exclusion list are skipped automatically.
                </p>
              </div>
            ) : (
              <>
                <div className="flex-row flex-wrap">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={loading}
                    onClick={() => void captureSingleSnapshot()}
                  >
                    <Camera size={15} aria-hidden="true" />
                    <span>{loading ? "Capturing..." : "Capture Single Snapshot"}</span>
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void openSystemPermissions("screen_recording")}
                  >
                    <ExternalLink size={14} aria-hidden="true" />
                    <span>Screen Recording Settings</span>
                  </button>
                </div>

                {snapshot?.image_data_url ? (
                  <figure style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <img
                      src={snapshot.image_data_url}
                      alt="Single user-authorized desktop workspace snapshot"
                      width={snapshot.width ?? 1280}
                      height={snapshot.height ?? 800}
                      style={{
                        width: "100%",
                        height: "auto",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    />
                    <figcaption className="text-sm text-muted">
                      {snapshot.message} (Active app: {snapshot.active_window.app_name})
                    </figcaption>
                  </figure>
                ) : (
                  <div className="state-box">
                    <strong>{snapshot ? snapshot.message : "Ready for single-shot capture."}</strong>
                    <p className="text-sm text-muted">
                      Click Capture Single Snapshot to request one frame from your OS compositor.
                    </p>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="panel" aria-label="Semantic Accessibility Tree Inspector">
            <div className="panel-header">
              <div className="flex-row">
                <Layers size={16} aria-hidden="true" />
                <h2 className="panel-title">Accessibility Element Inspector</h2>
              </div>
              {axResult && (
                <StatusTag
                  tone={axResult.accessibility_granted ? "success" : "warning"}
                  label={axResult.accessibility_granted ? "Accessibility granted" : "Permission required"}
                />
              )}
            </div>

            <div className="flex-row flex-wrap">
              <label htmlFor="live-ax-app" className="visually-hidden">
                Select running application to inspect
              </label>
              <select
                id="live-ax-app"
                className="select"
                style={{ flex: "1 1 200px" }}
                value={targetApp}
                onChange={(e) => setTargetApp(e.target.value)}
              >
                <option value="">Frontmost application (auto)</option>
                {runningApps.map((appName) => (
                  <option key={appName} value={appName}>
                    {appName}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-primary"
                disabled={loading}
                onClick={() => void inspectWindow()}
              >
                <RefreshCw size={14} aria-hidden="true" />
                <span>Inspect Accessibility Tree</span>
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => void openSystemPermissions("accessibility")}
              >
                <ExternalLink size={14} aria-hidden="true" />
                <span>Accessibility Settings</span>
              </button>
            </div>

            {axResult ? (
              <div className="list-stack" style={{ gap: 8 }}>
                <div className="panel-subtle text-sm">
                  <strong>{axResult.app_name}</strong>: {axResult.message}
                </div>
                {axResult.elements.length > 0 && (
                  <div className="list-stack" style={{ maxHeight: 240, overflowY: "auto" }}>
                    {axResult.elements.map((el, i) => (
                      <div key={i} className="list-row">
                        <div>
                          <div style={{ fontWeight: 580 }}>{el.name}</div>
                          <div className="mono text-sm text-muted">{el.selector}</div>
                        </div>
                        <StatusTag tone="neutral" label={el.role} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted">
                Inspect semantic buttons, fields, and windows before executing controlled desktop
                interactions. Secure password fields are always skipped.
              </p>
            )}
          </section>
        </div>

        <aside className="panel" aria-label="Accessibility and privacy controls">
          <h2 className="panel-title">Window &amp; Privacy Context</h2>
          <div className="panel-subtle list-stack" style={{ gap: 6 }}>
            <div className="field-label">Active Window</div>
            {activeWindow ? (
              <>
                <div style={{ fontWeight: 600 }}>{activeWindow.app_name}</div>
                {activeWindow.window_title && (
                  <div className="text-sm">{activeWindow.window_title}</div>
                )}
                <div className="text-sm text-muted">{activeWindow.note}</div>
              </>
            ) : (
              <p className="text-sm text-muted">
                Click Inspect Accessibility Tree to query the frontmost desktop application.
              </p>
            )}
          </div>

          <div className="list-stack">
            <div className="field-label">Visible Running Applications ({runningApps.length})</div>
            <div className="flex-row flex-wrap">
              {runningApps.slice(0, 12).map((a) => (
                <StatusTag key={a} tone="neutral" label={a} />
              ))}
            </div>
          </div>

          <div className="list-stack">
            <div className="field-label">Interaction Priority Order</div>
            <ol
              className="text-sm text-muted"
              style={{ paddingInlineStart: 18, display: "flex", flexDirection: "column", gap: 4 }}
            >
              <li>Native application APIs</li>
              <li>Native accessibility interfaces (AX / UIA / AT-SPI)</li>
              <li>Playwright Browser DOM selectors</li>
              <li>Opt-in computer vision verification</li>
              <li>Controlled DPI-aware coordinates only as final fallback</li>
            </ol>
          </div>

          <div className="panel-subtle list-stack" style={{ gap: 6 }}>
            <div className="flex-row">
              <ShieldCheck size={15} aria-hidden="true" />
              <span className="field-label">Excluded Sensitive Apps</span>
            </div>
            <p className="text-sm text-muted">
              {settings.excluded_apps.join(", ") || "None configured"}
            </p>
          </div>

          {profile && (
            <div className="list-stack" style={{ gap: 6 }}>
              <div className="field-label">Detected Displays</div>
              {profile.displays.map((d, i) => (
                <div key={i} className="text-sm text-muted tabular">
                  {d.name}: {d.width}x{d.height} ({d.scale_factor}x DPI)
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </>
  );
};
