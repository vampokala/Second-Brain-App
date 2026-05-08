"""Synchronous pgvector-backed vector store (Chroma-compatible hooks for HybridRetriever)."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import ollama
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


def _vector_literal(vec: List[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class PgVectorStore:
    """Vector ops against document_chunks using cosine distance (<=>)."""

    mode = "pgvector"

    def __init__(self, database_url_sync: str, embed_model: str | None = None):
        self._engine = create_engine(database_url_sync, pool_pre_ping=True)
        self._session = sessionmaker(self._engine, expire_on_commit=False, class_=Session)
        host = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        self._ollama = ollama.Client(host=host)
        self._embed_model = embed_model or os.getenv("EMBED_MODEL", "nomic-embed-text")

    def generate_embedding(self, prompt: str) -> List[float]:
        attempts = 3
        last: Exception | None = None
        for idx in range(attempts):
            try:
                response = self._ollama.embeddings(model=self._embed_model, prompt=prompt)
                return list(response["embedding"])
            except Exception as exc:  # noqa: BLE001
                last = exc
                if idx == attempts - 1:
                    raise
                time.sleep(0.35 * (idx + 1))
        raise last or RuntimeError("embedding failed")

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

    def create_collection(self, collection_name: str) -> None:  # noqa: ARG002
        return

    def add_documents(
        self,
        collection_name: str,
        documents: List[Dict],
        *,
        skip_embedding: bool = False,
    ) -> None:  # noqa: ARG002
        """Upsert chunk rows; documents must include id and text plus metadata dict."""
        if os.getenv("SECOND_BRAIN_SKIP_EMBED", "").strip().lower() in ("1", "true", "yes"):
            logger.warning("SECOND_BRAIN_SKIP_EMBED set; skipping vector upserts")
            return
        with self._session() as session:
            for doc in documents:
                chunk_id = str(doc["id"])
                body = doc["text"]
                meta = {k: v for k, v in doc.items() if k not in ("id", "text")}
                if skip_embedding:
                    literal = None
                else:
                    emb_vec = self.generate_embedding(body)
                    literal = _vector_literal(emb_vec)
                sql = """
                        INSERT INTO document_chunks (
                          id, chunk_id, source_path, chunk_index, content, heading, section,
                          file_type, tags, metadata, embedding
                        ) VALUES (
                          :id, :chunk_id, :source_path, :chunk_index, :content, :heading, :section,
                          :file_type, CAST(:tags AS jsonb), CAST(:metadata AS jsonb),
                          CAST(:embedding AS vector)
                        )
                        ON CONFLICT (chunk_id) DO UPDATE SET
                          source_path = EXCLUDED.source_path,
                          chunk_index = EXCLUDED.chunk_index,
                          content = EXCLUDED.content,
                          heading = EXCLUDED.heading,
                          section = EXCLUDED.section,
                          file_type = EXCLUDED.file_type,
                          tags = EXCLUDED.tags,
                          metadata = EXCLUDED.metadata,
                          embedding = EXCLUDED.embedding
                        """
                if literal is None:
                    sql = """
                        INSERT INTO document_chunks (
                          id, chunk_id, source_path, chunk_index, content, heading, section,
                          file_type, tags, metadata, embedding
                        ) VALUES (
                          :id, :chunk_id, :source_path, :chunk_index, :content, :heading, :section,
                          :file_type, CAST(:tags AS jsonb), CAST(:metadata AS jsonb), NULL
                        )
                        ON CONFLICT (chunk_id) DO UPDATE SET
                          source_path = EXCLUDED.source_path,
                          chunk_index = EXCLUDED.chunk_index,
                          content = EXCLUDED.content,
                          heading = EXCLUDED.heading,
                          section = EXCLUDED.section,
                          file_type = EXCLUDED.file_type,
                          tags = EXCLUDED.tags,
                          metadata = EXCLUDED.metadata,
                          embedding = EXCLUDED.embedding
                        """
                params = {
                    "id": str(uuid.uuid4()),
                    "chunk_id": chunk_id,
                    "source_path": str(meta.get("source_path") or meta.get("relpath") or ""),
                    "chunk_index": int(meta.get("chunk_index") or 0),
                    "content": body,
                    "heading": meta.get("heading"),
                    "section": meta.get("section"),
                    "file_type": meta.get("file_type"),
                    "tags": json.dumps(meta.get("tags") or []),
                    "metadata": json.dumps(meta),
                }
                if literal is not None:
                    params["embedding"] = literal
                session.execute(text(sql.strip()), params)
            session.commit()

    def query_documents(
        self,
        collection_name: str,  # noqa: ARG002
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        q_emb = self.generate_embedding(query_text)
        literal = _vector_literal(q_emb)
        sql = """
            SELECT chunk_id AS id,
                   content AS text,
                   metadata,
                   (embedding <=> CAST(:q AS vector)) AS distance
            FROM document_chunks
            WHERE embedding IS NOT NULL
        """
        params: Dict[str, Any] = {"q": literal, "k": top_k}
        if filters:
            for fk, fv in filters.items():
                sql += f" AND metadata->>:f_{fk} = :v_{fk}"
                params[f"f_{fk}"] = fk
                params[f"v_{fk}"] = str(fv)
        sql += " ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"
        with self._session() as session:
            rows = session.execute(text(sql), params).mappings().all()
        out: List[Dict] = []
        for row in rows:
            meta = row["metadata"] or {}
            out.append(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "metadata": dict(meta) if isinstance(meta, dict) else {},
                    "distance": float(row["distance"]) if row["distance"] is not None else None,
                }
            )
        return out

    def delete_source_path(self, source_path: str) -> None:
        with self._session() as session:
            session.execute(
                text("DELETE FROM document_chunks WHERE source_path = :p OR chunk_id LIKE :c"),
                {"p": source_path, "c": f"{source_path}#%"},
            )
            session.commit()
