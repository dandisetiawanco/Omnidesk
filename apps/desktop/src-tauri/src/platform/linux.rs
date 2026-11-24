use std::env;
use std::process::Command;

use super::{
    validate_app_identifier, ActiveWindowSnapshot, CapabilityEntry, DisplayInfo, PlatformAdapter,
};

pub struct LinuxAdapter;

impl LinuxAdapter {
    fn is_wayland() -> bool {
        env::var("XDG_SESSION_TYPE")
            .map(|v| v.eq_ignore_ascii_case("wayland"))
            .unwrap_or(false)
            || env::var("WAYLAND_DISPLAY").is_ok()
    }
}

impl PlatformAdapter for LinuxAdapter {
    fn platform_id(&self) -> &'static str {
        "linux"
    }

    fn desktop_environment(&self) -> (String, String) {
        let de = env::var("XDG_CURRENT_DESKTOP").unwrap_or_else(|_| "Linux Desktop".to_string());
        let ds = if Self::is_wayland() {
            "Wayland".to_string()
        } else {
            "X11".to_string()
        };
        (de, ds)
    }

    fn detect_gpu(&self) -> String {
        "Linux DRM / Mesa GPU".to_string()
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
        let de = env::var("XDG_CURRENT_DESKTOP")
            .unwrap_or_default()
            .to_lowercase();
        if de.contains("kde") || de.contains("hyprland") {
            "linux_compositor"
        } else {
            "solid_fallback"
        }
    }

    fn platform_capabilities(&self) -> Vec<CapabilityEntry> {
        let wayland = Self::is_wayland();
        vec![
            CapabilityEntry {
                id: "linux.at_spi".into(),
                name: "AT-SPI Accessibility Bus".into(),
                category: "os".into(),
                status: "experimental".into(),
                maturity: "experimental".into(),
                detail: "Reads accessible UI trees over D-Bus AT-SPI when desktop accessibility is enabled."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "linux.screen_portal".into(),
                name: if wayland {
                    "XDG Desktop Portal (Wayland)"
                } else {
                    "X11 Screen Capture"
                }
                .into(),
                category: "vision".into(),
                status: if wayland { "permission_required" } else { "experimental" }.into(),
                maturity: if wayland { "experimental" } else { "implemented_untested" }.into(),
                detail: if wayland {
                    "Wayland restricts global capture and input injection; OmniDesk uses compositor-approved XDG portals only."
                        .into()
                } else {
                    "X11 capture available on demand when enabled by user.".into()
                },
                platform_note: Some(
                    if wayland {
                        "Global synthetic pointer injection is intentionally unsupported under Wayland without portal consent."
                    } else {
                        "X11 session detected."
                    }
                    .into(),
                ),
            },
            CapabilityEntry {
                id: "linux.secret_service".into(),
                name: "Secret Service API".into(),
                category: "security".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: "Stores provider credentials via org.freedesktop.secrets (GNOME Keyring / KWallet)."
                    .into(),
                platform_note: None,
            },
        ]
    }

    fn launch_application(&self, app_name: &str) -> Result<String, String> {
        let clean = validate_app_identifier(app_name)?;
        let status = Command::new("gtk-launch")
            .arg(&clean)
            .status()
            .or_else(|_| Command::new("xdg-open").arg(&clean).status())
            .map_err(|e| format!("Failed to launch {clean}: {e}"))?;
        if status.success() {
            Ok(format!("Launched {clean}."))
        } else {
            Err(format!("Linux desktop launcher could not open '{clean}'."))
        }
    }

    fn active_window(&self) -> ActiveWindowSnapshot {
        let wayland = Self::is_wayland();
        ActiveWindowSnapshot {
            app_name: if wayland {
                "Restricted on Wayland".into()
            } else {
                "X11 Active Window".into()
            },
            window_title: if wayland {
                "Wayland compositors isolate global window titles without a portal grant".into()
            } else {
                "Inspectable via X11 / AT-SPI".into()
            },
            accessibility_available: !wayland,
            note: "OmniDesk reports Wayland isolation transparently.".into(),
        }
    }

    fn list_running_apps(&self) -> Vec<String> {
        Vec::new()
    }

    fn open_permission_settings(&self, _pane: &str) -> Result<String, String> {
        Err("Open your Linux desktop environment Privacy / Portal settings directly.".into())
    }
}
