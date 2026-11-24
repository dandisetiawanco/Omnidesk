use std::collections::BTreeSet;
use std::env;
use std::fs;
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

    fn run_cmd(bin: &str, args: &[&str]) -> Option<String> {
        let out = Command::new(bin).args(args).output().ok()?;
        if !out.status.success() {
            return None;
        }
        let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if s.is_empty() {
            None
        } else {
            Some(s)
        }
    }

    fn dbus_service_present(service_name: &str) -> bool {
        if let Some(out) = Self::run_cmd("busctl", &["--user", "list", "--no-legend"]) {
            if out.contains(service_name) {
                return true;
            }
        }
        Self::run_cmd(
            "gdbus",
            &[
                "call",
                "--session",
                "--dest",
                "org.freedesktop.DBus",
                "--object-path",
                "/org/freedesktop/DBus",
                "--method",
                "org.freedesktop.DBus.NameHasOwner",
                service_name,
            ],
        )
        .map(|s| s.contains("true"))
        .unwrap_or(false)
    }

    fn parse_xrandr_displays(raw: &str) -> Vec<DisplayInfo> {
        let mut displays = Vec::new();
        for line in raw.lines() {
            if !line.contains(" connected") {
                continue;
            }
            let name = line.split_whitespace().next().unwrap_or("Display").to_string();
            let mut width = 1920u32;
            let mut height = 1080u32;
            for token in line.split_whitespace() {
                if let Some((dim, _offset)) = token.split_once('+') {
                    if let Some((w, h)) = dim.split_once('x') {
                        if let (Ok(pw), Ok(ph)) = (w.parse::<u32>(), h.parse::<u32>()) {
                            width = pw;
                            height = ph;
                            break;
                        }
                    }
                }
            }
            let scale = env::var("GDK_SCALE")
                .ok()
                .and_then(|s| s.parse::<f64>().ok())
                .unwrap_or(1.0);
            displays.push(DisplayInfo {
                name,
                width,
                height,
                scale_factor: scale,
            });
        }
        displays
    }
}

impl PlatformAdapter for LinuxAdapter {
    fn platform_id(&self) -> &'static str {
        "linux"
    }

    fn desktop_environment(&self) -> (String, String) {
        let de = env::var("XDG_CURRENT_DESKTOP")
            .or_else(|_| env::var("DESKTOP_SESSION"))
            .unwrap_or_else(|_| "Linux Desktop".to_string());
        let ds = if Self::is_wayland() {
            "Wayland".to_string()
        } else {
            "X11".to_string()
        };
        (de, ds)
    }

    fn detect_gpu(&self) -> String {
        if let Some(lspci) = Self::run_cmd("lspci", &["-mm"]) {
            let gpus: Vec<String> = lspci
                .lines()
                .filter(|line| {
                    line.contains("VGA compatible controller")
                        || line.contains("3D controller")
                        || line.contains("Display controller")
                })
                .filter_map(|line| {
                    let quoted: Vec<&str> = line.split('"').collect();
                    if quoted.len() >= 6 {
                        Some(format!("{} {}", quoted[3], quoted[5]).trim().to_string())
                    } else {
                        None
                    }
                })
                .collect();
            if !gpus.is_empty() {
                return gpus.join(" / ");
            }
        }
        if fs::metadata("/sys/class/drm/card0").is_ok() {
            return "Linux DRM / Mesa GPU (card0)".to_string();
        }
        "Linux DRM / Mesa GPU".to_string()
    }

    fn detect_displays(&self) -> Vec<DisplayInfo> {
        if let Some(raw) = Self::run_cmd("xrandr", &["--current"]) {
            let parsed = Self::parse_xrandr_displays(&raw);
            if !parsed.is_empty() {
                return parsed;
            }
        }
        if let Some(raw) = Self::run_cmd("wlr-randr", &[]) {
            let mut displays = Vec::new();
            let mut current_name: Option<String> = None;
            for line in raw.lines() {
                if !line.starts_with(' ') && !line.trim().is_empty() {
                    current_name = line.split_whitespace().next().map(|s| s.to_string());
                } else if line.contains("current") {
                    if let (Some(name), Some(res)) = (&current_name, line.split_whitespace().next())
                    {
                        if let Some((w, h)) = res.split_once('x') {
                            if let (Ok(pw), Ok(ph)) = (w.parse::<u32>(), h.parse::<u32>()) {
                                displays.push(DisplayInfo {
                                    name: name.clone(),
                                    width: pw,
                                    height: ph,
                                    scale_factor: 1.0,
                                });
                            }
                        }
                    }
                }
            }
            if !displays.is_empty() {
                return displays;
            }
        }
        vec![DisplayInfo {
            name: "Primary Display".into(),
            width: 1920,
            height: 1080,
            scale_factor: env::var("GDK_SCALE")
                .ok()
                .and_then(|s| s.parse::<f64>().ok())
                .unwrap_or(1.0),
        }]
    }

    fn glass_material_kind(&self) -> &'static str {
        let de = env::var("XDG_CURRENT_DESKTOP")
            .unwrap_or_default()
            .to_lowercase();
        if de.contains("kde") || de.contains("plasma") || de.contains("hyprland") || de.contains("sway") {
            "linux_compositor"
        } else {
            "solid_fallback"
        }
    }

    fn platform_capabilities(&self) -> Vec<CapabilityEntry> {
        let wayland = Self::is_wayland();
        let has_atspi = Self::dbus_service_present("org.a11y.Bus");
        let has_portal = Self::dbus_service_present("org.freedesktop.portal.Desktop");
        let has_secrets = Self::dbus_service_present("org.freedesktop.secrets");
        let has_notify = Self::dbus_service_present("org.freedesktop.Notifications");

        vec![
            CapabilityEntry {
                id: "linux.at_spi".into(),
                name: "AT-SPI2 Accessibility Bus".into(),
                category: "os".into(),
                status: if has_atspi { "available" } else { "permission_required" }.into(),
                maturity: "implemented_untested".into(),
                detail: if has_atspi {
                    "AT-SPI2 D-Bus accessibility service detected for semantic UI tree inspection and Action/EditableText interaction."
                } else {
                    "Enable desktop toolkit accessibility (org.a11y.Bus) in GNOME/KDE settings to expose semantic UI trees."
                }
                .into(),
                platform_note: Some("Password fields (ROLE_PASSWORD_TEXT) are always skipped.".into()),
            },
            CapabilityEntry {
                id: "linux.portal".into(),
                name: if wayland {
                    "XDG Desktop Portals (Wayland)"
                } else {
                    "X11 Windowing & XDG Portals"
                }
                .into(),
                category: "vision".into(),
                status: if wayland {
                    if has_portal { "permission_required" } else { "unsupported" }
                } else {
                    "available"
                }
                .into(),
                maturity: "implemented_untested".into(),
                detail: if wayland {
                    "Wayland restricts global capture and synthetic input; OmniDesk uses compositor-approved XDG Desktop Portals only."
                } else {
                    "X11 session supports active window inspection, wmctrl/xdotool controls, and optional XDG portals."
                }
                .into(),
                platform_note: Some(
                    if wayland {
                        "Unauthorized global key/pointer injection is intentionally refused under Wayland."
                    } else {
                        "X11 session detected."
                    }
                    .into(),
                ),
            },
            CapabilityEntry {
                id: "linux.secret_service".into(),
                name: "Secret Service API (D-Bus)".into(),
                category: "security".into(),
                status: if has_secrets { "available" } else { "not_installed" }.into(),
                maturity: "implemented_untested".into(),
                detail: "Stores provider credentials via org.freedesktop.secrets (GNOME Keyring / KWallet)."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "linux.notifications_and_tray".into(),
                name: "Desktop Notifications, Tray & Shortcuts".into(),
                category: "automation".into(),
                status: if has_notify { "available" } else { "experimental" }.into(),
                maturity: "implemented_untested".into(),
                detail: "Uses org.freedesktop.Notifications and StatusNotifierItem tray; Wayland global shortcuts require desktop portal consent."
                    .into(),
                platform_note: Some(format!("Session: {} ({})", self.desktop_environment().0, if wayland { "Wayland" } else { "X11" })),
            },
        ]
    }

    fn launch_application(&self, app_name: &str) -> Result<String, String> {
        let clean = validate_app_identifier(app_name)?;
        let desktop_id = if clean.ends_with(".desktop") {
            clean.clone()
        } else {
            format!("{}.desktop", clean.to_lowercase().replace(' ', "-"))
        };

        if let Ok(st) = Command::new("gtk-launch").arg(&desktop_id).status() {
            if st.success() {
                return Ok(format!("Launched {clean} via gtk-launch."));
            }
        }
        if let Ok(st) = Command::new("gtk-launch").arg(&clean).status() {
            if st.success() {
                return Ok(format!("Launched {clean} via gtk-launch."));
            }
        }
        if let Ok(st) = Command::new("xdg-open").arg(&clean).status() {
            if st.success() {
                return Ok(format!("Opened {clean} via xdg-open."));
            }
        }
        Err(format!(
            "Linux desktop launcher could not locate desktop entry for '{clean}'."
        ))
    }

    fn active_window(&self) -> ActiveWindowSnapshot {
        if Self::is_wayland() {
            let has_atspi = Self::dbus_service_present("org.a11y.Bus");
            return ActiveWindowSnapshot {
                app_name: "Isolated by Wayland compositor".into(),
                window_title: "Wayland blocks global active-window queries without a compositor portal"
                    .into(),
                accessibility_available: has_atspi,
                note: if has_atspi {
                    "AT-SPI2 is active; target applications can be inspected via AT-SPI while respecting Wayland isolation."
                } else {
                    "OmniDesk reports Wayland isolation transparently and never attempts unsafe hooks."
                }
                .into(),
            };
        }

        if let Some(win_id) = Self::run_cmd("xdotool", &["getactivewindow"]) {
            let title = Self::run_cmd("xdotool", &["getwindowname", &win_id])
                .unwrap_or_else(|| "Active X11 window".into());
            let app_name = Self::run_cmd("xdotool", &["getwindowpid", &win_id])
                .and_then(|pid| fs::read_to_string(format!("/proc/{}/comm", pid.trim())).ok())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "X11 Application".into());
            return ActiveWindowSnapshot {
                app_name,
                window_title: title,
                accessibility_available: Self::dbus_service_present("org.a11y.Bus"),
                note: "Active window resolved via X11 xdotool and /proc.".into(),
            };
        }

        ActiveWindowSnapshot {
            app_name: "X11 Session".into(),
            window_title: "Install xdotool or enable AT-SPI2 for live window titles".into(),
            accessibility_available: Self::dbus_service_present("org.a11y.Bus"),
            note: "X11 session detected without xdotool on PATH.".into(),
        }
    }

    fn list_running_apps(&self) -> Vec<String> {
        let mut names = BTreeSet::new();
        if !Self::is_wayland() {
            if let Some(raw) = Self::run_cmd("wmctrl", &["-lp"]) {
                for line in raw.lines() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 3 {
                        if let Ok(comm) = fs::read_to_string(format!("/proc/{}/comm", parts[2])) {
                            let clean = comm.trim().to_string();
                            if !clean.is_empty() {
                                names.insert(clean);
                            }
                        }
                    }
                }
            }
        }
        if names.is_empty() {
            if let Some(raw) = Self::run_cmd("ps", &["-eo", "comm="]) {
                for line in raw.lines() {
                    let clean = line.trim();
                    if matches!(
                        clean,
                        "firefox"
                            | "chromium"
                            | "google-chrome"
                            | "code"
                            | "gedit"
                            | "kate"
                            | "nautilus"
                            | "dolphin"
                            | "libreoffice"
                            | "soffice.bin"
                            | "gnome-text-editor"
                            | "gnome-calculator"
                            | "kcalc"
                    ) {
                        names.insert(clean.to_string());
                    }
                }
            }
        }
        names.into_iter().collect()
    }

    fn open_permission_settings(&self, pane: &str) -> Result<String, String> {
        let de = env::var("XDG_CURRENT_DESKTOP")
            .unwrap_or_default()
            .to_lowercase();
        if de.contains("gnome") {
            let panel = match pane {
                "accessibility" => "universal-access",
                _ => "privacy",
            };
            if Command::new("gnome-control-center")
                .arg(panel)
                .spawn()
                .is_ok()
            {
                return Ok(format!("Opened GNOME Settings ({panel})."));
            }
        } else if de.contains("kde") || de.contains("plasma") {
            let module = match pane {
                "accessibility" => "kcm_access",
                _ => "kcm_flatpak",
            };
            if Command::new("systemsettings").arg(module).spawn().is_ok() {
                return Ok(format!("Opened KDE System Settings ({module})."));
            }
        }
        Err("Open your Linux desktop Privacy / Accessibility settings directly.".into())
    }
}
