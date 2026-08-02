"""Unit tests for gateway key validation."""

from __future__ import annotations

import asyncio

from src.api.key_validator import validate_key


class _FakeResponse:
    def __init__(self, *, ok: bool, text: str = "ok"):
        self.is_success = ok
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self._response


def test_validate_gateway_key_happy_path(monkeypatch):
    fake = _FakeAsyncClient(_FakeResponse(ok=True))
    monkeypatch.setattr("src.api.key_validator.httpx.AsyncClient", lambda **kwargs: fake)
    monkeypatch.setenv("GATEWAY_BASE_URL", "http://gw.test/v1")
    monkeypatch.setenv("GATEWAY_DEFAULT_MODEL", "org-model")

    ok, msg = asyncio.run(validate_key("gateway", "sk-test"))

    assert ok is True
    assert msg == "ok"
    assert fake.calls[0]["url"] == "http://gw.test/v1/chat/completions"
    assert fake.calls[0]["headers"]["Authorization"] == "Bearer sk-test"
    assert fake.calls[0]["json"]["model"] == "org-model"


def test_validate_gateway_key_missing():
    ok, msg = asyncio.run(validate_key("gateway", ""))
    assert ok is False
    assert msg == "missing key"


def test_validate_gateway_key_http_error(monkeypatch):
    fake = _FakeAsyncClient(_FakeResponse(ok=False, text="unauthorized"))
    monkeypatch.setattr("src.api.key_validator.httpx.AsyncClient", lambda **kwargs: fake)

    ok, msg = asyncio.run(validate_key("litellm", "sk-bad"))

    assert ok is False
    assert "unauthorized" in msg
