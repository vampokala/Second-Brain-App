"""FastAPI request/response models."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QueryRequestModel(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    use_llm: bool = True
    use_rerank: bool = True
    stream: bool = False
    include_citations: bool = True
    provider: Optional[str] = None
    model: Optional[str] = None
    reranker_model: Optional[str] = None
    provider_api_key: Optional[str] = None
    session_id: Optional[str] = None
    knowledge_scope: Literal["global", "session", "both"] = "global"


class CitationModel(BaseModel):
    raw_id: str
    chunk_id: str
    resolved: bool
    title: Optional[str] = None
    source: Optional[str] = None
    verification_score: float = 0.0
    verification: str = "unresolved"


class RetrievedChunkModel(BaseModel):
    id: str
    score: float = 0.0
    source: str = "hybrid"
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
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
    validation_issues: List[str] = Field(default_factory=list)
    citations: List[CitationModel] = Field(default_factory=list)
    retrieved: List[RetrievedChunkModel] = Field(default_factory=list)
    truthfulness: Optional[TruthfulnessModel] = None


class HealthModel(BaseModel):
    status: str
    collection: str


class MetricsModel(BaseModel):
    cache_ttl_seconds: int
    available_providers: List[str]


class LLMConfigModel(BaseModel):
    """Public LLM routing options for UI clients (no secrets)."""

    default_provider: str
    default_model_by_provider: Dict[str, str]
    allowed_models_by_provider: Dict[str, List[str]]
    provider_key_configured: Dict[str, bool] = Field(
        default_factory=dict,
        description="Whether server-side API key env vars are configured for each provider",
    )
    demo_mode: bool = Field(
        False,
        description="True when API is running in hosted demo profile",
    )
