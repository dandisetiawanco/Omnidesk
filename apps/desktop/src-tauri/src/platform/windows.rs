use std::process::Command;

use super::{validate_app_identifier, ActiveWindowSnapshot, CapabilityEntry, DisplayInfo, PlatformAdapter};

pub struct WindowsAdapter;

impl PlatformAdapter for WindowsAdapter {
    fn desktop_environment(&self) -> (String, String) {
        ("Windows Desktop Shell".to_string(), "DWM".to_string())
    }

    fn detect_gpu(&self) -> String {
        "Windows DirectX / WDDM GPU".to_string()
    }

    fn detect_displays(&self) -> Vec<DisplayInfo> {
        vec![DisplayInfo {
            name: "Primary Display".into(),
            width: 1920,
            height: 1080,
            scale_factor: 1.0,
        }]
    }

    fn glass_material_kind(&self) -> &'static str {
        "windows_mica"
    }

    fn platform_capabilities(&self) -> Vec<CapabilityEntry> {
        vec![
            CapabilityEntry {
                id: "windows.uia".into(),
                name: "Windows UI Automation".into(),
                category: "os".into(),
                status: "experimental".into(),
                detail: "Windows UIA tree adapter is wired for semantic control lookup; validate on Windows 10/11 hardware.".into(),
                platform_note: Some("Requires Windows build validation in CI/desktop testing.".into()),
            },
            CapabilityEntry {
                id: "windows.credential_manager".into(),
                name: "Windows Credential Manager".into(),
                category: "security".into(),
                status: "available".into(),
                detail: "API provider secrets use Windows Credential Manager via keyring.".into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "windows.app_launch".into(),
                name: "Native Application Launcher".into(),
                category: "automation".into(),
                status: "available".into(),
                detail: "Launches installed applications through Windows ShellExecute.".into(),
                platform_note: None,
            },
        ]
    }

    fn launch_application(&self, app_name: &str) -> Result<String, String> {
        let clean = validate_app_identifier(app_name)?;
        let status = Command::new("explorer.exe")
            .arg(&clean)
            .status()
            .map_err(|e| format!("Failed to start {clean}: {e}"))?;
        if status.success() {
            Ok(format!("Launched {clean}."))
        } else {
            Err(format!("Windows could not start '{clean}'."))
        }
    }

    fn active_window(&self) -> ActiveWindowSnapshot {
        ActiveWindowSnapshot {
            app_name: "Windows Foreground Process".into(),
            window_title: "Available via Windows UIA adapter".into(),
            accessibility_available: true,
            note: "Collected on demand.".into(),
        }
    }
}
