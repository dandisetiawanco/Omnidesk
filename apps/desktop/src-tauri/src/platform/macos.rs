use std::process::Command;

use super::{
    validate_app_identifier, ActiveWindowSnapshot, CapabilityEntry, DisplayInfo, PlatformAdapter,
};

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
        unsafe { AXIsProcessTrusted() }
    }

    fn screen_recording_granted() -> bool {
        unsafe { CGPreflightScreenCaptureAccess() }
    }

    fn frontmost_app_via_lsappinfo() -> Option<String> {
        let front = Command::new("lsappinfo").arg("front").output().ok()?;
        if !front.status.success() {
            return None;
        }
        let asn = String::from_utf8_lossy(&front.stdout).trim().to_string();
        if asn.is_empty() {
            return None;
        }
        let info = Command::new("lsappinfo")
            .args(["info", "-only", "name", &asn])
            .output()
            .ok()?;
        if !info.status.success() {
            return None;
        }
        let text = String::from_utf8_lossy(&info.stdout);
        for line in text.lines() {
            if let Some((_, rhs)) = line.split_once('=') {
                let clean = rhs.trim().trim_matches('"').to_string();
                if !clean.is_empty() {
                    return Some(clean);
                }
            }
        }
        None
    }
}

impl PlatformAdapter for MacOsAdapter {
    fn platform_id(&self) -> &'static str {
        "macos"
    }

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
                            if let Some(ndrv) = gpu.get("spdisplays_ndrvs").and_then(|v| v.as_array())
                            {
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
                maturity: "implemented_tested".into(),
                detail: if ax {
                    "Accessibility permission granted for semantic UI tree inspection and controlled input."
                        .into()
                } else {
                    "Grant Accessibility in System Settings > Privacy & Security to enable semantic UI control."
                        .into()
                },
                platform_note: Some("Verified via AXIsProcessTrusted; OmniDesk never bypasses TCC.".into()),
            },
            CapabilityEntry {
                id: "macos.screen_capture".into(),
                name: "ScreenCaptureKit / Screen Recording".into(),
                category: "vision".into(),
                status: if screen { "available" } else { "permission_required" }.into(),
                maturity: "implemented_tested".into(),
                detail: if screen {
                    "Screen Recording granted for explicit opt-in Live Workspace snapshots.".into()
                } else {
                    "Grant Screen Recording in System Settings > Privacy & Security for opt-in Live Workspace previews."
                        .into()
                },
                platform_note: Some("Single-shot capture runs only on explicit user action.".into()),
            },
            CapabilityEntry {
                id: "macos.keychain".into(),
                name: "macOS Keychain Credential Store".into(),
                category: "security".into(),
                status: "available".into(),
                maturity: "implemented_tested".into(),
                detail: "API provider credentials are stored in macOS Keychain via Security framework."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "macos.app_launch".into(),
                name: "Native App Launcher & Process Recognition".into(),
                category: "automation".into(),
                status: "available".into(),
                maturity: "implemented_tested".into(),
                detail: "Lists running GUI apps via LaunchServices (`lsappinfo`) and opens/focuses apps via `open -a`."
                    .into(),
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
        let app = Self::frontmost_app_via_lsappinfo().unwrap_or_else(|| "Unknown".into());
        let window_title = if ax {
            Command::new("osascript")
                .args([
                    "-e",
                    "tell application \"System Events\" to get title of front window of first application process whose frontmost is true",
                ])
                .output()
                .ok()
                .filter(|o| o.status.success())
                .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "Active window (no title reported)".into())
        } else {
            "Window title & element tree require macOS Accessibility permission".into()
        };

        ActiveWindowSnapshot {
            app_name: app,
            window_title,
            accessibility_available: ax,
            note: "Frontmost application identified via LaunchServices without background surveillance."
                .into(),
        }
    }

    fn list_running_apps(&self) -> Vec<String> {
        let output = Command::new("lsappinfo")
            .arg("visibleProcessList")
            .output()
            .ok();
        let mut apps = Vec::new();
        if let Some(out) = output {
            if out.status.success() {
                let raw = String::from_utf8_lossy(&out.stdout);
                for token in raw.split('"').skip(1).step_by(2) {
                    let clean = token.replace('_', " ").trim().to_string();
                    if !clean.is_empty() && !apps.contains(&clean) {
                        apps.push(clean);
                    }
                }
            }
        }
        apps
    }

    fn open_permission_settings(&self, pane: &str) -> Result<String, String> {
        let url = match pane {
            "accessibility" => {
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
            }
            "screen_recording" => {
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
            }
            "automation" => {
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
            }
            _ => return Err(format!("Unsupported macOS privacy pane: {pane}")),
        };
        let status = Command::new("open")
            .arg(url)
            .status()
            .map_err(|e| format!("Failed to open System Settings: {e}"))?;
        if status.success() {
            Ok(format!("Opened macOS System Settings ({pane})."))
        } else {
            Err("Could not open macOS System Settings.".into())
        }
    }
}
