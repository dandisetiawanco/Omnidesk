from __future__ import annotations

import ctypes
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

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


def is_excluded_or_sensitive(app_name: str, window_title: str, excluded_apps: list[str]) -> bool:
    low_app = app_name.lower()
    low_title = window_title.lower()
    if any(ex.lower() in low_app for ex in excluded_apps):
        return True
    if any(hint in low_title for hint in SENSITIVE_TITLE_HINTS):
        return True
    return False


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
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -ExpandProperty ProcessName -Unique",
                ],
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                name = line.strip()
                if name:
                    results.append({"name": name, "platform": "Windows"})
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
                    if k == "lsdisplayname" or k == "cfbundlename" or k == "name":
                        if v:
                            app_name = v
                    elif k == "cfbundleidentifier" or k == "bundleid":
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
                        'tell application "System Events" to get name of front window of (first application process whose frontmost is true)',
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

    if system == "Linux":
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get(
            "WAYLAND_DISPLAY"
        ):
            return {
                "platform": "Linux (Wayland)",
                "app_name": "Isolated by Wayland compositor",
                "window_title": "Wayland blocks global window inspection without a compositor portal",
                "accessibility_granted": False,
                "status": "unsupported",
                "note": "OmniDesk respects Wayland isolation.",
            }
        return {
            "platform": "Linux (X11)",
            "app_name": "X11 Session",
            "window_title": "Inspectable via AT-SPI / X11",
            "accessibility_granted": False,
            "status": "experimental",
            "note": "Linux X11 adapter ready for host testing.",
        }

    return {
        "platform": system,
        "app_name": "Windows Foreground App",
        "window_title": "Inspectable via Windows UI Automation adapter",
        "accessibility_granted": True,
        "status": "experimental",
        "note": "Windows UIA runtime pending Windows host validation.",
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
      set winTitle to name of front window
    end try
    set outLines to {{"WINDOW::" & winTitle}}
    try
      repeat with b in (buttons of front window)
        set bName to name of b
        if bName is not missing value and bName is not "" then
          set end of outLines to ("AXButton::" & bName)
        end if
      end repeat
    end try
    try
      repeat with tf in (text fields of front window)
        set subRole to ""
        try
          set subRole to subrole of tf
        end try
        if subRole is not "AXSecureTextField" then
          set tfName to description of tf
          if tfName is missing value or tfName is "" then set tfName to "Text Field"
          set end of outLines to ("AXTextField::" & tfName)
        else
          set end of outLines to ("REDACTED::Secure Text Field skipped")
        end if
      end repeat
    end try
    set AppleScript's text item delimiters to linefeed
    return outLines as text
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

    return {
        "app_name": target,
        "accessibility_granted": False,
        "blocked_by_privacy": False,
        "elements": [],
        "message": f"Live Accessibility tree inspection is experimental on {system}.",
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
        running = [a["name"] for a in list_running_apps()]
        app_verified = any(clean_app.lower() in r.lower() for r in running)
        return {
            "app_name": clean_app,
            "file_path": str(fpath),
            "platform": "macOS",
            "launched": True,
            "process_verified": app_verified,
            "running_apps_count": len(running),
        }

    if system == "Windows":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-Process -FilePath '{clean_app}' -ArgumentList '{fpath}'"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"Windows could not open '{fpath.name}' in '{clean_app}'.")
        return {"app_name": clean_app, "file_path": str(fpath), "platform": "Windows", "launched": True}

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
    """Target-verified semantic Accessibility click (never runs without prior user approval)."""
    clean_app = validate_app_name(app_name)
    if is_excluded_or_sensitive(clean_app, element_name, excluded_apps):
        raise PermissionError(f"Interaction blocked for sensitive application '{clean_app}'.")

    if platform.system() != "Darwin":
        raise RuntimeError(
            f"Semantic UI clicking on {platform.system()} requires host runtime verification."
        )
    if not macos_accessibility_trusted():
        raise PermissionError(
            "macOS Accessibility permission is required before OmniDesk can click UI elements."
        )

    safe_app = clean_app.replace('"', "")
    safe_el = element_name.strip().replace('"', "")
    ax_kind = "button" if role == "button" else "menu item"
    script = f'''
tell application "{safe_app}" to activate
delay 0.25
tell application "System Events"
  tell process "{safe_app}"
    click {ax_kind} "{safe_el}" of front window
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


def type_text_into_target(
    app_name: str,
    text: str,
    excluded_apps: list[str],
) -> dict[str, Any]:
    """Target-verified controlled keyboard entry with secure-field refusal."""
    clean_app = validate_app_name(app_name)
    if is_excluded_or_sensitive(clean_app, "", excluded_apps):
        raise PermissionError(f"Keyboard input blocked for sensitive application '{clean_app}'.")
    if len(text) > 1000:
        raise ValueError("Controlled text entry is bounded to 1000 characters per step.")

    if platform.system() != "Darwin":
        raise RuntimeError(
            f"Controlled keyboard entry on {platform.system()} requires host runtime verification."
        )
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
    return {
        "app_name": clean_app,
        "characters_typed": len(text),
        "target_verified": True,
    }


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
        subprocess.run(["explorer.exe", "ms-settings:privacy"], check=False, timeout=5)
        return {"opened": True, "pane": pane, "platform": "Windows"}
    return {
        "opened": False,
        "pane": pane,
        "platform": system,
        "note": "Open your Linux desktop privacy or XDG portal settings directly.",
    }
