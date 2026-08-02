"""Multi-turn chat streaming over RAG + Postgres."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.core.chat_store import ChatStore, NewMessage
from src.core.conversation_summarizer import maybe_summarize
from src.core.personas import (
    build_persona_system_section,
    join_nonempty,
    persona_addon_applied,
    persona_display,
)
from src.core.prompt_modes import mode_instructions
from src.core.rag_orchestrator import QueryRequest, RAGOrchestrator, StreamingQuerySession
from src.core.rolling_memory import load_memory_excerpt
from src.core.web_search import WebPack, search_and_fetch
from src.utils.config import Config

logger = logging.getLogger(__name__)


@dataclass
class BudgetSplit:
    history: int
    retrieval: int
    generation: int


@dataclass(frozen=True)
class ChatPersonaPrefs:
    persona_id: str = "wiki_maintainer"
    student_grade: str = "9"
    addon: str | None = None
    rolling_memory_enabled: bool = True


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


def _format_history(*, summary: str | None, messages: list[Any], max_chars: int) -> str:
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


def _chunk_payload(display_items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in display_items[:16]:
        legacy = item.to_legacy_dict()
        meta = dict(legacy.get("metadata") or {})
        source = str(meta.get("relpath") or meta.get("source_path") or "")
        title = meta.get("title") or meta.get("heading")
        out.append(
            {
                "id": legacy.get("id"),
                "score": float(legacy.get("score") or 0.0),
                "source": source,
                "preview": (legacy.get("text") or "")[:240],
                "title": title if isinstance(title, str) else None,
                "kind": "wiki" if "wiki/" in source else "raw",
            }
        )
    return out


def _citation_payload(citations: list[Any] | None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for c in citations or []:
        if not isinstance(c, dict):
            continue
        src = str(c.get("source") or "")
        cid = str(c.get("chunk_id") or c.get("raw_id") or "")
        payload.append(
            {
                "chunk_id": cid,
                "source": src,
                "title": c.get("title"),
                "kind": "wiki" if "wiki/" in src else "raw",
            }
        )
    return payload


def _truthfulness_dict(final: Any) -> dict[str, Any] | None:
    tf = getattr(final, "truthfulness", None)
    if tf is None:
        return None
    to_dict = getattr(tf, "to_dict", None)
    return to_dict() if callable(to_dict) else None


def _compose_system(
    *,
    persona: ChatPersonaPrefs,
    system_prompt: str | None,
    grounding_mode: str,
    include_web: bool,
    hit_count: int,
    has_web: bool,
    memory_excerpt: str,
    web_markdown: str,
) -> str | None:
    persona_block = build_persona_system_section(
        persona_id=persona.persona_id,
        student_grade=persona.student_grade,
        addon=persona.addon,
    )
    mode = mode_instructions(grounding_mode, include_web, hit_count, has_web)
    memory_block = f"### Rolling memory\n{memory_excerpt}\n" if memory_excerpt else None
    return join_nonempty(persona_block, mode, memory_block, web_markdown or None, system_prompt)


def _should_skip_corpus(grounding_mode: str) -> bool:
    return grounding_mode == "allow_general"


class ChatOrchestrator:
    def __init__(
        self,
        cfg: Config,
        rag: RAGOrchestrator,
        store: ChatStore,
        *,
        vault_path: Path | None = None,
    ) -> None:
        self._cfg = cfg
        self._rag = rag
        self._store = store
        self._vault_path = vault_path

    def _memory_excerpt(self, prefs: ChatPersonaPrefs) -> str:
        if not prefs.rolling_memory_enabled or self._vault_path is None:
            return ""
        return load_memory_excerpt(self._vault_path)

    def _history_block(self, ctx: Any, msgs: list[Any]) -> str:
        prior = msgs[:-1]
        total = self._cfg.context.max_tokens
        hist_chars_est = sum(len(m.content or "") for m in prior) // 4
        budget = allocate_budget(total, hist_chars_est, max(500, total // 2))
        return _format_history(
            summary=ctx.chat.summary_cache,
            messages=prior,
            max_chars=max(256, budget.history * 4),
        )

    def _build_full_query(
        self,
        *,
        prefs: ChatPersonaPrefs,
        system_prompt: str | None,
        grounding_mode: str,
        include_web: bool,
        hit_count: int,
        web_pack: WebPack,
        history_block: str,
        memory_excerpt: str,
        user_msg: str,
    ) -> str:
        composed = _compose_system(
            persona=prefs,
            system_prompt=system_prompt,
            grounding_mode=grounding_mode,
            include_web=include_web,
            hit_count=hit_count,
            has_web=web_pack.pages_fetched > 0,
            memory_excerpt=memory_excerpt,
            web_markdown=web_pack.context_markdown,
        )
        sys_block = f"{composed.strip()}\n\n" if composed else ""
        return f"{sys_block}{history_block}\n\nUser: {user_msg.strip()}\n\nAssistant:"

    def _make_request(
        self,
        *,
        full_query: str,
        user_msg: str,
        provider: str,
        model: str,
        provider_api_key: str | None,
        scope: str,
        skip_corpus: bool,
        docs_for_gen: list[Any],
        display_items: list[Any],
    ) -> QueryRequest:
        scope_val = "global" if scope in ("vault", "global", "") else scope
        prefetch = ([], []) if skip_corpus else None
        if not skip_corpus and docs_for_gen is not None and display_items is not None:
            prefetch = None
        return QueryRequest(
            query_text=full_query,
            retrieval_query=user_msg.strip(),
            top_k=6,
            use_llm=True,
            use_rerank=not skip_corpus,
            stream=True,
            provider=provider,
            model=model,
            provider_api_key=provider_api_key,
            include_citations=True,
            knowledge_scope=scope_val,
            skip_retrieval=skip_corpus,
            prefetched_retrieval=([], []) if skip_corpus else prefetch,
        )

    def _retrieve(
        self,
        req: QueryRequest,
        user_msg: str,
    ) -> tuple[list[Any], list[Any], list[dict[str, Any]]]:
        step_latencies: dict[str, float] = {}
        with self._rag.observer.trace_request("chat", query=user_msg) as trace:
            docs_for_gen, display_items = self._rag._retrieve_docs_for_query(req, trace, step_latencies)
        return docs_for_gen, display_items, _chunk_payload(display_items)

    async def _prepare_user_turn(
        self,
        chat_id: uuid.UUID,
        user_msg: str,
        *,
        append_user: bool,
        parent_id: uuid.UUID | None,
        anchor_user_message_id: uuid.UUID | None,
    ) -> Any | dict[str, Any]:
        if append_user:
            await self._store.append_message(
                chat_id,
                NewMessage(role="user", content=user_msg, parent_id=parent_id),
            )
        elif anchor_user_message_id is not None:
            await self._store.set_leaf(chat_id, anchor_user_message_id)
        ctx = await self._store.get_chat(chat_id)
        if ctx is None:
            return {"event": "error", "data": {"message": "chat not found"}}
        if len(ctx.messages) < 1:
            return {"event": "error", "data": {"message": "empty chat"}}
        return ctx

    async def _run_generation(self, req: QueryRequest) -> Any:
        buf: list[str] = []

        def _gen_stream() -> Any:
            try:
                with StreamingQuerySession(self._rag, req) as sess:
                    for piece in sess.iter_tokens():
                        buf.append(piece)
                    return sess.finalize(), "".join(buf)
            except Exception as exc:
                return exc

        return await asyncio.to_thread(_gen_stream)

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
        grounding_mode: str = "corpus_only",
        include_web_search: bool = False,
        persona: ChatPersonaPrefs | None = None,
        brave_api_key: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        prefs = persona or ChatPersonaPrefs()
        use_provider, use_model = provider, model
        if route_llm:
            use_provider, use_model = route_llm(provider, model)

        early = self._early_error(append_user, anchor_user_message_id, include_web_search, brave_api_key)
        if early:
            yield early
            return

        t0 = time.perf_counter()
        prepared = await self._prepare_user_turn(
            chat_id,
            user_msg,
            append_user=append_user,
            parent_id=parent_id,
            anchor_user_message_id=anchor_user_message_id,
        )
        if isinstance(prepared, dict):
            yield prepared
            return

        ctx = prepared
        msgs = ctx.messages
        async for evt in self._stream_body(
            chat_id=chat_id,
            user_msg=user_msg,
            ctx=ctx,
            msgs=msgs,
            prefs=prefs,
            system_prompt=system_prompt,
            scope=scope,
            grounding_mode=grounding_mode,
            include_web_search=include_web_search,
            brave_api_key=brave_api_key,
            use_provider=use_provider,
            use_model=use_model,
            provider_api_key=provider_api_key,
            t0=t0,
        ):
            yield evt

    def _early_error(
        self,
        append_user: bool,
        anchor_user_message_id: uuid.UUID | None,
        include_web_search: bool,
        brave_api_key: str | None,
    ) -> dict[str, Any] | None:
        if not append_user and anchor_user_message_id is None:
            return {"event": "error", "data": {"message": "anchor_user_message_id required"}}
        if include_web_search and not (brave_api_key or "").strip():
            return {
                "event": "error",
                "data": {"message": "Web search requires brave_search_api_key in Settings."},
            }
        return None

    async def _stream_body(
        self,
        *,
        chat_id: uuid.UUID,
        user_msg: str,
        ctx: Any,
        msgs: list[Any],
        prefs: ChatPersonaPrefs,
        system_prompt: str | None,
        scope: str,
        grounding_mode: str,
        include_web_search: bool,
        brave_api_key: str | None,
        use_provider: str,
        use_model: str,
        provider_api_key: str | None,
        t0: float,
    ) -> AsyncIterator[dict[str, Any]]:
        web_pack = WebPack(pages_fetched=0, context_markdown="")
        if include_web_search:
            web_pack = await search_and_fetch(user_msg.strip(), api_key=brave_api_key or "")

        skip_corpus = _should_skip_corpus(grounding_mode)
        history_block = self._history_block(ctx, msgs)
        memory_excerpt = self._memory_excerpt(prefs)

        docs_for_gen: list[Any] = []
        display_items: list[Any] = []
        chunk_payload: list[dict[str, Any]] = []

        if not skip_corpus:
            probe_query = self._build_full_query(
                prefs=prefs,
                system_prompt=system_prompt,
                grounding_mode=grounding_mode,
                include_web=include_web_search,
                hit_count=0,
                web_pack=web_pack,
                history_block=history_block,
                memory_excerpt=memory_excerpt,
                user_msg=user_msg,
            )
            probe = self._make_request(
                full_query=probe_query,
                user_msg=user_msg,
                provider=use_provider,
                model=use_model,
                provider_api_key=provider_api_key,
                scope=scope,
                skip_corpus=False,
                docs_for_gen=[],
                display_items=[],
            )
            docs_for_gen, display_items, chunk_payload = self._retrieve(probe, user_msg)

        full_query = self._build_full_query(
            prefs=prefs,
            system_prompt=system_prompt,
            grounding_mode=grounding_mode,
            include_web=include_web_search,
            hit_count=len(chunk_payload),
            web_pack=web_pack,
            history_block=history_block,
            memory_excerpt=memory_excerpt,
            user_msg=user_msg,
        )
        req = self._make_request(
            full_query=full_query,
            user_msg=user_msg,
            provider=use_provider,
            model=use_model,
            provider_api_key=provider_api_key,
            scope=scope,
            skip_corpus=skip_corpus,
            docs_for_gen=docs_for_gen,
            display_items=display_items,
        )
        req_stream = replace(req, prefetched_retrieval=(docs_for_gen, display_items))

        yield {
            "event": "meta",
            "data": {
                "grounding_mode": grounding_mode,
                "include_web_search": include_web_search,
                "hit_count": len(chunk_payload),
                "max_score": max((c["score"] for c in chunk_payload), default=None),
                "web_pages_fetched": web_pack.pages_fetched,
                "persona_display": persona_display(
                    persona_id=prefs.persona_id,
                    student_grade=prefs.student_grade,
                ),
                "persona_addon_applied": persona_addon_applied(prefs.addon),
                "brave_key_configured": bool((brave_api_key or "").strip()),
            },
        }
        yield {"event": "retrieval", "data": {"chunks": chunk_payload}}

        gen_result = await self._run_generation(req_stream)
        if isinstance(gen_result, BaseException):
            yield {"event": "error", "data": {"message": str(gen_result)}}
            return

        final, text_acc = gen_result
        for i in range(0, len(text_acc), 32):
            yield {"event": "token", "data": {"text": text_acc[i : i + 32]}}

        citation_payload = _citation_payload(final.citations)
        yield {"event": "citations", "data": {"citations": citation_payload}}

        asst = await self._persist_assistant(chat_id, msgs[-1].id, text_acc, final, chunk_payload, citation_payload)
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
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "citation_count": len(citation_payload),
                "retrieved_count": len(chunk_payload),
                "truthfulness": _truthfulness_dict(final),
            },
        }

    async def _persist_assistant(
        self,
        chat_id: uuid.UUID,
        user_leaf: uuid.UUID,
        text_acc: str,
        final: Any,
        chunk_payload: list[dict[str, Any]],
        citation_payload: list[dict[str, Any]],
    ) -> Any:
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
        return asst
