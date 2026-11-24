from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess

import psutil

from omnidesk_engine.automation.browser import find_cached_chromium_executable
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


def _cpu_model() -> str:
    if platform.system() == "Darwin":
        try:
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=2).strip()
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

        capabilities.extend(
            [
                CapabilityEntry(
                    id="macos.accessibility",
                    name="macOS Accessibility API",
                    category="os",
                    status="permission_required",
                    detail="Grant Accessibility in System Settings > Privacy & Security for semantic desktop element targeting.",
                    platform_note="OmniDesk never bypasses macOS TCC protections.",
                ),
                CapabilityEntry(
                    id="macos.screen_capture",
                    name="ScreenCaptureKit / Screen Recording",
                    category="vision",
                    status="permission_required",
                    detail="Opt-in snapshots only. Grant Screen Recording when enabling Live Workspace.",
                ),
                CapabilityEntry(
                    id="macos.app_launch",
                    name="Native Application Launcher",
                    category="automation",
                    status="available",
                    detail="Opens installed macOS applications using LaunchServices.",
                ),
            ]
        )
    elif system == "Windows":
        os_name = "Windows"
        os_ver = platform.version()
        de = "Windows Desktop Shell"
        ds = "DWM"
        glass = "windows_mica"
        gpu = "Windows DirectX GPU"
        displays = [DisplayInfo(name="Primary Display", width=1920, height=1080, scale_factor=1.0)]
        capabilities.append(
            CapabilityEntry(
                id="windows.uia",
                name="Windows UI Automation",
                category="os",
                status="experimental",
                detail="Adapter prepared for Windows 10/11 UIA accessibility tree.",
            )
        )
    else:
        os_name = "Linux"
        os_ver = platform.release()
        de = os.environ.get("XDG_CURRENT_DESKTOP", "Linux Desktop")
        is_wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(
            os.environ.get("WAYLAND_DISPLAY")
        )
        ds = "Wayland" if is_wayland else "X11"
        glass = "linux_compositor" if any(k in de.lower() for k in ("kde", "hyprland")) else "solid_fallback"
        gpu = "Linux Mesa / DRM GPU"
        displays = [DisplayInfo(name="Primary Display", width=1920, height=1080, scale_factor=1.0)]
        capabilities.append(
            CapabilityEntry(
                id="linux.portal",
                name="XDG Desktop Portals & AT-SPI",
                category="os",
                status="permission_required" if is_wayland else "experimental",
                detail=(
                    "Wayland restricts global capture and synthetic input; OmniDesk uses compositor portals only."
                    if is_wayland
                    else "X11 + AT-SPI desktop inspection."
                ),
            )
        )

    ollama_bin = shutil.which("ollama")
    capabilities.append(
        CapabilityEntry(
            id="runtime.ollama",
            name="Local Ollama Inference",
            category="ai_runtime",
            status="available" if ollama_bin else "not_installed",
            detail=(
                "Ollama CLI detected locally."
                if ollama_bin
                else "Ollama is not installed on this device. Install Ollama or connect a provider in Models."
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
            detail="Scoped directory inspection, SHA-256 duplicate detection, dry-run previews, reversible moves, and .xlsx reporting.",
        )
    )

    capabilities.append(
        CapabilityEntry(
            id="security.keyring",
            name="OS Secure Credential Vault",
            category="security",
            status="available" if vault.backend_name() != "unavailable" else "unsupported",
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
