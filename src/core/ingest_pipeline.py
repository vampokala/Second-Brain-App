"""Vault ingest: BM25 snapshot + pgvector chunks, events, embed queue, atomic reindex."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import delete, text
from sqlalchemy.orm import Session, sessionmaker

from src.api.models_ingest import IngestItemResult, IngestScanPreviewResponse, IngestScanSummary
from src.api.sse_bus import SSEBus
from src.core.bm25_index import BM25Index
from src.core.document_processor import DocumentProcessor
from src.core.ingest_manifest import (
    clear_manifest,
    file_sha256,
    load_manifest,
    manifest_path,
    remove_manifest_entry,
    should_skip,
    update_manifest_entry,
)
from src.core.ingest_paths import resolve_vault_ingest_path, should_skip_path
from src.core.ingest_run_state import get_ingest_run_state
from src.core.ingest_scan_preview import scan_vault_preview
from src.core.log_appender import append_log
from src.core.rag_orchestrator import COLLECTION_NAME
from src.core.rolling_memory import memory_path
from src.core.supported_formats import is_supported
from src.core.wiki_stub_writer import write_stub
from src.db.models import BM25Snapshot, Chat, DocumentChunk, EmbedQueue, IngestEvent, VaultFile
from src.db.session import async_session_factory, get_sync_engine, sync_session_factory
from src.utils.config import Config
from src.utils.pgvector_store import PgVectorStore
from src.utils.sb_env import SecondBrainSettings, load_second_brain_settings

logger = logging.getLogger(__name__)

_VISION_MAX_BYTES = int(os.getenv("VISION_MAX_BYTES", "5000000"))
_VISION_MAX_EDGE = int(os.getenv("VISION_MAX_EDGE_PX", "4096"))
_BM25_LOCK = threading.Lock()


def _should_skip_path(path: Path, vault: Path) -> bool:
    """Backward-compatible alias."""
    return should_skip_path(path, vault)


def vision_enabled_runtime() -> bool:
    """Resolve vision flag at call time (env wins; else process default off)."""
    return os.getenv("VISION_INGEST_ENABLED", "").strip().lower() in ("1", "true", "yes")


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
        return
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


def _summarize_results(results: list[IngestItemResult]) -> IngestScanSummary:
    total = len(results)
    ingested = sum(1 for r in results if r.status == "ingested")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    cancelled = sum(1 for r in results if r.status == "cancelled")
    return IngestScanSummary(
        total=total,
        ingested=ingested,
        skipped=skipped,
        failed=failed,
        cancelled=cancelled,
    )


def _wipe_subdir_contents(root: Path) -> None:
    """Delete files and nested dirs under *root*, keeping *root* itself."""
    if not root.is_dir():
        root.mkdir(parents=True, exist_ok=True)
        return
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


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
        self._exclusive = asyncio.Lock()
        self._vision_enabled_override: bool | None = None

    def set_vision_enabled(self, enabled: bool | None) -> None:
        """Optional runtime override from Settings DB (None = env only)."""
        self._vision_enabled_override = enabled

    def is_vision_enabled(self) -> bool:
        return self._vision_enabled()

    def _vision_enabled(self) -> bool:
        if self._vision_enabled_override is not None:
            return self._vision_enabled_override
        return vision_enabled_runtime()

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
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        details = details or {}
        err = details.get("error")
        message = status if not err else f"{status}: {err}"
        payload: dict[str, Any] = {
            "file_path": file_path,
            "event_type": event_type,
            "status": status,
            "details": details,
            "phase": event_type if event_type != "ingest" else "file",
            "message": message,
            "relative_path": file_path,
            "relativePath": file_path,
        }
        if current is not None:
            payload["current"] = current
        if total is not None:
            payload["total"] = total
        self._bus.publish(payload)
        get_ingest_run_state().emit_progress(payload)

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
        with _BM25_LOCK:
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

    def _manifest_file(self) -> Path:
        return manifest_path(self._vault)

    def _ingest_file_sync(self, abs_path: Path, relpath_str: str) -> IngestItemResult:
        run_state = get_ingest_run_state()
        if run_state.should_cancel():
            return IngestItemResult(path=relpath_str, status="cancelled", chunk_count=0)

        try:
            stat = abs_path.stat()
            digest = file_sha256(abs_path)
        except OSError as exc:
            logger.warning("ingest_stat_or_hash_failed path=%s error=%s", abs_path, exc)
            return IngestItemResult(
                path=relpath_str,
                status="failed",
                chunk_count=0,
                error=f"filesystem read failed: {exc}",
            )

        try:
            manifest = load_manifest(self._manifest_file())
            if should_skip(relpath_str, digest, manifest):
                return IngestItemResult(path=relpath_str, status="skipped", chunk_count=0)

            vault_root = str(self._vault)
            vision = self._vision_enabled()
            if run_state.should_cancel():
                return IngestItemResult(path=relpath_str, status="cancelled", chunk_count=0)
            result = self._processor.process_document(
                str(abs_path),
                vault_root=vault_root,
                relpath=relpath_str,
                vision_enabled=vision,
                vision_max_bytes=_VISION_MAX_BYTES,
                vision_max_edge=_VISION_MAX_EDGE,
            )
            if result is None:
                return IngestItemResult(
                    path=relpath_str,
                    status="skipped",
                    chunk_count=0,
                    error="duplicate",
                )
            meta = result["metadata"]
            chunks = result["chunks"]
            if not chunks:
                return IngestItemResult(
                    path=relpath_str,
                    status="failed",
                    chunk_count=0,
                    error="no extractable text (empty or scanned document without OCR)",
                )
            out = self._ingest_processed(relpath_str, meta, chunks)
            if out.status == "ingested":
                update_manifest_entry(
                    self._manifest_file(),
                    relpath_str,
                    digest,
                    size=stat.st_size,
                    mtime_ms=int(stat.st_mtime * 1000),
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.exception("ingest failed %s", abs_path)
            return IngestItemResult(path=relpath_str, status="failed", chunk_count=0, error=str(exc))

    async def _wiki_after_ingest(self, abs_path: Path, relpath_str: str, out: IngestItemResult) -> None:
        if out.status != "ingested" or out.chunk_count <= 0:
            return
        rel = relpath_str.replace("\\", "/")
        if not rel.lower().startswith("raw/"):
            return
        summary = ""
        if rel.lower().endswith(".md"):
            try:
                summary = await asyncio.to_thread(abs_path.read_text, encoding="utf-8", errors="replace")
            except OSError:
                summary = ""
        else:
            summary = f"Ingested source with {out.chunk_count} searchable chunk(s)."
        await write_stub(abs_path, self.settings.vault_path, summary)
        await append_log(self.settings.vault_path, relpath_str)

    async def _ingest_file_inner(
        self,
        abs_path: Path,
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> IngestItemResult:
        """Ingest one file; caller must already hold serialization guarantees."""
        abs_path = abs_path.resolve()
        relpath_str = str(abs_path.relative_to(self._vault)).replace("\\", "/")
        self._emit(relpath_str, "ingest", "processing", current=current, total=total)
        await self._persist_event(relpath_str, "ingest", "processing")
        out = await asyncio.to_thread(self._ingest_file_sync, abs_path, relpath_str)
        status = out.status if out.status in ("failed", "skipped", "cancelled") else "ingested"
        self._emit(
            relpath_str,
            "ingest",
            status,
            {"error": out.error, "chunk_count": out.chunk_count},
            current=current,
            total=total,
        )
        await self._persist_event(
            relpath_str,
            "ingest",
            status,
            {"chunk_count": out.chunk_count, "error": out.error},
        )
        if status == "ingested":
            try:
                await self._wiki_after_ingest(abs_path, relpath_str, out)
            except Exception as exc:  # noqa: BLE001
                # Wiki stub/log is best-effort; never fail the ingest/scan batch.
                logger.warning(
                    "wiki_after_ingest_failed path=%s error=%s",
                    relpath_str,
                    exc,
                )
        return out

    async def ingest_file(
        self,
        abs_path: Path,
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> IngestItemResult:
        # Exclusive lock serializes watcher + scan + upload on bind mounts (macOS Docker).
        async with self._exclusive:
            async with self._sem:
                return await self._ingest_file_inner(abs_path, current=current, total=total)

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
        safe_title = page.title.replace("\\", "\\\\").replace('"', '\\"')
        frontmatter = "\n".join(
            ["---", f'title: "{safe_title}"', f"source_url: {url}", "---", "", page.text]
        )
        return await self.ingest_text(rel, frontmatter)

    async def remove_path(self, relpath: str) -> None:
        relpath_norm = relpath.replace("\\", "/").lstrip("/")

        def _sync() -> None:
            with _BM25_LOCK:
                self.bm25.remove_by_relpath(relpath_norm)
                self._pg.delete_source_path(relpath_norm)
                factory = self._sync_factory()
                with factory() as session:
                    self._persist_bm25(session)
                    session.execute(delete(VaultFile).where(VaultFile.path == relpath_norm))
                    session.execute(delete(EmbedQueue).where(EmbedQueue.file_path == relpath_norm))
                    session.commit()
            remove_manifest_entry(self._manifest_file(), relpath_norm)

        async with self._sem:
            await asyncio.to_thread(_sync)
            self._emit(relpath_norm, "remove", "ok")
            await self._persist_event(relpath_norm, "remove", "ok")

    def _collect_files(self) -> list[Path]:
        vision = self._vision_enabled()
        out: list[Path] = []
        for sub in self.settings.vault_subdirs:
            root = self._vault / sub
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if not is_supported(p.suffix, vision_enabled=vision):
                    continue
                if should_skip_path(p, self._vault):
                    continue
                out.append(p.resolve())
        return sorted(out)

    def emit_scan_failed(self, error: str) -> None:
        self._emit("", "scan", "failed", {"error": error})

    def _emit_scan_complete(
        self,
        results: list[IngestItemResult],
        *,
        total: int,
    ) -> IngestScanSummary:
        summary = _summarize_results(results)
        failed_paths = [
            {"path": r.path, "error": r.error or "failed"}
            for r in results
            if r.status == "failed"
        ]
        logger.info(
            "vault_scan_complete total=%s ingested=%s skipped=%s failed=%s cancelled=%s",
            summary.total,
            summary.ingested,
            summary.skipped,
            summary.failed,
            summary.cancelled,
        )
        self._emit(
            "",
            "scan",
            "complete",
            {
                "ingested": summary.ingested,
                "skipped": summary.skipped,
                "failed": summary.failed,
                "cancelled": summary.cancelled,
                "total": summary.total,
                "failed_paths": failed_paths[:50],
            },
            current=total,
            total=total,
        )
        return summary

    def scan_preview(self) -> IngestScanPreviewResponse:
        """Walk vault and classify new/changed files without ingesting."""
        return scan_vault_preview(
            self._vault,
            list(self.settings.vault_subdirs),
            vision_enabled=self._vision_enabled(),
        )

    async def ingest_selected_paths(
        self,
        paths: list[str],
    ) -> tuple[list[IngestItemResult], IngestScanSummary]:
        """Ingest an explicit list of vault-relative paths with SSE progress."""
        vision = self._vision_enabled()
        resolved: list[Path] = []
        seen: set[str] = set()
        for raw in paths:
            norm = raw.replace("\\", "/").strip().lstrip("/")
            if norm in seen:
                continue
            seen.add(norm)
            resolved.append(
                resolve_vault_ingest_path(self._vault, norm, vision_enabled=vision)
            )

        logger.info("vault_ingest_paths_waiting_for_lock selected=%s", len(resolved))
        async with self._exclusive:
            run_state = get_ingest_run_state()
            run_state.clear()
            total = len(resolved)
            self._emit(
                "",
                "scan",
                "processing",
                {"message": f"Ingesting {total} selected files"},
                current=0,
                total=total,
            )
            results: list[IngestItemResult] = []
            for idx, abs_path in enumerate(resolved, start=1):
                if run_state.should_cancel():
                    rel = str(abs_path.relative_to(self._vault)).replace("\\", "/")
                    results.append(
                        IngestItemResult(
                            path=rel,
                            status="cancelled",
                            chunk_count=0,
                            error="cancelled",
                        )
                    )
                    break
                out = await self._ingest_file_inner(abs_path, current=idx, total=total)
                results.append(out)
            summary = self._emit_scan_complete(results, total=total)
            return results, summary

    async def scan_and_ingest(self) -> tuple[list[IngestItemResult], IngestScanSummary]:
        """Walk vault subdirs and ingest new/changed files (manifest skip)."""
        logger.info("vault_scan_waiting_for_lock")
        async with self._exclusive:
            run_state = get_ingest_run_state()
            run_state.clear()
            files = await asyncio.to_thread(self._collect_files)
            total = len(files)
            logger.info("vault_scan_started file_count=%s", total)
            self._emit(
                "",
                "scan",
                "processing",
                {"message": f"Scanning {total} files"},
                current=0,
                total=total,
            )
            results: list[IngestItemResult] = []
            for idx, abs_path in enumerate(files, start=1):
                if run_state.should_cancel():
                    rel = str(abs_path.relative_to(self._vault)).replace("\\", "/")
                    results.append(
                        IngestItemResult(
                            path=rel,
                            status="cancelled",
                            chunk_count=0,
                            error="cancelled",
                        )
                    )
                    break
                # Already holding exclusive — do not call ingest_file (would deadlock).
                out = await self._ingest_file_inner(abs_path, current=idx, total=total)
                results.append(out)
            summary = self._emit_scan_complete(results, total=total)
            return results, summary

    def _reindex_atomic_sync(self) -> None:
        new_idx = BM25Index()
        processor = DocumentProcessor(
            chunk_size=self._cfg.chunk_size,
            overlap=self._cfg.overlap,
            tokenizer_name=self._cfg.chunk_tokenizer,
        )
        vault_root = str(self._vault)
        vision = self._vision_enabled()
        all_docs: list[dict[str, Any]] = []
        vault_rows: list[dict[str, Any]] = []
        for abs_path in self._collect_files():
            relpath_str = str(abs_path.relative_to(self._vault)).replace("\\", "/")
            try:
                result = processor.process_document(
                    str(abs_path),
                    vault_root=vault_root,
                    relpath=relpath_str,
                    vision_enabled=vision,
                    vision_max_bytes=_VISION_MAX_BYTES,
                    vision_max_edge=_VISION_MAX_EDGE,
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
            try:
                st = abs_path.stat()
                digest = file_sha256(abs_path)
                update_manifest_entry(
                    self._manifest_file(),
                    relpath_str,
                    digest,
                    size=st.st_size,
                    mtime_ms=int(st.st_mtime * 1000),
                )
            except OSError as exc:
                logger.warning("reindex manifest update failed path=%s error=%s", relpath_str, exc)
            vault_rows.append(
                {
                    "path": relpath_str,
                    "title": meta.get("title"),
                    "section": str(meta.get("section") or "") or None,
                    "file_type": meta.get("file_type"),
                    "tags": meta.get("tags"),
                    "chunk_count": len(chunks),
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

        with _BM25_LOCK:
            self.bm25 = new_idx
            factory = self._sync_factory()
            with factory() as session:
                self._persist_bm25(session)
                session.execute(delete(VaultFile))
                for row in vault_rows:
                    session.merge(VaultFile(**row))
                session.commit()

    async def reindex_atomic(self) -> None:
        async with self._exclusive:
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

    def _clear_vault_sync(self) -> None:
        with _BM25_LOCK:
            self.bm25 = BM25Index()
            factory = self._sync_factory()
            with factory() as session:
                session.execute(delete(DocumentChunk))
                session.execute(delete(VaultFile))
                session.execute(delete(EmbedQueue))
                session.execute(delete(IngestEvent))
                session.execute(delete(BM25Snapshot))
                self._persist_bm25(session)
                session.commit()
        for sub in self.settings.vault_subdirs:
            _wipe_subdir_contents(self._vault / sub)
        clear_manifest(self._manifest_file())

    async def clear_vault_index_and_files(self) -> None:
        async with self._exclusive:
            await asyncio.to_thread(self._clear_vault_sync)

    async def clear_memory(self) -> None:
        path = memory_path(self._vault)

        def _rm() -> None:
            if path.is_file():
                path.unlink()

        await asyncio.to_thread(_rm)

    async def clear_chats(self) -> None:
        fac = self._async_factory()
        async with fac() as session:
            await session.execute(delete(Chat))
            await session.commit()


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
