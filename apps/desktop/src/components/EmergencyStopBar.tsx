import React from "react";
import { OctagonX, ShieldAlert } from "lucide-react";
import type { TaskRun } from "@omnidesk/shared-schemas";

interface EmergencyStopBarProps {
  activeTask: TaskRun | null;
  onInspect: () => void;
  onOpenApproval: () => void;
  onEmergencyStop: () => void;
}

export const EmergencyStopBar: React.FC<EmergencyStopBarProps> = ({
  activeTask,
  onInspect,
  onOpenApproval,
  onEmergencyStop,
}) => {
  if (!activeTask) return null;
  const awaiting = activeTask.status === "awaiting_approval" && Boolean(activeTask.pending_approval);

  return (
    <div className="emergency-bar" role="status" aria-live="polite">
      <div className="flex-row flex-wrap">
        <ShieldAlert size={17} aria-hidden="true" />
        <strong>{awaiting ? "Approval waiting:" : "Execution active:"}</strong>
        <span>{activeTask.title}</span>
        <span className="text-sm">({activeTask.status.replace(/_/g, " ")})</span>
      </div>
      <div className="flex-row">
        {awaiting ? (
          <button type="button" className="btn btn-primary" onClick={onOpenApproval}>
            Review Approval
          </button>
        ) : (
          <button type="button" className="btn" onClick={onInspect}>
            Inspect Timeline
          </button>
        )}
        <button type="button" className="btn btn-danger" onClick={onEmergencyStop}>
          <OctagonX size={15} aria-hidden="true" />
          <span>Emergency Stop</span>
        </button>
      </div>
    </div>
  );
};
