use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayInfo {
    pub name: String,
    pub width: u32,
    pub height: u32,
    pub scale_factor: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityEntry {
    pub id: String,
    pub name: String,
    pub category: String,
    pub status: String,
    pub detail: String,
    pub platform_note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActiveWindowSnapshot {
    pub app_name: String,
    pub window_title: String,
    pub accessibility_available: bool,
    pub note: String,
}

pub trait PlatformAdapter {
    fn desktop_environment(&self) -> (String, String);
    fn detect_gpu(&self) -> String;
    fn detect_displays(&self) -> Vec<DisplayInfo>;
    fn glass_material_kind(&self) -> &'static str;
    fn platform_capabilities(&self) -> Vec<CapabilityEntry>;
    fn launch_application(&self, app_name: &str) -> Result<String, String>;
    fn active_window(&self) -> ActiveWindowSnapshot;
}

/// Reject characters that could invoke shell expansion or path traversal.
pub fn validate_app_identifier(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.len() > 80 {
        return Err("Application name must be between 1 and 80 characters.".into());
    }
    let valid = trimmed.chars().all(|c| {
        c.is_ascii_alphanumeric() || matches!(c, ' ' | '-' | '_' | '.')
    });
    if !valid || trimmed.contains("..") {
        return Err("Application name contains unsupported characters.".into());
    }
    Ok(trimmed.to_string())
}

#[cfg(target_os = "macos")]
mod macos;
#[cfg(target_os = "windows")]
mod windows;
#[cfg(target_os = "linux")]
mod linux;

pub fn current_adapter() -> Box<dyn PlatformAdapter> {
    #[cfg(target_os = "macos")]
    {
        Box::new(macos::MacOsAdapter)
    }
    #[cfg(target_os = "windows")]
    {
        Box::new(windows::WindowsAdapter)
    }
    #[cfg(target_os = "linux")]
    {
        Box::new(linux::LinuxAdapter)
    }
}

#[cfg(test)]
mod tests {
    use super::validate_app_identifier;

    #[test]
    fn accepts_standard_app_names() {
        assert_eq!(validate_app_identifier("Calculator").unwrap(), "Calculator");
        assert_eq!(
            validate_app_identifier("Visual Studio Code").unwrap(),
            "Visual Studio Code"
        );
    }

    #[test]
    fn rejects_shell_metacharacters() {
        assert!(validate_app_identifier("Finder; rm -rf /").is_err());
        assert!(validate_app_identifier("$(whoami)").is_err());
        assert!(validate_app_identifier("../evil").is_err());
    }
}
