use tauri::WebviewWindow;

/// Applies native OS translucent materials where genuinely supported and leaves
/// CSS solid fallbacks intact on unsupported compositors.
pub fn apply_adaptive_glass(window: &WebviewWindow) -> &'static str {
    #[cfg(target_os = "macos")]
    {
        use window_vibrancy::{apply_vibrancy, NSVisualEffectMaterial};
        // UnderWindowBackground blends smoothly behind sidebar + topbar while keeping high-contrast panels crisp.
        if apply_vibrancy(
            window,
            NSVisualEffectMaterial::UnderWindowBackground,
            None,
            Some(12.0),
        )
        .is_ok()
        {
            return "macos_vibrancy";
        }
        if apply_vibrancy(window, NSVisualEffectMaterial::Sidebar, None, None).is_ok() {
            return "macos_vibrancy";
        }
    }

    #[cfg(target_os = "windows")]
    {
        use window_vibrancy::{apply_acrylic, apply_mica};
        if apply_mica(window, None).is_ok() {
            return "windows_mica";
        }
        if apply_acrylic(window, Some((16, 20, 28, 208))).is_ok() {
            return "windows_acrylic";
        }
    }

    let _ = window;
    "solid_fallback"
}
