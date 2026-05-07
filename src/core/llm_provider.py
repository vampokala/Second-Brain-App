"""LLM provider abstractions for local and cloud models."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Iterator, Optional, Protocol

import ollama
import requests
from src.utils.config import LLMSettings, provider_api_key_env


def _raise_for_status_with_detail(resp: requests.Response, provider: str) -> None:
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detail = ""
        try:
            body = resp.json()
            detail = json.dumps(body)
        except Exception:
            detail = (resp.text or "").strip()
        detail = detail[:1200]
        if detail:
            msg = f"{provider} API error ({resp.status_code}): {detail}"
        else:
            msg = f"{provider} API error ({resp.status_code})"
        raise ValueError(msg) from exc


class LLMProvider(Protocol):
    def generate(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> str:
        ...

    def stream(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> Iterator[str]:
        ...


@dataclass
class LLMSelection:
    provider: str
    model: str


class OllamaProvider:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._client = ollama.Client(host=base_url)

    def generate(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> str:
        resp = self._chat_with_retry(model=model, prompt=prompt, stream=False)
        return str(resp.get("message", {}).get("content") or "")

    def stream(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> Iterator[str]:
        attempts = 3
        for idx in range(attempts):
            started = False
            try:
                stream = self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                for chunk in stream:  # type: ignore[assignment]
                    started = True
                    msg = chunk.get("message") or {}
                    piece = msg.get("content") or ""
                    if piece:
                        yield piece
                return
            except Exception:
                # Only retry startup failures; avoid duplicating partial streamed output.
                if started or idx == attempts - 1:
                    raise
                time.sleep(0.35 * (idx + 1))

    def _chat_with_retry(self, *, model: str, prompt: str, stream: bool):
        attempts = 3
        last_error: Exception | None = None
        messages = [{"role": "user", "content": prompt}]
        for idx in range(attempts):
            try:
                if stream:
                    return self._client.chat(
                        model=model,
                        messages=messages,
                        stream=True,
                    )
                return self._client.chat(
                    model=model,
                    messages=messages,
                    stream=False,
                )
            except Exception as exc:  # transient local daemon failures
                last_error = exc
                if idx == attempts - 1:
                    raise
                time.sleep(0.35 * (idx + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected Ollama retry state")


class OpenAIProvider:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _key(self, api_key_override: Optional[str] = None) -> str:
        key = api_key_override or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return key

    def generate(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> str:
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key(api_key_override)}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=self.timeout_seconds,
        )
        _raise_for_status_with_detail(resp, "openai")
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])

    def stream(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> Iterator[str]:
        with requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key(api_key_override)}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "stream": True,
            },
            timeout=self.timeout_seconds,
            stream=True,
        ) as resp:
            _raise_for_status_with_detail(resp, "openai")
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {})
                piece = delta.get("content")
                if piece:
                    yield str(piece)


class AnthropicProvider:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _key(self, api_key_override: Optional[str] = None) -> str:
        key = api_key_override or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        return key

    def generate(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> str:
        resp = requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self._key(api_key_override),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout_seconds,
        )
        _raise_for_status_with_detail(resp, "anthropic")
        data = resp.json()
        blocks = data.get("content", [])
        if not blocks:
            return ""
        return str(blocks[0].get("text", ""))

    def stream(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> Iterator[str]:
        with requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self._key(api_key_override),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
            timeout=self.timeout_seconds,
            stream=True,
        ) as resp:
            _raise_for_status_with_detail(resp, "anthropic")
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "content_block_delta":
                    piece = (payload.get("delta") or {}).get("text")
                    if piece:
                        yield str(piece)


class GeminiProvider:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _key(self, api_key_override: Optional[str] = None) -> str:
        key = api_key_override or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider")
        return key

    def generate(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> str:
        resp = requests.post(
            f"{self.base_url}/models/{model}:generateContent",
            params={"key": self._key(api_key_override)},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=self.timeout_seconds,
        )
        _raise_for_status_with_detail(resp, "gemini")
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return str(parts[0].get("text", "")) if parts else ""

    def stream(self, prompt: str, model: str, api_key_override: Optional[str] = None) -> Iterator[str]:
        with requests.post(
            f"{self.base_url}/models/{model}:streamGenerateContent",
            params={"key": self._key(api_key_override), "alt": "sse"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=self.timeout_seconds,
            stream=True,
        ) as resp:
            _raise_for_status_with_detail(resp, "gemini")
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                candidates = payload.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    continue
                piece = parts[0].get("text")
                if piece:
                    yield str(piece)


class LLMProviderRouter:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self._providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(settings.ollama_base_url),
            "openai": OpenAIProvider(settings.openai_base_url, settings.request_timeout_seconds),
            "anthropic": AnthropicProvider(settings.anthropic_base_url, settings.request_timeout_seconds),
            "gemini": GeminiProvider(settings.gemini_base_url, settings.request_timeout_seconds),
        }

    def resolve_selection(
        self,
        provider: Optional[str],
        model: Optional[str],
        *,
        has_api_key_override: bool = False,
    ) -> LLMSelection:
        normalized = self.settings.normalize_provider(provider)
        key_env = provider_api_key_env(normalized)
        if key_env and not has_api_key_override and not os.getenv(key_env):
            raise ValueError(f"{key_env} is required for provider {normalized!r}")
        selected_model = self.settings.resolve_model(normalized, model)
        return LLMSelection(provider=normalized, model=selected_model)

    def generate(self, provider: str, model: str, prompt: str, api_key_override: Optional[str] = None) -> str:
        impl = self._providers.get(provider)
        if impl is None:
            raise ValueError(f"Unsupported provider: {provider}")
        return impl.generate(prompt, model, api_key_override=api_key_override)

    def stream(
        self,
        provider: str,
        model: str,
        prompt: str,
        api_key_override: Optional[str] = None,
    ) -> Iterator[str]:
        impl = self._providers.get(provider)
        if impl is None:
            raise ValueError(f"Unsupported provider: {provider}")
        yield from impl.stream(prompt, model, api_key_override=api_key_override)
