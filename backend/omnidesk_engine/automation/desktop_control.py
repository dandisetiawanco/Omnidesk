from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from omnidesk_engine.automation.apps import validate_app_name
from omnidesk_engine.security.policy import (
    redact_sensitive_text,
    validate_child_path,
    validate_scoped_directory,
)

SENSITIVE_TITLE_HINTS = (
    "password",
    "passcode",
    "sign in",
    "log in",
    "login",
    "2fa",
    "otp",
    "one-time",
    "keychain",
    "wallet",
    "checkout",
    "payment",
    "credit card",
    "cvv",
    "banking",
)


def macos_accessibility_trusted() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        lib = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return False


def macos_screen_recording_granted() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        lib = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        lib.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        return bool(lib.CGPreflightScreenCaptureAccess())
    except Exception:
        return False


def linux_is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(
        os.environ.get("WAYLAND_DISPLAY")
    )


def linux_dbus_service_present(service_name: str) -> bool:
    if platform.system() != "Linux":
        return False
    if shutil.which("busctl"):
        try:
            out = subprocess.check_output(
                ["busctl", "--user", "list", "--no-legend"], text=True, timeout=2
            )
            if service_name in out:
                return True
        except Exception:
            pass
    if shutil.which("gdbus"):
        try:
            out = subprocess.check_output(
                [
                    "gdbus",
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
                text=True,
                timeout=2,
            )
            return "true" in out.lower()
        except Exception:
            pass
    return False


def is_excluded_or_sensitive(app_name: str, window_title: str, excluded_apps: list[str]) -> bool:
    low_app = app_name.lower()
    low_title = window_title.lower()
    if any(ex.lower() in low_app for ex in excluded_apps):
        return True
    if any(hint in low_title for hint in SENSITIVE_TITLE_HINTS):
        return True
    return False


def _run_powershell(script: str, timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _load_linux_atspi() -> Any | None:
    try:
        import gi  # type: ignore[import-not-found]

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi  # type: ignore[import-not-found]

        return Atspi
    except Exception:
        return None


def list_running_apps() -> list[dict[str, Any]]:
    """Lists visible user-facing GUI applications without prompting for elevated OS permissions."""
    system = platform.system()
    results: list[dict[str, Any]] = []
    if system == "Darwin":
        try:
            raw = subprocess.check_output(
                ["lsappinfo", "visibleProcessList"], text=True, timeout=4
            )
            seen: set[str] = set()
            for token in re.findall(r'"([^"]+)"', raw):
                clean = token.replace("_", " ").strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    results.append({"name": clean, "platform": "macOS"})
        except Exception:
            pass
        return results

    if system == "Windows":
        try:
            proc = _run_powershell(
                "Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } | Select-Object -ExpandProperty ProcessName -Unique | Sort-Object",
                timeout=5,
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    name = line.strip()
                    if name:
                        results.append({"name": name, "platform": "Windows"})
        except Exception:
            pass
        return results

    if system == "Linux":
        seen_linux: set[str] = set()
        # 1. Prefer AT-SPI2 accessible application list (works across GNOME/KDE on X11 & Wayland when enabled).
        Atspi = _load_linux_atspi()
        if Atspi is not None:
            try:
                desktop = Atspi.get_desktop(0)
                if desktop is not None:
                    for i in range(desktop.get_child_count()):
                        child = desktop.get_child_at_index(i)
                        if child and child.get_name():
                            name = str(child.get_name()).strip()
                            if name and name not in seen_linux:
                                seen_linux.add(name)
                                results.append({"name": name, "platform": "Linux"})
            except Exception:
                pass
        # 2. X11 wmctrl window listing.
        if not results and not linux_is_wayland() and shutil.which("wmctrl"):
            try:
                raw = subprocess.check_output(["wmctrl", "-lp"], text=True, timeout=4)
                for line in raw.splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and parts[2].isdigit():
                        pid = int(parts[2])
                        try:
                            name = psutil.Process(pid).name()
                            if name and name not in seen_linux:
                                seen_linux.add(name)
                                results.append({"name": name, "platform": "Linux (X11)"})
                        except Exception:
                            pass
            except Exception:
                pass
        return results

    return results


def get_frontmost_application() -> dict[str, Any]:
    """Identifies the current frontmost desktop application reliably and honestly."""
    system = platform.system()
    if system == "Darwin":
        ax = macos_accessibility_trusted()
        app_name = "Unknown"
        bundle_id = None
        pid = None
        try:
            asn = subprocess.check_output(["lsappinfo", "front"], text=True, timeout=3).strip()
            if asn:
                info = subprocess.check_output(
                    ["lsappinfo", "info", "-only", "name,bundleID,pid", asn],
                    text=True,
                    timeout=3,
                )
                for line in info.splitlines():
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip().strip('"').lower()
                    v = v.strip().strip('"')
                    if k in ("lsdisplayname", "cfbundlename", "name"):
                        if v:
                            app_name = v
                    elif k in ("cfbundleidentifier", "bundleid"):
                        bundle_id = v
                    elif k == "pid" and v.isdigit():
                        pid = int(v)
        except Exception:
            pass

        window_title = ""
        if ax:
            try:
                proc = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to get name of window 1 of (first application process whose frontmost is true)',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if proc.returncode == 0:
                    window_title = proc.stdout.strip()
            except Exception:
                pass

        return {
            "platform": "macOS",
            "app_name": app_name,
            "bundle_id": bundle_id,
            "pid": pid,
            "window_title": window_title
            or (
                "Active window (untitled)"
                if ax
                else "Window title requires macOS Accessibility permission"
            ),
            "accessibility_granted": ax,
            "status": "ok",
            "note": (
                "Active application and window title verified via LaunchServices & Accessibility."
                if ax
                else "Frontmost app identified via LaunchServices; grant Accessibility in System Settings for UI element inspection."
            ),
        }

    if system == "Windows":
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(max(length + 1, 256))
            user32.GetWindowTextW(hwnd, buf, len(buf))
            window_title = buf.value.strip()
            pid_c = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
            pid_val = int(pid_c.value)
            app_name = psutil.Process(pid_val).name() if pid_val else "Unknown"
            if app_name.lower().endswith(".exe"):
                app_name = app_name[:-4]
            return {
                "platform": "Windows",
                "app_name": app_name,
                "pid": pid_val or None,
                "window_title": window_title or "Active window (untitled)",
                "accessibility_granted": True,
                "status": "ok",
                "note": "Active window verified via Win32 User32 GetForegroundWindow.",
            }
        except Exception as exc:
            return {
                "platform": "Windows",
                "app_name": "Unknown",
                "window_title": "Could not inspect foreground window",
                "accessibility_granted": True,
                "status": "error",
                "note": redact_sensitive_text(str(exc)),
            }

    if system == "Linux":
        wayland = linux_is_wayland()
        atspi_ready = linux_dbus_service_present("org.a11y.Bus")
        if wayland:
            Atspi = _load_linux_atspi()
            if Atspi is not None:
                try:
                    desktop = Atspi.get_desktop(0)
                    for i in range(desktop.get_child_count()):
                        app = desktop.get_child_at_index(i)
                        if not app:
                            continue
                        for j in range(app.get_child_count()):
                            win = app.get_child_at_index(j)
                            if win and win.get_state_set().contains(Atspi.StateType.ACTIVE):
                                return {
                                    "platform": "Linux (Wayland)",
                                    "app_name": str(app.get_name() or "Unknown"),
                                    "window_title": str(win.get_name() or "Active window"),
                                    "accessibility_granted": True,
                                    "status": "ok",
                                    "note": "Active window resolved via AT-SPI2 accessibility bus under Wayland.",
                                }
                except Exception:
                    pass
            return {
                "platform": "Linux (Wayland)",
                "app_name": "Isolated by Wayland compositor",
                "window_title": "Wayland blocks global window inspection without AT-SPI2 or a compositor portal",
                "accessibility_granted": atspi_ready,
                "status": "unsupported",
                "note": "OmniDesk respects Wayland isolation and never uses unsafe hooks.",
            }

        if shutil.which("xdotool"):
            try:
                wid = subprocess.check_output(["xdotool", "getactivewindow"], text=True, timeout=3).strip()
                title = subprocess.check_output(["xdotool", "getwindowname", wid], text=True, timeout=3).strip()
                pid_str = subprocess.check_output(["xdotool", "getwindowpid", wid], text=True, timeout=3).strip()
                pid_val = int(pid_str) if pid_str.isdigit() else None
                app_name = psutil.Process(pid_val).name() if pid_val else "X11 Application"
                return {
                    "platform": "Linux (X11)",
                    "app_name": app_name,
                    "pid": pid_val,
                    "window_title": title or "Active X11 window",
                    "accessibility_granted": atspi_ready,
                    "status": "ok",
                    "note": "Active window resolved via X11 xdotool and process table.",
                }
            except Exception:
                pass
        return {
            "platform": "Linux (X11)",
            "app_name": "X11 Session",
            "window_title": "Install xdotool or enable AT-SPI2 for live window titles",
            "accessibility_granted": atspi_ready,
            "status": "experimental",
            "note": "X11 session detected without xdotool on PATH.",
        }

    return {
        "platform": system,
        "app_name": "Unknown",
        "window_title": "Unsupported OS",
        "accessibility_granted": False,
        "status": "unsupported",
        "note": f"Unsupported platform: {system}.",
    }


def _inspect_windows_uia_tree(target: str) -> dict[str, Any]:
    escaped = target.replace("'", "''")
    script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$target = '{escaped}'
$proc = Get-Process | Where-Object {{ $_.MainWindowHandle -ne 0 -and ($_.ProcessName -ieq $target -or $_.MainWindowTitle -ilike "*$target*") }} | Select-Object -First 1
if (-not $proc) {{
  Write-Output '{{"missing": true}}'
  exit 0
}}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$cond = [System.Windows.Automation.Condition]::TrueCondition
$nodes = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
$items = @()
for ($i = 0; $i -lt [Math]::Min($nodes.Count, 40); $i++) {{
  $el = $nodes.Item($i)
  try {{
    if ($el.Current.IsPassword) {{
      $items += @{{ role = 'REDACTED'; name = 'Secure Password Field skipped' }}
    }} else {{
      $role = $el.Current.ControlType.ProgrammaticName
      $name = $el.Current.Name
      if ([string]::IsNullOrWhiteSpace($name)) {{ $name = $role }}
      $items += @{{ role = $role; name = $name }}
    }}
  }} catch {{}}
}}
@{{ missing = $false; window_title = $proc.MainWindowTitle; elements = $items }} | ConvertTo-Json -Depth 4 -Compress
"""
    proc = _run_powershell(script, timeout=10)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {
            "app_name": target,
            "accessibility_granted": True,
            "blocked_by_privacy": False,
            "elements": [],
            "message": redact_sensitive_text(proc.stderr.strip() or "Windows UIA inspection failed."),
        }
    data = json.loads(proc.stdout.strip())
    if data.get("missing"):
        return {
            "app_name": target,
            "accessibility_granted": True,
            "blocked_by_privacy": False,
            "elements": [],
            "message": f"Application '{target}' does not have an open window.",
        }
    raw_items = data.get("elements") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    elements = [
        {
            "role": str(item.get("role", "Control")),
            "name": redact_sensitive_text(str(item.get("name", ""))),
            "selector": f"uia://window[@name='{target}']//{item.get('role', 'Control')}[@name='{item.get('name', '')}']",
        }
        for item in raw_items[:40]
    ]
    return {
        "app_name": target,
        "window_title": data.get("window_title") or "Front Window",
        "accessibility_granted": True,
        "blocked_by_privacy": False,
        "element_count": len(elements),
        "elements": elements,
        "message": f"Inspected {len(elements)} Windows UIA element(s) in '{target}'.",
    }


def _inspect_linux_atspi_tree(target: str) -> dict[str, Any]:
    Atspi = _load_linux_atspi()
    if Atspi is None:
        return {
            "app_name": target,
            "accessibility_granted": linux_dbus_service_present("org.a11y.Bus"),
            "blocked_by_privacy": False,
            "elements": [],
            "message": "AT-SPI2 Python bindings (python3-gi + gir1.2-atspi-2.0) are not installed on this host.",
        }

    desktop = Atspi.get_desktop(0)
    matched_app = None
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app and target.lower() in str(app.get_name() or "").lower():
            matched_app = app
            break

    if matched_app is None:
        return {
            "app_name": target,
            "accessibility_granted": True,
            "blocked_by_privacy": False,
            "elements": [],
            "message": f"Application '{target}' was not found on the AT-SPI2 accessibility tree.",
        }

    elements: list[dict[str, str]] = []
    win_title = ""

    def walk(node: Any, depth: int) -> None:
        nonlocal win_title
        if node is None or depth > 5 or len(elements) >= 40:
            return
        try:
            role = node.get_role()
            role_name = str(node.get_role_name() or "widget")
            name = str(node.get_name() or "").strip()
            if depth == 1 and not win_title and name:
                win_title = name
            if role == Atspi.Role.PASSWORD_TEXT:
                elements.append(
                    {
                        "role": "REDACTED",
                        "name": "Password field skipped",
                        "selector": f"atspi://app[@name='{target}']//REDACTED",
                    }
                )
                return
            if depth >= 1 and (name or role_name in ("push button", "menu item", "text", "entry")):
                label = redact_sensitive_text(name or role_name)
                elements.append(
                    {
                        "role": role_name,
                        "name": label,
                        "selector": f"atspi://app[@name='{target}']//{role_name}[@name='{label}']",
                    }
                )
            for idx in range(min(node.get_child_count(), 25)):
                walk(node.get_child_at_index(idx), depth + 1)
        except Exception:
            return

    walk(matched_app, 0)
    return {
        "app_name": target,
        "window_title": win_title or target,
        "accessibility_granted": True,
        "blocked_by_privacy": False,
        "element_count": len(elements),
        "elements": elements,
        "message": f"Inspected {len(elements)} AT-SPI2 semantic element(s) in '{target}'.",
    }


def inspect_accessibility_tree(
    app_name: str | None,
    excluded_apps: list[str],
) -> dict[str, Any]:
    """Reads semantic UI controls from the target or frontmost application when permitted."""
    front = get_frontmost_application()
    target = validate_app_name(app_name) if app_name else front["app_name"]

    if is_excluded_or_sensitive(target, front.get("window_title", ""), excluded_apps):
        return {
            "app_name": target,
            "accessibility_granted": front["accessibility_granted"],
            "blocked_by_privacy": True,
            "elements": [],
            "message": f"Accessibility inspection refused for sensitive or excluded application '{target}'.",
        }

    system = platform.system()
    if system == "Darwin":
        if not macos_accessibility_trusted():
            return {
                "app_name": target,
                "window_title": front.get("window_title"),
                "accessibility_granted": False,
                "blocked_by_privacy": False,
                "elements": [],
                "message": "macOS Accessibility permission is not granted yet. Open System Settings > Privacy & Security > Accessibility and enable OmniDesk.",
            }

        safe_target = target.replace('"', "")
        script = f'''
tell application "System Events"
  if not (exists process "{safe_target}") then return "MISSING_PROCESS"
  tell process "{safe_target}"
    set winTitle to ""
    try
      set winTitle to name of window 1
    end try
    if winTitle is missing value then set winTitle to ""
    set collectedItems to {{"WINDOW::" & winTitle}}
    try
      set uiElems to UI elements of window 1
      repeat with el in uiElems
        try
          set r to role of el
          set sr to ""
          try
            set sr to subrole of el
          end try
          if sr is "AXSecureTextField" then
            set end of collectedItems to "REDACTED::Secure Text Field skipped"
          else
            set lbl to ""
            try
              set n to name of el
              if n is not missing value and n is not "" then set lbl to n as text
            end try
            if lbl is "" then
              try
                set d to description of el
                if d is not missing value and d is not "" then set lbl to d as text
              end try
            end if
            if lbl is "" then
              try
                set t to title of el
                if t is not missing value and t is not "" then set lbl to t as text
              end try
            end if
            if lbl is "" then set lbl to r as text
            set end of collectedItems to ((r as text) & "::" & lbl)
          end if
        end try
      end repeat
    end try
    try
      repeat with sa in (scroll areas of window 1)
        repeat with innerEl in (UI elements of sa)
          try
            set ir to role of innerEl
            set isr to ""
            try
              set isr to subrole of innerEl
            end try
            if isr is "AXSecureTextField" then
              set end of collectedItems to "REDACTED::Secure Text Field skipped"
            else
              set ilbl to ir as text
              try
                set idesc to description of innerEl
                if idesc is not missing value and idesc is not "" then set ilbl to idesc as text
              end try
              set end of collectedItems to ((ir as text) & "::" & ilbl)
            end if
          end try
        end repeat
      end repeat
    end try
    set AppleScript's text item delimiters to linefeed
    return collectedItems as text
  end tell
end tell
'''
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=6)
        if proc.returncode != 0:
            return {
                "app_name": target,
                "accessibility_granted": True,
                "blocked_by_privacy": False,
                "elements": [],
                "message": redact_sensitive_text(
                    proc.stderr.strip() or "Could not query System Events Accessibility tree."
                ),
            }
        raw = proc.stdout.strip()
        if raw == "MISSING_PROCESS":
            return {
                "app_name": target,
                "accessibility_granted": True,
                "blocked_by_privacy": False,
                "elements": [],
                "message": f"Application '{target}' is not currently running.",
            }

        win_title = ""
        elements: list[dict[str, str]] = []
        for line in raw.splitlines():
            if "::" not in line:
                continue
            role, label = line.split("::", 1)
            if role == "WINDOW":
                win_title = label.strip()
            else:
                elements.append(
                    {
                        "role": role,
                        "name": redact_sensitive_text(label.strip()),
                        "selector": f"ax://application[@name='{target}']//{role}[@name='{label.strip()}']",
                    }
                )
        return {
            "app_name": target,
            "window_title": win_title or "Front Window",
            "accessibility_granted": True,
            "blocked_by_privacy": False,
            "element_count": len(elements),
            "elements": elements[:40],
            "message": f"Inspected {len(elements)} semantic UI element(s) in '{target}'.",
        }

    if system == "Windows":
        return _inspect_windows_uia_tree(target)

    if system == "Linux":
        return _inspect_linux_atspi_tree(target)

    return {
        "app_name": target,
        "accessibility_granted": False,
        "blocked_by_privacy": False,
        "elements": [],
        "message": f"Accessibility tree inspection is unsupported on {system}.",
    }


def open_document_in_app(
    app_name: str,
    file_path: str | Path,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Opens a verified scoped file inside a real native desktop application and confirms launch."""
    clean_app = validate_app_name(app_name)
    fpath = Path(file_path).expanduser().resolve()
    validate_scoped_directory(fpath.parent, allowed_roots=allowed_roots)
    validate_child_path(fpath.parent, fpath)
    if not fpath.exists():
        raise FileNotFoundError(f"Document does not exist: {fpath}")

    system = platform.system()
    if system == "Darwin":
        proc = subprocess.run(
            ["open", "-a", clean_app, str(fpath)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"macOS could not open '{fpath.name}' in '{clean_app}'.")
        app_verified = False
        running: list[str] = []
        for _ in range(10):
            running = [a["name"] for a in list_running_apps()]
            if any(clean_app.lower() in r.lower() for r in running):
                app_verified = True
                break
            time.sleep(0.2)
        return {
            "app_name": clean_app,
            "file_path": str(fpath),
            "platform": "macOS",
            "launched": True,
            "process_verified": app_verified,
            "running_apps_count": len(running),
        }

    if system == "Windows":
        esc_app = clean_app.replace("'", "''")
        esc_path = str(fpath).replace("'", "''")
        proc = _run_powershell(
            f"Start-Process -FilePath '{esc_app}' -ArgumentList '\"{esc_path}\"' -ErrorAction Stop",
            timeout=15,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"Windows could not open '{fpath.name}' in '{clean_app}'.")
        app_verified = False
        running = []
        for _ in range(10):
            running = [a["name"] for a in list_running_apps()]
            if any(clean_app.lower() in r.lower() for r in running):
                app_verified = True
                break
            time.sleep(0.2)
        return {
            "app_name": clean_app,
            "file_path": str(fpath),
            "platform": "Windows",
            "launched": True,
            "process_verified": app_verified,
            "running_apps_count": len(running),
        }

    # Linux: prefer gtk-launch when an explicit app desktop entry exists, falling back to xdg-open.
    launched = False
    if shutil.which("gtk-launch"):
        desktop_id = f"{clean_app.lower().replace(' ', '-')}.desktop"
        proc = subprocess.run(["gtk-launch", desktop_id, str(fpath)], capture_output=True, text=True, timeout=10)
        launched = proc.returncode == 0
    if not launched:
        proc = subprocess.run(["xdg-open", str(fpath)], capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"Linux could not open '{fpath.name}'.")
    return {"app_name": clean_app, "file_path": str(fpath), "platform": "Linux", "launched": True}


def click_semantic_element(
    app_name: str,
    element_name: str,
    excluded_apps: list[str],
    role: str = "button",
) -> dict[str, Any]:
    """Target-verified semantic Accessibility click across macOS AX, Windows UIA, and Linux AT-SPI2."""
    clean_app = validate_app_name(app_name)
    if is_excluded_or_sensitive(clean_app, element_name, excluded_apps):
        raise PermissionError(f"Interaction blocked for sensitive application '{clean_app}'.")

    system = platform.system()
    safe_el = element_name.strip().replace('"', "")

    if system == "Darwin":
        if not macos_accessibility_trusted():
            raise PermissionError(
                "macOS Accessibility permission is required before OmniDesk can click UI elements."
            )
        safe_app = clean_app.replace('"', "")
        ax_kind = "button" if role == "button" else "menu item"
        script = f'''
tell application "{safe_app}" to activate
delay 0.25
tell application "System Events"
  tell process "{safe_app}"
    click {ax_kind} "{safe_el}" of window 1
  end tell
end tell
'''
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
        if proc.returncode != 0:
            raise RuntimeError(
                redact_sensitive_text(
                    proc.stderr.strip() or f"Could not find {ax_kind} '{safe_el}' in '{clean_app}'."
                )
            )
        return {
            "app_name": clean_app,
            "element_name": safe_el,
            "role": ax_kind,
            "clicked": True,
            "target_verified": True,
        }

    if system == "Windows":
        esc_app = clean_app.replace("'", "''")
        esc_el = safe_el.replace("'", "''")
        script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$proc = Get-Process | Where-Object {{ $_.MainWindowHandle -ne 0 -and ($_.ProcessName -ieq '{esc_app}' -or $_.MainWindowTitle -ilike '*{esc_app}*') }} | Select-Object -First 1
if (-not $proc) {{ throw "Target application not running." }}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, '{esc_el}')
$el = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
if (-not $el) {{ throw "UI element '{esc_el}' not found in '{esc_app}'." }}
if ($el.Current.IsPassword) {{ throw "REFUSED_PASSWORD_FIELD" }}
$pat = $null
if ($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pat)) {{
  $pat.Invoke()
  Write-Output "INVOKED"
}} elseif ($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern, [ref]$pat)) {{
  $pat.Toggle()
  Write-Output "TOGGLED"
}} else {{
  throw "Element does not support UIA InvokePattern or TogglePattern."
}}
"""
        proc = _run_powershell(script, timeout=10)
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "REFUSED_PASSWORD_FIELD" in err:
                raise PermissionError("Refused interacting with a Windows password control.")
            raise RuntimeError(redact_sensitive_text(err or f"Windows UIA click failed for '{safe_el}'."))
        return {
            "app_name": clean_app,
            "element_name": safe_el,
            "role": role,
            "clicked": True,
            "target_verified": True,
        }

    if system == "Linux":
        Atspi = _load_linux_atspi()
        if Atspi is None:
            raise RuntimeError("Linux AT-SPI2 bindings are unavailable; cannot perform semantic click safely.")
        desktop = Atspi.get_desktop(0)
        found = None

        def find_node(node: Any, depth: int) -> Any:
            if node is None or depth > 6:
                return None
            if node.get_role() == Atspi.Role.PASSWORD_TEXT:
                return None
            if str(node.get_name() or "").strip().lower() == safe_el.lower():
                return node
            for idx in range(min(node.get_child_count(), 30)):
                res = find_node(node.get_child_at_index(idx), depth + 1)
                if res is not None:
                    return res
            return None

        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            if app and clean_app.lower() in str(app.get_name() or "").lower():
                found = find_node(app, 0)
                if found is not None:
                    break
        if found is None:
            raise RuntimeError(f"AT-SPI2 element '{safe_el}' not found in '{clean_app}'.")
        action_iface = found.get_action_iface()
        if action_iface is None or action_iface.get_n_actions() < 1:
            raise RuntimeError(f"AT-SPI2 element '{safe_el}' exposes no invokable action.")
        action_iface.do_action(0)
        return {
            "app_name": clean_app,
            "element_name": safe_el,
            "role": role,
            "clicked": True,
            "target_verified": True,
        }

    raise RuntimeError(f"Semantic UI clicking is unsupported on {system}.")


def type_text_into_target(
    app_name: str,
    text: str,
    excluded_apps: list[str],
) -> dict[str, Any]:
    """Target-verified controlled keyboard entry with secure-field refusal across macOS, Windows, and Linux."""
    clean_app = validate_app_name(app_name)
    if is_excluded_or_sensitive(clean_app, "", excluded_apps):
        raise PermissionError(f"Keyboard input blocked for sensitive application '{clean_app}'.")
    if len(text) > 1000:
        raise ValueError("Controlled text entry is bounded to 1000 characters per step.")

    system = platform.system()

    if system == "Darwin":
        if not macos_accessibility_trusted():
            raise PermissionError(
                "macOS Accessibility permission is required before OmniDesk can type into external apps."
            )
        safe_app = clean_app.replace('"', "")
        safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
tell application "{safe_app}" to activate
delay 0.2
tell application "System Events"
  tell process "{safe_app}"
    set focusedSubrole to ""
    try
      set focusedSubrole to value of attribute "AXSubrole" of (value of attribute "AXFocusedUIElement")
    end try
    if focusedSubrole is "AXSecureTextField" then error "REFUSED_SECURE_FIELD"
    keystroke "{safe_text}"
  end tell
end tell
'''
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "REFUSED_SECURE_FIELD" in err:
                raise PermissionError("Refused typing into a macOS secure password field.")
            raise RuntimeError(redact_sensitive_text(err or f"Failed typing into '{clean_app}'."))
        return {"app_name": clean_app, "characters_typed": len(text), "target_verified": True}

    if system == "Windows":
        esc_app = clean_app.replace("'", "''")
        esc_text = text.replace("'", "''")
        # Escape SendKeys special characters safely if ValuePattern is not exposed.
        sendkeys_safe = re.sub(r"([+^%~(){}\[\]])", r"{\1}", text).replace("'", "''")
        script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class WinFocus2 {{ [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }}' -ErrorAction SilentlyContinue
$proc = Get-Process | Where-Object {{ $_.MainWindowHandle -ne 0 -and ($_.ProcessName -ieq '{esc_app}' -or $_.MainWindowTitle -ilike '*{esc_app}*') }} | Select-Object -First 1
if (-not $proc) {{ throw "Target application not running." }}
[WinFocus2]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 180
$focused = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($focused -and $focused.Current.IsPassword) {{ throw "REFUSED_SECURE_FIELD" }}
$pat = $null
if ($focused -and $focused.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pat)) {{
  $pat.SetValue('{esc_text}')
  Write-Output "VALUE_PATTERN"
}} else {{
  [System.Windows.Forms.SendKeys]::SendWait('{sendkeys_safe}')
  Write-Output "SENDKEYS"
}}
"""
        proc = _run_powershell(script, timeout=10)
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "REFUSED_SECURE_FIELD" in err:
                raise PermissionError("Refused typing into a Windows password field.")
            raise RuntimeError(redact_sensitive_text(err or f"Windows text input failed for '{clean_app}'."))
        return {"app_name": clean_app, "characters_typed": len(text), "target_verified": True}

    if system == "Linux":
        # 1. Prefer AT-SPI2 EditableText (works without unsafe global input injection, skips password fields).
        Atspi = _load_linux_atspi()
        if Atspi is not None:
            desktop = Atspi.get_desktop(0)
            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                if not app or clean_app.lower() not in str(app.get_name() or "").lower():
                    continue
                stack = [app]
                visited = 0
                while stack and visited < 200:
                    node = stack.pop()
                    visited += 1
                    try:
                        if node.get_state_set().contains(Atspi.StateType.FOCUSED):
                            if node.get_role() == Atspi.Role.PASSWORD_TEXT:
                                raise PermissionError("Refused typing into a Linux password field.")
                            editable = node.get_editable_text_iface()
                            if editable is not None:
                                editable.insert_text(0, text, len(text.encode("utf-8")))
                                return {
                                    "app_name": clean_app,
                                    "characters_typed": len(text),
                                    "target_verified": True,
                                }
                        for idx in range(min(node.get_child_count(), 25)):
                            stack.append(node.get_child_at_index(idx))
                    except PermissionError:
                        raise
                    except Exception:
                        continue

        # 2. Controlled X11 fallback ONLY on X11; never bypass Wayland isolation.
        if linux_is_wayland():
            raise PermissionError(
                "Wayland restricts synthetic keyboard injection without a compositor RemoteDesktop portal; enable AT-SPI2 EditableText instead."
            )
        if not shutil.which("xdotool"):
            raise RuntimeError("Install xdotool or enable AT-SPI2 EditableText for X11 text entry.")
        front = get_frontmost_application()
        if clean_app.lower() not in str(front.get("app_name", "")).lower():
            raise PermissionError(
                f"Active X11 window '{front.get('app_name')}' does not match approved target '{clean_app}'."
            )
        proc = subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            raise RuntimeError(redact_sensitive_text(proc.stderr.strip() or "xdotool text entry failed."))
        return {"app_name": clean_app, "characters_typed": len(text), "target_verified": True}

    raise RuntimeError(f"Controlled keyboard entry is unsupported on {system}.")


def open_os_permission_settings(pane: str) -> dict[str, Any]:
    system = platform.system()
    if system == "Darwin":
        urls = {
            "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
            "automation": "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
        }
        if pane not in urls:
            raise ValueError(f"Unknown permission pane: {pane}")
        subprocess.run(["open", urls[pane]], check=True, timeout=5)
        return {"opened": True, "pane": pane, "platform": "macOS"}
    if system == "Windows":
        uri = "ms-settings:easeofaccess-display" if pane == "accessibility" else "ms-settings:privacy"
        subprocess.run(["explorer.exe", uri], check=False, timeout=5)
        return {"opened": True, "pane": pane, "platform": "Windows"}
    if system == "Linux":
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in de and shutil.which("gnome-control-center"):
            panel = "universal-access" if pane == "accessibility" else "privacy"
            subprocess.Popen(["gnome-control-center", panel])
            return {"opened": True, "pane": pane, "platform": "Linux (GNOME)"}
        if ("kde" in de or "plasma" in de) and shutil.which("systemsettings"):
            mod = "kcm_access" if pane == "accessibility" else "kcm_flatpak"
            subprocess.Popen(["systemsettings", mod])
            return {"opened": True, "pane": pane, "platform": "Linux (KDE)"}
    return {
        "opened": False,
        "pane": pane,
        "platform": system,
        "note": "Open your Linux desktop privacy or XDG portal settings directly.",
    }
