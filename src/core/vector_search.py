"""Vector similarity search facade over VectorDatabase (spec: vector_search.py)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from src.utils.database import VectorDatabase


class VectorSearch:
    def __init__(self, db: VectorDatabase, collection_name: str):
        self._db = db
        self._collection = collection_name

    def embed_query(self, query: str) -> List[float]:
        return self._db.generate_embedding(query)

    def similarity_search(self, embedding: List[float], k: int = 50) -> List[Dict]:
        """Query by precomputed embedding (Chroma path)."""
        if self._db.mode != "dev":
            raise NotImplementedError("similarity_search by raw embedding is only wired for Chroma dev mode")

        collection = self._db.chroma_client.get_or_create_collection(name=self._collection)
        results = collection.query(
            query_embeddings=cast(Any, [embedding]),
            n_results=k,
        )
        ids: List[str] = (results["ids"] or [[]])[0]
        docs: List[str] = (results["documents"] or [[]])[0]
        raw_metas = (results["metadatas"] or [[]])[0]
        metas: List[Dict[str, Any]] = cast(List[Dict[str, Any]], raw_metas)
        dists: List[float] = (results["distances"] or [[]])[0]
        return [
            {"id": id_, "text": doc, "metadata": meta or {}, "distance": dist}
            for id_, doc, meta, dist in zip(ids, docs, metas, dists)
        ]

    def search(
        self,
        query: str,
        k: int = 50,
        filters: Optional[Dict] = None,
        max_distance: Optional[float] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Dict]:
        hits = self._db.query_documents(self._collection, query, top_k=k, filters=filters)
        out: List[Dict] = []
        for h in hits:
            dist = h.get("distance")
            if dist is not None:
                if max_distance is not None and dist > max_distance:
                    continue
                sim = 1.0 - float(dist)
                if min_similarity is not None and sim < min_similarity:
                    continue
            out.append(h)
        return out

    def filter_by_metadata(self, results: List[Dict], filters: Dict) -> List[Dict]:
        if not filters:
            return results
        filtered: List[Dict] = []
        for r in results:
            meta = r.get("metadata") or {}
            if all(meta.get(k) == v for k, v in filters.items()):
                filtered.append(r)
        return filtered
