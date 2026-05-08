"""Background conversation summarization."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.llm_provider import LLMProviderRouter
from src.db.models import Chat, Message
from src.utils.config import LLMSettings

logger = logging.getLogger(__name__)


async def maybe_summarize(
    chat_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    provider: str,
    model: str,
    llm: LLMSettings | None = None,
    turn_threshold: int = 5,
) -> None:
    """If unsummarized turns exceed threshold, refresh ``summary_cache`` (never raises)."""
    try:
        async with session_factory() as session:
            ch = await session.get(Chat, chat_id)
            if ch is None:
                return
            cnt = await session.execute(select(func.count()).select_from(Message).where(Message.chat_id == chat_id))
            n = int(cnt.scalar_one() or 0)
            if n < turn_threshold:
                return
            res = await session.execute(
                select(Message.role, Message.content)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.desc())
                .limit(20)
            )
            rows = list(res.all())
            lines = [f"{role}: {(content or '').strip()}" for role, content in reversed(rows)]
            blob = "\n".join(lines)[:8000]
            router = LLMProviderRouter(llm or LLMSettings())
            sel = router.resolve_selection(provider, model, has_api_key_override=False)
            prompt = "Summarize the following dialogue in <= 6 bullet points:\n\n" + blob
            summary = await asyncio.to_thread(router.generate, sel.provider, sel.model, prompt)
            await session.execute(
                update(Chat).where(Chat.id == chat_id).values(summary_cache=summary.strip(), updated_at=func.now())
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("summarize skip chat_id=%s: %s", chat_id, exc)
