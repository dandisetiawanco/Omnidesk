from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from omnidesk_engine.automation.desktop_control import is_excluded_or_sensitive, linux_is_wayland
from omnidesk_engine.db import Database
from omnidesk_engine.intelligence.planner import TaskPlanner
from omnidesk_engine.providers.registry import (
    ProviderRegistry,
    detect_model_capabilities,
    estimate_cost_usd,
    extract_json_object,
)
from omnidesk_engine.schemas import AppSettings, ProviderConfigUpdate
from omnidesk_engine.security.credentials import CredentialVault


def test_model_capability_detection_and_cost_estimation() -> None:
    caps = detect_model_capabilities(["gemini-2.5-flash", "qwen2.5:1.5b", "claude-sonnet-4-5"])
    assert "vision" in caps["gemini-2.5-flash"]
    assert "fast_tier" in caps["gemini-2.5-flash"]
    assert "local_cpu_friendly" in caps["qwen2.5:1.5b"]
    assert "structured_json" in caps["claude-sonnet-4-5"]

    cost = estimate_cost_usd("gemini-2.5-flash", 1000, 500)
    assert cost is not None and cost > 0
    assert estimate_cost_usd("qwen2.5:1.5b", 1000, 500) is None


def test_extract_json_object_handles_fences_and_noise() -> None:
    raw = 'Sure!\n```json\n{"title": "Scan", "steps": [{"title": "List", "tool": "apps.list_running", "parameters": {}}]}\n```'
    parsed = extract_json_object(raw)
    assert parsed is not None
    assert parsed["title"] == "Scan"
    assert extract_json_object("not json at all") is None


def test_privacy_mode_local_only_excludes_cloud_providers(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    vault = CredentialVault()
    reg = ProviderRegistry(db, vault)

    settings = db.get_settings()
    settings.privacy_mode = "local_only"
    db.save_settings(settings)
    local_candidates = reg._ordered_candidates(None)
    assert "gemini" not in local_candidates
    assert "openai" not in local_candidates
    assert "anthropic" not in local_candidates
    assert "ollama" in local_candidates

    settings.privacy_mode = "cloud_assisted"
    settings.provider_fallback_order = ["anthropic", "gemini", "ollama"]
    db.save_settings(settings)
    cloud_candidates = reg._ordered_candidates("openai")
    assert cloud_candidates[:3] == ["openai", "anthropic", "gemini"]


def test_planner_rejects_malformed_or_unsafe_llm_plan_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "test.db")
    vault = CredentialVault()
    reg = ProviderRegistry(db, vault)
    planner = TaskPlanner(reg)

    async def fake_bad_plan(*_args: Any, **_kwargs: Any):
        return (
            {
                "title": "Bad Plan",
                "steps": [
                    {"title": "Run shell", "tool": "system.shell_command", "parameters": {"cmd": "ls"}},
                    {"title": "Bogus", "tool": "not.a.real.tool", "parameters": {}},
                ],
            },
            "ollama:qwen2.5:1.5b",
            None,
            None,
        )

    monkeypatch.setattr(reg, "complete_json_plan", fake_bad_plan)
    title, steps, source, _scope, _usage, fallback_note = asyncio.run(
        planner.build_plan("Inspect my Downloads folder", target_directory=str(tmp_path))
    )
    assert source == "local_deterministic_planner"
    assert fallback_note is not None
    assert "rejected by policy validation" in fallback_note
    assert all(s.tool != "system.shell_command" for s in steps)
    assert title


def test_provider_primary_model_and_context_limit_persistence(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    vault = CredentialVault()
    reg = ProviderRegistry(db, vault)

    updated = asyncio.run(
        reg.update_provider(
            "ollama",
            ProviderConfigUpdate(primary_model="qwen2.5:1.5b", context_limit=2048),
        )
    )
    assert updated.primary_model == "qwen2.5:1.5b"
    assert updated.context_limit == 2048


def test_sensitive_app_and_wayland_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_excluded_or_sensitive("1Password", "Vault", ["1Password"]) is True
    assert is_excluded_or_sensitive("TextEdit", "Sign in to Bank", ["1Password"]) is True
    assert is_excluded_or_sensitive("TextEdit", "Meeting Notes.txt", ["1Password"]) is False

    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert linux_is_wayland() is True
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert linux_is_wayland() is False
