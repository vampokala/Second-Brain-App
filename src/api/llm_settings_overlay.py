"""Runtime LLM settings overlay (DB/Settings → /config/llm + process env).

Gateway base URL, default models, and allowed model lists can be updated via
PATCH /settings without restarting the API. Environment variables present at
API startup (Docker/host) remain locked and are never overwritten from DB.
"""

from __future__ import annotations

import os
from typing import Any

from src.utils.config import LLMSettings

# Env vars present before DB hydration — Docker/host overrides.
_locked_env: set[str] = set()
_lock_captured: bool = False

_overlay: dict[str, Any] = {
    "default_model_by_provider": {},
    "allowed_models_by_provider": {},
    "gateway_base_url": None,
}


def lock_existing_env() -> None:
    """Snapshot env overrides. Call once at API startup before DB hydration."""
    global _lock_captured
    from src.api.settings_secrets import ENV_PLAIN, ENV_WINS

    _locked_env.clear()
    for env_name in (*ENV_WINS.values(), *ENV_PLAIN.values(), "GATEWAY_DEFAULT_MODEL"):
        if os.getenv(env_name):
            _locked_env.add(env_name)
    _lock_captured = True


def boot_env_has(env_name: str) -> bool:
    return env_name in _locked_env


def lock_was_captured() -> bool:
    return _lock_captured


def apply_rows(rows: dict[str, Any]) -> None:
    """Merge persisted settings into the in-memory overlay and hydrate env."""
    defaults = rows.get("default_model_by_provider")
    if isinstance(defaults, dict):
        cleaned = {str(k): str(v) for k, v in defaults.items() if v}
        _overlay["default_model_by_provider"] = {
            **_overlay["default_model_by_provider"],
            **cleaned,
        }
        gateway_model = cleaned.get("gateway", "").strip()
        if gateway_model and not boot_env_has("GATEWAY_DEFAULT_MODEL"):
            os.environ["GATEWAY_DEFAULT_MODEL"] = gateway_model

    allowed = rows.get("allowed_models_by_provider")
    if isinstance(allowed, dict):
        merged_allowed = dict(_overlay["allowed_models_by_provider"])
        for provider, models in allowed.items():
            if not isinstance(models, list):
                continue
            existing = list(merged_allowed.get(str(provider), []))
            for model in models:
                text = str(model).strip()
                if text and text not in existing:
                    existing.append(text)
            merged_allowed[str(provider)] = existing
        _overlay["allowed_models_by_provider"] = merged_allowed

    raw_url = rows.get("gateway_base_url")
    if isinstance(raw_url, str) and raw_url.strip():
        url = raw_url.strip()
        _overlay["gateway_base_url"] = url
        if not boot_env_has("GATEWAY_BASE_URL"):
            os.environ["GATEWAY_BASE_URL"] = url


def apply_patch(patch: dict[str, Any]) -> None:
    apply_rows(patch)


def resolved_gateway_base_url(llm: LLMSettings) -> str:
    if boot_env_has("GATEWAY_BASE_URL"):
        return (os.getenv("GATEWAY_BASE_URL") or llm.gateway_base_url).rstrip("/")
    overlay_url = _overlay.get("gateway_base_url")
    if isinstance(overlay_url, str) and overlay_url.strip():
        return overlay_url.strip().rstrip("/")
    env_url = (os.getenv("GATEWAY_BASE_URL") or "").strip()
    if env_url:
        return env_url.rstrip("/")
    return llm.gateway_base_url.rstrip("/")


def merge_for_config(llm: LLMSettings) -> dict[str, Any]:
    """Build public LLM config fields with Settings overlay applied."""
    defaults = dict(llm.default_model_by_provider)
    defaults.update(_overlay.get("default_model_by_provider") or {})
    env_gateway_model = (os.getenv("GATEWAY_DEFAULT_MODEL") or "").strip()
    if env_gateway_model:
        defaults["gateway"] = env_gateway_model

    allowed: dict[str, list[str]] = {k: list(v) for k, v in llm.allowed_models_by_provider.items()}
    for provider, models in (_overlay.get("allowed_models_by_provider") or {}).items():
        current = list(allowed.get(provider, []))
        for model in models:
            if model not in current:
                current.append(model)
        allowed[provider] = current

    gateway_default = (defaults.get("gateway") or "").strip()
    if gateway_default:
        gateway_allowed = list(allowed.get("gateway") or [])
        if gateway_default not in gateway_allowed:
            gateway_allowed.insert(0, gateway_default)
        allowed["gateway"] = gateway_allowed

    allowed.setdefault("gateway", [])

    return {
        "default_provider": llm.default_provider,
        "default_model_by_provider": defaults,
        "allowed_models_by_provider": allowed,
        "gateway_base_url": resolved_gateway_base_url(llm),
    }
