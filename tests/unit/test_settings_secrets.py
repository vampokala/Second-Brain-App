"""Unit tests for settings secret helpers."""

from __future__ import annotations

from src.api.settings_secrets import (
    ENV_WINS,
    extract_secret,
    hydrate_env_from_value,
    is_secret_setting_key,
    mask_secret,
    strip_connector_secrets,
    wrap_secret,
)


def test_connector_keys_map_to_expected_env_names():
    assert ENV_WINS["github_token"] == "GITHUB_TOKEN"
    assert ENV_WINS["jira_api_token"] == "JIRA_API_TOKEN"
    assert ENV_WINS["confluence_api_token"] == "CONFLUENCE_API_TOKEN"
    assert ENV_WINS["slack_bot_token"] == "SLACK_BOT_TOKEN"


def test_is_secret_setting_key_for_connector_and_llm():
    assert is_secret_setting_key("github_token") is True
    assert is_secret_setting_key("openai_api_key") is True
    assert is_secret_setting_key("default_model_by_provider") is False


def test_extract_and_wrap_secret():
    assert extract_secret({"secret": "abc"}) == "abc"
    assert extract_secret("plain") == "plain"
    assert extract_secret({"secret": "  "}) is None
    assert wrap_secret("x") == {"secret": "x"}


def test_mask_secret_boundary():
    assert mask_secret("ab") == "****"
    assert mask_secret("abcdefgh") == "****efgh"


def test_hydrate_sets_env_when_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert hydrate_env_from_value("github_token", {"secret": "ghp_test"}) is True
    import os

    assert os.getenv("GITHUB_TOKEN") == "ghp_test"


def test_hydrate_skips_when_env_already_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "from-docker")
    assert hydrate_env_from_value("github_token", {"secret": "from-ui"}) is False
    import os

    assert os.getenv("GITHUB_TOKEN") == "from-docker"


def test_hydrate_noop_for_unknown_key(monkeypatch):
    assert hydrate_env_from_value("not_a_secret", {"secret": "x"}) is False


def test_strip_connector_secrets_removes_token_fields():
    cleaned = strip_connector_secrets({"email": "a@b.com", "token": "secret", "api_token": "x", "branch": "main"})
    assert cleaned == {"email": "a@b.com", "branch": "main"}
    assert strip_connector_secrets(None) == {}
