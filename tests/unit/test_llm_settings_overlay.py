"""Unit tests for AI Gateway settings overlay."""

from __future__ import annotations

import os

import pytest
import src.api.llm_settings_overlay as overlay
from src.utils.config import LLMSettings


@pytest.fixture(autouse=True)
def _reset_overlay(monkeypatch):
    monkeypatch.delenv("GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("GATEWAY_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    overlay._overlay["default_model_by_provider"] = {}
    overlay._overlay["allowed_models_by_provider"] = {}
    overlay._overlay["gateway_base_url"] = None
    overlay._locked_env.clear()
    overlay._lock_captured = False
    yield
    overlay._locked_env.clear()
    overlay._lock_captured = False
    overlay._overlay["default_model_by_provider"] = {}
    overlay._overlay["allowed_models_by_provider"] = {}
    overlay._overlay["gateway_base_url"] = None


def test_apply_rows_sets_gateway_url_and_default_model():
    overlay.apply_rows(
        {
            "gateway_base_url": "http://gateway.internal/v1",
            "default_model_by_provider": {"gateway": "org-gpt"},
            "allowed_models_by_provider": {"gateway": ["org-gpt"]},
        }
    )

    assert os.getenv("GATEWAY_BASE_URL") == "http://gateway.internal/v1"
    assert os.getenv("GATEWAY_DEFAULT_MODEL") == "org-gpt"
    merged = overlay.merge_for_config(LLMSettings())
    assert merged["gateway_base_url"] == "http://gateway.internal/v1"
    assert merged["default_model_by_provider"]["gateway"] == "org-gpt"
    assert "org-gpt" in merged["allowed_models_by_provider"]["gateway"]


def test_boot_env_locks_gateway_url(monkeypatch):
    monkeypatch.setenv("GATEWAY_BASE_URL", "http://from-docker/v1")
    overlay.lock_existing_env()
    assert overlay.boot_env_has("GATEWAY_BASE_URL") is True

    overlay.apply_rows({"gateway_base_url": "http://from-ui/v1"})

    assert os.getenv("GATEWAY_BASE_URL") == "http://from-docker/v1"
    assert overlay.resolved_gateway_base_url(LLMSettings()) == "http://from-docker/v1"


def test_merge_for_config_keeps_empty_gateway_list():
    merged = overlay.merge_for_config(LLMSettings())
    assert "gateway" in merged["allowed_models_by_provider"]
    assert isinstance(merged["allowed_models_by_provider"]["gateway"], list)


def test_apply_rows_ignores_blank_gateway_url():
    overlay.apply_rows({"gateway_base_url": "   "})
    assert overlay._overlay["gateway_base_url"] is None
    assert os.getenv("GATEWAY_BASE_URL") is None
