'''
- ChromaDB for development
- Qdrant for production scaling
- Embedding generation via Ollama
- Batch operations for efficiency
- Metadata filtering capabilities
'''
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

import chromadb
import ollama

# qdrant_client is imported lazily inside _init_qdrant() so the module can be
# imported on environments where qdrant-client is not installed (e.g. HF Spaces
# running in Chroma-only / dev mode).

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768
BATCH_SIZE = 100

_ST_MODEL_NAME = "all-MiniLM-L6-v2"


class VectorDatabase:
    def __init__(
        self,
        mode: str = "dev",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        chroma_path: str = "./chroma_db",
    ):
        self.mode = mode
        self._chroma_path = chroma_path
        self._qdrant_host = qdrant_host
        self._qdrant_port = qdrant_port
        self._chroma_client: Optional[chromadb.ClientAPI] = None
        self._qdrant_client: Optional[Any] = None  # QdrantClient, imported lazily
        self._ollama_client = ollama.Client(host=self._resolve_ollama_host())
        self._st_model: Optional[Any] = None  # SentenceTransformer, loaded lazily
        self._embedding_provider = os.getenv("DOC_EMBEDDING_PROVIDER", "ollama").lower()

    # --- client accessors (lazy init) ---

    @property
    def chroma_client(self) -> chromadb.ClientAPI:
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(path=self._chroma_path)
            logger.info("ChromaDB initialized at %s", self._chroma_path)
        return self._chroma_client

    @property
    def qdrant_client(self) -> Any:
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient  # noqa: PLC0415

            self._qdrant_client = QdrantClient(host=self._qdrant_host, port=self._qdrant_port)
            logger.info("Qdrant initialized at %s:%s", self._qdrant_host, self._qdrant_port)
        return self._qdrant_client

    # --- embedding ---

    @staticmethod
    def _resolve_ollama_host() -> str:
        return (
            os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        )

    def _generate_st_embedding(self, text: str) -> List[float]:
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._st_model = SentenceTransformer(_ST_MODEL_NAME)
            logger.info("SentenceTransformer loaded: %s", _ST_MODEL_NAME)
        return self._st_model.encode(text, show_progress_bar=False).tolist()

    def generate_embedding(self, text: str) -> List[float]:
        if self._embedding_provider == "sentence_transformers":
            return self._generate_st_embedding(text)
        attempts = 3
        last_error: Exception | None = None
        for idx in range(attempts):
            try:
                response = self._ollama_client.embeddings(model=OLLAMA_MODEL, prompt=text)
                return response["embedding"]  # type: ignore[return-value]
            except Exception as exc:
                last_error = exc
                if idx == attempts - 1:
                    raise
                time.sleep(0.35 * (idx + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected Ollama embedding retry state")

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

    # --- collection management ---

    def create_collection(self, collection_name: str) -> None:
        if self.mode == "dev":
            self.chroma_client.get_or_create_collection(name=collection_name)
            logger.info("ChromaDB collection %r ready", collection_name)
        else:
            from qdrant_client.http.models import Distance, VectorParams  # noqa: PLC0415
            if not self.qdrant_client.collection_exists(collection_name):
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                logger.info("Qdrant collection %r created", collection_name)

    # --- insert ---

    def add_documents(self, collection_name: str, documents: List[Dict]) -> None:
        """Insert documents with embeddings generated from document['text'].

        Each document dict must have 'id' and 'text'; all other keys go into metadata.
        """
        for batch_start in range(0, len(documents), BATCH_SIZE):
            batch = documents[batch_start: batch_start + BATCH_SIZE]
            texts = [doc["text"] for doc in batch]
            embeddings = self.generate_embeddings_batch(texts)

            if self.mode == "dev":
                collection = self.chroma_client.get_or_create_collection(name=collection_name)
                metadatas = [
                    ({k: v for k, v in doc.items() if k not in ("id", "text")} or None)
                    for doc in batch
                ]
                collection.upsert(  # type: ignore[arg-type]
                    ids=[str(doc["id"]) for doc in batch],
                    documents=texts,
                    embeddings=embeddings,  # type: ignore[arg-type]
                    metadatas=metadatas,  # type: ignore[arg-type]
                )
            else:
                from qdrant_client.http.models import PointStruct  # noqa: PLC0415
                points = [
                    PointStruct(
                        id=doc["id"],
                        vector=embedding,
                        payload={k: v for k, v in doc.items() if k not in ("id", "text")},
                    )
                    for doc, embedding in zip(batch, embeddings)
                ]
                self.qdrant_client.upsert(collection_name=collection_name, points=points)

            logger.info("Upserted batch of %d documents into %r", len(batch), collection_name)

    # --- query ---

    def query_documents(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search for similar documents, optionally filtered by metadata key/value pairs."""
        query_embedding = self.generate_embedding(query_text)

        if self.mode == "dev":
            collection = self.chroma_client.get_or_create_collection(name=collection_name)
            where = ({k: v for k, v in filters.items()} if filters else None)
            results = collection.query(
                query_embeddings=[query_embedding],  # type: ignore[arg-type]
                n_results=top_k,
                where=where,
            )
            ids: List[str] = (results["ids"] or [[]])[0]
            docs: List[str] = (results["documents"] or [[]])[0]
            metas: List[Dict] = (results["metadatas"] or [[]])[0]  # type: ignore[assignment]
            dists: List[float] = (results["distances"] or [[]])[0]
            return [
                {"id": id_, "text": doc, "metadata": meta, "distance": dist}
                for id_, doc, meta, dist in zip(ids, docs, metas, dists)
            ]
        else:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue  # noqa: PLC0415
            search_filter: Optional[Any] = None
            if filters:
                conditions: Sequence[FieldCondition] = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                search_filter = Filter(must=list(conditions))

            response = self.qdrant_client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=search_filter,
            )
            return [
                {"id": hit.id, "metadata": hit.payload, "score": hit.score}
                for hit in response.points
            ]
