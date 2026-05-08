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


FileNode.model_rebuild()
