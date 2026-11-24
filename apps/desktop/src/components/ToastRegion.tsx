import React from "react";
import { X } from "lucide-react";

export interface ToastMessage {
  id: string;
  title: string;
  detail?: string;
  tone: "info" | "success" | "error";
}

interface ToastRegionProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastRegion: React.FC<ToastRegionProps> = ({ toasts, onDismiss }) => (
  <div className="toast-stack" aria-live="polite" aria-atomic="false">
    {toasts.map((toast) => (
      <div
        key={toast.id}
        className="toast-item"
        role={toast.tone === "error" ? "alert" : "status"}
      >
        <div>
          <div style={{ fontWeight: 600 }}>{toast.title}</div>
          {toast.detail && <div className="text-sm text-muted">{toast.detail}</div>}
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label="Dismiss notification"
          onClick={() => onDismiss(toast.id)}
        >
          <X size={15} aria-hidden="true" />
        </button>
      </div>
    ))}
  </div>
);
