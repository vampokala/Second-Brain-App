"""Vault file browser API (cache-backed + safe filesystem reads)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import frontmatter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.models_vault import FileContent, FileNode, FileTree, VaultStats
from src.db.models import DocumentChunk, IngestEvent, VaultFile
from src.db.session import get_async_session
from src.utils.sb_env import SecondBrainSettings, load_second_brain_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])

_SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".html"}


def _require_settings() -> SecondBrainSettings:
    if not os.getenv("DATABASE_URL", "").strip():
        raise HTTPException(
            status_code=503,
            detail="Vault browser requires DATABASE_URL (Postgres).",
        )
    return load_second_brain_settings()


def _resolve_safe(vault: Path, rel: str) -> Path:
    vault_r = vault.resolve()
    rel_norm = rel.replace("\\", "/").lstrip("/")
    candidate = (vault_r / rel_norm).resolve()
    try:
        candidate.relative_to(vault_r)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal rejected") from None
    return candidate


def _strip_prefix(full: str, prefix: str) -> str:
    pfx = prefix.replace("\\", "/").rstrip("/")
    f = full.replace("\\", "/").lstrip("/")
    if not pfx:
        return f
    if f == pfx:
        return ""
    if f.startswith(pfx + "/"):
        return f[len(pfx) + 1 :]
    return ""


def _build_tree(paths: list[str], prefix: str, max_depth: int) -> list[FileNode]:
    pfx = prefix.replace("\\", "/").rstrip("/")
    trie: dict[str, dict[str, Any]] = {}

    for full in paths:
        rel = _strip_prefix(full, pfx)
        if not rel:
            continue
        parts = rel.split("/")[:max_depth]
        cur = trie
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            is_file = is_last and "." in part
            if part not in cur:
                cur[part] = {"children": {}, "file": False}
            if is_file:
                cur[part]["file"] = True
            cur = cur[part]["children"]

    def emit(path_so_far: str, sub: dict[str, Any]) -> list[FileNode]:
        out: list[FileNode] = []
        for name in sorted(sub.keys()):
            meta = sub[name]
            children_trie = meta["children"]
            is_file = bool(meta["file"])
            path = f"{path_so_far}/{name}".replace("//", "/").strip("/") if path_so_far else name
            full_path = f"{pfx}/{path}".replace("//", "/").strip("/") if pfx else path
            if children_trie:
                ch = emit(path, children_trie)
                if ch:
                    out.append(FileNode(name=name, path=full_path, kind="dir", children=ch))
                elif is_file:
                    out.append(FileNode(name=name, path=full_path, kind="file", children=[]))
                else:
                    out.append(FileNode(name=name, path=full_path, kind="dir", children=[]))
            elif is_file:
                out.append(FileNode(name=name, path=full_path, kind="file", children=[]))
            else:
                out.append(FileNode(name=name, path=full_path, kind="dir", children=[]))
        return out

    return emit("", trie)


async def _refresh_vault_rows(
    session: AsyncSession, vault: Path, base_pref: str, filter_q: str | None, limit: int
) -> None:
    root = vault / base_pref if base_pref else vault
    if not root.is_dir():
        return
    seen: int = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if seen >= limit:
                break
            ext = Path(fn).suffix.lower()
            if ext not in _SUPPORTED:
                continue
            abs_p = Path(dirpath) / fn
            try:
                rel = str(abs_p.relative_to(vault)).replace("\\", "/")
            except ValueError:
                continue
            if filter_q and filter_q.lower() not in rel.lower():
                continue
            st = abs_p.stat()
            await session.merge(
                VaultFile(
                    path=rel,
                    title=None,
                    section=None,
                    file_type=ext.lstrip("."),
                    tags=None,
                    mtime=int(st.st_mtime),
                    size_bytes=st.st_size,
                    chunk_count=None,
                )
            )
            seen += 1
        if seen >= limit:
            break


@router.get("/files", response_model=FileTree)
async def list_files(
    prefix: str = Query("raw/", description="Path prefix under vault"),
    depth: int = Query(3, ge=1, le=16),
    limit: int = Query(500, ge=1, le=2000),
    filter_q: str | None = Query(None, alias="filter"),
    refresh: bool = Query(False),
    session: AsyncSession = Depends(get_async_session),
) -> FileTree:
    settings = _require_settings()
    vault = settings.vault_path
    pref_raw = prefix.replace("\\", "/").lstrip("/").rstrip("/")

    if pref_raw:
        path_clause = or_(VaultFile.path == pref_raw, VaultFile.path.startswith(pref_raw + "/"))
    else:
        path_clause = True

    q = select(VaultFile.path).where(path_clause)
    if filter_q:
        q = q.where(VaultFile.path.ilike(f"%{filter_q}%"))
    q = q.order_by(VaultFile.path.asc()).limit(limit)
    res = await session.execute(q)
    paths = [row[0] for row in res.all()]

    # Keep cache and filesystem in sync: prune stale rows for deleted files.
    # This avoids showing paths that no longer exist under /vault/raw or /vault/wiki.
    if paths and vault.is_dir():
        stale: list[str] = []
        for p in paths:
            abs_p = _resolve_safe(vault, p)
            if not abs_p.is_file():
                stale.append(p)
        if stale:
            await session.execute(delete(VaultFile).where(VaultFile.path.in_(stale)))
            await session.commit()
            res = await session.execute(q)
            paths = [row[0] for row in res.all()]

    if (refresh or not paths) and vault.is_dir():
        await _refresh_vault_rows(session, vault, pref_raw, filter_q, limit)
        await session.commit()
        res = await session.execute(q)
        paths = [row[0] for row in res.all()]

    nodes = _build_tree(paths, pref_raw, depth)
    display_prefix = pref_raw + "/" if pref_raw else ""
    return FileTree(prefix=display_prefix, nodes=nodes)


@router.get("/files/{path:path}", response_model=FileContent)
async def read_vault_file(path: str) -> FileContent:
    settings = _require_settings()
    vault = settings.vault_path
    target = _resolve_safe(vault, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    st = target.stat()
    ext = target.suffix.lower()
    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    fm: dict[str, Any] | None = None
    body = text
    if ext == ".md":
        post = frontmatter.loads(text)
        fm = dict(post.metadata) if post.metadata else None
        body = post.content or ""
    return FileContent(
        path=str(target.relative_to(vault.resolve())).replace("\\", "/"),
        frontmatter=fm,
        body=body,
        mtime=st.st_mtime,
        size_bytes=st.st_size,
    )


@router.get("/stats", response_model=VaultStats)
async def vault_stats(session: AsyncSession = Depends(get_async_session)) -> VaultStats:
    settings = _require_settings()
    fc = await session.execute(select(func.count()).select_from(VaultFile))
    file_count = int(fc.scalar_one())
    cc = await session.execute(select(func.count()).select_from(DocumentChunk))
    chunk_count = int(cc.scalar_one())
    last_row = await session.execute(
        select(IngestEvent.created_at)
        .where(IngestEvent.status == "ingested")
        .order_by(IngestEvent.created_at.desc())
        .limit(1)
    )
    last = last_row.scalar_one_or_none()
    last_s = last.isoformat() if last else None
    return VaultStats(
        file_count=file_count,
        chunk_count=chunk_count,
        last_ingest_at=last_s,
        embed_model=settings.embed_model,
    )
