"""GitHub.com vs GitHub Enterprise Server (GHES) / ghe.com host helpers.

Env vars (optional):
- ``GITHUB_HOST`` — web host, e.g. ``https://github.company.com`` or
  ``https://acme.ghe.com``. Used to derive API and OAuth endpoints.
- ``GITHUB_API_URL`` — explicit REST API base (overrides derived
  ``{host}/api/v3``). For github.com this is ``https://api.github.com``.
- ``GITHUB_MCP_URL`` — MCP endpoint override (self-hosted github-mcp-server
  for GHES; remote Copilot MCP is github.com-only).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

_DEFAULT_API = "https://api.github.com"
_DEFAULT_WEB = "https://github.com"
_DEFAULT_MCP = "https://api.githubcopilot.com/mcp"


def normalize_github_host(url: str | None) -> str | None:
    """Return scheme+host with no path/trailing slash, or None if empty/invalid."""
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc}".rstrip("/")


def normalize_github_api_base(url: str | None) -> str | None:
    """Normalize a GitHub REST API base URL.

    Accepts either ``https://api.github.com``, ``https://host/api/v3``, or a
    bare enterprise web host (``https://github.company.com`` → ``.../api/v3``).
    """
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme or "https"
    host = parsed.netloc.lower()
    path = (parsed.path or "").rstrip("/")

    if host in {"api.github.com", "github.com"}:
        return _DEFAULT_API

    if path.endswith("/api/v3") or path == "/api/v3":
        return f"{scheme}://{parsed.netloc}/api/v3"
    if path in {"", "/"}:
        # Enterprise web host entered as API base — append /api/v3.
        if host.endswith(".ghe.com") or host not in {"github.com", "www.github.com"}:
            return f"{scheme}://{parsed.netloc}/api/v3"
        return _DEFAULT_API
    # Keep explicit custom paths (rare proxies).
    return f"{scheme}://{parsed.netloc}{path}".rstrip("/")


def resolve_github_host() -> str:
    """Web host for OAuth / HTML links (GITHUB_HOST or github.com)."""
    return normalize_github_host(os.getenv("GITHUB_HOST")) or _DEFAULT_WEB


def resolve_github_api_base(config: dict | None = None) -> str:
    """REST API base: config.base_url → GITHUB_API_URL → derive from GITHUB_HOST → api.github.com."""
    cfg = (config or {}).get("base_url") if config else None
    from_cfg = normalize_github_api_base(str(cfg) if cfg else None)
    if from_cfg:
        return from_cfg
    from_env = normalize_github_api_base(os.getenv("GITHUB_API_URL"))
    if from_env:
        return from_env
    host = normalize_github_host(os.getenv("GITHUB_HOST"))
    if host and host != _DEFAULT_WEB:
        derived = normalize_github_api_base(host)
        if derived:
            return derived
    return _DEFAULT_API


def resolve_github_oauth_urls() -> tuple[str, str]:
    """Return (authorize_url, token_url) for github.com or GITHUB_HOST."""
    host = resolve_github_host()
    return (
        f"{host}/login/oauth/authorize",
        f"{host}/login/oauth/access_token",
    )


def resolve_github_mcp_url(override: str | None = None) -> str:
    """MCP endpoint: GITHUB_MCP_URL → explicit override → Copilot remote MCP."""
    env_url = (os.getenv("GITHUB_MCP_URL") or "").strip()
    if env_url:
        return env_url.rstrip("/")
    if override:
        return override.rstrip("/")
    return _DEFAULT_MCP


def is_github_enterprise() -> bool:
    """True when GITHUB_HOST / GITHUB_API_URL points away from github.com."""
    host = normalize_github_host(os.getenv("GITHUB_HOST"))
    if host and host != _DEFAULT_WEB:
        return True
    api = normalize_github_api_base(os.getenv("GITHUB_API_URL"))
    return bool(api and api != _DEFAULT_API)
