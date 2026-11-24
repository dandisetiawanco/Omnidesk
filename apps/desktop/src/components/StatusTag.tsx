import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  PauseCircle,
  ShieldAlert,
  XCircle,
} from "lucide-react";

export type StatusTone = "neutral" | "accent" | "success" | "warning" | "danger";

interface StatusTagProps {
  tone: StatusTone;
  label: string;
  kind?: "check" | "warn" | "danger" | "clock" | "pause" | "shield";
}

export const StatusTag: React.FC<StatusTagProps> = ({ tone, label, kind }) => {
  const Icon =
    kind === "check"
      ? CheckCircle2
      : kind === "warn"
        ? AlertTriangle
        : kind === "danger"
          ? XCircle
          : kind === "pause"
            ? PauseCircle
            : kind === "shield"
              ? ShieldAlert
              : kind === "clock"
                ? Clock
                : null;

  return (
    <span className="status-tag" data-tone={tone}>
      {Icon && <Icon size={13} aria-hidden="true" />}
      <span>{label}</span>
    </span>
  );
};
