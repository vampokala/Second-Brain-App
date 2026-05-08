"""Lightweight provider key validation (single call)."""

from __future__ import annotations

import os

import httpx

from src.utils.config import load_config


async def validate_key(provider: str, api_key: str | None) -> tuple[bool, str]:
    p = (provider or "").strip().lower()
    cfg = load_config("config.yaml").llm
    timeout = 30.0
    try:
        if p == "openai":
            k = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
            if not k:
                return False, "missing key"
            url = cfg.openai_base_url.rstrip("/") + "/chat/completions"
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {k}"},
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                )
            return r.is_success, (r.text[:200] if not r.is_success else "ok")
        if p == "anthropic":
            k = (api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip()
            if not k:
                return False, "missing key"
            url = cfg.anthropic_base_url.rstrip("/") + "/messages"
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    url,
                    headers={
                        "x-api-key": k,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
            return r.is_success, (r.text[:200] if not r.is_success else "ok")
        if p == "ollama":
            return True, "local"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]
    return False, "unsupported"
