"""Pydantic models for vault browse API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileNode(BaseModel):
    name: str
    path: str
    kind: Literal["file", "dir"]
    children: list["FileNode"] = Field(default_factory=list)


class FileTree(BaseModel):
    prefix: str
    nodes: list[FileNode]


class FileContent(BaseModel):
    path: str
    frontmatter: dict[str, Any] | None = None
    body: str
    mtime: float | None = None
    size_bytes: int


class VaultStats(BaseModel):
    file_count: int
    chunk_count: int
    last_ingest_at: str | None = None
    embed_model: str
    vault_path: str = ""
    vault_host_path: str | None = None


class VaultClearBody(BaseModel):
    confirm: Literal["delete"]
    clear_vault: bool = False
    clear_memory: bool = False
    clear_chats: bool = False


class VaultClearTargets(BaseModel):
    vault: bool = False
    memory: bool = False
    chats: bool = False


class VaultClearResponse(BaseModel):
    cleared: VaultClearTargets
    detail: str


FileNode.model_rebuild()
