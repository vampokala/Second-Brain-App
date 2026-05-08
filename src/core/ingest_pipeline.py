"""Vault ingest: BM25 snapshot + pgvector chunks, events, embed queue, atomic reindex."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import delete, text
from sqlalchemy.orm import Session, sessionmaker

from src.api.models_ingest import IngestItemResult
from src.api.sse_bus import SSEBus
from src.core.bm25_index import BM25Index
from src.core.document_processor import DocumentProcessor
from src.core.log_appender import append_log
from src.core.rag_orchestrator import COLLECTION_NAME
from src.core.wiki_stub_writer import write_stub
from src.db.models import EmbedQueue, IngestEvent, VaultFile
from src.db.session import async_session_factory, get_sync_engine, sync_session_factory
from src.utils.config import Config
from src.utils.pgvector_store import PgVectorStore
from src.utils.sb_env import SecondBrainSettings, load_second_brain_settings

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".html"}
_SKIP_NAME_RE = re.compile(
    r"^(\.DS_Store|~\$.*|.*\.tmp$|.*\.swp)$",
    re.IGNORECASE,
)


def _should_skip_path(path: Path, vault: Path) -> bool:
    name = path.name
    if _SKIP_NAME_RE.match(name):
        return True
    try:
        rel = path.relative_to(vault)
    except ValueError:
        return True
    parts = rel.parts
    if ".git" in parts or ".obsidian" in parts or "node_modules" in parts:
        return True
    return False


def _insert_shadow_row(
    session: Session,
    table_sql: str,
    doc: dict[str, Any],
    embedding_sql: str | None,
) -> None:
    """Insert one row into shadow table; embedding_sql is pg vector literal or None."""
    body = doc["text"]
    meta = {k: v for k, v in doc.items() if k not in ("id", "text")}
    chunk_id = str(doc["id"])
    params: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "chunk_id": chunk_id,
        "source_path": str(meta.get("relpath") or ""),
        "chunk_index": int(meta.get("chunk_index") or 0),
        "content": body,
        "heading": meta.get("heading"),
        "section": meta.get("section"),
        "file_type": meta.get("file_type"),
        "tags": json.dumps(meta.get("tags") or []),
        "metadata": json.dumps(meta),
    }
    if embedding_sql is None:
        session.execute(
            text(
                f"""
                INSERT INTO {table_sql} (
                  id, chunk_id, source_path, chunk_index, content, heading, section,
                  file_type, tags, metadata, embedding
                ) VALUES (
                  :id, :chunk_id, :source_path, :chunk_index, :content, :heading, :section,
                  :file_type, CAST(:tags AS jsonb), CAST(:metadata AS jsonb), NULL
                )
                """
            ),
            params,
        )
    else:
        params["embedding"] = embedding_sql
        session.execute(
            text(
                f"""
                INSERT INTO {table_sql} (
                  id, chunk_id, source_path, chunk_index, content, heading, section,
                  file_type, tags, metadata, embedding
                ) VALUES (
                  :id, :chunk_id, :source_path, :chunk_index, :content, :heading, :section,
                  :file_type, CAST(:tags AS jsonb), CAST(:metadata AS jsonb),
                  CAST(:embedding AS vector)
                )
                """
            ),
            params,
        )


class IngestPipeline:
    def __init__(
        self,
        cfg: Config,
        settings: SecondBrainSettings,
        semaphore: asyncio.Semaphore,
        bus: SSEBus,
        ollama_available: Callable[[], bool] | None = None,
    ) -> None:
        self._cfg = cfg
        self.settings = settings
        self._sem = semaphore
        self._bus = bus
        self._ollama_ok = ollama_available or (lambda: True)
        self._processor = DocumentProcessor(
            chunk_size=cfg.chunk_size,
            overlap=cfg.overlap,
            tokenizer_name=cfg.chunk_tokenizer,
        )
        self.bm25 = self._load_bm25()
        self._pg = PgVectorStore(settings.database_url_sync, settings.embed_model)
        self._vault = settings.vault_path.resolve()
        self._async_factory = async_session_factory
        self._sync_factory = sync_session_factory

    def _load_bm25(self) -> BM25Index:
        factory = sync_session_factory()
        with factory() as session:
            return BM25Index.load_from_db(session)

    def _persist_bm25(self, session: Session) -> None:
        self.bm25.save_to_db(session)

    def _emit(
        self,
        file_path: str,
        event_type: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._bus.publish(
            {
                "file_path": file_path,
                "event_type": event_type,
                "status": status,
                "details": details or {},
            }
        )

    async def _persist_event(
        self,
        file_path: str,
        event_type: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        fac = self._async_factory()
        async with fac() as session:
            session.add(
                IngestEvent(
                    file_path=file_path,
                    event_type=event_type,
                    status=status,
                    details=details,
                )
            )
            await session.commit()

    def _add_chunks_to_bm25(
        self,
        relpath: str,
        metadata: dict[str, Any],
        chunks: list[str],
    ) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        section = str(metadata.get("section") or "")
        title = str(metadata.get("title") or "")
        tags = metadata.get("tags") or []
        file_type = str(metadata.get("file_type") or "")
        for i, chunk in enumerate(chunks):
            doc_id = f"{relpath}#{i}"
            index_text = BM25Index.compose_index_text(chunk, metadata)
            meta = {
                "relpath": relpath,
                "source_path": relpath,
                "chunk_index": i,
                "section": section,
                "title": title,
                "heading": None,
                "file_type": file_type,
                "tags": tags,
            }
            docs.append({"id": doc_id, "text": chunk, **meta})
            self.bm25.add_document(
                doc_id,
                chunk,
                {**metadata, "relpath": relpath, "chunk_index": i},
                index_text=index_text,
            )
        return docs

    def _ingest_processed(
        self,
        relpath: str,
        metadata: dict[str, Any],
        chunks: list[str],
    ) -> IngestItemResult:
        self.bm25.remove_by_relpath(relpath)
        self._pg.delete_source_path(relpath)
        if not chunks:
            factory = self._sync_factory()
            with factory() as session:
                self._persist_bm25(session)
                session.commit()
            return IngestItemResult(path=relpath, status="ingested", chunk_count=0)

        docs = self._add_chunks_to_bm25(relpath, metadata, chunks)
        n = len(docs)
        embed_ok = self._ollama_ok()
        factory = self._sync_factory()
        try:
            if embed_ok:
                self._pg.add_documents(COLLECTION_NAME, docs, skip_embedding=False)
            else:
                raise RuntimeError("ollama unavailable")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding failed for %s, queuing: %s", relpath, exc)
            self._pg.delete_source_path(relpath)
            self._pg.add_documents(COLLECTION_NAME, docs, skip_embedding=True)
            with factory() as session:
                session.execute(delete(EmbedQueue).where(EmbedQueue.file_path == relpath))
                session.add(EmbedQueue(file_path=relpath, status="pending"))
                self._persist_bm25(session)
                session.merge(
                    VaultFile(
                        path=relpath,
                        title=metadata.get("title"),
                        section=str(metadata.get("section") or "") or None,
                        file_type=metadata.get("file_type"),
                        tags=metadata.get("tags"),
                        size_bytes=None,
                        chunk_count=n,
                    )
                )
                session.commit()
            return IngestItemResult(path=relpath, status="ingested", chunk_count=n)

        with factory() as session:
            self._persist_bm25(session)
            session.merge(
                VaultFile(
                    path=relpath,
                    title=metadata.get("title"),
                    section=str(metadata.get("section") or "") or None,
                    file_type=metadata.get("file_type"),
                    tags=metadata.get("tags"),
                    size_bytes=None,
                    chunk_count=n,
                )
            )
            session.execute(delete(EmbedQueue).where(EmbedQueue.file_path == relpath))
            session.commit()
        return IngestItemResult(path=relpath, status="ingested", chunk_count=n)

    def _ingest_file_sync(self, abs_path: Path, relpath_str: str) -> IngestItemResult:
        vault_root = str(self._vault)
        try:
            result = self._processor.process_document(
                str(abs_path),
                vault_root=vault_root,
                relpath=relpath_str,
            )
            if result is None:
                return IngestItemResult(path=relpath_str, status="ingested", chunk_count=0, error="duplicate")
            meta = result["metadata"]
            chunks = result["chunks"]
            return self._ingest_processed(relpath_str, meta, chunks)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ingest failed %s", abs_path)
            return IngestItemResult(path=relpath_str, status="failed", chunk_count=0, error=str(exc))

    async def _wiki_after_raw_md(self, abs_path: Path, relpath_str: str, out: IngestItemResult) -> None:
        if out.status == "failed" or out.error == "duplicate":
            return
        rel = relpath_str.replace("\\", "/")
        if not rel.lower().startswith("raw/") or not rel.lower().endswith(".md"):
            return
        summary = ""
        try:
            summary = await asyncio.to_thread(abs_path.read_text, encoding="utf-8", errors="replace")
        except OSError:
            pass
        await write_stub(abs_path, self.settings.vault_path, summary)
        await append_log(self.settings.vault_path, relpath_str)

    async def ingest_file(self, abs_path: Path) -> IngestItemResult:
        abs_path = abs_path.resolve()
        relpath_str = str(abs_path.relative_to(self._vault)).replace("\\", "/")
        async with self._sem:
            self._emit(relpath_str, "ingest", "processing")
            await self._persist_event(relpath_str, "ingest", "processing")
            out = await asyncio.to_thread(self._ingest_file_sync, abs_path, relpath_str)
            status = "failed" if out.status == "failed" else "ingested"
            self._emit(relpath_str, "ingest", status, {"error": out.error})
            await self._persist_event(
                relpath_str,
                "ingest",
                status,
                {"chunk_count": out.chunk_count, "error": out.error},
            )
            if status == "ingested":
                await self._wiki_after_raw_md(abs_path, relpath_str, out)
            return out

    async def ingest_text(self, relpath: str, body: str) -> IngestItemResult:
        relpath_norm = relpath.replace("\\", "/").lstrip("/")
        dest = (self._vault / relpath_norm).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        return await self.ingest_file(dest)

    async def ingest_url(self, url: str, relpath: str | None) -> IngestItemResult:
        from src.core.url_extractor import extract_url  # noqa: PLC0415

        page = await asyncio.to_thread(extract_url, url)
        parsed = urlparse(url)
        slug = (parsed.netloc + parsed.path).replace("/", "_")[:80].strip("_") or "page"
        safe = re.sub(r"[^\w\-]+", "_", slug, flags=re.UNICODE)[:80]
        rel = relpath or f"raw/imports/{safe}.md"
        frontmatter = "\n".join(
            ["---", f'title: "{page.title}"', f"source_url: {url}", "---", "", page.text]
        )
        return await self.ingest_text(rel, frontmatter)

    async def remove_path(self, relpath: str) -> None:
        relpath_norm = relpath.replace("\\", "/").lstrip("/")

        def _sync() -> None:
            self.bm25.remove_by_relpath(relpath_norm)
            self._pg.delete_source_path(relpath_norm)
            factory = self._sync_factory()
            with factory() as session:
                self._persist_bm25(session)
                session.execute(delete(VaultFile).where(VaultFile.path == relpath_norm))
                session.execute(delete(EmbedQueue).where(EmbedQueue.file_path == relpath_norm))
                session.commit()

        async with self._sem:
            await asyncio.to_thread(_sync)
            self._emit(relpath_norm, "remove", "ok")
            await self._persist_event(relpath_norm, "remove", "ok")

    def _collect_files(self) -> list[Path]:
        out: list[Path] = []
        for sub in self.settings.vault_subdirs:
            root = self._vault / sub
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in _SUPPORTED:
                    continue
                if _should_skip_path(p, self._vault):
                    continue
                out.append(p.resolve())
        return sorted(out)

    def _reindex_atomic_sync(self) -> None:
        new_idx = BM25Index()
        processor = DocumentProcessor(
            chunk_size=self._cfg.chunk_size,
            overlap=self._cfg.overlap,
            tokenizer_name=self._cfg.chunk_tokenizer,
        )
        vault_root = str(self._vault)
        all_docs: list[dict[str, Any]] = []
        for abs_path in self._collect_files():
            relpath_str = str(abs_path.relative_to(self._vault)).replace("\\", "/")
            try:
                result = processor.process_document(
                    str(abs_path),
                    vault_root=vault_root,
                    relpath=relpath_str,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("reindex skip %s: %s", abs_path, exc)
                continue
            if result is None:
                continue
            meta = result["metadata"]
            chunks = result["chunks"]
            for i, chunk in enumerate(chunks):
                doc_id = f"{relpath_str}#{i}"
                index_text = BM25Index.compose_index_text(chunk, meta)
                new_idx.add_document(
                    doc_id,
                    chunk,
                    {**meta, "relpath": relpath_str, "chunk_index": i},
                    index_text=index_text,
                )
                all_docs.append(
                    {
                        "id": doc_id,
                        "text": chunk,
                        "relpath": relpath_str,
                        "source_path": relpath_str,
                        "chunk_index": i,
                        "section": str(meta.get("section") or ""),
                        "title": str(meta.get("title") or ""),
                        "heading": None,
                        "file_type": str(meta.get("file_type") or ""),
                        "tags": meta.get("tags") or [],
                    }
                )

        suffix = int(time.time())
        shadow = f"document_chunks_sb_{suffix}"
        old = f"document_chunks_old_{suffix}"
        table_ref = f'"{shadow}"'
        engine = get_sync_engine()
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {table_ref} (LIKE document_chunks INCLUDING ALL)"))

        embed_ok = self._ollama_ok()
        fac = sessionmaker(engine, expire_on_commit=False, class_=Session)
        with fac() as session:
            for doc in all_docs:
                lit: str | None = None
                if embed_ok:
                    try:
                        vec = self._pg.generate_embedding(doc["text"])
                        lit = "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
                    except Exception:  # noqa: BLE001
                        lit = None
                _insert_shadow_row(session, table_ref, doc, lit)
            session.commit()

        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE document_chunks RENAME TO "{old}"'))
            conn.execute(text(f"ALTER TABLE {table_ref} RENAME TO document_chunks"))
            conn.execute(text(f'DROP TABLE "{old}" CASCADE'))

        self.bm25 = new_idx
        factory = self._sync_factory()
        with factory() as session:
            self._persist_bm25(session)
            session.commit()

    async def reindex_atomic(self) -> None:
        await asyncio.to_thread(self._reindex_atomic_sync)

    async def drain_embed_queue(self) -> int:
        from sqlalchemy import select  # noqa: PLC0415

        fac = self._async_factory()
        async with fac() as session:
            res = await session.execute(select(EmbedQueue).where(EmbedQueue.status == "pending"))
            rows = list(res.scalars().all())
        n = 0
        for row in rows:
            path = (self._vault / row.file_path).resolve()
            if path.is_file():
                await self.ingest_file(path)
                n += 1
            else:
                async with fac() as s:
                    from sqlalchemy import update  # noqa: PLC0415

                    await s.execute(
                        update(EmbedQueue)
                        .where(EmbedQueue.id == row.id)
                        .values(status="failed", error_message="file missing")
                    )
                    await s.commit()
        return n


def build_pipeline(
    cfg: Config,
    bus: SSEBus,
    semaphore: asyncio.Semaphore,
    ollama_available: Callable[[], bool] | None = None,
) -> IngestPipeline | None:
    if not os.getenv("DATABASE_URL", "").strip():
        return None
    settings = load_second_brain_settings()
    if settings.vector_backend.lower() != "pgvector":
        return None
    return IngestPipeline(cfg, settings, semaphore, bus, ollama_available=ollama_available)
