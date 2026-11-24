import React, { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Cpu,
  Download,
  KeyRound,
  Play,
  Power,
  RefreshCw,
  ShieldCheck,
  Square,
  Trash2,
} from "lucide-react";
import type { AppSettings, ProviderStatus } from "@omnidesk/shared-schemas";
import { api } from "../lib/api";
import { StatusTag } from "../components/StatusTag";

interface ModelsViewProps {
  providers: ProviderStatus[];
  settings: AppSettings;
  onSaveSettings: (next: AppSettings) => Promise<void>;
  onRefresh: (probe?: boolean) => Promise<void>;
  onNotify: (title: string, detail?: string, tone?: "info" | "success" | "error") => void;
}

const RECOMMENDED_LOCAL_MODELS = [
  { id: "qwen2.5:1.5b", note: "~986 MB Q4_K_M | Strong JSON planning on 8 GB RAM" },
  { id: "qwen2.5:0.5b", note: "~398 MB Q4_K_M | Ultra-lightweight CPU option" },
];

export const ModelsView: React.FC<ModelsViewProps> = ({
  providers,
  settings,
  onSaveSettings,
  onRefresh,
  onNotify,
}) => {
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({});
  const [urlDrafts, setUrlDrafts] = useState<Record<string, string>>({});
  const [primaryDrafts, setPrimaryDrafts] = useState<Record<string, string>>({});
  const [ctxDrafts, setCtxDrafts] = useState<Record<string, number>>({});
  const [roleDrafts, setRoleDrafts] = useState<
    Record<string, { vision: string; lightweight: string }>
  >({});
  const [busyId, setBusyId] = useState<string | null>(null);

  // Local Ollama pull state
  const [pullModelName, setPullModelName] = useState("qwen2.5:1.5b");
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<{
    status: string;
    percent: number;
    completed_mb: number;
    total_mb: number;
  } | null>(null);

  // Live streaming verification state
  const [streamProvider, setStreamProvider] = useState<string>("ollama");
  const [streamPrompt, setStreamPrompt] = useState(
    "Reply in one short sentence confirming local or cloud inference is working."
  );
  const [streaming, setStreaming] = useState(false);
  const [streamOutput, setStreamOutput] = useState("");
  const [streamMeta, setStreamMeta] = useState<string>("");
  const streamAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!pulling) return;
    const timer = window.setInterval(() => {
      void api
        .getOllamaPullStatus()
        .then((map) => {
          const entry = map[pullModelName.trim()];
          if (entry) setPullProgress(entry);
        })
        .catch(() => {});
    }, 900);
    return () => window.clearInterval(timer);
  }, [pulling, pullModelName]);

  const getPrimary = (p: ProviderStatus) =>
    primaryDrafts[p.id] ?? p.primary_model ?? p.selected_models.planning ?? p.available_models[0] ?? "";

  const getAdvancedRoles = (p: ProviderStatus) => {
    const primary = getPrimary(p);
    return (
      roleDrafts[p.id] ?? {
        vision: p.selected_models.vision ?? primary,
        lightweight: p.selected_models.lightweight ?? primary,
      }
    );
  };

  const getContextLimit = (p: ProviderStatus) =>
    ctxDrafts[p.id] ?? p.context_limit ?? settings.local_context_limit ?? 2048;

  const handleSave = async (p: ProviderStatus) => {
    setBusyId(p.id);
    try {
      const primary = getPrimary(p).trim();
      const adv = getAdvancedRoles(p);
      await api.updateProvider(p.id, {
        api_key: keyDrafts[p.id]?.trim() || undefined,
        base_url: urlDrafts[p.id]?.trim() || p.base_url || undefined,
        primary_model: primary || undefined,
        context_limit: p.kind === "local" ? getContextLimit(p) : undefined,
        selected_models: {
          planning: primary || undefined,
          vision: adv.vision?.trim() || primary || undefined,
          lightweight: adv.lightweight?.trim() || primary || undefined,
        },
      });
      setKeyDrafts((prev) => ({ ...prev, [p.id]: "" }));
      await onRefresh(false);
      onNotify(
        `${p.label} saved`,
        keyDrafts[p.id]?.trim()
          ? "Credential stored in OS secure vault."
          : "Primary model and routing settings updated.",
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

  const handleStartOllama = async () => {
    setBusyId("ollama");
    try {
      const res = await api.startOllama();
      await onRefresh(false);
      onNotify("Local Ollama ready", res.detail, "success");
    } catch (err) {
      onNotify("Could not start Ollama", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusyId(null);
    }
  };

  const handlePullOllama = async () => {
    const clean = pullModelName.trim();
    if (!clean) return;
    setPulling(true);
    setPullProgress({ status: "connecting", percent: 0, completed_mb: 0, total_mb: 0 });
    try {
      const res = await api.pullOllamaModel(clean);
      setPullProgress(res);
      await onRefresh(false);
      onNotify("Local model downloaded", `${clean} is ready for offline planning.`, "success");
    } catch (err) {
      onNotify("Model download failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setPulling(false);
    }
  };

  const handleUnloadModel = async (model: string) => {
    setBusyId("ollama");
    try {
      await api.unloadOllamaModel(model);
      await onRefresh(false);
      onNotify("Model unloaded", `Released ${model} from system memory.`, "info");
    } catch (err) {
      onNotify("Unload failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusyId(null);
    }
  };

  const handleDeleteModel = async (model: string) => {
    setBusyId("ollama");
    try {
      await api.deleteOllamaModel(model);
      await onRefresh(false);
      onNotify("Local model deleted", `Removed ${model} from Ollama storage.`, "info");
    } catch (err) {
      onNotify("Delete failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setBusyId(null);
    }
  };

  const handleMoveFallback = async (index: number, direction: -1 | 1) => {
    const order = [...(settings.provider_fallback_order ?? ["ollama", "gemini", "openai", "anthropic", "openai_compatible"])];
    const target = index + direction;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    await onSaveSettings({ ...settings, provider_fallback_order: order });
  };

  const handleStreamTest = async () => {
    if (!streamPrompt.trim()) return;
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setStreaming(true);
    setStreamOutput("");
    setStreamMeta("Connecting...");
    try {
      await api.streamProviderPreview(
        streamPrompt.trim(),
        streamProvider || undefined,
        (ev) => {
          if (ev.event === "start") {
            setStreamMeta(`Streaming from ${ev.provider}:${ev.model}`);
          } else if (ev.event === "token" && ev.text) {
            setStreamOutput((prev) => prev + ev.text);
          } else if (ev.event === "done") {
            const tokens =
              ev.prompt_tokens || ev.completion_tokens
                ? ` | ${ev.prompt_tokens ?? 0} in / ${ev.completion_tokens ?? 0} out tokens`
                : "";
            setStreamMeta((prev) => `${prev.replace("Streaming from ", "Completed via ")}${tokens}`);
          } else if (ev.event === "error") {
            setStreamMeta(ev.message || "Provider returned an error.");
          }
        },
        controller.signal
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setStreamMeta(err instanceof Error ? err.message : "Stream interrupted.");
      }
    } finally {
      setStreaming(false);
    }
  };

  const handleCancelStream = async () => {
    streamAbortRef.current?.abort();
    try {
      await api.cancelProviderInference();
    } catch {
      // Ignore cancellation cleanup errors.
    }
    setStreaming(false);
    setStreamMeta("Cancelled.");
  };

  const fallbackOrder = settings.provider_fallback_order ?? [
    "ollama",
    "gemini",
    "openai",
    "anthropic",
    "openai_compatible",
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Models</h1>
          <p className="page-subtitle">
            Pick one primary model per provider. Local Ollama runs offline on this machine; cloud
            keys are stored exclusively in your operating system credential vault.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void onRefresh(true)}>
          <RefreshCw size={15} aria-hidden="true" />
          <span>Probe All Providers</span>
        </button>
      </div>

      <div className="panel-subtle flex-row justify-between flex-wrap">
        <div className="flex-row">
          <ShieldCheck size={17} aria-hidden="true" />
          <span className="text-sm">
            Privacy Mode is currently <strong>{settings.privacy_mode.replace("_", " ")}</strong>.{" "}
            {settings.privacy_mode === "local_only"
              ? "Cloud providers stay blocked until you enable Cloud-assisted mode in Settings."
              : "Configured providers run in fallback order with deterministic safety fallback."}
          </span>
        </div>
      </div>

      <div className="list-stack" style={{ gap: 16 }}>
        {providers.map((p) => {
          const primary = getPrimary(p);
          const adv = getAdvancedRoles(p);
          const isBusy = busyId === p.id;
          const activeCaps = p.model_capabilities?.[primary] ?? [];

          return (
            <section key={p.id} className="panel" aria-label={`${p.label} configuration`}>
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">{p.label}</h2>
                  <p className="text-sm text-muted">{p.status_detail}</p>
                </div>
                <div className="flex-row flex-wrap">
                  <StatusTag tone="neutral" label={p.kind} />
                  {p.id === "ollama" && (
                    <StatusTag
                      tone={p.runtime_installed ? "success" : "warning"}
                      label={p.runtime_installed ? "Runtime installed" : "Runtime missing"}
                    />
                  )}
                  <StatusTag
                    tone={p.reachable ? "success" : p.configured ? "accent" : "neutral"}
                    kind={p.reachable ? "check" : undefined}
                    label={
                      p.reachable
                        ? "Ready"
                        : p.configured
                          ? "Configured"
                          : "Not configured"
                    }
                  />
                </div>
              </div>

              <div className="two-col">
                <div className="field">
                  <label htmlFor={`primary-${p.id}`} className="field-label">
                    Primary Model
                  </label>
                  {p.available_models.length > 0 ? (
                    <select
                      id={`primary-${p.id}`}
                      className="select mono"
                      value={primary}
                      onChange={(e) =>
                        setPrimaryDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))
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
                      id={`primary-${p.id}`}
                      className="input mono"
                      placeholder={p.id === "ollama" ? "Pull a local model below" : "Enter model identifier"}
                      value={primary}
                      onChange={(e) =>
                        setPrimaryDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                    />
                  )}
                </div>

                {p.id !== "ollama" ? (
                  <div className="field">
                    <label htmlFor={`key-${p.id}`} className="field-label">
                      API Key (OS Keychain / Credential Manager)
                    </label>
                    <input
                      id={`key-${p.id}`}
                      className="input mono"
                      type="password"
                      autoComplete="off"
                      placeholder={
                        p.masked_key
                          ? `Stored securely (${p.masked_key})`
                          : "Paste API key to store securely"
                      }
                      value={keyDrafts[p.id] ?? ""}
                      onChange={(e) =>
                        setKeyDrafts((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                    />
                  </div>
                ) : (
                  <div className="field">
                    <label htmlFor={`url-${p.id}`} className="field-label">
                      Local Runtime Endpoint
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
              </div>

              {p.kind === "custom" && (
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

              {p.id === "ollama" && (
                <div className="panel-subtle list-stack" style={{ gap: 10 }}>
                  <div className="flex-row justify-between flex-wrap">
                    <div className="flex-row">
                      <Cpu size={15} aria-hidden="true" />
                      <strong className="text-sm">Local Model Manager (RAM-conscious)</strong>
                    </div>
                    {!p.reachable && p.runtime_installed && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={isBusy}
                        onClick={() => void handleStartOllama()}
                      >
                        <Power size={14} aria-hidden="true" />
                        <span>Start Local Ollama</span>
                      </button>
                    )}
                  </div>

                  {p.loaded_models && p.loaded_models.length > 0 && (
                    <div className="flex-row flex-wrap text-sm">
                      <span className="text-muted">Currently loaded in RAM:</span>
                      {p.loaded_models.map((m) => (
                        <span key={m} className="flex-row" style={{ gap: 6 }}>
                          <StatusTag tone="accent" label={m} />
                          <button
                            type="button"
                            className="btn btn-ghost"
                            style={{ minHeight: 28, padding: "2px 8px" }}
                            disabled={isBusy}
                            onClick={() => void handleUnloadModel(m)}
                          >
                            Unload from RAM
                          </button>
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex-row flex-wrap">
                    <input
                      aria-label="Local Ollama model to download"
                      className="input mono"
                      style={{ flex: "1 1 220px" }}
                      value={pullModelName}
                      onChange={(e) => setPullModelName(e.target.value)}
                      placeholder="e.g. qwen2.5:1.5b"
                    />
                    <button
                      type="button"
                      className="btn"
                      disabled={pulling || !p.runtime_installed}
                      onClick={() => void handlePullOllama()}
                    >
                      <Download size={14} aria-hidden="true" />
                      <span>{pulling ? "Downloading..." : "Download Model"}</span>
                    </button>
                  </div>

                  <div className="flex-row flex-wrap text-sm text-muted">
                    <span>Recommended for 8 GB RAM:</span>
                    {RECOMMENDED_LOCAL_MODELS.map((rec) => (
                      <button
                        key={rec.id}
                        type="button"
                        className="btn btn-ghost"
                        style={{ minHeight: 26, padding: "2px 8px", fontSize: 12 }}
                        onClick={() => setPullModelName(rec.id)}
                        title={rec.note}
                      >
                        {rec.id}
                      </button>
                    ))}
                  </div>

                  {pullProgress && (
                    <div className="text-sm mono">
                      Download: {pullProgress.status} ({pullProgress.percent}%
                      {pullProgress.total_mb > 0
                        ? ` | ${pullProgress.completed_mb} / ${pullProgress.total_mb} MB`
                        : ""}
                      )
                    </div>
                  )}

                  {p.available_models.length > 0 && (
                    <div className="flex-row flex-wrap text-sm">
                      <span className="text-muted">Installed locally:</span>
                      {p.available_models.map((m) => (
                        <span key={m} className="flex-row" style={{ gap: 4 }}>
                          <StatusTag tone="neutral" label={m} />
                          <button
                            type="button"
                            className="btn btn-ghost"
                            aria-label={`Delete ${m}`}
                            style={{ minHeight: 26, padding: "2px 6px" }}
                            disabled={isBusy}
                            onClick={() => void handleDeleteModel(m)}
                          >
                            <Trash2 size={12} aria-hidden="true" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <details className="panel-subtle">
                <summary className="text-sm" style={{ fontWeight: 560, cursor: "pointer" }}>
                  Advanced routing &amp; context settings (optional)
                </summary>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                    gap: 12,
                    marginTop: 12,
                  }}
                >
                  <div className="field">
                    <label htmlFor={`vision-${p.id}`} className="field-label">
                      Vision Role Override
                    </label>
                    <input
                      id={`vision-${p.id}`}
                      className="input mono"
                      value={adv.vision}
                      onChange={(e) =>
                        setRoleDrafts((prev) => ({
                          ...prev,
                          [p.id]: { ...adv, vision: e.target.value },
                        }))
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`light-${p.id}`} className="field-label">
                      Lightweight Role Override
                    </label>
                    <input
                      id={`light-${p.id}`}
                      className="input mono"
                      value={adv.lightweight}
                      onChange={(e) =>
                        setRoleDrafts((prev) => ({
                          ...prev,
                          [p.id]: { ...adv, lightweight: e.target.value },
                        }))
                      }
                    />
                  </div>
                  {p.kind === "local" && (
                    <div className="field">
                      <label htmlFor={`ctx-${p.id}`} className="field-label">
                        Context Limit (tokens)
                      </label>
                      <select
                        id={`ctx-${p.id}`}
                        className="select mono"
                        value={getContextLimit(p)}
                        onChange={(e) =>
                          setCtxDrafts((prev) => ({ ...prev, [p.id]: Number(e.target.value) }))
                        }
                      >
                        <option value={1024}>1024 (Lowest RAM)</option>
                        <option value={2048}>2048 (Recommended for 8 GB)</option>
                        <option value={4096}>4096 (Balanced)</option>
                        <option value={8192}>8192 (16+ GB RAM)</option>
                      </select>
                    </div>
                  )}
                </div>
              </details>

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

              {activeCaps.length > 0 && (
                <div className="flex-row flex-wrap text-sm">
                  <span className="text-muted">Detected capabilities ({primary}):</span>
                  {activeCaps.map((cap) => (
                    <StatusTag key={cap} tone="neutral" label={cap.replace(/_/g, " ")} />
                  ))}
                </div>
              )}
            </section>
          );
        })}

        <details className="panel">
          <summary className="panel-title" style={{ cursor: "pointer" }}>
            Provider Fallback Priority &amp; Live Streaming Test
          </summary>
          <div className="list-stack" style={{ gap: 16, marginTop: 14 }}>
            <div className="list-stack" style={{ gap: 8 }}>
              <span className="field-label">Automatic Fallback Order</span>
              <p className="text-sm text-muted">
                If the top provider is unreachable, rate-limited, or produces an invalid plan,
                OmniDesk tries the next permitted provider and falls back safely to the
                deterministic local planner.
              </p>
              {fallbackOrder.map((pid, idx) => (
                <div key={pid} className="list-row">
                  <div className="flex-row">
                    <span className="kbd-cap tabular">{idx + 1}</span>
                    <span className="mono">{pid}</span>
                  </div>
                  <div className="flex-row">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={idx === 0}
                      aria-label={`Move ${pid} up`}
                      onClick={() => void handleMoveFallback(idx, -1)}
                    >
                      <ArrowUp size={14} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={idx === fallbackOrder.length - 1}
                      aria-label={`Move ${pid} down`}
                      onClick={() => void handleMoveFallback(idx, 1)}
                    >
                      <ArrowDown size={14} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel-subtle list-stack" style={{ gap: 10 }}>
              <span className="field-label">Live Streaming &amp; Cancellation Verification</span>
              <div className="flex-row flex-wrap">
                <select
                  aria-label="Provider for live stream test"
                  className="select mono"
                  style={{ maxWidth: 220 }}
                  value={streamProvider}
                  onChange={(e) => setStreamProvider(e.target.value)}
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Test prompt"
                  className="input"
                  style={{ flex: "1 1 240px" }}
                  value={streamPrompt}
                  onChange={(e) => setStreamPrompt(e.target.value)}
                />
                {!streaming ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void handleStreamTest()}
                  >
                    <Play size={14} aria-hidden="true" />
                    <span>Stream Test</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => void handleCancelStream()}
                  >
                    <Square size={14} aria-hidden="true" />
                    <span>Cancel</span>
                  </button>
                )}
              </div>
              {streamMeta && <div className="text-sm text-muted mono">{streamMeta}</div>}
              {streamOutput && (
                <div
                  className="panel-subtle text-sm"
                  style={{ background: "var(--bg-surface)", whiteSpace: "pre-wrap" }}
                >
                  {streamOutput}
                </div>
              )}
            </div>
          </div>
        </details>
      </div>
    </>
  );
};
