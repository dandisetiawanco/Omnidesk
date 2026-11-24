use std::process::Command;

use super::{
    validate_app_identifier, ActiveWindowSnapshot, CapabilityEntry, DisplayInfo, PlatformAdapter,
};

pub struct WindowsAdapter;

impl WindowsAdapter {
    fn run_powershell(script: &str) -> Option<String> {
        let output = Command::new("powershell")
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ])
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if text.is_empty() {
            None
        } else {
            Some(text)
        }
    }

    /// Reads the Windows OS build number (22000+ is Windows 11 with Mica support).
    pub(crate) fn windows_build_number() -> u32 {
        Self::run_powershell(
            "(Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' -Name CurrentBuildNumber).CurrentBuildNumber",
        )
        .and_then(|s| s.trim().parse::<u32>().ok())
        .unwrap_or(0)
    }

    fn transparency_enabled() -> bool {
        Self::run_powershell(
            "(Get-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name EnableTransparency -ErrorAction SilentlyContinue).EnableTransparency",
        )
        .map(|s| s.trim() != "0")
        .unwrap_or(true)
    }
}

impl PlatformAdapter for WindowsAdapter {
    fn platform_id(&self) -> &'static str {
        "windows"
    }

    fn desktop_environment(&self) -> (String, String) {
        let build = Self::windows_build_number();
        let shell = if build >= 22000 {
            format!("Windows 11 Shell (Build {build})")
        } else if build > 0 {
            format!("Windows 10 Shell (Build {build})")
        } else {
            "Windows Desktop Shell".to_string()
        };
        (shell, "DWM".to_string())
    }

    fn detect_gpu(&self) -> String {
        Self::run_powershell(
            "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' / '",
        )
        .unwrap_or_else(|| "Windows DirectX / WDDM GPU".to_string())
    }

    fn detect_displays(&self) -> Vec<DisplayInfo> {
        let script = r#"
Add-Type -AssemblyName System.Windows.Forms
$i = 1
[System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
  $name = if ($_.Primary) { "Primary Display" } else { "Display $i" }
  "$name|$($_.Bounds.Width)|$($_.Bounds.Height)|1.0"
  $i++
}
"#;
        if let Some(raw) = Self::run_powershell(script) {
            let parsed: Vec<DisplayInfo> = raw
                .lines()
                .filter_map(|line| {
                    let mut parts = line.split('|');
                    let name = parts.next()?.trim().to_string();
                    let width = parts.next()?.trim().parse::<u32>().ok()?;
                    let height = parts.next()?.trim().parse::<u32>().ok()?;
                    let scale_factor = parts.next()?.trim().parse::<f64>().unwrap_or(1.0);
                    Some(DisplayInfo {
                        name,
                        width,
                        height,
                        scale_factor,
                    })
                })
                .collect();
            if !parsed.is_empty() {
                return parsed;
            }
        }
        vec![DisplayInfo {
            name: "Primary Display".into(),
            width: 1920,
            height: 1080,
            scale_factor: 1.0,
        }]
    }

    fn glass_material_kind(&self) -> &'static str {
        if !Self::transparency_enabled() {
            return "solid_fallback";
        }
        let build = Self::windows_build_number();
        if build >= 22000 {
            "windows_mica"
        } else if build >= 17134 {
            "windows_acrylic"
        } else {
            "solid_fallback"
        }
    }

    fn platform_capabilities(&self) -> Vec<CapabilityEntry> {
        let build = Self::windows_build_number();
        let glass_note = if build >= 22000 {
            "Windows 11 detected: Mica backdrop enabled with solid fallback."
        } else if build >= 17134 {
            "Windows 10 detected: Acrylic backdrop enabled with solid fallback."
        } else {
            "Adaptive solid fallback enabled when DWM transparency is unavailable."
        };

        vec![
            CapabilityEntry {
                id: "windows.uia".into(),
                name: "Windows UI Automation (UIA)".into(),
                category: "os".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: "Inspects accessible UI trees and executes Invoke/Toggle/Value patterns while skipping password controls."
                    .into(),
                platform_note: Some(
                    "Implemented for Windows 10/11 via UIAutomationClient; pending native Windows host verification."
                        .into(),
                ),
            },
            CapabilityEntry {
                id: "windows.foreground_and_apps".into(),
                name: "Foreground Window & Running App Discovery".into(),
                category: "automation".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: "Reads active foreground window title/process via Win32 User32 and enumerates GUI windows."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "windows.app_launch".into(),
                name: "Native App Launcher & Window Switcher".into(),
                category: "automation".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: "Focuses running applications via SetForegroundWindow or launches apps via Start-Process."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "windows.credential_manager".into(),
                name: "Windows Credential Manager".into(),
                category: "security".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: "Stores provider API keys in Windows Credential Manager (never plaintext)."
                    .into(),
                platform_note: None,
            },
            CapabilityEntry {
                id: "windows.glass_and_dpi".into(),
                name: "Windows Mica / Acrylic & High-DPI Shell".into(),
                category: "os".into(),
                status: "available".into(),
                maturity: "implemented_untested".into(),
                detail: glass_note.into(),
                platform_note: Some("Tray icon and CommandOrControl+Shift+Space shortcut enabled.".into()),
            },
        ]
    }

    fn launch_application(&self, app_name: &str) -> Result<String, String> {
        let clean = validate_app_identifier(app_name)?;
        let escaped = clean.replace('\'', "''");
        // Focus an existing window first if running; otherwise start the application cleanly.
        let script = format!(
            r#"
$target = '{escaped}'
$running = Get-Process | Where-Object {{ $_.MainWindowHandle -ne 0 -and ($_.ProcessName -ieq $target -or $_.MainWindowTitle -ilike "*$target*") }} | Select-Object -First 1
if ($running) {{
  Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class WinFocus {{ [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }}' -ErrorAction SilentlyContinue
  [WinFocus]::SetForegroundWindow($running.MainWindowHandle) | Out-Null
  Write-Output "FOCUSED::$($running.ProcessName)"
}} else {{
  Start-Process -FilePath $target -ErrorAction Stop
  Write-Output "LAUNCHED::$target"
}}
"#
        );
        if let Some(out) = Self::run_powershell(&script) {
            if out.starts_with("FOCUSED::") {
                return Ok(format!("Switched focus to {clean}."));
            }
            if out.starts_with("LAUNCHED::") {
                return Ok(format!("Launched {clean}."));
            }
        }
        let status = Command::new("cmd")
            .args(["/C", "start", "", &clean])
            .status()
            .map_err(|e| format!("Failed to start {clean}: {e}"))?;
        if status.success() {
            Ok(format!("Launched {clean}."))
        } else {
            Err(format!("Windows could not start '{clean}'."))
        }
    }

    fn active_window(&self) -> ActiveWindowSnapshot {
        let script = r#"
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WinActive {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
}
"@ -ErrorAction SilentlyContinue
$hwnd = [WinActive]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 512
[void][WinActive]::GetWindowText($hwnd, $sb, $sb.Capacity)
$pidOut = 0
[void][WinActive]::GetWindowThreadProcessId($hwnd, [ref]$pidOut)
$procName = try { (Get-Process -Id $pidOut -ErrorAction Stop).ProcessName } catch { "Unknown" }
Write-Output "$procName|$($sb.ToString())"
"#;
        if let Some(raw) = Self::run_powershell(script) {
            if let Some((app, title)) = raw.split_once('|') {
                return ActiveWindowSnapshot {
                    app_name: app.trim().to_string(),
                    window_title: if title.trim().is_empty() {
                        "Active window (untitled)".into()
                    } else {
                        title.trim().to_string()
                    },
                    accessibility_available: true,
                    note: "Active window inspected via Win32 User32 GetForegroundWindow.".into(),
                };
            }
        }
        ActiveWindowSnapshot {
            app_name: "Unknown".into(),
            window_title: "Could not read foreground window".into(),
            accessibility_available: true,
            note: "Windows User32 foreground query returned no active window.".into(),
        }
    }

    fn list_running_apps(&self) -> Vec<String> {
        let script = "Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } | Select-Object -ExpandProperty ProcessName -Unique | Sort-Object";
        Self::run_powershell(script)
            .map(|out| {
                out.lines()
                    .map(|l| l.trim().to_string())
                    .filter(|l| !l.is_empty())
                    .collect()
            })
            .unwrap_or_default()
    }

    fn open_permission_settings(&self, pane: &str) -> Result<String, String> {
        let uri = match pane {
            "accessibility" => "ms-settings:easeofaccess-display",
            "screen_recording" => "ms-settings:privacy-broadfilesystemaccess",
            _ => "ms-settings:privacy",
        };
        Command::new("explorer.exe")
            .arg(uri)
            .status()
            .map_err(|e| format!("Failed to open Windows Settings: {e}"))?;
        Ok(format!("Opened Windows Settings ({uri})."))
    }
}
