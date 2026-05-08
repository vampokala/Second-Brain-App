'''
- Document indexing with preprocessing
- Query processing and scoring
- Index persistence and loading
- Parameter tuning (k1, b values)
'''
import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict] = []
        self._doc_lengths: Dict[str, int] = {}       # fast O(1) length lookup
        self._total_doc_length: int = 0
        self.avg_doc_length: float = 0.0
        self.inverted_index: Dict[str, List[Dict]] = {}

    # --- preprocessing ---

    @staticmethod
    def compose_index_text(
        chunk_text: str,
        metadata: Optional[Dict] = None,
        title_weight: int = 3,
    ) -> str:
        """Repeat title (and light metadata) so BM25 can field-bias without a multi-field engine."""
        metadata = metadata or {}
        parts: List[str] = []
        title = str(metadata.get("title") or "").strip()
        if title:
            parts.extend([title] * max(1, title_weight))
        parts.append(chunk_text)
        extras: List[str] = []
        ft = metadata.get("file_type")
        if ft:
            extras.append(str(ft))
        auth = metadata.get("author")
        if auth and str(auth).strip().lower() not in ("unknown", ""):
            extras.append(str(auth))
        if extras:
            parts.append(" ".join(extras))
        return "\n".join(parts)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return text.split()

    # --- indexing ---

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict,
        index_text: Optional[str] = None,
    ) -> None:
        """Index BM25 over ``index_text`` when provided; ``text`` is the stored chunk for retrieval."""
        body_for_index = index_text if index_text is not None else text
        tokens = self._tokenize(body_for_index)
        doc_length = len(tokens)

        self.documents.append({'id': doc_id, 'text': text, 'metadata': metadata})
        self._doc_lengths[doc_id] = doc_length
        self._total_doc_length += doc_length
        self.avg_doc_length = self._total_doc_length / len(self.documents)

        for token, freq in Counter(tokens).items():
            if token not in self.inverted_index:
                self.inverted_index[token] = []
            self.inverted_index[token].append({'doc_id': doc_id, 'term_freq': freq})

    def remove_by_relpath(self, relpath: str) -> None:
        """Drop all chunks for a vault-relative path and rebuild postings."""
        norm = relpath.replace("\\", "/").lstrip("/")
        kept: List[Dict] = []
        for doc in self.documents:
            md = doc.get("metadata") or {}
            r = str(md.get("relpath") or "").replace("\\", "/").lstrip("/")
            if r == norm:
                continue
            kept.append(doc)
        if len(kept) == len(self.documents):
            return
        self.documents = kept
        self._rebuild_inverted_index()

    def _rebuild_inverted_index(self) -> None:
        self._doc_lengths.clear()
        self._total_doc_length = 0
        self.inverted_index.clear()
        self.avg_doc_length = 0.0
        for doc in self.documents:
            doc_id = doc["id"]
            index_text = self.compose_index_text(doc["text"], doc.get("metadata"))
            tokens = self._tokenize(index_text)
            doc_length = len(tokens)
            self._doc_lengths[doc_id] = doc_length
            self._total_doc_length += doc_length
            for token, freq in Counter(tokens).items():
                if token not in self.inverted_index:
                    self.inverted_index[token] = []
                self.inverted_index[token].append({'doc_id': doc_id, 'term_freq': freq})
        if self.documents:
            self.avg_doc_length = self._total_doc_length / len(self.documents)

    # --- scoring ---

    def score(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        query_tokens = self._tokenize(query)
        n = len(self.documents)
        if n == 0:
            return []
        scores: Dict[str, float] = {}

        for token in query_tokens:
            if token not in self.inverted_index:
                continue
            postings = self.inverted_index[token]
            df = len(postings)
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1)

            for posting in postings:
                doc_id = posting['doc_id']
                tf = posting['term_freq']
                dl = self._doc_lengths[doc_id]
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self.avg_doc_length)
                )
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * tf_norm

        results = sorted(
            [
                {**doc, 'score': scores[doc['id']]}
                for doc in self.documents
                if doc['id'] in scores
            ],
            key=lambda x: x['score'],
            reverse=True,
        )
        return results[:top_k] if top_k is not None else results

    # --- persistence ---

    def to_snapshot(self) -> Dict:
        """Serialize index for JSON / Postgres JSONB (same keys as save file)."""
        return {
            "k1": self.k1,
            "b": self.b,
            "documents": self.documents,
            "doc_lengths": self._doc_lengths,
            "total_doc_length": self._total_doc_length,
            "avg_doc_length": self.avg_doc_length,
            "inverted_index": self.inverted_index,
        }

    @classmethod
    def from_snapshot(cls, data: Dict) -> "BM25Index":
        index = cls(k1=float(data.get("k1", 1.5)), b=float(data.get("b", 0.75)))
        index.documents = list(data.get("documents") or [])
        index._doc_lengths = dict(data.get("doc_lengths") or {})
        index._total_doc_length = int(data.get("total_doc_length") or 0)
        index.avg_doc_length = float(data.get("avg_doc_length") or 0.0)
        index.inverted_index = dict(data.get("inverted_index") or {})
        if not index.documents:
            index._doc_lengths.clear()
            index._total_doc_length = 0
            index.avg_doc_length = 0.0
            index.inverted_index.clear()
        elif not index.inverted_index:
            index._rebuild_inverted_index()
        return index

    def save(self, file_path: str) -> None:
        with open(file_path, "w") as f:
            json.dump(self.to_snapshot(), f)

    @classmethod
    def load(cls, file_path: str) -> "BM25Index":
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls.from_snapshot(data)

    def save_to_db(self, session: "Session") -> None:
        """Persist BM25 JSON snapshot to Postgres (single-row table)."""
        from src.db.models import BM25Snapshot

        session.merge(BM25Snapshot(id=1, payload=self.to_snapshot()))

    @classmethod
    def load_from_db(cls, session: "Session") -> "BM25Index":
        from src.db.models import BM25Snapshot

        row = session.get(BM25Snapshot, 1)
        if row is None or row.payload is None:
            return cls()
        return cls.from_snapshot(dict(row.payload))
