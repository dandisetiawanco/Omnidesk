import { describe, expect, it } from "vitest";
import {
  AppSettingsSchema,
  TaskRunSchema,
  WorkflowDefinitionSchema,
} from "./index";

describe("shared schemas", () => {
  it("validates a default local-first settings object", () => {
    const parsed = AppSettingsSchema.parse({
      theme: "system",
      performance_mode: false,
      privacy_mode: "local_only",
      cloud_screenshot_consent: false,
      data_retention_days: 30,
      excluded_apps: ["1Password", "Keychain Access"],
      scoped_directories: [],
      global_shortcut: "CommandOrControl+Shift+Space",
      onboarding_completed: false,
      telemetry_enabled: false,
    });
    expect(parsed.telemetry_enabled).toBe(false);
  });

  it("enforces bounded workflow loop limits", () => {
    expect(() =>
      WorkflowDefinitionSchema.parse({
        id: "wf-1",
        name: "Invalid Loop",
        description: "Too many iterations",
        version: 1,
        source: "manual",
        variables: [],
        max_loop_iterations: 500,
        nodes: [],
        edges: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    ).toThrow();
  });

  it("validates a structured task run contract", () => {
    const run = TaskRunSchema.parse({
      id: "task-1",
      prompt: "Inspect Downloads",
      title: "Inspect Downloads",
      status: "completed",
      planner_source: "local_structured_planner",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      can_undo: false,
      undone: false,
      steps: [],
      artifacts: [],
    });
    expect(run.status).toBe("completed");
  });
});
