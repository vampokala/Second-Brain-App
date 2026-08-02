import os

from src.core.llm_provider import AnthropicProvider, GeminiProvider, OpenAIProvider


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)


def test_openai_stream_parses_sse(monkeypatch):
    os.environ["OPENAI_API_KEY"] = "k"
    lines = [
        'data: {"choices":[{"delta":{"content":"hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _FakeResp(lines))
    p = OpenAIProvider("https://api.openai.com/v1", 10)
    assert "".join(p.stream("q", "gpt")) == "hello world"


def test_gateway_provider_reads_env_base_url_and_key(monkeypatch):
    os.environ["GATEWAY_API_KEY"] = "gw-key"
    monkeypatch.setenv("GATEWAY_BASE_URL", "http://litellm.local/v1")
    captured = {}

    def _post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return _FakeResp(['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"])

    monkeypatch.setattr("requests.post", _post)
    p = OpenAIProvider(
        "http://localhost:4000/v1",
        10,
        api_key_env="GATEWAY_API_KEY",
        base_url_env="GATEWAY_BASE_URL",
        provider_label="gateway",
    )
    assert "".join(p.stream("q", "org-model")) == "ok"
    assert captured["url"] == "http://litellm.local/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer gw-key"


def test_anthropic_stream_parses_sse(monkeypatch):
    os.environ["ANTHROPIC_API_KEY"] = "k"
    lines = [
        'data: {"type":"content_block_delta","delta":{"text":"hi"}}',
        'data: {"type":"content_block_delta","delta":{"text":" there"}}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _FakeResp(lines))
    p = AnthropicProvider("https://api.anthropic.com/v1", 10)
    assert "".join(p.stream("q", "claude")) == "hi there"


def test_gemini_stream_parses_sse(monkeypatch):
    os.environ["GEMINI_API_KEY"] = "k"
    lines = [
        'data: {"candidates":[{"content":{"parts":[{"text":"a"}]}}]}',
        'data: {"candidates":[{"content":{"parts":[{"text":"b"}]}}]}',
    ]
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _FakeResp(lines))
    p = GeminiProvider("https://generativelanguage.googleapis.com/v1beta", 10)
    assert "".join(p.stream("q", "gemini-1.5-flash")) == "ab"
