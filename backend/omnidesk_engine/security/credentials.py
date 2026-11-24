from __future__ import annotations

import os
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "digital.ngoprek.omnidesk"
SUPPORTED_PROVIDERS = ("openai", "gemini", "anthropic", "ollama", "openai_compatible")


@dataclass(frozen=True)
class CredentialSummary:
    configured: bool
    masked_key: str | None
    storage_backend: str


def mask_key(secret: str) -> str:
    clean = secret.strip()
    if len(clean) <= 8:
        return "****"
    return f"{clean[:4]}...{clean[-4:]}"


class CredentialVault:
    """Stores provider API keys strictly in OS Keychain / Credential Manager / Secret Service.

    Never writes secrets to plaintext files, SQLite, logs, or frontend payloads.
    """

    def __init__(self) -> None:
        self._env_map = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai_compatible": "OMNIDESK_OPENAI_COMPAT_API_KEY",
        }

    def _validate_provider(self, provider_id: str) -> None:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider_id}")

    def backend_name(self) -> str:
        try:
            kr = keyring.get_keyring()
            return kr.name
        except Exception:
            return "unavailable"

    def set_secret(self, provider_id: str, secret: str) -> CredentialSummary:
        self._validate_provider(provider_id)
        cleaned = secret.strip()
        if len(cleaned) < 8:
            raise ValueError("API key must be at least 8 characters.")
        try:
            keyring.set_password(SERVICE_NAME, provider_id, cleaned)
        except KeyringError as exc:
            raise RuntimeError(
                "OS secure credential store is unavailable; refusing to store API key in plaintext."
            ) from exc
        return CredentialSummary(
            configured=True,
            masked_key=mask_key(cleaned),
            storage_backend=self.backend_name(),
        )

    def get_secret_internal(self, provider_id: str) -> str | None:
        self._validate_provider(provider_id)
        try:
            stored = keyring.get_password(SERVICE_NAME, provider_id)
            if stored and stored.strip():
                return stored.strip()
        except KeyringError:
            pass
        env_var = self._env_map.get(provider_id)
        if env_var:
            val = os.environ.get(env_var, "").strip()
            if val:
                return val
        return None

    def get_summary(self, provider_id: str) -> CredentialSummary:
        secret = self.get_secret_internal(provider_id)
        if secret:
            return CredentialSummary(
                configured=True,
                masked_key=mask_key(secret),
                storage_backend=self.backend_name(),
            )
        return CredentialSummary(
            configured=False,
            masked_key=None,
            storage_backend=self.backend_name(),
        )

    def delete_secret(self, provider_id: str) -> CredentialSummary:
        self._validate_provider(provider_id)
        try:
            keyring.delete_password(SERVICE_NAME, provider_id)
        except KeyringError:
            pass
        return CredentialSummary(
            configured=False,
            masked_key=None,
            storage_backend=self.backend_name(),
        )
