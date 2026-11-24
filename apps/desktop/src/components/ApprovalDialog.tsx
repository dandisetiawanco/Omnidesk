import React, { useEffect, useId, useRef } from "react";
import { ShieldAlert, Undo2, X } from "lucide-react";
import type { ApprovalRequest } from "@omnidesk/shared-schemas";
import { StatusTag } from "./StatusTag";
import { closeDialogWithTransition } from "../lib/dialog";

interface ApprovalDialogProps {
  approval: ApprovalRequest | null;
  submitting: boolean;
  onDecision: (approved: boolean) => void;
  onDismiss: () => void;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  approval,
  submitting,
  onDecision,
  onDismiss,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (approval && !dlg.open) {
      dlg.showModal();
    } else if (!approval && dlg.open) {
      void closeDialogWithTransition(dlg);
    }
  }, [approval]);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    const onCancel = (e: Event) => {
      e.preventDefault();
      onDismiss();
    };
    dlg.addEventListener("cancel", onCancel);
    return () => dlg.removeEventListener("cancel", onCancel);
  }, [onDismiss]);

  return (
    <dialog ref={dialogRef} className="glass-dialog" aria-labelledby={titleId}>
      {approval && (
        <>
          <div className="dialog-header">
            <div className="flex-row">
              <ShieldAlert size={19} aria-hidden="true" />
              <h2 id={titleId} className="panel-title">
                Approval Required
              </h2>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-label="Hide approval dialog"
              onClick={onDismiss}
            >
              <X size={17} aria-hidden="true" />
            </button>
          </div>

          <div className="dialog-body">
            <div className="flex-row flex-wrap">
              <StatusTag
                tone={
                  approval.risk === "destructive" || approval.risk === "privileged_system"
                    ? "danger"
                    : approval.risk === "external_communication" || approval.risk === "sensitive_access"
                      ? "warning"
                      : "accent"
                }
                kind="shield"
                label={`Risk: ${approval.risk.replace(/_/g, " ")}`}
              />
              <StatusTag
                tone={approval.reversible ? "success" : "warning"}
                kind={approval.reversible ? "check" : "warn"}
                label={approval.reversible ? "Reversible via journal" : "Not reversible"}
              />
            </div>

            <div>
              <h3 style={{ fontSize: 15, fontWeight: 620 }}>{approval.title}</h3>
              <p className="text-muted" style={{ marginTop: 4 }}>
                {approval.summary}
              </p>
            </div>

            <div className="panel-subtle">
              <div className="field-label" style={{ marginBottom: 4 }}>
                Target Scope
              </div>
              <div className="mono text-sm" style={{ wordBreak: "break-all" }}>
                {approval.scope}
              </div>
            </div>

            <div>
              <div className="field-label" style={{ marginBottom: 6 }}>
                Dry-Run Preview
              </div>
              <ul
                style={{
                  paddingInlineStart: 18,
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                }}
              >
                {approval.dry_run_items.map((item, idx) => (
                  <li key={idx} className="text-sm mono">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {approval.reversible && (
              <div className="flex-row text-sm text-muted">
                <Undo2 size={14} aria-hidden="true" />
                <span>
                  OmniDesk records SHA-256 hashes for every file move so you can roll back from
                  Operator or Activity.
                </span>
              </div>
            )}
          </div>

          <div className="dialog-footer">
            {/* Safe action focused first per modern-web-guidance dialog guidelines */}
            <button
              type="button"
              className="btn"
              autoFocus
              disabled={submitting}
              onClick={() => onDecision(false)}
            >
              Deny &amp; Stop Task
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={submitting}
              onClick={() => onDecision(true)}
            >
              {submitting ? "Applying..." : "Approve & Execute"}
            </button>
          </div>
        </>
      )}
    </dialog>
  );
};
