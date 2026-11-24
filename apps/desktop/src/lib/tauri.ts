import { invoke } from "@tauri-apps/api/core";

export interface BackendConnection {
  base_url: string;
  token: string;
}

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function getBackendConnection(): Promise<BackendConnection> {
  if (isTauriRuntime()) {
    return invoke<BackendConnection>("get_backend_connection");
  }
  const url = import.meta.env.VITE_OMNIDESK_API_URL || "http://127.0.0.1:17420";
  const token = import.meta.env.VITE_OMNIDESK_SESSION_TOKEN || "";
  return { base_url: url, token };
}

export async function pickScopedDirectory(): Promise<string | null> {
  if (isTauriRuntime()) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      directory: true,
      multiple: false,
      title: "Select Scoped Directory for OmniDesk",
    });
    return typeof selected === "string" ? selected : null;
  }
  return null;
}

export async function sendDesktopNotification(title: string, body: string): Promise<void> {
  if (!isTauriRuntime()) return;
  try {
    const notif = await import("@tauri-apps/plugin-notification");
    let granted = await notif.isPermissionGranted();
    if (!granted) {
      const perm = await notif.requestPermission();
      granted = perm === "granted";
    }
    if (granted) {
      notif.sendNotification({ title, body });
    }
  } catch {
    // Notification permission may be declined by the user; fail silently.
  }
}
