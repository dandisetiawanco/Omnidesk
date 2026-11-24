use std::process::Command;

use super::{validate_app_identifier, ActiveWindowSnapshot, CapabilityEntry, DisplayInfo, PlatformAdapter};

#[link(name = "ApplicationServices", kind = "framework")]
extern "C" {
    fn AXIsProcessTrusted() -> bool;
}

#[link(name = "CoreGraphics", kind = "framework")]
extern "C" {
    fn CGPreflightScreenCaptureAccess() -> bool;
}

pub struct MacOsAdapter;

impl MacOsAdapter {
    fn accessibility_trusted() -> bool {
        // Safe read-only macOS TCC trust query; never prompts or bypasses permissions.
        unsafe { AXIsProcessTrusted() }
    }

    fn screen_recording_granted() -> bool {
        unsafe { CGPreflightScreenCaptureAccess() }
    }
}

impl PlatformAdapter for MacOsAdapter {
    fn desktop_environment(&self) -> (String, String) {
        ("macOS Aqua".to_string(), "Quartz Compositor".to_string())
    }

    fn detect_gpu(&self) -> String {
        let output = Command::new("system_profiler")
            .args(["SPDisplaysDataType", "-json"])
            .output();
        if let Ok(out) = output {
            if out.status.success() {
                if let Ok(val) = serde_json::from_slice::<serde_json::Value>(&out.stdout) {
                    if let Some(gpus) = val.get("SPDisplaysDataType").and_then(|v| v.as_array()) {
                        let names: Vec<String> = gpus
                            .iter()
                            .filter_map(|g| {
                                g.get("sppci_model")
                                    .and_then(|s| s.as_str())
                                    .map(|s| s.to_string())
                            })
                            .collect();
                        if !names.is_empty() {
                            return names.join(" / ");
                        }
                    }
                }
            }
        }
        "macOS Metal GPU".to_string()
    }

    fn detect_displays(&self) -> Vec<DisplayInfo> {
        let output = Command::new("system_profiler")
            .args(["SPDisplaysDataType", "-json"])
            .output();
        let mut displays = Vec::new();
        if let Ok(out) = output {
            if out.status.success() {
                if let Ok(val) = serde_json::from_slice::<serde_json::Value>(&out.stdout) {
                    if let Some(gpus) = val.get("SPDisplaysDataType").and_then(|v| v.as_array()) {
                        for gpu in gpus {
                            if let Some(ndrv) = gpu.get("spdisplays_ndrvs").and_then(|v| v.as_array()) {
                                for d in ndrv {
                                    let name = d
                                        .get("_name")
                                        .and_then(|s| s.as_str())
                                        .unwrap_or("Display")
                                        .to_string();
                                    let res = d
                                        .get("_spdisplays_pixels")
                                        .and_then(|s| s.as_str())
                                        .unwrap_or("1440 x 900");
                                    let nums: Vec<u32> = res
                                        .split(|c: char| !c.is_ascii_digit())
                                        .filter(|s| !s.is_empty())
                                        .filter_map(|s| s.parse::<u32>().ok())
                                        .collect();
                                    let (w, h) = if nums.len() >= 2 {
                                        (nums[0], nums[1])
                                    } else {
                                        (1440, 900)
                                    };
                                    let is_retina = d
                                        .get("spdisplays_retina")
                                        .and_then(|s| s.as_str())
                                        .map(|s| s.contains("yes"))
                                        .unwrap_or(false);
                                    displays.push(DisplayInfo {
                                        name,
                                        width: w,
                                        height: h,
                                        scale_factor: if is_retina { 2.0 } else { 1.0 },
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
        if displays.is_empty() {
            displays.push(DisplayInfo {
                name: "Built-in Display".to_string(),
                width: 1440,
                height: 900,
                scale_factor: 2.0,
            });
        }
        displays
    }

    fn glass_material_kind(&self) -> &'static str {
        "macos_vibrancy"
    }

    fn platform_capabilities(&self) -> Vec<CapabilityEntry> {
        let ax = Self::accessibility_trusted();
        let screen = Self::screen_recording_granted();

        vec![
            CapabilityEntry {
                id: "macos.accessibility".into(),
                name: "macOS Accessibility API".into(),
                category: "os".into(),
                status: if ax { "available" } else { "permission_required" }.into(),
                detail: if ax {
                    "Accessibility permission granted for semantic UI tree inspection.".into()
                } else {
                    "Grant Accessibility in System Settings > Privacy & Security to enable semantic UI control.".into()
                },
                platform_note: Some("Checked via AXIsProcessTrusted; OmniDesk never bypasses TCC.".into()),
            },
            CapabilityEntry {
                id: "macos.screen_capture".into(),
                name: "ScreenCaptureKit / Screen Recording".into(),
                category: "vision".into(),
                status: if screen { "available" } else { "permission_required" }.into(),
                detail: if screen {
                    "Screen Recording permission granted for explicit opt-in workspace snapshots.".into()
                } else {
                    "Grant Screen Recording in System Settings > Privacy & Security when you want Live Workspace previews.".into()
                },
                platform_note: Some("Capture runs only when explicitly requested by the user.".into()),
            },
            CapabilityEntry {
                id: "macos.keychain".into(),
                name: "macOS Keychain Credential Store".into(),
                category: "security".into(),
                status: "available".into(),
                detail: "API provider credentials are stored in macOS Keychain via Security framework.".into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "macos.app_launch".into(),
                name: "Native Application Launcher".into(),
                category: "automation".into(),
                status: "available".into(),
                detail: "Opens installed macOS applications using LaunchServices (`open -a`).".into(),
                platform_note: None,
            },
        ]
    }

    fn launch_application(&self, app_name: &str) -> Result<String, String> {
        let clean = validate_app_identifier(app_name)?;
        let status = Command::new("open")
            .args(["-a", &clean])
            .status()
            .map_err(|e| format!("Failed to invoke macOS LaunchServices: {e}"))?;
        if status.success() {
            Ok(format!("Launched {clean}."))
        } else {
            Err(format!("Application '{clean}' could not be opened on macOS."))
        }
    }

    fn active_window(&self) -> ActiveWindowSnapshot {
        let ax = Self::accessibility_trusted();
        let output = Command::new("osascript")
            .args([
                "-e",
                "tell application \"System Events\" to get name of first application process whose frontmost is true",
            ])
            .output();
        match output {
            Ok(out) if out.status.success() => {
                let app = String::from_utf8_lossy(&out.stdout).trim().to_string();
                ActiveWindowSnapshot {
                    app_name: if app.is_empty() { "Unknown".into() } else { app },
                    window_title: if ax {
                        "Frontmost window accessible".into()
                    } else {
                        "Window title requires macOS Accessibility permission".into()
                    },
                    accessibility_available: ax,
                    note: "Collected on demand without background surveillance.".into(),
                }
            }
            _ => ActiveWindowSnapshot {
                app_name: "Permission required".into(),
                window_title: "Grant Automation / Accessibility permission in System Settings".into(),
                accessibility_available: ax,
                note: "macOS blocked Apple Events query until user authorizes System Events.".into(),
            },
        }
    }
}
