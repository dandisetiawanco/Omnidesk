from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess

import psutil

from omnidesk_engine.automation.browser import find_cached_chromium_executable
from omnidesk_engine.automation.desktop_control import (
    linux_dbus_service_present,
    linux_is_wayland,
    macos_accessibility_trusted,
    macos_screen_recording_granted,
)
from omnidesk_engine.providers.registry import find_ollama_binary
from omnidesk_engine.schemas import CapabilityEntry, DisplayInfo, SystemProfile
from omnidesk_engine.security.credentials import CredentialVault


def _macos_gpu_and_displays() -> tuple[str, list[DisplayInfo]]:
    gpu = "macOS Metal GPU"
    displays: list[DisplayInfo] = []
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            text=True,
            timeout=5,
        )
        data = json.loads(out).get("SPDisplaysDataType", [])
        models = [g.get("sppci_model") for g in data if g.get("sppci_model")]
        if models:
            gpu = " / ".join(models)
        for g in data:
            for d in g.get("spdisplays_ndrvs", []):
                name = d.get("_name", "Display")
                pixels = d.get("_spdisplays_pixels", "1440 x 900")
                nums = [int(tok) for tok in pixels.replace("x", " ").split() if tok.isdigit()]
                w, h = (nums[0], nums[1]) if len(nums) >= 2 else (1440, 900)
                retina = "yes" in str(d.get("spdisplays_retina", "")).lower()
                displays.append(
                    DisplayInfo(name=name, width=w, height=h, scale_factor=2.0 if retina else 1.0)
                )
    except Exception:
        pass
    if not displays:
        displays.append(DisplayInfo(name="Primary Display", width=1440, height=900, scale_factor=2.0))
    return gpu, displays


def _windows_gpu_displays_and_build() -> tuple[str, list[DisplayInfo], int]:
    gpu = "Windows DirectX / WDDM GPU"
    displays: list[DisplayInfo] = []
    build = 0
    try:
        parts = platform.version().split(".")
        if len(parts) >= 3 and parts[2].isdigit():
            build = int(parts[2])
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' / '",
            ],
            text=True,
            timeout=5,
        ).strip()
        if out:
            gpu = out
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; $i=1; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { $n=if($_.Primary){'Primary Display'}else{\"Display $i\"}; \"$n|$($_.Bounds.Width)|$($_.Bounds.Height)|1.0\"; $i++ }",
            ],
            text=True,
            timeout=5,
        )
        for line in out.splitlines():
            segs = line.strip().split("|")
            if len(segs) >= 3 and segs[1].isdigit() and segs[2].isdigit():
                displays.append(
                    DisplayInfo(
                        name=segs[0],
                        width=int(segs[1]),
                        height=int(segs[2]),
                        scale_factor=float(segs[3]) if len(segs) >= 4 else 1.0,
                    )
                )
    except Exception:
        pass
    if not displays:
        displays.append(DisplayInfo(name="Primary Display", width=1920, height=1080, scale_factor=1.0))
    return gpu, displays, build


def _linux_gpu_and_displays() -> tuple[str, list[DisplayInfo]]:
    gpu = "Linux DRM / Mesa GPU"
    displays: list[DisplayInfo] = []
    if shutil.which("lspci"):
        try:
            out = subprocess.check_output(["lspci", "-mm"], text=True, timeout=3)
            gpus: list[str] = []
            for line in out.splitlines():
                if any(k in line for k in ("VGA compatible controller", "3D controller", "Display controller")):
                    quoted = line.split('"')
                    if len(quoted) >= 6:
                        gpus.append(f"{quoted[3]} {quoted[5]}".strip())
            if gpus:
                gpu = " / ".join(gpus)
        except Exception:
            pass
    if shutil.which("xrandr"):
        try:
            out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=3)
            for line in out.splitlines():
                if " connected" not in line:
                    continue
                tokens = line.split()
                name = tokens[0]
                w, h = 1920, 1080
                for tok in tokens:
                    if "+" in tok and "x" in tok.split("+")[0]:
                        dim = tok.split("+")[0].split("x")
                        if len(dim) == 2 and dim[0].isdigit() and dim[1].isdigit():
                            w, h = int(dim[0]), int(dim[1])
                            break
                displays.append(
                    DisplayInfo(
                        name=name,
                        width=w,
                        height=h,
                        scale_factor=float(os.environ.get("GDK_SCALE", "1.0")),
                    )
                )
        except Exception:
            pass
    if not displays:
        displays.append(DisplayInfo(name="Primary Display", width=1920, height=1080, scale_factor=1.0))
    return gpu, displays


def _cpu_model() -> str:
    if platform.system() == "Darwin":
        try:
            return subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=2
            ).strip()
        except Exception:
            pass
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.lower().startswith("model name") and ":" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
    return platform.processor() or platform.machine()


def collect_system_profile(vault: CredentialVault) -> SystemProfile:
    system = platform.system()
    arch = platform.machine()
    mem_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    cores = psutil.cpu_count(logical=True) or 1
    cpu = _cpu_model()

    capabilities: list[CapabilityEntry] = []

    if system == "Darwin":
        os_name = "macOS"
        os_ver = platform.mac_ver()[0] or platform.release()
        de = "macOS Aqua"
        ds = "Quartz Compositor"
        glass = "macos_vibrancy"
        gpu, displays = _macos_gpu_and_displays()
        ax_ok = macos_accessibility_trusted()
        scr_ok = macos_screen_recording_granted()

        capabilities.extend(
            [
                CapabilityEntry(
                    id="macos.accessibility",
                    name="macOS Accessibility API",
                    category="os",
                    status="available" if ax_ok else "permission_required",
                    maturity="implemented_tested",
                    detail=(
                        "Accessibility permission granted for live UI element inspection and controlled interaction."
                        if ax_ok
                        else "Grant Accessibility in System Settings > Privacy & Security for semantic UI control."
                    ),
                    platform_note="Checked live via AXIsProcessTrusted; OmniDesk never bypasses macOS TCC.",
                ),
                CapabilityEntry(
                    id="macos.screen_capture",
                    name="ScreenCaptureKit / Screen Recording (Optional)",
                    category="vision",
                    status="available" if scr_ok else "permission_required",
                    maturity="implemented_tested",
                    detail=(
                        "Screen Recording granted for explicit opt-in Live Workspace snapshots."
                        if scr_ok
                        else "Optional. Semantic Accessibility automation works without Screen Recording."
                    ),
                ),
                CapabilityEntry(
                    id="macos.app_launch",
                    name="Native App Launcher & Process Observer",
                    category="automation",
                    status="available",
                    maturity="implemented_tested",
                    detail="Lists running GUI apps via LaunchServices (`lsappinfo`) and opens apps/documents via `open -a`.",
                ),
            ]
        )
    elif system == "Windows":
        os_name = "Windows"
        os_ver = platform.version()
        gpu, displays, build = _windows_gpu_displays_and_build()
        de = f"Windows 11 Shell (Build {build})" if build >= 22000 else f"Windows 10 Shell (Build {build or 'unknown'})"
        ds = "DWM"
        glass = "windows_mica" if build >= 22000 else ("windows_acrylic" if build >= 17134 else "solid_fallback")
        capabilities.extend(
            [
                CapabilityEntry(
                    id="windows.uia",
                    name="Windows UI Automation (UIA)",
                    category="os",
                    status="available",
                    maturity="implemented_untested",
                    detail="UIAutomationClient tree inspection, Invoke/Toggle/Value patterns, and Win32 foreground detection.",
                    platform_note="Implemented for Windows 10 & 11; pending native Windows host verification.",
                ),
                CapabilityEntry(
                    id="windows.app_launch",
                    name="Native App Launcher & Window Switcher",
                    category="automation",
                    status="available",
                    maturity="implemented_untested",
                    detail="Focuses running windows via SetForegroundWindow or launches apps via Start-Process.",
                ),
            ]
        )
    else:
        os_name = "Linux"
        os_ver = platform.release()
        de = os.environ.get("XDG_CURRENT_DESKTOP", "Linux Desktop")
        is_wayland = linux_is_wayland()
        ds = "Wayland" if is_wayland else "X11"
        glass = (
            "linux_compositor"
            if any(k in de.lower() for k in ("kde", "plasma", "hyprland", "sway"))
            else "solid_fallback"
        )
        gpu, displays = _linux_gpu_and_displays()
        has_atspi = linux_dbus_service_present("org.a11y.Bus")
        has_portal = linux_dbus_service_present("org.freedesktop.portal.Desktop")
        capabilities.extend(
            [
                CapabilityEntry(
                    id="linux.at_spi",
                    name="AT-SPI2 Accessibility Bus",
                    category="os",
                    status="available" if has_atspi else "permission_required",
                    maturity="implemented_untested",
                    detail="Semantic UI tree inspection and Action/EditableText interaction via AT-SPI2 (skips password fields).",
                ),
                CapabilityEntry(
                    id="linux.portal",
                    name="XDG Desktop Portals & Window Session",
                    category="vision",
                    status=("permission_required" if has_portal else "unsupported") if is_wayland else "available",
                    maturity="implemented_untested",
                    detail=(
                        "Wayland restricts global capture and synthetic input; OmniDesk uses compositor portals only."
                        if is_wayland
                        else "X11 session supports wmctrl/xdotool window inspection and controlled input."
                    ),
                ),
            ]
        )

    ollama_bin = find_ollama_binary()
    capabilities.append(
        CapabilityEntry(
            id="runtime.ollama",
            name="Local Ollama Inference",
            category="ai_runtime",
            status="available" if ollama_bin else "not_installed",
            maturity="implemented_tested",
            detail=(
                f"Ollama runtime detected at {ollama_bin}."
                if ollama_bin
                else "Ollama is not installed on this device. Install Ollama or configure a provider in Models."
            ),
        )
    )

    chromium = find_cached_chromium_executable()
    capabilities.append(
        CapabilityEntry(
            id="automation.playwright",
            name="Playwright Browser Automation",
            category="browser",
            status="available" if chromium else "not_installed",
            maturity="implemented_tested",
            detail=(
                "Playwright Chromium binary detected locally for DOM inspection and form preparation."
                if chromium
                else "Chromium binary not found; run `playwright install chromium` to enable browser automation."
            ),
        )
    )

    capabilities.append(
        CapabilityEntry(
            id="automation.filesystem",
            name="Scoped File & Excel Engine",
            category="automation",
            status="available",
            maturity="implemented_tested",
            detail="Scoped directory inspection, SHA-256 duplicate detection, dry-run previews, reversible moves, and .xlsx reporting.",
        )
    )

    capabilities.append(
        CapabilityEntry(
            id="security.keyring",
            name="OS Secure Credential Vault",
            category="security",
            status="available" if vault.backend_name() != "unavailable" else "unsupported",
            maturity="implemented_tested",
            detail=f"Active keyring backend: {vault.backend_name()}. API keys are never written to plaintext files.",
        )
    )

    return SystemProfile(
        os_name=os_name,
        os_version=os_ver,
        arch=arch,
        cpu_model=cpu,
        cpu_cores=cores,
        memory_total_gb=mem_gb,
        gpu_name=gpu,
        desktop_environment=de,
        display_server=ds,
        displays=displays,
        glass_material=glass,  # type: ignore[arg-type]
        capabilities=capabilities,
    )
