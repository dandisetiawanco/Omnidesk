import type {
  AppSettings,
  ProviderStatus,
  SystemProfile,
  TaskRun,
  TeachSession,
  WorkflowDefinition,
} from "@omnidesk/shared-schemas";
import { getBackendConnection } from "./tauri";

export interface AuditEntry {
  id: string;
  timestamp: string;
  category: string;
  action: string;
  detail: string;
  risk?: string | null;
  task_id?: string | null;
}

export interface LiveSnapshotResult {
  captured: boolean;
  blocked_by_privacy: boolean;
  active_window: {
    platform: string;
    app_name: string;
    status: string;
    note: string;
  };
  width?: number;
  height?: number;
  message: string;
  image_data_url: string | null;
}

export interface DemoSandboxInfo {
  directory: string;
  file_count: number;
  expected_duplicate_groups: number;
  prompt: string;
}

class OmniDeskApiClient {
  private baseUrl = "http://127.0.0.1:17420";
  private token = "";
  private ready = false;

  async init(): Promise<void> {
    if (this.ready) return;
    const conn = await getBackendConnection();
    this.baseUrl = conn.base_url.replace(/\/$/, "");
    this.token = conn.token;
    this.ready = true;
  }

  setConnection(baseUrl: string, token: string): void {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.token = token;
    this.ready = true;
  }

  getConnectionInfo(): { baseUrl: string; authenticated: boolean } {
    return { baseUrl: this.baseUrl, authenticated: this.token.length >= 16 };
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    await this.init();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    };
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    const resp = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (!resp.ok) {
      let detail = `Request failed (${resp.status})`;
      try {
        const err = await resp.json();
        if (err && typeof err.detail === "string") detail = err.detail;
      } catch {
        // Keep HTTP status message.
      }
      throw new Error(detail);
    }
    return (await resp.json()) as T;
  }

  async health(): Promise<{ status: string; version: string }> {
    await this.init();
    const resp = await fetch(`${this.baseUrl}/health`);
    if (!resp.ok) throw new Error(`Backend unreachable (${resp.status})`);
    return resp.json();
  }

  getSystemProfile(): Promise<SystemProfile> {
    return this.request("/api/system/profile");
  }

  getActiveWindow(): Promise<{ platform: string; app_name: string; status: string; note: string }> {
    return this.request("/api/system/active-window");
  }

  captureLiveSnapshot(): Promise<LiveSnapshotResult> {
    return this.request("/api/live/snapshot", { method: "POST" });
  }

  getSettings(): Promise<AppSettings> {
    return this.request("/api/settings");
  }

  saveSettings(settings: AppSettings): Promise<AppSettings> {
    return this.request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  }

  listProviders(probe = false): Promise<ProviderStatus[]> {
    return this.request(`/api/providers?probe=${probe ? "true" : "false"}`);
  }

  updateProvider(
    providerId: string,
    payload: {
      api_key?: string;
      clear_key?: boolean;
      base_url?: string;
      selected_models?: { planning?: string; vision?: string; lightweight?: string };
    }
  ): Promise<ProviderStatus> {
    return this.request(`/api/providers/${providerId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  testProvider(providerId: string): Promise<ProviderStatus> {
    return this.request(`/api/providers/${providerId}/test`, { method: "POST" });
  }

  listTasks(): Promise<TaskRun[]> {
    return this.request("/api/tasks");
  }

  createTask(payload: {
    prompt: string;
    target_directory?: string;
    dry_run_only?: boolean;
    provider_id?: string;
  }): Promise<TaskRun> {
    return this.request("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  decideApproval(taskId: string, approved: boolean, note?: string): Promise<TaskRun> {
    return this.request(`/api/tasks/${taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved, note }),
    });
  }

  pauseTask(taskId: string): Promise<TaskRun> {
    return this.request(`/api/tasks/${taskId}/pause`, { method: "POST" });
  }

  resumeTask(taskId: string): Promise<TaskRun> {
    return this.request(`/api/tasks/${taskId}/resume`, { method: "POST" });
  }

  cancelTask(taskId: string): Promise<TaskRun> {
    return this.request(`/api/tasks/${taskId}/cancel`, { method: "POST" });
  }

  undoTask(taskId: string): Promise<{
    task_id: string;
    reverted_count: number;
    skipped_count: number;
    errors: string[];
  }> {
    return this.request(`/api/tasks/${taskId}/undo`, { method: "POST" });
  }

  deleteTask(taskId: string): Promise<{ deleted: boolean }> {
    return this.request(`/api/tasks/${taskId}`, { method: "DELETE" });
  }

  emergencyStop(): Promise<{ stopped_task_ids: string[]; count: number }> {
    return this.request("/api/emergency-stop", { method: "POST" });
  }

  setupDemoSandbox(): Promise<DemoSandboxInfo> {
    return this.request("/api/demo/setup-downloads", { method: "POST" });
  }

  listAudit(): Promise<AuditEntry[]> {
    return this.request("/api/audit");
  }

  clearHistory(): Promise<{ cleared_tasks: number }> {
    return this.request("/api/history", { method: "DELETE" });
  }

  listWorkflows(): Promise<WorkflowDefinition[]> {
    return this.request("/api/workflows");
  }

  saveWorkflow(wf: WorkflowDefinition): Promise<WorkflowDefinition> {
    return this.request("/api/workflows", {
      method: "POST",
      body: JSON.stringify(wf),
    });
  }

  deleteWorkflow(id: string): Promise<{ deleted: boolean }> {
    return this.request(`/api/workflows/${id}`, { method: "DELETE" });
  }

  runWorkflow(id: string, variables: Record<string, string>, dryRun = false): Promise<TaskRun> {
    return this.request(`/api/workflows/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ variables, dry_run: dryRun }),
    });
  }

  listTeachSessions(): Promise<TeachSession[]> {
    return this.request("/api/teach/sessions");
  }

  startTeachSession(name: string): Promise<TeachSession> {
    return this.request("/api/teach/sessions", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }

  recordTeachStep(
    sessionId: string,
    step: {
      kind: "app_focus" | "file_action" | "browser_navigation" | "ui_semantic_click" | "report_export";
      summary: string;
      selector: string;
      app_name?: string;
      parameters: Record<string, unknown>;
      is_secure_field?: boolean;
    }
  ): Promise<TeachSession> {
    return this.request(`/api/teach/sessions/${sessionId}/step`, {
      method: "POST",
      body: JSON.stringify(step),
    });
  }

  captureTeachWindow(sessionId: string): Promise<TeachSession> {
    return this.request(`/api/teach/sessions/${sessionId}/capture-window`, { method: "POST" });
  }

  stopTeachSession(sessionId: string): Promise<TeachSession> {
    return this.request(`/api/teach/sessions/${sessionId}/stop`, { method: "POST" });
  }

  convertTeachSession(sessionId: string, name?: string): Promise<WorkflowDefinition> {
    const query = name ? `?name=${encodeURIComponent(name)}` : "";
    return this.request(`/api/teach/sessions/${sessionId}/convert${query}`, { method: "POST" });
  }

  listMcpTools(): Promise<
    Array<{ name: string; description: string; risk: string; requires_approval: boolean }>
  > {
    return this.request("/api/mcp/tools");
  }

  /** Streams task updates via authenticated fetch ReadableStream (never puts tokens in URLs). */
  async streamTaskEvents(
    onTaskUpdate: (task: TaskRun) => void,
    signal: AbortSignal
  ): Promise<void> {
    await this.init();
    const resp = await fetch(`${this.baseUrl}/api/events/stream`, {
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : {},
      signal,
    });
    if (!resp.ok || !resp.body) return;

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const dataLine = block
          .split("\n")
          .find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        try {
          const parsed = JSON.parse(dataLine.slice(5).trim());
          if (parsed && parsed.task) {
            onTaskUpdate(parsed.task as TaskRun);
          }
        } catch {
          // Ignore malformed keepalive chunks.
        }
      }
    }
  }
}

export const api = new OmniDeskApiClient();
