"""FastAPI request/response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequestModel(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    use_llm: bool = True
    use_rerank: bool = True
    stream: bool = False
    include_citations: bool = True
    provider: str | None = None
    model: str | None = None
    reranker_model: str | None = None
    provider_api_key: str | None = None
    session_id: str | None = None
    knowledge_scope: Literal["global", "session", "both"] = "global"


class CitationModel(BaseModel):
    raw_id: str
    chunk_id: str
    resolved: bool
    title: str | None = None
    source: str | None = None
    verification_score: float = 0.0
    verification: str = "unresolved"


class RetrievedChunkModel(BaseModel):
    id: str
    score: float = 0.0
    source: str = "hybrid"
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    preview: str = ""


class TruthfulnessModel(BaseModel):
    nli_faithfulness: float = 0.0
    citation_groundedness: float = 0.0
    uncited_claims: int = 0
    score: float = 0.0


class QueryResponseModel(BaseModel):
    query: str
    provider: str
    model: str
    answer: str = ""
    processing_time_ms: float = 0.0
    cached: bool = False
    validation_issues: list[str] = Field(default_factory=list)
    citations: list[CitationModel] = Field(default_factory=list)
    retrieved: list[RetrievedChunkModel] = Field(default_factory=list)
    truthfulness: TruthfulnessModel | None = None


class HealthModel(BaseModel):
    status: str
    collection: str
    ollama_available: bool | None = None
    ollama_models: list[str] | None = None


class MetricsModel(BaseModel):
    cache_ttl_seconds: int
    available_providers: list[str]


class LLMConfigModel(BaseModel):
    """Public LLM routing options for UI clients (no secrets)."""

    default_provider: str
    default_model_by_provider: dict[str, str]
    allowed_models_by_provider: dict[str, list[str]]
    provider_key_configured: dict[str, bool] = Field(
        default_factory=dict,
        description="Whether server-side API key env vars are configured for each provider",
    )
    gateway_base_url: str = Field(
        "",
        description="AI Gateway / LiteLLM OpenAI-compatible base URL (no secrets)",
    )
    demo_mode: bool = Field(
        False,
        description="True when API is running in hosted demo profile",
    )
