use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};
use sysinfo::System;

use crate::platform::{current_adapter, CapabilityEntry, DisplayInfo};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemProfile {
    pub os_name: String,
    pub os_version: String,
    pub arch: String,
    pub cpu_model: String,
    pub cpu_cores: usize,
    pub memory_total_gb: f64,
    pub gpu_name: String,
    pub desktop_environment: String,
    pub display_server: String,
    pub displays: Vec<DisplayInfo>,
    pub glass_material: String,
    pub capabilities: Vec<CapabilityEntry>,
}

fn check_ollama_installed() -> bool {
    let candidates = [
        "ollama",
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
    ];
    candidates.iter().any(|bin| {
        Command::new(bin)
            .arg("--version")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    })
}

fn check_playwright_browser_cache() -> bool {
    let candidates = [
        std::env::var("HOME")
            .ok()
            .map(|h| PathBuf::from(h).join("Library/Caches/ms-playwright")),
        std::env::var("HOME")
            .ok()
            .map(|h| PathBuf::from(h).join(".cache/ms-playwright")),
        std::env::var("LOCALAPPDATA")
            .ok()
            .map(|h| PathBuf::from(h).join("ms-playwright")),
    ];
    candidates.into_iter().flatten().any(|dir| {
        dir.exists()
            && std::fs::read_dir(dir)
                .map(|mut rd| rd.next().is_some())
                .unwrap_or(false)
    })
}

pub fn collect_system_profile() -> SystemProfile {
    let mut sys = System::new_all();
    sys.refresh_cpu_all();
    sys.refresh_memory();

    let adapter = current_adapter();
    let (desktop_environment, display_server) = adapter.desktop_environment();

    let cpu_model = sys
        .cpus()
        .first()
        .map(|c| c.brand().trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "Unknown CPU".to_string());

    let memory_total_gb =
        ((sys.total_memory() as f64) / (1024.0 * 1024.0 * 1024.0) * 10.0).round() / 10.0;

    let mut capabilities = adapter.platform_capabilities();

    let ollama_installed = check_ollama_installed();
    capabilities.push(CapabilityEntry {
        id: "runtime.ollama".into(),
        name: "Local Ollama Inference".into(),
        category: "ai_runtime".into(),
        status: if ollama_installed { "available" } else { "not_installed" }.into(),
        maturity: "implemented_tested".into(),
        detail: if ollama_installed {
            "Ollama CLI detected for local model inference.".into()
        } else {
            "Ollama is not installed on this device. Install Ollama or configure a provider in Models."
                .into()
        },
        platform_note: None,
    });

    let playwright_ready = check_playwright_browser_cache();
    capabilities.push(CapabilityEntry {
        id: "automation.playwright".into(),
        name: "Playwright Browser Automation".into(),
        category: "browser".into(),
        status: if playwright_ready { "available" } else { "not_installed" }.into(),
        maturity: "implemented_tested".into(),
        detail: if playwright_ready {
            "Playwright Chromium browser binaries detected locally for real DOM automation.".into()
        } else {
            "Run `uv run playwright install chromium` in backend/ to download Chromium.".into()
        },
        platform_note: None,
    });

    capabilities.push(CapabilityEntry {
        id: "automation.filesystem".into(),
        name: "Scoped File & Spreadsheet Engine".into(),
        category: "automation".into(),
        status: "available".into(),
        maturity: "implemented_tested".into(),
        detail: "Scoped inspection, SHA-256 duplicate detection, dry-run planning, reversible moves, and .xlsx reporting."
            .into(),
        platform_note: None,
    });

    SystemProfile {
        os_name: System::name().unwrap_or_else(|| std::env::consts::OS.to_string()),
        os_version: System::os_version().unwrap_or_else(|| "Unknown".to_string()),
        arch: std::env::consts::ARCH.to_string(),
        cpu_model,
        cpu_cores: sys.cpus().len(),
        memory_total_gb,
        gpu_name: adapter.detect_gpu(),
        desktop_environment,
        display_server,
        displays: adapter.detect_displays(),
        glass_material: adapter.glass_material_kind().to_string(),
        capabilities,
    }
}

#[cfg(test)]
mod tests {
    use super::collect_system_profile;

    #[test]
    fn collects_real_host_profile() {
        let profile = collect_system_profile();
        assert!(!profile.os_name.is_empty());
        assert!(profile.cpu_cores >= 1);
        assert!(profile.memory_total_gb > 0.0);
        assert!(profile
            .capabilities
            .iter()
            .any(|c| c.id == "automation.filesystem" && c.maturity == "implemented_tested"));
    }
}
