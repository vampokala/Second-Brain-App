import re
from dataclasses import dataclass
from enum import Enum
from typing import List


class QueryIntent(Enum):
    FACTUAL = "factual"
    EXPLORATORY = "exploratory"
    COMPARATIVE = "comparative"


@dataclass
class ProcessedQuery:
    original: str
    normalized: str
    tokens: List[str]
    expanded_terms: List[str]
    intent: QueryIntent
    is_complex: bool

    @property
    def all_terms(self) -> List[str]:
        return list(dict.fromkeys(self.tokens + self.expanded_terms))


_STOP_WORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "with", "this", "that", "are", "was",
    "be", "has", "have", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "shall",
}

_FACTUAL_SIGNALS = {"what", "who", "when", "where", "which", "how many", "define", "list"}
_EXPLORATORY_SIGNALS = {"why", "how", "explain", "describe", "discuss", "compare", "analyze"}
_COMPARATIVE_SIGNALS = {"vs", "versus", "compare", "difference", "between", "better"}

_SYNONYMS: dict[str, List[str]] = {
    "use": ["utilize", "apply"],
    "build": ["construct", "create", "develop"],
    "fast": ["quick", "rapid", "efficient"],
    "error": ["bug", "issue", "fault", "exception"],
    "document": ["file", "record", "text"],
    "search": ["find", "retrieve", "query", "lookup"],
    "large": ["big", "huge", "extensive"],
    "small": ["tiny", "minimal", "compact"],
    "data": ["information", "records"],
    "model": ["system", "approach"],
    "index": ["catalog", "registry"],
}


class QueryProcessor:
    def process(self, query: str) -> ProcessedQuery:
        normalized = self.normalize(query)
        tokens = self._tokenize(normalized)
        expanded = self._expand(tokens)
        intent = self._detect_intent(query)
        is_complex = len(tokens) > 8 or "and" in query.lower() or "or" in query.lower()

        return ProcessedQuery(
            original=query,
            normalized=normalized,
            tokens=tokens,
            expanded_terms=expanded,
            intent=intent,
            is_complex=is_complex,
        )

    def process_query(self, query: str) -> ProcessedQuery:
        """Alias for :meth:`process` (Phase 2 spec naming)."""
        return self.process(query)

    def normalize_text(self, text: str) -> str:
        """Alias for :meth:`normalize` (Phase 2 spec naming)."""
        return self.normalize(text)

    def expand_query(self, query: str) -> List[str]:
        """Return synonym expansions for tokenized query (excludes original tokens)."""
        normalized = self.normalize(query)
        tokens = self._tokenize(normalized)
        return self._expand(tokens)

    def detect_intent(self, query: str) -> QueryIntent:
        return self._detect_intent(query)

    def normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _tokenize(self, text: str) -> List[str]:
        return [w for w in text.split() if w not in _STOP_WORDS and len(w) > 1]

    def _expand(self, tokens: List[str]) -> List[str]:
        extra: List[str] = []
        for token in tokens:
            extra.extend(_SYNONYMS.get(token, []))
        return extra

    def _detect_intent(self, query: str) -> QueryIntent:
        lower = query.lower()
        if any(sig in lower for sig in _COMPARATIVE_SIGNALS):
            return QueryIntent.COMPARATIVE
        if any(lower.startswith(sig) or f" {sig} " in lower for sig in _EXPLORATORY_SIGNALS):
            return QueryIntent.EXPLORATORY
        return QueryIntent.FACTUAL
