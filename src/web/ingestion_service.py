"""Helpers for Streamlit upload and ingest workflow."""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from src.ingest import BM25_INDEX_PATH, COLLECTION_NAME, collect_files, ingest

_LOCK = threading.Lock()
_SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md", ".html"}
MAX_FILES_PER_SESSION = int(os.getenv("DOC_DEMO_MAX_FILES", "3"))
MAX_FILE_BYTES = int(os.getenv("DOC_DEMO_MAX_FILE_MB", "3")) * 1024 * 1024
MAX_SESSION_BYTES = int(os.getenv("DOC_DEMO_MAX_SESSION_MB", "8")) * 1024 * 1024


@dataclass
class IngestFileResult:
    filename: str
    status: str
    message: str = ""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _magic_matches_ext(ext: str, payload: bytes) -> bool:
    if ext == ".pdf":
        return payload.startswith(b"%PDF")
    if ext == ".docx":
        return payload.startswith(b"PK\x03\x04")
    return True


def save_uploaded_files(
    upload_dir: str,
    files: Iterable[object],
    existing_bytes: int = 0,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_session_bytes: int | None = None,
) -> List[IngestFileResult]:
    os.makedirs(upload_dir, exist_ok=True)
    results: List[IngestFileResult] = []
    current_bytes = max(0, existing_bytes)
    max_files = MAX_FILES_PER_SESSION if max_files is None else max_files
    max_file_bytes = MAX_FILE_BYTES if max_file_bytes is None else max_file_bytes
    max_session_bytes = MAX_SESSION_BYTES if max_session_bytes is None else max_session_bytes
    queued_count = 0
    for f in files:
        name = getattr(f, "name", "unknown")
        data = getattr(f, "getvalue", lambda: b"")()
        ext = Path(name).suffix.lower()
        if ext not in _SUPPORTED_EXTS:
            results.append(IngestFileResult(filename=name, status="failed", message=f"Unsupported type: {ext}"))
            continue
        if not _magic_matches_ext(ext, data):
            results.append(IngestFileResult(filename=name, status="rejected", message="type_mismatch"))
            continue
        if len(data) > max_file_bytes:
            results.append(IngestFileResult(filename=name, status="rejected", message="oversize"))
            continue
        if queued_count >= max_files:
            results.append(IngestFileResult(filename=name, status="rejected", message="file_count_cap"))
            continue
        if (current_bytes + len(data)) > max_session_bytes:
            results.append(IngestFileResult(filename=name, status="rejected", message="session_disk_cap"))
            continue
        digest = _sha256_bytes(data)[:12]
        out_path = os.path.join(upload_dir, f"{digest}_{Path(name).name}")
        if os.path.exists(out_path):
            results.append(IngestFileResult(filename=name, status="skipped", message="Duplicate upload"))
            continue
        with open(out_path, "wb") as w:
            w.write(data)
        queued_count += 1
        current_bytes += len(data)
        results.append(IngestFileResult(filename=name, status="queued", message=out_path))
    return results


def run_ingest(
    upload_dir: str,
    bm25_index_path: str | None = None,
    collection_name: str | None = None,
    chroma_path: str | None = None,
) -> dict:
    with _LOCK:
        files = collect_files(upload_dir)
        if not files:
            return {"processed_files": 0, "status": "empty"}
        ingest(
            upload_dir,
            bm25_index_path=bm25_index_path or BM25_INDEX_PATH,
            collection_name=collection_name or COLLECTION_NAME,
            chroma_path=chroma_path or "data/embeddings/chroma",
        )
        return {"processed_files": len(files), "status": "ok"}
