"""App-setting secrets: env mapping, masking, and process-env hydration.

Connector tokens and LLM keys may be saved via PATCH /settings. Sync and LLM
code still read ``os.environ``; this module keeps those in sync after save and
on API startup. Docker ``.env`` values still win (never overwritten).
"""

from __future__ import annotations

import os
from typing import Any

# Setting key → process environment variable. Env always wins over DB.
ENV_WINS: dict[str, str] = {
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "gateway_api_key": "GATEWAY_API_KEY",
    "github_token": "GITHUB_TOKEN",
    "jira_api_token": "JIRA_API_TOKEN",
    "confluence_api_token": "CONFLUENCE_API_TOKEN",
    "slack_bot_token": "SLACK_BOT_TOKEN",
    "brave_search_api_key": "BRAVE_SEARCH_API_KEY",
    "google_oauth_client_id": "GOOGLE_OAUTH_CLIENT_ID",
    "google_oauth_client_secret": "GOOGLE_OAUTH_CLIENT_SECRET",
}

# Non-secret settings mirrored into process env (Docker/host env still wins).
ENV_PLAIN: dict[str, str] = {
    "gateway_base_url": "GATEWAY_BASE_URL",
}

_SECRET_SUFFIXES = ("_api_key", "_token", "_bot_token")


def is_secret_setting_key(key: str) -> bool:
    if key in ENV_WINS:
        return True
    return any(key.endswith(suf) for suf in _SECRET_SUFFIXES)


def extract_secret(value: Any) -> str | None:
    if isinstance(value, dict) and "secret" in value:
        raw = value.get("secret")
        return str(raw) if raw is not None and str(raw).strip() else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def wrap_secret(value: Any) -> dict[str, str]:
    if isinstance(value, dict) and "secret" in value:
        return {"secret": str(value.get("secret") or "")}
    return {"secret": str(value or "")}


def mask_secret(val: str) -> str:
    if len(val) <= 4:
        return "****"
    return "****" + val[-4:]


def hydrate_env_from_value(setting_key: str, value: Any, *, force: bool = False) -> bool:
    """Set ``os.environ`` from a settings value if env is not already set.

    Returns True when the process env was updated. ``force=True`` overwrites a
    previously hydrated value but never a boot-time (Docker/host) override.
    """
    from src.api.llm_settings_overlay import boot_env_has

    env_name = ENV_WINS.get(setting_key) or ENV_PLAIN.get(setting_key)
    if not env_name:
        return False
    if boot_env_has(env_name):
        return False
    if os.getenv(env_name) and not force:
        return False

    if setting_key in ENV_WINS:
        secret = extract_secret(value)
        if not secret:
            return False
        os.environ[env_name] = secret
        return True

    text = value.strip() if isinstance(value, str) else str(value or "").strip()
    if not text:
        return False
    os.environ[env_name] = text
    return True


def hydrate_env_from_rows(rows: dict[str, Any]) -> list[str]:
    """Hydrate all known secrets/plain env values from a settings row map."""
    from src.api.llm_settings_overlay import apply_rows

    updated: list[str] = []
    for key, value in rows.items():
        if key not in ENV_WINS and key not in ENV_PLAIN:
            continue
        if hydrate_env_from_value(key, value):
            env_name = ENV_WINS.get(key) or ENV_PLAIN[key]
            updated.append(env_name)
    apply_rows(rows)
    return updated


def strip_connector_secrets(config: dict | None) -> dict:
    """Remove accidental secret fields before persisting connector config."""
    cleaned = dict(config or {})
    for key in ("token", "api_token", "password", "secret", "access_token"):
        cleaned.pop(key, None)
    return cleaned
