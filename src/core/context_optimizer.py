"""Token-budget context packing for RAG prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Union

from src.core.reranker import RankedResult
from src.core.retrieval_result import RetrievalResult
from transformers import AutoTokenizer


@dataclass
class OptimizedContext:
    """Chunks selected to fit within a token budget."""

    documents: List[Dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    was_truncated: bool = False
    dropped_count: int = 0


def _unwrap_chunk(
    item: Union[RetrievalResult, RankedResult, Dict[str, Any]],
) -> RetrievalResult:
    if isinstance(item, RankedResult):
        return item.result
    if isinstance(item, RetrievalResult):
        return item
    # legacy dict from to_legacy_dict
    return RetrievalResult(
        id=str(item["id"]),
        text=str(item["text"]),
        metadata=dict(item.get("metadata") or {}),
        fusion_score=float(item.get("score") or 0.0),
        sources=list(item.get("sources") or []),
        confidence=float(item.get("confidence") or 0.0),
    )


class ContextOptimizer:
    """Pack retrieved chunks into a prompt-sized context using a HF tokenizer."""

    def __init__(self, max_context_tokens: int = 4000, tokenizer_name: str = "gpt2") -> None:
        self.max_context_tokens = max_context_tokens
        self.tokenizer_name = tokenizer_name
        self._tokenizer = None

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
        return self._tokenizer

    def _count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def compress_document(self, text: str, max_tokens: int) -> str:
        """Word-split truncation to max_tokens with a short trailer."""
        if max_tokens <= 0:
            return ""
        words = text.split()
        low, high = 0, len(words)
        best = ""
        while low <= high:
            mid = (low + high) // 2
            candidate = " ".join(words[:mid])
            if self._count(candidate) <= max_tokens:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        if not best.strip():
            return self.tokenizer.decode(self.tokenizer.encode(text, add_special_tokens=False)[:max_tokens])  # type: ignore[no-any-return]
        trailer = "\n\n[... truncated for context length ...]"
        if self._count(best + trailer) > max_tokens:
            return best
        return best + trailer

    def optimize_context(
        self,
        query: str,
        documents: Sequence[Union[RetrievalResult, RankedResult, Dict[str, Any]]],
    ) -> OptimizedContext:
        """Greedily add highest-priority chunks until the token budget is exhausted."""
        if not documents:
            return OptimizedContext(documents=[], total_tokens=self._count(query), was_truncated=False, dropped_count=0)

        # Preserve incoming order as priority (caller should pass reranked order)
        wrapped: List[RetrievalResult] = [_unwrap_chunk(d) for d in documents]
        total_dropped = 0
        selected: List[Dict[str, Any]] = []
        used = self._count(query)

        for doc in wrapped:
            block = f"[{doc.id}]\n{doc.text}"
            block_tokens = self._count(block)
            remaining = self.max_context_tokens - used
            if block_tokens <= remaining:
                entry: Dict[str, Any] = {
                    "id": doc.id,
                    "text": doc.text,
                    "metadata": doc.metadata,
                    "fusion_score": doc.fusion_score,
                }
                selected.append(entry)
                used += block_tokens
                continue

            if remaining > 64:
                bracket_prefix = f"[{doc.id}]\n"
                max_for_compress = max(remaining - self._count(bracket_prefix), 32)
                compressed = self.compress_document(doc.text, max_tokens=max_for_compress)
                block2 = f"[{doc.id}]\n{compressed}"
                if self._count(block2) <= self.max_context_tokens - used:
                    selected.append(
                        {
                            "id": doc.id,
                            "text": compressed,
                            "metadata": doc.metadata,
                            "fusion_score": doc.fusion_score,
                            "was_compressed": True,
                        }
                    )
                    used += self._count(block2)
                    continue

            total_dropped += 1

        was_truncated = total_dropped > 0 or any(d.get("was_compressed") for d in selected)
        return OptimizedContext(
            documents=selected,
            total_tokens=used,
            was_truncated=was_truncated,
            dropped_count=total_dropped,
        )
