"""
YAML-based configuration with environment variable overrides.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


def _env_or(env_name: str, default: str) -> str:
    value = os.getenv(env_name)
    if value is None:
        return default
    trimmed = value.strip()
    return trimmed or default


def _truthy_env_string(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return True


def doc_ollama_runtime_enabled() -> bool:
    """Whether the Ollama LLM provider should appear in config and /config/llm.

    Ollama targets a local daemon and is unavailable on hosted Hugging Face Spaces.

    - If ``DOC_OLLAMA_ENABLED`` is set to a non-empty string, it wins (true/false
      semantics via ``_truthy_env_string``).
    - Otherwise, Ollama is disabled when ``SPACE_ID`` is set (HF Spaces injects this).
    - Otherwise Ollama stays enabled (local installs, CI, generic Docker).
    """
    raw = os.getenv("DOC_OLLAMA_ENABLED")
    if raw is not None and raw.strip() != "":
        return _truthy_env_string(raw)
    if os.getenv("SPACE_ID", "").strip():
        return False
    return True


def _strip_ollama_llm_settings(cfg: Config) -> Config:
    llm = cfg.llm
    new_allowed = {k: v for k, v in llm.allowed_models_by_provider.items() if k != "ollama"}
    new_defaults = {k: v for k, v in llm.default_model_by_provider.items() if k != "ollama"}
    if not new_allowed:
        return cfg
    new_default = llm.default_provider
    if new_default == "ollama" or new_default not in new_allowed:
        new_default = next(iter(new_allowed.keys()))
    new_llm = llm.model_copy(
        update={
            "allowed_models_by_provider": new_allowed,
            "default_model_by_provider": new_defaults,
            "default_provider": new_default,
        }
    )
    return cfg.model_copy(update={"llm": new_llm})


def _default_ollama_base_url() -> str:
    # OLLAMA_HOST is used by some Ollama setups; keep it as a fallback.
    return _env_or("OLLAMA_BASE_URL", _env_or("OLLAMA_HOST", "http://localhost:11434"))


class RerankerSettings(BaseModel):
    model: str = Field("cross-encoder/ms-marco-MiniLM-L-6-v2", description="Cross-encoder HF id")
    batch_size: int = Field(32, ge=1)
    score_threshold: float = Field(0.1, description="Minimum CE score to keep a candidate")
    top_k: int = Field(5, ge=1, description="Chunks to return after reranking")


class ContextSettings(BaseModel):
    max_tokens: int = Field(4000, ge=256, description="Max context tokens for the LLM prompt body")
    tokenizer: str = Field("gpt2", description="HF tokenizer id used only for counting")


class GenerationSettings(BaseModel):
    model: str = Field("qwen2.5-coder:14b", description="Default Ollama chat model")
    stream: bool = Field(False, description="Default streaming for CLI")
    cache_ttl: int = Field(300, ge=0, description="Response cache TTL seconds (0 disables)")


class LLMSettings(BaseModel):
    default_provider: str = Field("ollama", description="Default provider: ollama/openai/anthropic/gemini")
    default_model_by_provider: Dict[str, str] = Field(
        default_factory=lambda: {
            "ollama": "qwen2.5:7b",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-6",
            "gemini": "gemini-2.5-flash",
        }
    )
    allowed_models_by_provider: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "ollama": ["qwen2.5:7b", "deepseek-r1:8b"],
            "openai": ["gpt-4o-mini"],
            "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5"],
            "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
        }
    )
    request_timeout_seconds: int = Field(60, ge=5, le=600)
    openai_base_url: str = Field(
        default_factory=lambda: _env_or("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        description="OpenAI-compatible API base URL",
    )
    anthropic_base_url: str = Field(
        default_factory=lambda: _env_or("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        description="Anthropic API base URL",
    )
    gemini_base_url: str = Field(
        default_factory=lambda: _env_or("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
        description="Gemini API base URL",
    )
    ollama_base_url: str = Field(
        default_factory=_default_ollama_base_url,
        description="Ollama API base URL",
    )

    def normalize_provider(self, provider: Optional[str]) -> str:
        p = (provider or self.default_provider).strip().lower()
        aliases = {"claude": "anthropic"}
        return aliases.get(p, p)

    def provider_has_key(self, provider: str) -> bool:
        env_name = provider_api_key_env(provider)
        if env_name is None:
            return True
        return bool(os.getenv(env_name))

    def is_provider_enabled(self, provider: str) -> bool:
        p = self.normalize_provider(provider)
        allow = self.allowed_models_by_provider.get(p) or []
        if not allow:
            return False
        return self.provider_has_key(p)

    def resolve_model(self, provider: str, requested_model: Optional[str]) -> str:
        p = self.normalize_provider(provider)
        allowed = self.allowed_models_by_provider.get(p) or []
        if not allowed:
            raise ValueError(f"Provider {p!r} is disabled (no allowed models configured)")
        if requested_model:
            if requested_model not in allowed:
                raise ValueError(f"Model {requested_model!r} is not allowed for provider {p!r}")
            return requested_model
        default_model = self.default_model_by_provider.get(p)
        if default_model and default_model in allowed:
            return default_model
        return allowed[0]


class EvaluationSettings(BaseModel):
    inline_enabled: bool = Field(True, description="Attach truthfulness score to every query response")
    nli_model: str = Field(
        "cross-encoder/nli-deberta-v3-small",
        description="HuggingFace CrossEncoder model for NLI-based faithfulness scoring",
    )


class APISettings(BaseModel):
    auth_enabled: bool = Field(True, description="Require API key for protected routes")
    api_keys: List[str] = Field(default_factory=list, description="Static API keys (optional)")
    rate_limit_per_minute: int = Field(60, ge=1, le=2000)
    redis_rate_limit_enabled: bool = Field(True, description="Use Redis-backed distributed rate limiting")
    redis_url: str = Field("redis://localhost:6379/0", description="Redis URL for distributed rate limiting")

    def resolved_api_keys(self) -> List[str]:
        if self.api_keys:
            return [k for k in self.api_keys if k]
        from_env = os.getenv("DOC_API_KEYS", "")
        if not from_env.strip():
            return []
        return [x.strip() for x in from_env.split(",") if x.strip()]


class Config(BaseModel):
    chunk_size: int = Field(600, description="Chunk size in tokens")
    overlap: int = Field(100, description="Chunk overlap in tokens")
    chunk_tokenizer: str = Field("gpt2", description="Tokenizer encoding used for ingestion chunking")
    data_dir: str = Field("data", description="Directory for input files")
    output_dir: str = Field("output", description="Directory for processed output")
    log_level: str = Field("INFO", description="Logging level")
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    api: APISettings = Field(default_factory=APISettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)


def provider_api_key_env(provider: str) -> str | None:
    p = provider.strip().lower()
    if p == "openai":
        return "OPENAI_API_KEY"
    if p == "anthropic":
        return "ANTHROPIC_API_KEY"
    if p == "gemini":
        return "GEMINI_API_KEY"
    return None


def load_config(config_path: str = "config.yaml", env: str | None = None) -> Config:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f) or {}

    # Merge environment-specific overrides (e.g. config.dev.yaml)
    resolved_env = env or os.getenv("ENV", "dev")
    base, ext = os.path.splitext(config_path)
    env_config_path = f"{base}.{resolved_env}{ext}"
    if os.path.exists(env_config_path):
        with open(env_config_path, 'r') as f:
            env_overrides = yaml.safe_load(f) or {}
        config_data.update(env_overrides)

    # Override with environment variables (e.g. CHUNK_SIZE=500)
    for field_name, field_info in Config.model_fields.items():
        env_value = os.getenv(field_name.upper())
        if env_value is not None:
            annotation = field_info.annotation
            if annotation is not None:
                config_data[field_name] = annotation(env_value)

    try:
        cfg = Config(**config_data)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")
    if not doc_ollama_runtime_enabled():
        cfg = _strip_ollama_llm_settings(cfg)
    return cfg
