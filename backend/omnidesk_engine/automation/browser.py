from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

from omnidesk_engine.security.policy import detect_prompt_injection, validate_url


def find_cached_chromium_executable() -> str | None:
    """Finds Playwright-cached Chromium binaries on disk when exact version folders differ."""
    roots = [
        Path.home() / "Library" / "Caches" / "ms-playwright",
        Path.home() / ".cache" / "ms-playwright",
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.environ.get("LOCALAPPDATA") else None,
    ]
    patterns = [
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "chromium_headless_shell-*/chrome-mac/headless_shell",
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-win/chrome.exe",
    ]
    for root in roots:
        if not root or not root.exists():
            continue
        for pat in patterns:
            hits = sorted(glob.glob(str(root / pat)), reverse=True)
            if hits:
                return hits[0]
    return None


async def navigate_and_extract(
    url: str,
    selector: str | None = None,
    timeout_ms: int = 20000,
) -> dict[str, Any]:
    clean_url = validate_url(url)
    from playwright.async_api import async_playwright

    executable = find_cached_chromium_executable()
    launch_kwargs: dict[str, Any] = {"headless": True}
    if executable:
        launch_kwargs["executable_path"] = executable

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            response = await page.goto(clean_url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = await page.title()
            final_url = page.url

            if selector:
                locator = page.locator(selector).first
                extracted = (await locator.inner_text(timeout=5000)).strip()[:4000]
            else:
                extracted = (await page.locator("body").inner_text(timeout=5000)).strip()[:4000]

            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.slice(0, 15).map(e => ({text: (e.innerText || '').trim().slice(0, 80), href: e.href}))",
            )
            injection_hits = detect_prompt_injection(extracted)

            return {
                "url": final_url,
                "status_code": response.status if response else None,
                "title": title,
                "text_excerpt": extracted[:1200],
                "link_count": len(links),
                "links": links,
                "prompt_injection_signals": len(injection_hits),
                "untrusted_content_isolated": True,
            }
        finally:
            await browser.close()


async def prepare_form(
    url: str,
    fields: dict[str, str],
    timeout_ms: int = 20000,
) -> dict[str, Any]:
    """Fills form inputs in Playwright and reports verification without submitting external forms."""
    clean_url = validate_url(url)
    from playwright.async_api import async_playwright

    executable = find_cached_chromium_executable()
    launch_kwargs: dict[str, Any] = {"headless": True}
    if executable:
        launch_kwargs["executable_path"] = executable

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            page = await browser.new_page()
            await page.goto(clean_url, wait_until="domcontentloaded", timeout=timeout_ms)
            filled: list[str] = []
            missing: list[str] = []
            for selector, value in fields.items():
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.fill(value)
                    filled.append(selector)
                else:
                    missing.append(selector)
            return {
                "url": page.url,
                "filled_selectors": filled,
                "missing_selectors": missing,
                "submitted": False,
                "note": "Form values prepared without automatic external submission.",
            }
        finally:
            await browser.close()
