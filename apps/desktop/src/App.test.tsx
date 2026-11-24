import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { App } from "./App";
import { api } from "./lib/api";

describe("OmniDesk Desktop App UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "0.1.0" });
    vi.spyOn(api, "getSystemProfile").mockResolvedValue({
      os_name: "macOS",
      os_version: "15.8.3",
      arch: "x86_64",
      cpu_model: "Intel Core i5",
      cpu_cores: 8,
      memory_total_gb: 8,
      gpu_name: "Intel Iris Plus",
      desktop_environment: "macOS Aqua",
      display_server: "Quartz Compositor",
      displays: [{ name: "Built-in Display", width: 2560, height: 1600, scale_factor: 2 }],
      glass_material: "macos_vibrancy",
      capabilities: [
        {
          id: "automation.filesystem",
          name: "Scoped File & Excel Engine",
          category: "automation",
          status: "available",
          detail: "Ready locally",
        },
      ],
    });
    vi.spyOn(api, "getSettings").mockResolvedValue({
      theme: "system",
      performance_mode: false,
      privacy_mode: "local_only",
      cloud_screenshot_consent: false,
      data_retention_days: 30,
      excluded_apps: ["1Password"],
      scoped_directories: [],
      global_shortcut: "CommandOrControl+Shift+Space",
      onboarding_completed: true,
      telemetry_enabled: false,
    });
    vi.spyOn(api, "listProviders").mockResolvedValue([
      {
        id: "ollama",
        label: "Ollama (Local)",
        kind: "local",
        configured: false,
        reachable: false,
        status_detail: "Ollama not reachable at http://127.0.0.1:11434",
        base_url: "http://127.0.0.1:11434",
        available_models: [],
        selected_models: {},
      },
    ]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "listWorkflows").mockResolvedValue([]);
    vi.spyOn(api, "listTeachSessions").mockResolvedValue([]);
    vi.spyOn(api, "listMcpTools").mockResolvedValue([]);
    vi.spyOn(api, "streamTaskEvents").mockResolvedValue();
  });

  it("renders Command Center, validates empty task form, and navigates sections", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Command Center" })).toBeInTheDocument();
    expect(screen.getAllByText(/Your computer. Powered by intelligence./i).length).toBeGreaterThan(0);

    // Empty form submission surfaces accessible error alert
    fireEvent.click(screen.getByRole("button", { name: /Plan & Execute/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Describe a desktop/i);

    // Sidebar collapse toggles aria-expanded
    const collapseBtn = screen.getByRole("button", { name: /Collapse sidebar/i });
    expect(collapseBtn).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(collapseBtn);
    expect(screen.getByRole("button", { name: /Expand sidebar/i })).toHaveAttribute(
      "aria-expanded",
      "false"
    );

    // Command palette opens on Cmd+K
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByRole("heading", { name: "Command Palette" })).toBeInTheDocument();

    // Navigate to Settings via sidebar button
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    });
    expect(screen.getByText(/NGOPREK DIGITAL/i)).toBeInTheDocument();
  });
});
