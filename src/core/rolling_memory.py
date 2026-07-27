"""Rolling personal memory file under vault/context/memory.md."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.chat_store import ChatStore

logger = logging.getLogger(__name__)

_ROLLUP_SYSTEM = (
    "You maintain a short personal memory file for a knowledge-base assistant. "
    "Extract stable facts, goals, preferences, and entities. Output markdown only, "
    "at most 120 lines. Prefer durable facts over ephemeral chat chatter."
)


def memory_path(vault_path: Path) -> Path:
    return vault_path.resolve() / "context" / "memory.md"


def load_memory_excerpt(vault_path: Path, max_chars: int = 4000) -> str:
    path = memory_path(vault_path)
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


async def write_memory(vault_path: Path, text: str) -> None:
    path = memory_path(vault_path)
    body = (text or "").strip() + "\n"

    def _atomic() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)

    await asyncio.to_thread(_atomic)


def _format_turns(messages: list[Any], limit: int = 24) -> str:
    recent = messages[-limit:]
    lines: list[str] = []
    for m in recent:
        role = getattr(m, "role", "user")
        content = (getattr(m, "content", None) or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def _complete_rollup(
    *,
    previous: str,
    transcript: str,
    provider: str,
    model: str,
    llm_cfg: Any,
) -> str:
    from src.core.llm_provider import LLMProviderRouter

    router = LLMProviderRouter(llm_cfg)
    sel = router.resolve_selection(provider, model, has_api_key_override=False)
    prompt = (
        f"{_ROLLUP_SYSTEM}\n\n"
        f"Previous memory:\n{previous or '(empty)'}\n\n"
        f"New conversation excerpt:\n{transcript}\n\n"
        "Write the updated memory markdown file body."
    )
    result = await asyncio.to_thread(router.generate, sel.provider, sel.model, prompt)
    text = (result or "").strip() if isinstance(result, str) else str(result or "").strip()
    return text or previous


async def roll_up_from_chat(
    chat_id: uuid.UUID,
    store: ChatStore,
    *,
    provider: str,
    model: str,
    vault_path: Path,
    llm_cfg: Any,
) -> str:
    ctx = await store.get_chat(chat_id)
    if ctx is None:
        raise ValueError(f"chat not found: {chat_id}")
    previous = load_memory_excerpt(vault_path, max_chars=8000)
    transcript = _format_turns(ctx.messages)
    if not transcript.strip():
        return previous
    updated = await _complete_rollup(
        previous=previous,
        transcript=transcript,
        provider=provider,
        model=model,
        llm_cfg=llm_cfg,
    )
    await write_memory(vault_path, updated)
    logger.info("rolling_memory_updated chat_id=%s chars=%s", chat_id, len(updated))
    return updated


async def roll_up_from_text(
    *,
    content: str,
    vault_path: Path,
    provider: str,
    model: str,
    llm_cfg: Any,
) -> str:
    previous = load_memory_excerpt(vault_path, max_chars=8000)
    body = (content or "").strip()
    if not body:
        return previous
    updated = await _complete_rollup(
        previous=previous,
        transcript=body,
        provider=provider,
        model=model,
        llm_cfg=llm_cfg,
    )
    await write_memory(vault_path, updated)
    return updated
