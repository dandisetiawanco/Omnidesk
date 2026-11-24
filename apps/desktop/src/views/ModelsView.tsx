import React, { useState } from "react";
import { CheckCircle2, KeyRound, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import type { ProviderStatus } from "@omnidesk/shared-schemas";
import { api } from "../lib/api";
import { StatusTag } from "../components/StatusTag";

interface ModelsViewProps {
  providers: ProviderStatus[];
  onRefresh: (probe?: boolean) => Promise<void>;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

export const ModelsView: React.FC<ModelsViewProps> = ({ providers, onRefresh, onNotify }) => {
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({});
  const [urlDrafts, setUrlDrafts] = useState<Record<string, string>>({});
  const [roleDrafts, setRoleDrafts] = useState<
    Record<string, { planning: string; vision: string; lightweight: string }>
  >({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const getRoles = (p: ProviderStatus) =>
    roleDrafts[p.id] ?? {
      planning: p.selected_models.planning ?? p.available_models[0] ?? "",
      vision: p.selected_models.vision ?? p.available_models[0] ?? "",
      lightweight: p.selected_models.lightweight ?? p.available_models[p.available_models.length - 1] ?? "",
    };

  const handleSave = async (p: ProviderStatus) => {
    setBusyId(p.id);
    try {
      const roles = getRoles(p);
      await api.updateProvider(p.id, {
        api_key: keyDrafts[p.id]?.trim() || undefined,
        base_url: urlDrafts[p.id]?.trim() || p.base_url || undefined,
        selected_models: roles,
      });
      setKeyDrafts((prev) => ({ ...prev, [p.id]: "" }));
      await onRefresh(false);
      onNotify(
        `${p.label} updated`,
        keyDrafts[p.id]?.trim()
          ? "Credential saved to OS secure storage (never stored in plaintext)."
          : "Model preferences saved locally.",
        "success"
      );
    } catch (err) {
      onNotify("Provider update failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusyId(null);
    }
  };

  const handleClearKey = async (p: ProviderStatus) => {
    setBusyId(p.id);
    try {
      await api.updateProvider(p.id, { clear_key: true });
      await onRefresh(false);
      onNotify("Credential removed", `Removed stored key for ${p.label} from OS keyring.`, "info");
    } finally {
      setBusyId(null);
    }
  };

  const handleTest = async (p: ProviderStatus) => {
    setBusyId(p.id);
    try {
      const res = await api.testProvider(p.id);
      await onRefresh(false);
      onNotify(
        res.reachable ? `${p.label} connected` : `${p.label} unavailable`,
        res.status_detail,
        res.reachable ? "success" : "error"
      );
    } catch (err) {
      onNotify("Connection check failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Models</h1>
          <p className="page-subtitle">
            Configure local and cloud model providers for task planning, vision, and lightweight
            operations. API keys are stored only in your operating system credential vault.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void onRefresh(true)}>
          <RefreshCw size={15} aria-hidden="true" />
          <span>Probe All Providers</span>
        </button>
      </div>

      <div className="panel-subtle flex-row">
        <ShieldCheck size={17} aria-hidden="true" />
        <span className="text-sm">
          Cloud providers are used only when Privacy Mode is set to Cloud-assisted in Settings.
          Ollama and OmniDesk&apos;s deterministic local planner always run offline on this device.
        </span>
      </div>

      <div className="list-stack" style={{ gap: 16 }}>
        {providers.map((p) => {
          const roles = getRoles(p);
          const isBusy = busyId === p.id;
          return (
            <section key={p.id} className="panel" aria-label={`${p.label} configuration`}>
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">{p.label}</h2>
                  <p className="text-sm text-muted">{p.status_detail}</p>
                </div>
                <div className="flex-row flex-wrap">
                  <StatusTag tone="neutral" label={p.kind} />
                  <StatusTag
                    tone={p.reachable ? "success" : p.configured ? "accent" : "neutral"}
                    kind={p.reachable ? "check" : undefined}
                    label={
                      p.reachable
                        ? "Reachable"
                        : p.configured
                          ? "Configured"
                          : "Not configured"
                    }
                  />
                </div>
              </div>

              <div className="two-col">
                {(p.kind === "local" || p.kind === "custom") && (
                  <div className="field">
                    <label htmlFor={`url-${p.id}`} className="field-label">
                      Endpoint Base URL
                    </label>
                    <input
                      id={`url-${p.id}`}
                      className="input mono"
                      type="url"
                      value={urlDrafts[p.id] ?? p.base_url ?? ""}
                      onChange={(e) =>
                        setUrlDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                    />
                  </div>
                )}

                {p.id !== "ollama" && (
                  <div className="field">
                    <label htmlFor={`key-${p.id}`} className="field-label">
                      API Key (stored in OS Keychain / Credential Manager)
                    </label>
                    <input
                      id={`key-${p.id}`}
                      className="input mono"
                      type="password"
                      autoComplete="off"
                      placeholder={
                        p.masked_key
                          ? `Stored securely (${p.masked_key})`
                          : "Paste API key to store in OS vault"
                      }
                      value={keyDrafts[p.id] ?? ""}
                      onChange={(e) =>
                        setKeyDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                    />
                  </div>
                )}
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 12,
                }}
              >
                {(["planning", "vision", "lightweight"] as const).map((role) => (
                  <div key={role} className="field">
                    <label htmlFor={`model-${p.id}-${role}`} className="field-label">
                      {role.charAt(0).toUpperCase() + role.slice(1)} Model
                    </label>
                    {p.available_models.length > 0 ? (
                      <select
                        id={`model-${p.id}-${role}`}
                        className="select mono"
                        value={roles[role]}
                        onChange={(e) =>
                          setRoleDrafts((prev) => ({
                            ...prev,
                            [p.id]: { ...roles, [role]: e.target.value },
                          }))
                        }
                      >
                        {p.available_models.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id={`model-${p.id}-${role}`}
                        className="input mono"
                        placeholder="Enter model identifier"
                        value={roles[role]}
                        onChange={(e) =>
                          setRoleDrafts((prev) => ({
                            ...prev,
                            [p.id]: { ...roles, [role]: e.target.value },
                          }))
                        }
                      />
                    )}
                  </div>
                ))}
              </div>

              <div className="flex-row justify-between flex-wrap">
                <div className="flex-row flex-wrap">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={isBusy}
                    onClick={() => void handleSave(p)}
                  >
                    <KeyRound size={14} aria-hidden="true" />
                    <span>{isBusy ? "Saving..." : "Save Configuration"}</span>
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={isBusy}
                    onClick={() => void handleTest(p)}
                  >
                    <CheckCircle2 size={14} aria-hidden="true" />
                    <span>Test &amp; Discover Models</span>
                  </button>
                </div>
                {p.configured && p.id !== "ollama" && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={isBusy}
                    onClick={() => void handleClearKey(p)}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                    <span>Remove Key</span>
                  </button>
                )}
              </div>

              {p.model_capabilities && Object.keys(p.model_capabilities).length > 0 && (
                <div className="flex-row flex-wrap text-sm">
                  <span className="text-muted">Capabilities for {roles.planning || p.available_models[0]}:</span>
                  {(p.model_capabilities[roles.planning || p.available_models[0]] ?? ["structured_json"]).map(
                    (cap) => (
                      <StatusTag key={cap} tone="neutral" label={cap.replace("_", " ")} />
                    )
                  )}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
};
