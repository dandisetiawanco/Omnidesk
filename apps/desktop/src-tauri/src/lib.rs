mod capabilities;
mod credentials;
mod platform;
mod window_material;

use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use rand::RngCore;
use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager, State};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

use crate::capabilities::{collect_system_profile, SystemProfile};
use crate::credentials::{check_secret, delete_secret, store_secret, CredentialStatus};
use crate::platform::{current_adapter, ActiveWindowSnapshot};

struct BackendState {
    base_url: String,
    token: String,
    platform_id: String,
    glass_material: String,
    child: Mutex<Option<Child>>,
}

#[derive(Serialize)]
struct BackendConnection {
    base_url: String,
    token: String,
    platform_id: String,
    glass_material: String,
}

fn generate_session_token() -> String {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn pick_loopback_port() -> u16 {
    if let Ok(listener) = TcpListener::bind("127.0.0.1:17420") {
        drop(listener);
        return 17420;
    }
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(17420)
}

/// Resolves the portable backend/ directory relative to current_dir or executable location.
fn locate_backend_dir() -> Option<PathBuf> {
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        roots.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            roots.push(parent.to_path_buf());
        }
    }

    for base in roots {
        let mut cursor = Some(base.as_path());
        for _ in 0..7 {
            if let Some(dir) = cursor {
                let candidate = dir.join("backend");
                if candidate.join("omnidesk_engine").exists() {
                    return Some(candidate);
                }
                cursor = dir.parent();
            } else {
                break;
            }
        }
    }
    None
}

fn spawn_local_engine(port: u16, token: &str) -> Option<Child> {
    let backend_dir = locate_backend_dir()?;
    let venv_python = if cfg!(target_os = "windows") {
        backend_dir.join(".venv/Scripts/python.exe")
    } else {
        backend_dir.join(".venv/bin/python")
    };
    let python_bin = if venv_python.exists() {
        venv_python
    } else {
        PathBuf::from("python3")
    };

    // Pass session token via environment variable rather than argv so process listings do not expose it.
    Command::new(python_bin)
        .current_dir(&backend_dir)
        .args([
            "-m",
            "uvicorn",
            "omnidesk_engine.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--log-level",
            "warning",
        ])
        .env("PYTHONPATH", &backend_dir)
        .env("OMNIDESK_SESSION_TOKEN", token)
        .env("OMNIDESK_PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

#[tauri::command]
fn get_backend_connection(state: State<'_, BackendState>) -> BackendConnection {
    BackendConnection {
        base_url: state.base_url.clone(),
        token: state.token.clone(),
        platform_id: state.platform_id.clone(),
        glass_material: state.glass_material.clone(),
    }
}

#[tauri::command]
fn get_system_profile() -> SystemProfile {
    collect_system_profile()
}

#[tauri::command]
fn get_active_window_snapshot() -> ActiveWindowSnapshot {
    current_adapter().active_window()
}

#[tauri::command]
fn list_running_apps() -> Vec<String> {
    current_adapter().list_running_apps()
}

#[tauri::command]
fn open_os_permission_settings(pane: String) -> Result<String, String> {
    current_adapter().open_permission_settings(&pane)
}

#[tauri::command]
fn launch_native_app(app_name: String) -> Result<String, String> {
    current_adapter().launch_application(&app_name)
}

#[tauri::command]
fn set_provider_credential(
    provider_id: String,
    api_key: String,
) -> Result<CredentialStatus, String> {
    store_secret(&provider_id, &api_key)
}

#[tauri::command]
fn get_provider_credential_status(provider_id: String) -> Result<CredentialStatus, String> {
    check_secret(&provider_id)
}

#[tauri::command]
fn remove_provider_credential(provider_id: String) -> Result<CredentialStatus, String> {
    delete_secret(&provider_id)
}

pub fn run() {
    let token = std::env::var("OMNIDESK_SESSION_TOKEN")
        .ok()
        .filter(|t| t.len() >= 24)
        .unwrap_or_else(generate_session_token);
    let port = pick_loopback_port();
    let child = spawn_local_engine(port, &token);
    let base_url = format!("http://127.0.0.1:{port}");
    let adapter = current_adapter();

    let state = BackendState {
        base_url,
        token,
        platform_id: adapter.platform_id().to_string(),
        glass_material: adapter.glass_material_kind().to_string(),
        child: Mutex::new(child),
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                            let _ = w.emit("omnidesk:open-palette", ());
                        }
                    }
                })
                .build(),
        )
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            get_backend_connection,
            get_system_profile,
            get_active_window_snapshot,
            list_running_apps,
            open_os_permission_settings,
            launch_native_app,
            set_provider_credential,
            get_provider_credential_status,
            remove_provider_credential,
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window_material::apply_adaptive_glass(&window);
            }

            // Register global shortcut without failing startup if another OS app already owns it.
            let _ = app
                .global_shortcut()
                .register("CommandOrControl+Shift+Space");

            let show_item = MenuItem::with_id(app, "show", "Open OmniDesk", true, None::<&str>)?;
            let palette_item =
                MenuItem::with_id(app, "palette", "Command Palette", true, None::<&str>)?;
            let stop_item =
                MenuItem::with_id(app, "emergency_stop", "Emergency Stop", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit OmniDesk", true, None::<&str>)?;
            let menu =
                Menu::with_items(app, &[&show_item, &palette_item, &stop_item, &quit_item])?;

            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("OmniDesk")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "palette" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                            let _ = w.emit("omnidesk:open-palette", ());
                        }
                    }
                    "emergency_stop" => {
                        let _ = app.emit("omnidesk:emergency-stop", ());
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                });

            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            let _ = tray.build(app);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Failed to build OmniDesk desktop application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state = app_handle.state::<BackendState>();
            let child_opt = state.child.lock().ok().and_then(|mut g| g.take());
            if let Some(mut proc) = child_opt {
                let _ = proc.kill();
                let _ = proc.wait();
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::generate_session_token;

    #[test]
    fn generates_high_entropy_hex_session_token() {
        let t1 = generate_session_token();
        let t2 = generate_session_token();
        assert_eq!(t1.len(), 64);
        assert_ne!(t1, t2);
        assert!(t1.chars().all(|c| c.is_ascii_hexdigit()));
    }
}
