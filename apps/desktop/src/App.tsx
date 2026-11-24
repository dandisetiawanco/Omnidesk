import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Circle, Command, Menu, RefreshCw, Square } from "lucide-react";
import type {
  AppSettings,
  ProviderStatus,
  SystemProfile,
  TaskRun,
  TeachSession,
  WorkflowDefinition,
} from "@omnidesk/shared-schemas";
import { api } from "./lib/api";
import { applyPerformanceMode, applyThemePreference, resolveSystemScheme } from "./lib/theme";
import { getNativeSystemProfile, isTauriRuntime, sendDesktopNotification } from "./lib/tauri";
import { BrandMark } from "./components/BrandMark";
import { Sidebar, type SectionId } from "./components/Sidebar";
import { CommandPalette } from "./components/CommandPalette";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { EmergencyStopBar } from "./components/EmergencyStopBar";
import { FloatingAssistant } from "./components/FloatingAssistant";
import { OnboardingDialog } from "./components/OnboardingDialog";
import { ToastRegion, type ToastMessage } from "./components/ToastRegion";
import { HomeView } from "./views/HomeView";

// Lazy-load secondary workspace sections for fast initial paint
const OperatorView = lazy(() =>
  import("./views/OperatorView").then((m) => ({ default: m.OperatorView }))
);
const LiveWorkspaceView = lazy(() =>
  import("./views/LiveWorkspaceView").then((m) => ({ default: m.LiveWorkspaceView }))
);
const WorkflowStudioView = lazy(() =>
  import("./views/WorkflowStudioView").then((m) => ({ default: m.WorkflowStudioView }))
);
const TeachModeView = lazy(() =>
  import("./views/TeachModeView").then((m) => ({ default: m.TeachModeView }))
);
const ActivityView = lazy(() =>
  import("./views/ActivityView").then((m) => ({ default: m.ActivityView }))
);
const ModelsView = lazy(() =>
  import("./views/ModelsView").then((m) => ({ default: m.ModelsView }))
);
const SettingsView = lazy(() =>
  import("./views/SettingsView").then((m) => ({ default: m.SettingsView }))
);

const DEFAULT_SETTINGS: AppSettings = {
  theme: "system",
  performance_mode: false,
  privacy_mode: "local_only",
  cloud_screenshot_consent: false,
  data_retention_days: 30,
  excluded_apps: ["1Password", "Bitwarden", "Keychain Access", "KeePassXC"],
  scoped_directories: [],
  global_shortcut: "CommandOrControl+Shift+Space",
  onboarding_completed: true,
  telemetry_enabled: false,
};

const SECTION_TITLES: Record<SectionId, string> = {
  home: "Home | OmniDesk",
  operator: "Operator | OmniDesk",
  live: "Live Workspace | OmniDesk",
  workflows: "Workflow Studio | OmniDesk",
  teach: "Teach Mode | OmniDesk",
  activity: "Activity | OmniDesk",
  models: "Models | OmniDesk",
  settings: "Settings | OmniDesk",
};

export const App: React.FC = () => {
  const [bootState, setBootState] = useState<"loading" | "ready" | "error">("loading");
  const [bootError, setBootError] = useState<string | null>(null);
  const [section, setSection] = useState<SectionId>("home");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const [profile, setProfile] = useState<SystemProfile | null>(null);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [tasks, setTasks] = useState<TaskRun[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [activeRecording, setActiveRecording] = useState<TeachSession | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [studioWfId, setStudioWfId] = useState<string | null>(null);
  const [demoDirectory, setDemoDirectory] = useState<string | null>(null);
  const [dismissedApprovalId, setDismissedApprovalId] = useState<string | null>(null);
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  const notify = useCallback(
    (title: string, detail?: string, tone: "info" | "success" | "error" = "info") => {
      const id = `t-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev.slice(-1), { id, title, detail, tone }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
      }, 3600);
    },
    []
  );

  const upsertTask = useCallback((updated: TaskRun) => {
    setTasks((prev) => {
      const exists = prev.some((t) => t.id === updated.id);
      if (exists) {
        return prev.map((t) => (t.id === updated.id ? updated : t));
      }
      return [updated, ...prev];
    });
  }, []);

  const refreshAll = useCallback(async () => {
    const [nativeProf, apiProf, cfg, provs, taskList, wfList, teachList] = await Promise.all([
      getNativeSystemProfile(),
      api.getSystemProfile(),
      api.getSettings(),
      api.listProviders(false),
      api.listTasks(),
      api.listWorkflows(),
      api.listTeachSessions(),
    ]);
    setProfile(nativeProf ?? apiProf);
    setSettings(cfg);
    applyThemePreference(cfg.theme);
    applyPerformanceMode(cfg.performance_mode);
    setProviders(provs);
    setTasks(taskList);
    setWorkflows(wfList);
    setActiveRecording(teachList.find((s) => s.status === "recording") ?? null);
  }, []);

  const bootstrap = useCallback(async () => {
    setBootState("loading");
    setBootError(null);
    const maxAttempts = 14;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        await api.health();
        await refreshAll();
        setBootState("ready");
        return;
      } catch (err) {
        if (attempt === maxAttempts) {
          setBootError(
            err instanceof Error
              ? err.message
              : "Could not reach the local OmniDesk engine on 127.0.0.1."
          );
          setBootState("error");
          return;
        }
        await new Promise((r) => setTimeout(r, 300));
      }
    }
  }, [refreshAll]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    document.title = SECTION_TITLES[section];
  }, [section]);

  useEffect(() => {
    if (settings.theme !== "system" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => {
      document.documentElement.setAttribute("data-theme", resolveSystemScheme());
    };
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, [settings.theme]);

  useEffect(() => {
    if (bootState !== "ready") return;
    const controller = new AbortController();
    void api
      .streamTaskEvents((task) => {
        upsertTask(task);
        if (task.status === "completed") {
          void sendDesktopNotification("OmniDesk task completed", task.title);
        }
      }, controller.signal)
      .catch(() => {});
    return () => controller.abort();
  }, [bootState, upsertTask]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    let unlistenPalette: (() => void) | undefined;
    let unlistenStop: (() => void) | undefined;
    void (async () => {
      const { listen } = await import("@tauri-apps/api/event");
      unlistenPalette = await listen("omnidesk:open-palette", () => setPaletteOpen(true));
      unlistenStop = await listen("omnidesk:emergency-stop", () => {
        void handleEmergencyStop();
      });
    })();
    return () => {
      unlistenPalette?.();
      unlistenStop?.();
    };
  }, []);

  const activeTask =
    tasks.find((t) =>
      ["awaiting_approval", "running", "paused", "planning"].includes(t.status)
    ) ?? null;

  const pendingApproval =
    tasks.find(
      (t) =>
        t.pending_approval &&
        t.pending_approval.status === "pending" &&
        t.pending_approval.id !== dismissedApprovalId
    )?.pending_approval ?? null;

  const handleStartTask = async (
    prompt: string,
    targetDir?: string,
    dryRun = false,
    providerId?: string,
    attachedApp?: string,
    attachedUrl?: string
  ) => {
    const created = await api.createTask({
      prompt,
      target_directory: targetDir,
      dry_run_only: dryRun,
      provider_id: providerId,
      attached_app: attachedApp,
      attached_url: attachedUrl,
    });
    upsertTask(created);
    setSelectedTaskId(created.id);
    setDismissedApprovalId(null);
    setSection("operator");
    notify("Task planned", created.title, "info");
  };

  const handleRunFlagshipDemo = async () => {
    try {
      const demo = await api.setupDemoSandbox();
      setDemoDirectory(demo.directory);
      await handleStartTask(demo.prompt, demo.directory, false);
    } catch (err) {
      notify("Flagship demo error", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const handleRunExternalAppDemo = async () => {
    try {
      const demo = await api.setupExternalAppDemo();
      await handleStartTask(demo.prompt, demo.directory, false, undefined, demo.app_name);
    } catch (err) {
      notify("External app demo error", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const handleApprovalDecision = async (approved: boolean) => {
    if (!pendingApproval) return;
    setSubmittingApproval(true);
    try {
      const updated = await api.decideApproval(pendingApproval.task_id, approved);
      upsertTask(updated);
      setDismissedApprovalId(null);
      notify(
        approved ? "Step approved" : "Step denied",
        approved
          ? "Executing verified operation with journal tracking."
          : "Execution stopped without applying changes.",
        approved ? "success" : "info"
      );
    } catch (err) {
      notify("Approval decision failed", err instanceof Error ? err.message : undefined, "error");
    } finally {
      setSubmittingApproval(false);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      const res = await api.emergencyStop();
      setActiveRecording(null);
      const refreshed = await api.listTasks();
      setTasks(refreshed);
      notify(
        "Emergency stop executed",
        res.count > 0 ? `Stopped ${res.count} active task(s).` : "All active observers and tasks halted.",
        "info"
      );
    } catch (err) {
      notify("Emergency stop failed", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const handleStopGlobalRecording = async () => {
    if (!activeRecording) return;
    try {
      await api.stopTeachSession(activeRecording.id);
      setActiveRecording(null);
      setSection("teach");
      notify("Teach Mode recording stopped", "Review captured steps and convert to a workflow.", "success");
    } catch (err) {
      notify("Could not stop recording", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const handleUndoTask = async (taskId: string) => {
    try {
      const res = await api.undoTask(taskId);
      const refreshed = await api.listTasks();
      setTasks(refreshed);
      notify(
        "Rollback completed",
        `Reverted ${res.reverted_count} operation(s)` +
          (res.skipped_count > 0 ? `, skipped ${res.skipped_count}.` : "."),
        res.skipped_count > 0 ? "info" : "success"
      );
    } catch (err) {
      notify("Undo failed", err instanceof Error ? err.message : undefined, "error");
    }
  };

  const handleSaveSettings = async (next: AppSettings) => {
    setSettings(next);
    applyThemePreference(next.theme);
    applyPerformanceMode(next.performance_mode);
    const saved = await api.saveSettings(next);
    setSettings(saved);
  };

  const handleOnboardingComplete = async (updated: AppSettings, prepareDemo: boolean) => {
    await handleSaveSettings(updated);
    if (prepareDemo) {
      try {
        const demo = await api.setupDemoSandbox();
        setDemoDirectory(demo.directory);
        notify("Demo sandbox ready", `Prepared 8 sample files with 2 duplicate pairs in ${demo.directory}.`, "success");
      } catch {
        // Non-fatal.
      }
    }
  };

  if (bootState === "loading") {
    return (
      <main
        style={{
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          background: "var(--bg-canvas)",
        }}
      >
        <div className="panel" style={{ maxWidth: 420, alignItems: "center", textAlign: "center" }}>
          <BrandMark size={44} decorative={false} />
          <h1 className="page-title" style={{ fontSize: "1.25rem" }}>
            Starting OmniDesk
          </h1>
          <p className="text-muted text-sm">
            Connecting to the authenticated local operator engine and inspecting device
            capabilities...
          </p>
        </div>
      </main>
    );
  }

  if (bootState === "error") {
    return (
      <main
        style={{
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          background: "var(--bg-canvas)",
        }}
      >
        <div className="panel" style={{ maxWidth: 500 }}>
          <div className="flex-row">
            <BrandMark size={32} />
            <h1 className="page-title" style={{ fontSize: "1.2rem" }}>
              Local Operator Engine Unreachable
            </h1>
          </div>
          <p className="text-muted">
            OmniDesk could not establish an authenticated connection to its local Python engine.
          </p>
          {bootError && (
            <div
              className="panel-subtle mono text-sm"
              role="alert"
              style={{ color: "var(--status-danger-text)" }}
            >
              {bootError}
            </div>
          )}
          <div className="flex-row">
            <button type="button" className="btn btn-primary" onClick={() => void bootstrap()}>
              <RefreshCw size={15} aria-hidden="true" />
              <span>Retry Connection</span>
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell" data-collapsed={sidebarCollapsed ? "true" : "false"}>
      <a href="#main-workspace" className="skip-link">
        Skip to main workspace
      </a>

      <Sidebar
        active={section}
        onSelect={setSection}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => {
          setMobileMenuOpen(false);
          mobileTriggerRef.current?.focus();
        }}
        onOpenPalette={() => setPaletteOpen(true)}
        activeTasksCount={activeTask ? 1 : 0}
        pendingApprovalsCount={pendingApproval ? 1 : 0}
      />

      <div className="workspace-column">
        <header className="topbar" data-tauri-drag-region="true">
          <div className="topbar-left" data-tauri-drag-region="true">
            <button
              ref={mobileTriggerRef}
              type="button"
              className="btn mobile-menu-trigger"
              aria-expanded={mobileMenuOpen}
              aria-label="Open navigation menu"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Menu size={16} aria-hidden="true" />
              <span>Menu</span>
            </button>
            <span className="text-sm text-muted" data-tauri-drag-region="true">
              {profile
                ? `${profile.os_name} ${profile.os_version} | ${profile.glass_material.replace(/_/g, " ")}`
                : "Local Desktop"}
            </span>
          </div>

          <div className="topbar-right">
            <button
              type="button"
              className="btn"
              style={{ minHeight: 30, fontSize: 12.5 }}
              onClick={() => setPaletteOpen(true)}
            >
              <Command size={14} aria-hidden="true" />
              <span>Command</span>
              <kbd className="kbd-cap">Cmd K</kbd>
            </button>
          </div>
        </header>

        {activeRecording && (
          <div className="recording-banner" role="status" aria-live="polite">
            <div className="flex-row flex-wrap">
              <Circle size={13} fill="currentColor" aria-hidden="true" />
              <strong>Teach Mode Recording:</strong>
              <span>{activeRecording.name}</span>
              <span className="text-sm">
                ({activeRecording.scope_app || "permitted external apps"} |{" "}
                {activeRecording.events.length} step(s))
              </span>
            </div>
            <div className="flex-row">
              <button type="button" className="btn" onClick={() => setSection("teach")}>
                Open Recorder
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => void handleStopGlobalRecording()}
              >
                <Square size={14} aria-hidden="true" />
                <span>Stop Recording</span>
              </button>
            </div>
          </div>
        )}

        <EmergencyStopBar
          activeTask={activeTask}
          onInspect={() => {
            if (activeTask) setSelectedTaskId(activeTask.id);
            setSection("operator");
          }}
          onOpenApproval={() => {
            setDismissedApprovalId(null);
            if (activeTask) setSelectedTaskId(activeTask.id);
            setSection("operator");
          }}
          onEmergencyStop={() => void handleEmergencyStop()}
        />

        <main id="main-workspace" className="main-content" tabIndex={-1}>
          <Suspense
            fallback={
              <div className="state-box">
                <strong>Loading workspace section...</strong>
              </div>
            }
          >
            <div key={section} className="view-stage">
              {section === "home" && (
                <HomeView
                  profile={profile}
                  providers={providers}
                  settings={settings}
                  tasks={tasks}
                  workflows={workflows}
                  demoDirectory={demoDirectory}
                  onStartTask={handleStartTask}
                  onRunFlagshipDemo={handleRunFlagshipDemo}
                  onRunExternalAppDemo={handleRunExternalAppDemo}
                  onOpenTask={(id) => {
                    setSelectedTaskId(id);
                    setSection("operator");
                  }}
                  onRunWorkflow={async (wf) => {
                    const vars: Record<string, string> = {};
                    if (demoDirectory) vars.target_directory = demoDirectory;
                    const run = await api.runWorkflow(wf.id, vars, false);
                    upsertTask(run);
                    setSelectedTaskId(run.id);
                    setSection("operator");
                  }}
                  onNavigateModels={() => setSection("models")}
                  onNavigateStudio={() => setSection("workflows")}
                />
              )}

              {section === "operator" && (
                <OperatorView
                  tasks={tasks}
                  selectedTaskId={selectedTaskId}
                  onSelectTask={setSelectedTaskId}
                  onStartTask={(prompt, dir) => handleStartTask(prompt, dir, false)}
                  onOpenApproval={() => setDismissedApprovalId(null)}
                  onPause={async (id) => upsertTask(await api.pauseTask(id))}
                  onResume={async (id) => upsertTask(await api.resumeTask(id))}
                  onCancel={async (id) => upsertTask(await api.cancelTask(id))}
                  onUndo={handleUndoTask}
                  onEmergencyStop={handleEmergencyStop}
                  onRunFlagshipDemo={handleRunFlagshipDemo}
                />
              )}

              {section === "live" && (
                <LiveWorkspaceView profile={profile} settings={settings} onNotify={notify} />
              )}

              {section === "workflows" && (
                <WorkflowStudioView
                  workflows={workflows}
                  initialWorkflowId={studioWfId}
                  onSaveWorkflow={async (wf) => {
                    const saved = await api.saveWorkflow(wf);
                    setWorkflows(await api.listWorkflows());
                    return saved;
                  }}
                  onDeleteWorkflow={async (id) => {
                    await api.deleteWorkflow(id);
                    setWorkflows(await api.listWorkflows());
                    notify("Workflow deleted", undefined, "info");
                  }}
                  onRunWorkflow={async (wf, vars, dryRun) => {
                    const run = await api.runWorkflow(wf.id, vars, dryRun);
                    upsertTask(run);
                    setSelectedTaskId(run.id);
                    setSection("operator");
                  }}
                  onNotify={notify}
                />
              )}

              {section === "teach" && (
                <TeachModeView
                  demoDirectory={demoDirectory}
                  activeRecording={activeRecording}
                  onRecordingChange={setActiveRecording}
                  onWorkflowCreated={(wf) => {
                    setWorkflows((prev) => [wf, ...prev.filter((w) => w.id !== wf.id)]);
                  }}
                  onOpenInStudio={(wfId) => {
                    setStudioWfId(wfId);
                    setSection("workflows");
                  }}
                  onTestWorkflow={async (wf) => {
                    const vars: Record<string, string> = {};
                    if (demoDirectory) vars.target_directory = demoDirectory;
                    const run = await api.runWorkflow(wf.id, vars, true);
                    upsertTask(run);
                    setSelectedTaskId(run.id);
                    setSection("operator");
                  }}
                  onNotify={notify}
                />
              )}

              {section === "activity" && (
                <ActivityView
                  tasks={tasks}
                  onRefresh={async () => setTasks(await api.listTasks())}
                  onOpenTask={(id) => {
                    setSelectedTaskId(id);
                    setSection("operator");
                  }}
                  onUndoTask={handleUndoTask}
                  onDeleteTask={async (id) => {
                    await api.deleteTask(id);
                    setTasks((prev) => prev.filter((t) => t.id !== id));
                    notify("Task entry deleted", undefined, "info");
                  }}
                  onClearHistory={async () => {
                    await api.clearHistory();
                    setTasks([]);
                    setSelectedTaskId(null);
                    notify("Local history cleared", undefined, "info");
                  }}
                />
              )}

              {section === "models" && (
                <ModelsView
                  providers={providers}
                  onRefresh={async (probe = false) => setProviders(await api.listProviders(probe))}
                  onNotify={notify}
                />
              )}

              {section === "settings" && (
                <SettingsView
                  settings={settings}
                  profile={profile}
                  onSaveSettings={handleSaveSettings}
                  onNotify={notify}
                />
              )}
            </div>
          </Suspense>
        </main>
      </div>

      <FloatingAssistant
        activeTask={activeTask}
        onStartTask={(prompt) => handleStartTask(prompt)}
        onOpenOperator={() => {
          if (activeTask) setSelectedTaskId(activeTask.id);
          setSection("operator");
        }}
        onOpenApproval={() => {
          setDismissedApprovalId(null);
          if (activeTask) setSelectedTaskId(activeTask.id);
          setSection("operator");
        }}
        onEmergencyStop={handleEmergencyStop}
      />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={setSection}
        onStartPrompt={(prompt) => void handleStartTask(prompt)}
        onRunWorkflow={(wf) => {
          void api
            .runWorkflow(wf.id, demoDirectory ? { target_directory: demoDirectory } : {}, false)
            .then((run) => {
              upsertTask(run);
              setSelectedTaskId(run.id);
              setSection("operator");
            });
        }}
        onRunFlagshipDemo={() => void handleRunFlagshipDemo()}
        onEmergencyStop={() => void handleEmergencyStop()}
        workflows={workflows}
        activeTask={activeTask}
      />

      <ApprovalDialog
        approval={pendingApproval}
        submitting={submittingApproval}
        onDecision={(approved) => void handleApprovalDecision(approved)}
        onDismiss={() => {
          if (pendingApproval) setDismissedApprovalId(pendingApproval.id);
        }}
      />

      <OnboardingDialog
        open={!settings.onboarding_completed}
        settings={settings}
        onComplete={(updated, prepareDemo) => void handleOnboardingComplete(updated, prepareDemo)}
      />

      <ToastRegion
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />
    </div>
  );
};
