"""Conversation title generation (LLM with heuristic fallback)."""

from __future__ import annotations

import asyncio

from src.core.llm_provider import LLMProviderRouter
from src.utils.config import LLMSettings


async def generate_title(first_message: str, provider: str, model: str, *, llm: LLMSettings | None = None) -> str:
    """Fallback chain: model title prompt, then first six words."""
    text = (first_message or "").strip()
    if not text:
        return "New chat"
    router = LLMProviderRouter(llm or LLMSettings())
    prompt = (
        "Generate a very short title (max 8 words, no quotes) for a chat that starts with this user message:\n\n"
        f"{text[:500]}\n\nTitle:"
    )
    try:
        sel = router.resolve_selection(provider, model, has_api_key_override=False)
        raw = await asyncio.to_thread(router.generate, sel.provider, sel.model, prompt)
        out = raw.strip().splitlines()[0]
        out = out.strip().strip('"').strip("'")
        if 3 <= len(out) <= 80:
            return out
    except Exception:
        pass
    words = text.split()[:6]
    return " ".join(words) if words else "New chat"
