"""Template-based RAG prompts with optional filesystem overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml
from src.core.context_optimizer import OptimizedContext
from src.core.query_processor import QueryIntent

FACTUAL_TEMPLATE = """You are a helpful assistant that answers questions based on provided documents.
Always cite your sources and be precise in your answers.

Context Documents:
{context}

Question: {query}

Instructions:
- Answer based only on the provided context
- Include citations in [Doc chunk_id] format using the bracketed ids shown in the context (e.g. [Doc my-chunk-id])
- If information is not in the context, say so clearly
- Be concise but comprehensive

Answer:
"""

EXPLORATORY_TEMPLATE = """You are a knowledgeable assistant helping explore a topic using provided documents.
Provide a thoughtful analysis while staying grounded in the sources.

Context Documents:
{context}

Question: {query}

Instructions:
- Synthesize information from multiple sources when relevant
- Highlight different perspectives if they exist
- Use citations to support key points
- Suggest follow-up questions if appropriate

Analysis:
"""

DEFAULT_TEMPLATE = FACTUAL_TEMPLATE


def _format_context(ctx: OptimizedContext) -> str:
    parts = []
    for doc in ctx.documents:
        did = doc.get("id", "")
        text = doc.get("text", "")
        parts.append(f"[Doc {did}]\n{text}")
    return "\n\n---\n\n".join(parts)


class PromptManager:
    """Build user prompts from templates; optional YAML overrides under template_path."""

    def __init__(self, template_path: str | Path | None = None) -> None:
        self.template_path = Path(template_path) if template_path else Path("config/prompts")
        self.templates: Dict[str, str] = {
            "factual": FACTUAL_TEMPLATE,
            "exploratory": EXPLORATORY_TEMPLATE,
            "default": DEFAULT_TEMPLATE,
        }
        self._load_dir_templates()

    def _load_dir_templates(self) -> None:
        root = self.template_path
        if not root.is_dir():
            return
        for name in ("factual", "exploratory", "default"):
            p = root / f"{name}.yaml"
            if p.is_file():
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    body = data.get("template")
                    if isinstance(body, str):
                        self.templates[name] = body

    @staticmethod
    def intent_to_query_type(intent: QueryIntent) -> str:
        if intent is QueryIntent.EXPLORATORY or intent is QueryIntent.COMPARATIVE:
            return "exploratory"
        return "factual"

    def get_system_prompt(self, query_type: str) -> str:
        """Short system line for chat APIs that support a system role."""
        if query_type == "exploratory":
            return (
                "You are a careful analyst. Ground every claim in the provided context "
                "and cite chunk ids in [Doc id] form."
            )
        return (
            "You are a precise assistant. Answer only from the provided context and "
            "cite chunk ids in [Doc id] form."
        )

    def build_prompt(self, query: str, context: OptimizedContext, query_type: str = "factual") -> str:
        tpl = self.templates.get(query_type) or self.templates["default"]
        ctx_block = _format_context(context)
        return tpl.format(context=ctx_block, query=query)
