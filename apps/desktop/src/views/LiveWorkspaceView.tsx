import React, { useState } from "react";
import { Camera, EyeOff, RefreshCw, ShieldCheck } from "lucide-react";
import type { AppSettings, SystemProfile } from "@omnidesk/shared-schemas";
import { api, type LiveSnapshotResult } from "../lib/api";
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
  const [activeWindow, setActiveWindow] = useState<{
    platform: string;
    app_name: string;
    status: string;
    note: string;
  } | null>(null);
  const [snapshot, setSnapshot] = useState<LiveSnapshotResult | null>(null);

  const inspectWindow = async () => {
    setLoading(true);
    try {
      const ctx = await api.getActiveWindow();
      setActiveWindow(ctx);
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

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Workspace</h1>
          <p className="page-subtitle">
            Inspect active desktop window context and accessibility readiness on demand. OmniDesk
            never captures your screen continuously in the background.
          </p>
        </div>
        <div className="flex-row">
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
                snapshot. Applications in your privacy exclusion list are automatically skipped.
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
                  disabled={loading}
                  onClick={() => void inspectWindow()}
                >
                  <RefreshCw size={15} aria-hidden="true" />
                  <span>Check Active Window</span>
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
                    Click &quot;Capture Single Snapshot&quot; to request one frame from your OS
                    compositor. On macOS, grant Screen Recording permission in System Settings if
                    prompted.
                  </p>
                </div>
              )}
            </>
          )}
        </section>

        <aside className="panel" aria-label="Accessibility and privacy controls">
          <h2 className="panel-title">Window &amp; Accessibility Context</h2>
          <div className="panel-subtle list-stack" style={{ gap: 6 }}>
            <div className="field-label">Active Window Inspection</div>
            {activeWindow ? (
              <>
                <div style={{ fontWeight: 600 }}>{activeWindow.app_name}</div>
                <div className="text-sm text-muted">{activeWindow.note}</div>
              </>
            ) : (
              <p className="text-sm text-muted">
                No window queried yet. Click Check Active Window to query on demand.
              </p>
            )}
            <button
              type="button"
              className="btn"
              style={{ alignSelf: "flex-start" }}
              disabled={loading}
              onClick={() => void inspectWindow()}
            >
              Query Active Window
            </button>
          </div>

          <div className="list-stack">
            <div className="field-label">Targeting Priority Order</div>
            <ol className="text-sm text-muted" style={{ paddingInlineStart: 18, display: "flex", flexDirection: "column", gap: 4 }}>
              <li>Native OS accessibility tree (AX / UIA / AT-SPI)</li>
              <li>Semantic application selectors</li>
              <li>Playwright Browser DOM selectors</li>
              <li>Opt-in vision verification</li>
              <li>DPI-aware coordinates only as final fallback</li>
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
