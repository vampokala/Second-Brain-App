"""Unit tests for GitHub Enterprise host / API URL helpers."""

from __future__ import annotations

import pytest
from src.core.connectors.github import GitHubConnector
from src.core.connectors.github_host import (
    is_github_enterprise,
    normalize_github_api_base,
    normalize_github_host,
    resolve_github_api_base,
    resolve_github_mcp_url,
    resolve_github_oauth_urls,
)


def test_normalize_github_host_strips_path():
    assert normalize_github_host("https://github.company.com/foo") == "https://github.company.com"
    assert normalize_github_host("github.company.com") == "https://github.company.com"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.github.com", "https://api.github.com"),
        ("https://github.com", "https://api.github.com"),
        ("https://github.company.com", "https://github.company.com/api/v3"),
        ("https://github.company.com/api/v3", "https://github.company.com/api/v3"),
        ("https://github.company.com/api/v3/", "https://github.company.com/api/v3"),
        ("https://acme.ghe.com", "https://acme.ghe.com/api/v3"),
        ("github.company.com", "https://github.company.com/api/v3"),
    ],
)
def test_normalize_github_api_base(raw: str, expected: str):
    assert normalize_github_api_base(raw) == expected


def test_resolve_github_api_base_prefers_config_over_env(monkeypatch):
    monkeypatch.setenv("GITHUB_HOST", "https://env-host.example")
    monkeypatch.setenv("GITHUB_API_URL", "https://env-api.example/api/v3")
    assert resolve_github_api_base({"base_url": "https://cfg.example/api/v3"}) == "https://cfg.example/api/v3"


def test_resolve_github_api_base_derives_from_host(monkeypatch):
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    monkeypatch.setenv("GITHUB_HOST", "https://github.company.com")
    assert resolve_github_api_base({}) == "https://github.company.com/api/v3"


def test_resolve_github_oauth_urls_use_enterprise_host(monkeypatch):
    monkeypatch.setenv("GITHUB_HOST", "https://github.company.com")
    authorize, token = resolve_github_oauth_urls()
    assert authorize == "https://github.company.com/login/oauth/authorize"
    assert token == "https://github.company.com/login/oauth/access_token"


def test_resolve_github_oauth_urls_default_github_com(monkeypatch):
    monkeypatch.delenv("GITHUB_HOST", raising=False)
    authorize, token = resolve_github_oauth_urls()
    assert authorize == "https://github.com/login/oauth/authorize"
    assert token == "https://github.com/login/oauth/access_token"


def test_resolve_github_mcp_url_env_wins(monkeypatch):
    monkeypatch.setenv("GITHUB_MCP_URL", "http://ghes-mcp:8080/mcp/")
    assert resolve_github_mcp_url("https://api.githubcopilot.com/mcp") == "http://ghes-mcp:8080/mcp"


def test_is_github_enterprise(monkeypatch):
    monkeypatch.delenv("GITHUB_HOST", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert is_github_enterprise() is False
    monkeypatch.setenv("GITHUB_HOST", "https://github.company.com")
    assert is_github_enterprise() is True


def test_github_connector_uses_enterprise_api_base(monkeypatch):
    monkeypatch.delenv("GITHUB_HOST", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    conn = GitHubConnector(
        "acme/repo",
        {"base_url": "https://github.company.com"},
        token="t",
    )
    assert conn.base_url == "https://github.company.com/api/v3"
