export type ThemePreference = "system" | "light" | "dark";

const STORAGE_KEY = "omnidesk.color-scheme";
const PERF_KEY = "omnidesk.performance-mode";

export function resolveSystemScheme(): "light" | "dark" {
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "dark";
}

export function applyThemePreference(pref: ThemePreference): void {
  const meta = document.querySelector('meta[name="color-scheme"]');
  try {
    if (pref === "system") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, pref);
    }
  } catch {
    // Continue applying theme even if storage is unavailable.
  }

  if (pref === "system") {
    meta?.setAttribute("content", "light dark");
    document.documentElement.setAttribute("data-theme", resolveSystemScheme());
  } else {
    meta?.setAttribute("content", pref);
    document.documentElement.setAttribute("data-theme", pref);
  }
}

export function applyPerformanceMode(enabled: boolean): void {
  try {
    localStorage.setItem(PERF_KEY, enabled ? "true" : "false");
  } catch {
    // Ignore storage error.
  }
  if (enabled) {
    document.documentElement.setAttribute("data-performance", "true");
  } else {
    document.documentElement.removeAttribute("data-performance");
  }
}
