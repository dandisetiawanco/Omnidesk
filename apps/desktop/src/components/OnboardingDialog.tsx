import React, { useEffect, useId, useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import type { AppSettings } from "@omnidesk/shared-schemas";
import { BrandMark } from "./BrandMark";
import { closeDialogWithTransition } from "../lib/dialog";

interface OnboardingDialogProps {
  open: boolean;
  settings: AppSettings;
  onComplete: (updated: AppSettings, prepareDemo: boolean) => void;
}

export const OnboardingDialog: React.FC<OnboardingDialogProps> = ({
  open,
  settings,
  onComplete,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [privacyMode, setPrivacyMode] = useState<"local_only" | "cloud_assisted">(
    settings.privacy_mode
  );
  const [prepareDemo, setPrepareDemo] = useState(true);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      dlg.showModal();
    } else if (!open && dlg.open) {
      void closeDialogWithTransition(dlg);
    }
  }, [open]);

  const handleFinish = () => {
    onComplete(
      {
        ...settings,
        privacy_mode: privacyMode,
        onboarding_completed: true,
        telemetry_enabled: false,
      },
      prepareDemo
    );
  };

  return (
    <dialog ref={dialogRef} className="glass-dialog" aria-labelledby={titleId}>
      <div className="dialog-header">
        <div className="flex-row">
          <BrandMark size={26} />
          <div>
            <h2 id={titleId} className="panel-title">
              Welcome to OmniDesk
            </h2>
            <p className="text-sm text-muted">Your computer. Powered by intelligence.</p>
          </div>
        </div>
      </div>

      <div className="dialog-body">
        <p>
          OmniDesk operates files, browsers, and desktop applications through structured plans
          with deny-by-default permissions. Every file modification or external action pauses for
          your explicit approval.
        </p>

        <fieldset
          style={{
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <legend className="field-label" style={{ paddingInline: 6 }}>
            Choose Privacy Mode
          </legend>
          <label className="flex-row" style={{ alignItems: "flex-start" }}>
            <input
              type="radio"
              name="onboarding-privacy"
              checked={privacyMode === "local_only"}
              onChange={() => setPrivacyMode("local_only")}
            />
            <span>
              <strong>Local-only (Recommended)</strong>
              <br />
              <span className="text-sm text-muted">
                All planning, file organization, and local Ollama models stay on this machine. No
                context leaves your computer.
              </span>
            </span>
          </label>
          <label className="flex-row" style={{ alignItems: "flex-start" }}>
            <input
              type="radio"
              name="onboarding-privacy"
              checked={privacyMode === "cloud_assisted"}
              onChange={() => setPrivacyMode("cloud_assisted")}
            />
            <span>
              <strong>Cloud-assisted</strong>
              <br />
              <span className="text-sm text-muted">
                Enables configured OpenAI, Google Gemini, or Anthropic Claude providers stored in
                your OS Keychain.
              </span>
            </span>
          </label>
        </fieldset>

        <label className="flex-row" style={{ alignItems: "flex-start" }}>
          <input
            type="checkbox"
            checked={prepareDemo}
            onChange={(e) => setPrepareDemo(e.target.checked)}
          />
          <span>
            Prepare a safe sandbox folder with sample files and intentional duplicates so I can
            test the Downloads Organization &amp; Excel Report demo right away.
          </span>
        </label>

        <div className="flex-row text-sm text-muted">
          <ShieldCheck size={15} aria-hidden="true" />
          <span>Telemetry is disabled by default. API keys are never stored in plaintext.</span>
        </div>
      </div>

      <div className="dialog-footer">
        <button type="button" className="btn btn-primary" autoFocus onClick={handleFinish}>
          Open Command Center
        </button>
      </div>
    </dialog>
  );
};
