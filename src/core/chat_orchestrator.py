"""Multi-turn chat streaming over RAG + Postgres."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, replace
from typing import Any

from src.core.chat_store import ChatStore, NewMessage
from src.core.conversation_summarizer import maybe_summarize
from src.core.rag_orchestrator import QueryRequest, RAGOrchestrator, StreamingQuerySession
from src.utils.config import Config

logger = logging.getLogger(__name__)


@dataclass
class BudgetSplit:
    history: int
    retrieval: int
    generation: int


def allocate_budget(total_tokens: int, history_tokens: int, retrieval_tokens: int) -> BudgetSplit:
    generation_floor = int(total_tokens * 0.15)
    available = total_tokens - generation_floor
    history_actual = min(history_tokens, int(available * 0.4))
    retrieval_actual = min(retrieval_tokens, available - history_actual)
    generation = total_tokens - history_actual - retrieval_actual
    return BudgetSplit(
        history=history_actual,
        retrieval=retrieval_actual,
        generation=max(generation, generation_floor),
    )


def _format_history(
    *,
    summary: str | None,
    messages: list[Any],
    max_chars: int,
) -> str:
    blocks: list[str] = []
    if summary:
        blocks.append(f"Conversation summary:\n{summary.strip()}\n")
    for m in messages:
        label = "User" if m.role == "user" else "Assistant"
        blocks.append(f"{label}: {(m.content or '').strip()}")
    text = "\n".join(blocks).strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


class ChatOrchestrator:
    def __init__(self, cfg: Config, rag: RAGOrchestrator, store: ChatStore) -> None:
        self._cfg = cfg
        self._rag = rag
        self._store = store

    async def stream(
        self,
        chat_id: uuid.UUID,
        user_msg: str,
        *,
        provider: str,
        model: str,
        system_prompt: str | None,
        scope: str,
        provider_api_key: str | None = None,
        parent_id: uuid.UUID | None = None,
        route_llm: Callable[[str, str], tuple[str, str]] | None = None,
        append_user: bool = True,
        anchor_user_message_id: uuid.UUID | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        use_provider, use_model = provider, model
        if route_llm:
            use_provider, use_model = route_llm(provider, model)

        if not append_user and anchor_user_message_id is None:
            yield {"event": "error", "data": {"message": "anchor_user_message_id required"}}
            return

        t0 = time.perf_counter()
        if append_user:
            await self._store.append_message(
                chat_id,
                NewMessage(role="user", content=user_msg, parent_id=parent_id),
            )
        elif anchor_user_message_id is not None:
            await self._store.set_leaf(chat_id, anchor_user_message_id)
        ctx = await self._store.get_chat(chat_id)
        if ctx is None:
            yield {"event": "error", "data": {"message": "chat not found"}}
            return
        msgs = ctx.messages
        if len(msgs) < 1:
            yield {"event": "error", "data": {"message": "empty chat"}}
            return

        prior = msgs[:-1]
        total = self._cfg.context.max_tokens
        hist_chars_est = sum(len((m.content or "")) for m in prior) // 4
        b = allocate_budget(total, hist_chars_est, max(500, total // 2))
        max_hist_chars = max(256, b.history * 4)
        history_block = _format_history(
            summary=ctx.chat.summary_cache,
            messages=prior,
            max_chars=max_hist_chars,
        )
        sys_block = f"{system_prompt.strip()}\n\n" if system_prompt else ""
        full_query = f"{sys_block}{history_block}\n\nUser: {user_msg.strip()}\n\nAssistant:"

        scope_val = "global" if scope in ("vault", "global", "") else scope
        req = QueryRequest(
            query_text=full_query,
            retrieval_query=user_msg.strip(),
            top_k=6,
            use_llm=True,
            use_rerank=True,
            stream=True,
            provider=use_provider,
            model=use_model,
            provider_api_key=provider_api_key,
            include_citations=True,
            knowledge_scope=scope_val,
        )

        step_latencies: dict[str, float] = {}
        with self._rag.observer.trace_request("chat", query=user_msg) as trace:
            docs_for_gen, display_items = self._rag._retrieve_docs_for_query(req, trace, step_latencies)

        chunk_payload: list[dict[str, Any]] = []
        for item in display_items[:16]:
            legacy = item.to_legacy_dict()
            meta = dict(legacy.get("metadata") or {})
            chunk_payload.append(
                {
                    "id": legacy.get("id"),
                    "score": float(legacy.get("score") or 0.0),
                    "source": str(meta.get("relpath") or meta.get("source_path") or ""),
                    "preview": (legacy.get("text") or "")[:240],
                }
            )
        yield {"event": "retrieval", "data": {"chunks": chunk_payload}}

        req_stream = replace(
            req,
            prefetched_retrieval=(docs_for_gen, display_items),
        )

        buf: list[str] = []

        def _gen_stream() -> Any:
            try:
                with StreamingQuerySession(self._rag, req_stream) as sess:
                    for piece in sess.iter_tokens():
                        buf.append(piece)
                    return sess.finalize()
            except Exception as exc:  # noqa: BLE001
                return exc

        final = await asyncio.to_thread(_gen_stream)
        if isinstance(final, BaseException):
            yield {"event": "error", "data": {"message": str(final)}}
            return

        text_acc = "".join(buf)
        step = 32
        for i in range(0, len(text_acc), step):
            yield {"event": "token", "data": {"text": text_acc[i : i + step]}}

        citation_payload: list[dict[str, Any]] = []
        for c in final.citations or []:
            if isinstance(c, dict):
                src = str(c.get("source") or "")
                cid = str(c.get("chunk_id") or c.get("raw_id") or "")
                citation_payload.append(
                    {
                        "chunk_id": cid,
                        "source": src,
                        "title": c.get("title"),
                        "kind": "wiki" if "wiki/" in src else "raw",
                    }
                )

        yield {"event": "citations", "data": {"citations": citation_payload}}

        user_leaf = msgs[-1].id
        asst = await self._store.append_message(
            chat_id,
            NewMessage(
                role="assistant",
                content=text_acc or (final.answer or ""),
                parent_id=user_leaf,
                retrieved=chunk_payload or None,
            ),
        )
        if citation_payload:
            pairs = [
                (
                    str(c.get("chunk_id") or "unknown"),
                    str(c.get("source") or ""),
                    c.get("title") if isinstance(c.get("title"), str) else None,
                    None,
                )
                for c in citation_payload
            ]
            await self._store.add_citations(asst.id, pairs)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        asyncio.create_task(
            maybe_summarize(
                chat_id,
                self._store.session_factory,
                provider=use_provider,
                model=use_model,
                llm=self._cfg.llm,
            )
        )

        yield {
            "event": "final",
            "data": {
                "message_id": str(asst.id),
                "provider": use_provider,
                "model": use_model,
                "elapsed_ms": elapsed_ms,
            },
        }
