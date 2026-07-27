"""Pydantic models for multi-turn chat API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatCreateBody(BaseModel):
    title: str | None = None
    system_prompt: str | None = None
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    knowledge_scope: str = "vault"


class ChatPatchBody(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    knowledge_scope: str | None = None


class ChatMessageDTO(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    parent_id: uuid.UUID | None = None
    created_at: datetime
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieved: list[dict[str, Any]] = Field(default_factory=list)


class ChatListItemDTO(BaseModel):
    id: uuid.UUID
    title: str | None
    updated_at: datetime
    model: str
    provider: str
    pinned: bool


class ChatDetailDTO(BaseModel):
    id: uuid.UUID
    title: str | None
    pinned: bool
    system_prompt: str | None
    provider: str
    model: str
    knowledge_scope: str
    summary_cache: str | None = None
    messages: list[ChatMessageDTO]


class SendMessageBody(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    scope: str | None = None
    parent_id: uuid.UUID | None = None
    provider_api_key: str | None = None
    grounding_mode: str = "corpus_only"
    include_web_search: bool = False


class EditMessageBody(BaseModel):
    content: str


class SaveToWikiBody(BaseModel):
    title: str | None = None
    include_citations: bool = True
    reingest: bool = True


class SaveToWikiResponse(BaseModel):
    path: str
    ingested: bool = False
    chunk_count: int = 0


class MemoryResponse(BaseModel):
    content: str
    path: str


class MemoryUpdateResponse(BaseModel):
    content: str


class MessageSearchResult(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    role: str
    preview: str
    rank: float
