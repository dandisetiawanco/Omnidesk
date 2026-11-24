// Runs synchronously before first paint to avoid flashing the wrong color scheme.
(function initTheme() {
  try {
    var stored = localStorage.getItem("omnidesk.color-scheme");
    var meta = document.querySelector('meta[name="color-scheme"]');
    if (stored === "light" || stored === "dark") {
      if (meta) meta.setAttribute("content", stored);
      document.documentElement.setAttribute("data-theme", stored);
    } else {
      if (meta) meta.setAttribute("content", "light dark");
      var prefersDark =
        window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");
    }
    var perf = localStorage.getItem("omnidesk.performance-mode");
    if (perf === "true") {
      document.documentElement.setAttribute("data-performance", "true");
    }
  } catch (_) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();
