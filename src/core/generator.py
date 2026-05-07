"""RAG answer generation via pluggable providers with optional streaming."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Sequence, Union

if TYPE_CHECKING:
    from src.evaluation.truthfulness import TruthfulnessResult

from src.core.context_optimizer import ContextOptimizer, OptimizedContext
from src.core.llm_provider import LLMProviderRouter
from src.core.prompt_manager import PromptManager
from src.core.reranker import RankedResult
from src.core.response_processor import ResponseProcessor
from src.core.retrieval_result import RetrievalResult
from src.utils.config import LLMSettings


@dataclass
class GenerationResult:
    response_text: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    latency_ms: float = 0.0
    streamed: bool = False
    prompt: str = ""
    optimized_context: OptimizedContext | None = None
    provider: str = "ollama"
    # Persisted on cache write so cache hits can return inline scores without re-running NLI.
    truthfulness: Optional["TruthfulnessResult"] = None


@dataclass
class ValidationResult:
    is_valid: bool
    confidence: float
    issues: List[str] = field(default_factory=list)


class RAGGenerator:
    """Build prompt from optimized context and call selected provider."""

    def __init__(
        self,
        model_name: str,
        prompt_manager: PromptManager,
        context_optimizer: ContextOptimizer,
        provider_router: Optional[LLMProviderRouter] = None,
        provider: str = "ollama",
    ) -> None:
        self.model_name = model_name
        self.provider = provider
        self.prompt_manager = prompt_manager
        self.context_optimizer = context_optimizer
        self.response_processor = ResponseProcessor()
        self.provider_router = provider_router or LLMProviderRouter(LLMSettings())

    def _docs_for_citations(
        self,
        optimized: OptimizedContext,
    ) -> List[Dict[str, Any]]:
        return list(optimized.documents)

    def validate_response(self, response: str, context: OptimizedContext) -> ValidationResult:
        issues: List[str] = []
        text = (response or "").strip()
        if len(text) < 15:
            issues.append("response_too_short")
        corpus = " ".join(d.get("text", "") for d in context.documents).lower()
        words = {w for w in text.lower().split() if len(w) > 4}
        src_words = {w for w in corpus.split() if len(w) > 4}
        overlap = len(words & src_words) / max(len(words), 1) if words else 0.0
        if overlap < 0.05 and len(text) > 80:
            issues.append("low_lexical_overlap_with_context")
        confidence = min(1.0, 0.35 + overlap)
        is_valid = len(issues) == 0 or (len(issues) == 1 and "low_lexical_overlap_with_context" in issues)
        return ValidationResult(is_valid=is_valid, confidence=confidence, issues=issues)

    def generate(
        self,
        query: str,
        documents: Sequence[Union[RetrievalResult, RankedResult]],
        stream: bool = False,
        query_type: str = "factual",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        provider_api_key: Optional[str] = None,
    ) -> GenerationResult:
        selected_provider = provider or self.provider
        selected_model = model or self.model_name
        optimized = self.context_optimizer.optimize_context(query, list(documents))
        prompt = self.prompt_manager.build_prompt(query, optimized, query_type=query_type)
        t0 = time.perf_counter()
        if stream:
            parts: List[str] = []
            for piece in self.generate_stream_from_prompt(prompt, provider=selected_provider, model=selected_model):
                parts.append(piece)
            response_text = "".join(parts)
        else:
            response_text = self.provider_router.generate(
                selected_provider,
                selected_model,
                prompt,
                api_key_override=provider_api_key,
            )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        response_text = self.response_processor.format_response(response_text)
        cites = self.response_processor.extract_citations(response_text, self._docs_for_citations(optimized))
        return GenerationResult(
            response_text=response_text,
            citations=cites,
            model_name=selected_model,
            latency_ms=latency_ms,
            streamed=stream,
            prompt=prompt,
            optimized_context=optimized,
            provider=selected_provider,
        )

    def generate_stream_from_prompt(
        self,
        prompt: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        provider_api_key: Optional[str] = None,
    ) -> Iterator[str]:
        selected_provider = provider or self.provider
        selected_model = model or self.model_name
        yield from self.provider_router.stream(
            selected_provider,
            selected_model,
            prompt,
            api_key_override=provider_api_key,
        )

    def generate_stream(
        self,
        query: str,
        documents: Sequence[Union[RetrievalResult, RankedResult]],
        query_type: str = "factual",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        provider_api_key: Optional[str] = None,
    ) -> Iterator[str]:
        optimized = self.context_optimizer.optimize_context(query, list(documents))
        prompt = self.prompt_manager.build_prompt(query, optimized, query_type=query_type)
        yield from self.generate_stream_from_prompt(
            prompt,
            provider=provider,
            model=model,
            provider_api_key=provider_api_key,
        )
