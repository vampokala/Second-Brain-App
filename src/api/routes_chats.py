"""Chat CRUD + SSE message streaming."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from src.api.models_chats import (
    ChatCreateBody,
    ChatDetailDTO,
    ChatListItemDTO,
    ChatMessageDTO,
    ChatPatchBody,
    EditMessageBody,
    MessageSearchResult,
    SendMessageBody,
)
from src.core.chat_orchestrator import ChatOrchestrator
from src.core.chat_store import ChatStore, NewMessage
from src.core.title_generator import generate_title
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


def _store(request: Request) -> ChatStore:
    st = getattr(request.app.state, "chat_store", None)
    if st is None:
        raise HTTPException(status_code=503, detail="Chat store unavailable (DATABASE_URL required).")
    return st


def _orch(request: Request) -> ChatOrchestrator:
    o = getattr(request.app.state, "chat_orchestrator", None)
    if o is None:
        raise HTTPException(status_code=503, detail="Chat orchestrator unavailable.")
    return o


def _route_llm(request: Request):
    def inner(provider: str, model: str) -> tuple[str, str]:
        mon = getattr(request.app.state, "ollama_monitor", None)
        available = getattr(mon, "is_available", True) if mon is not None else True
        if provider == "ollama" and not available:
            from src.utils.config import load_config

            cfg = load_config("config.yaml")
            if cfg.llm.provider_has_key("openai"):
                return "openai", cfg.llm.resolve_model("openai", None)
            if cfg.llm.provider_has_key("anthropic"):
                return "anthropic", cfg.llm.resolve_model("anthropic", None)
            raise ValueError("Ollama unavailable and no cloud API keys configured.")
        return provider, model

    return inner


def _to_detail(ctx: Any) -> ChatDetailDTO:
    cites = ctx.citations_by_message
    msgs: list[ChatMessageDTO] = []
    for m in ctx.messages:
        payload = [
            {
                "chunk_id": c.chunk_id,
                "source": c.source,
                "title": c.title,
                "score": c.score,
            }
            for c in cites.get(m.id, [])
        ]
        msgs.append(
            ChatMessageDTO(
                id=m.id,
                role=m.role,
                content=m.content or "",
                parent_id=m.parent_id,
                created_at=m.created_at,
                citations=payload,
                retrieved=list(m.retrieved or []),
            )
        )
    c = ctx.chat
    return ChatDetailDTO(
        id=c.id,
        title=c.title,
        pinned=c.pinned,
        system_prompt=c.system_prompt,
        provider=c.provider,
        model=c.model,
        knowledge_scope=c.knowledge_scope,
        summary_cache=c.summary_cache,
        messages=msgs,
    )


@router.get("/search", response_model=list[MessageSearchResult])
async def search_messages(q: str, request: Request, limit: int = 50) -> list[MessageSearchResult]:
    hits = await _store(request).search(q, limit=limit)
    return [
        MessageSearchResult(
            message_id=h.message_id,
            chat_id=h.chat_id,
            role=h.role,
            preview=h.content_preview,
            rank=h.rank,
        )
        for h in hits
    ]


@router.get("", response_model=list[ChatListItemDTO])
async def list_chats(request: Request, limit: int = 50) -> list[ChatListItemDTO]:
    rows = await _store(request).list_chats(limit=limit)
    return [
        ChatListItemDTO(
            id=c.id,
            title=c.title,
            updated_at=c.updated_at,
            model=c.model,
            provider=c.provider,
            pinned=c.pinned,
        )
        for c in rows
    ]


@router.post("", response_model=ChatDetailDTO)
async def create_chat(body: ChatCreateBody, request: Request) -> ChatDetailDTO:
    ch = await _store(request).create_chat(
        title=body.title,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        scope=body.knowledge_scope,
    )
    ctx = await _store(request).get_chat(ch.id)
    assert ctx is not None
    return _to_detail(ctx)


@router.get("/{chat_id}", response_model=ChatDetailDTO)
async def get_chat(chat_id: uuid.UUID, request: Request) -> ChatDetailDTO:
    ctx = await _store(request).get_chat(chat_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _to_detail(ctx)


@router.patch("/{chat_id}", response_model=ChatDetailDTO)
async def patch_chat(chat_id: uuid.UUID, body: ChatPatchBody, request: Request) -> ChatDetailDTO:
    data = body.model_dump(exclude_none=True)
    ch = await _store(request).update_chat(chat_id, **data)
    if ch is None:
        raise HTTPException(status_code=404, detail="Not found")
    ctx = await _store(request).get_chat(chat_id)
    assert ctx is not None
    return _to_detail(ctx)


@router.delete("/{chat_id}")
async def delete_chat(chat_id: uuid.UUID, request: Request) -> dict[str, str]:
    await _store(request).delete_chat(chat_id)
    return {"status": "ok"}


@router.post("/{chat_id}/messages")
async def post_message(chat_id: uuid.UUID, body: SendMessageBody, request: Request) -> EventSourceResponse:
    store = _store(request)
    orch = _orch(request)
    ch = await store.get_chat(chat_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Not found")
    chat_row = ch.chat
    provider = body.provider or chat_row.provider
    model = body.model or chat_row.model
    scope = body.scope or chat_row.knowledge_scope
    system_prompt = body.system_prompt if body.system_prompt is not None else chat_row.system_prompt

    async def gen():
        first_user = len(ch.messages) == 0
        try:
            async for evt in orch.stream(
                chat_id,
                body.message,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                scope=scope,
                provider_api_key=body.provider_api_key,
                parent_id=body.parent_id,
                route_llm=_route_llm(request),
            ):
                yield {"event": evt["event"], "data": json.dumps(evt["data"])}
            if first_user:
                title = await generate_title(body.message, provider, model)
                await store.update_chat(chat_id, title=title)
        except Exception as exc:
            logger.exception("chat stream failed")
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(gen())


@router.post("/{chat_id}/messages/{message_id}/regenerate")
async def regenerate(chat_id: uuid.UUID, message_id: uuid.UUID, request: Request) -> EventSourceResponse:
    store = _store(request)
    orch = _orch(request)
    ctx = await store.get_chat(chat_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Not found")
    m = await store.get_message(message_id)
    if m is None or m.chat_id != chat_id or m.role != "assistant":
        raise HTTPException(status_code=400, detail="Not an assistant message")
    user_id = m.parent_id
    if user_id is None:
        raise HTTPException(status_code=400, detail="Orphan assistant message")
    user_m = await store.get_message(user_id)
    if user_m is None:
        raise HTTPException(status_code=400, detail="Parent missing")
    await store.delete_message(message_id)
    await store.set_leaf(chat_id, user_id)

    chat_row = ctx.chat

    async def gen():
        try:
            async for evt in orch.stream(
                chat_id,
                user_m.content or "",
                provider=chat_row.provider,
                model=chat_row.model,
                system_prompt=chat_row.system_prompt,
                scope=chat_row.knowledge_scope,
                provider_api_key=None,
                route_llm=_route_llm(request),
                append_user=False,
                anchor_user_message_id=user_id,
            ):
                yield {"event": evt["event"], "data": json.dumps(evt["data"])}
        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(gen())


@router.post("/{chat_id}/messages/{message_id}/edit")
async def edit_fork(
    chat_id: uuid.UUID, message_id: uuid.UUID, body: EditMessageBody, request: Request
) -> EventSourceResponse:
    store = _store(request)
    orch = _orch(request)
    m = await store.get_message(message_id)
    if m is None or m.chat_id != chat_id or m.role != "user":
        raise HTTPException(status_code=400, detail="Not a user message")
    new_m = await store.append_message(
        chat_id,
        NewMessage(role="user", content=body.content, parent_id=m.parent_id),
    )
    ctx = await store.get_chat(chat_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Not found")
    chat_row = ctx.chat

    async def gen():
        try:
            async for evt in orch.stream(
                chat_id,
                body.content,
                provider=chat_row.provider,
                model=chat_row.model,
                system_prompt=chat_row.system_prompt,
                scope=chat_row.knowledge_scope,
                provider_api_key=None,
                route_llm=_route_llm(request),
                append_user=False,
                anchor_user_message_id=new_m.id,
            ):
                yield {"event": evt["event"], "data": json.dumps(evt["data"])}
        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(gen())
