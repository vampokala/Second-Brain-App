"""
Integration tests: DocumentProcessor → BM25Index → VectorDatabase (ChromaDB dev mode).

VectorDatabase tests mock Ollama so the suite runs without a live Ollama instance.
To run against a real Ollama, set the env var INTEGRATION_LIVE=1.
"""
import os
import tempfile
from typing import List
from unittest.mock import patch

import pytest
from src import query as query_mod
from src.core.bm25_index import BM25Index
from src.core.document_processor import DocumentProcessor
from src.core.query_processor import QueryProcessor
from src.utils.database import VectorDatabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_txt(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


FAKE_EMBEDDING: List[float] = [0.1] * 768


# ---------------------------------------------------------------------------
# Processor → BM25 pipeline
# ---------------------------------------------------------------------------

class TestProcessorToBM25:
    def test_full_ingest_and_query(self):
        processor = DocumentProcessor(chunk_size=200, overlap=20)
        index = BM25Index()

        docs = [
            ("machine learning algorithms are powerful tools for data analysis", "ml"),
            ("python is a popular programming language for data science", "py"),
            ("neural networks are inspired by the human brain structure", "nn"),
        ]
        paths = []
        try:
            for content, doc_id in docs:
                path = _write_txt(content)
                paths.append(path)
                result = processor.process_document(path)
                assert result is not None
                for i, chunk in enumerate(result["chunks"]):
                    index.add_document(f"{doc_id}_{i}", chunk, result["metadata"])

            results = index.score("neural networks brain", top_k=1)
            assert len(results) == 1
            assert results[0]["id"].startswith("nn")
        finally:
            for p in paths:
                os.unlink(p)

    def test_duplicate_document_not_indexed(self):
        processor = DocumentProcessor()
        index = BM25Index()

        path = _write_txt("some content about cats")
        try:
            first = processor.process_document(path)
            second = processor.process_document(path)

            assert first is not None
            assert second is None  # duplicate blocked

            for i, chunk in enumerate(first["chunks"]):
                index.add_document(f"doc_{i}", chunk, first["metadata"])

            assert len(index.documents) == len(first["chunks"])
        finally:
            os.unlink(path)

    def test_multiple_formats_indexed_together(self):
        processor = DocumentProcessor(chunk_size=500, overlap=50)
        index = BM25Index()

        txt_path = _write_txt("databases store structured data efficiently")
        md_path = _write_txt("# Query\nSQL is used to query relational databases")
        md_path = md_path.replace(".txt", ".md")
        os.rename(md_path.replace(".md", ".txt"), md_path) if not md_path.endswith(".md") else None

        md_path2 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        md_path2.write("# Query\nSQL is used to query relational databases")
        md_path2.close()
        md_path2 = md_path2.name

        try:
            for path in [txt_path, md_path2]:
                result = processor.process_document(path)
                assert result is not None
                for i, chunk in enumerate(result["chunks"]):
                    index.add_document(f"{os.path.basename(path)}_{i}", chunk, result["metadata"])

            results = index.score("SQL relational databases")
            assert len(results) > 0
            assert results[0]["id"].startswith(os.path.basename(md_path2))
        finally:
            os.unlink(txt_path)
            os.unlink(md_path2)

    def test_bm25_ranking_reflects_term_density(self):
        processor = DocumentProcessor(chunk_size=500, overlap=0)
        index = BM25Index()

        high_path = _write_txt("python python python is great for data science python")
        low_path = _write_txt("java is also a programming language used in enterprise")
        try:
            for label, path in [("high", high_path), ("low", low_path)]:
                result = processor.process_document(path)
                assert result is not None
                for i, chunk in enumerate(result["chunks"]):
                    index.add_document(f"{label}_{i}", chunk, result["metadata"])

            results = index.score("python")
            assert results[0]["id"].startswith("high")
        finally:
            os.unlink(high_path)
            os.unlink(low_path)


# ---------------------------------------------------------------------------
# VectorDatabase (ChromaDB dev mode) — Ollama mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def vector_db(tmp_path):
    return VectorDatabase(mode="dev", chroma_path=str(tmp_path / "chroma"))


@pytest.fixture
def mock_embedding():
    """Avoid Ollama in CI; VectorDatabase uses Client.embeddings(), not ollama.embeddings."""
    if os.getenv("INTEGRATION_LIVE") == "1":
        yield
        return
    with patch.object(VectorDatabase, "generate_embedding", return_value=list(FAKE_EMBEDDING)):
        yield


class TestVectorDatabaseDev:
    def test_create_collection(self, vector_db, mock_embedding):
        vector_db.create_collection("test_col")
        # no error means collection created
        col = vector_db.chroma_client.get_or_create_collection("test_col")
        assert col is not None

    def test_add_and_query_documents(self, vector_db, mock_embedding):
        docs = [
            {"id": "1", "text": "machine learning is powerful", "source": "a"},
            {"id": "2", "text": "deep learning uses neural networks", "source": "b"},
            {"id": "3", "text": "python is great for scripting", "source": "c"},
        ]
        vector_db.add_documents("test_col", docs)
        results = vector_db.query_documents("test_col", "machine learning", top_k=2)
        assert len(results) == 2
        assert all("id" in r for r in results)

    def test_batch_insert(self, vector_db, mock_embedding):
        docs = [{"id": str(i), "text": f"document number {i}"} for i in range(150)]
        vector_db.add_documents("batch_col", docs)
        results = vector_db.query_documents("batch_col", "document", top_k=10)
        assert len(results) == 10

    def test_metadata_filter(self, vector_db, mock_embedding):
        docs = [
            {"id": "a1", "text": "cats are fluffy animals", "category": "animals"},
            {"id": "a2", "text": "dogs are loyal companions", "category": "animals"},
            {"id": "b1", "text": "python is a programming language", "category": "tech"},
        ]
        vector_db.add_documents("filtered_col", docs)
        results = vector_db.query_documents(
            "filtered_col", "language", top_k=5, filters={"category": "tech"}
        )
        assert all(r["metadata"].get("category") == "tech" for r in results)

    def test_upsert_overwrites_existing(self, vector_db, mock_embedding):
        docs = [{"id": "1", "text": "original text", "version": "v1"}]
        vector_db.add_documents("upsert_col", docs)

        updated = [{"id": "1", "text": "updated text", "version": "v2"}]
        vector_db.add_documents("upsert_col", updated)

        results = vector_db.query_documents("upsert_col", "text", top_k=1)
        assert results[0]["metadata"].get("version") == "v2"


# ---------------------------------------------------------------------------
# Full pipeline: Processor → BM25 + VectorDatabase together
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_process_index_and_retrieve(self, vector_db, mock_embedding):
        processor = DocumentProcessor(chunk_size=300, overlap=30)
        index = BM25Index()

        docs_content = [
            "transformer models revolutionized natural language processing tasks",
            "convolutional neural networks excel at image recognition tasks",
            "reinforcement learning trains agents through reward and penalty",
        ]
        paths = []
        try:
            for i, content in enumerate(docs_content):
                path = _write_txt(content)
                paths.append(path)
                result = processor.process_document(path)
                assert result is not None

                chunks_as_dicts = [
                    {"id": f"doc{i}_chunk{j}", "text": chunk, **result["metadata"]}
                    for j, chunk in enumerate(result["chunks"])
                ]
                vector_db.add_documents("pipeline_col", chunks_as_dicts)
                for j, chunk in enumerate(result["chunks"]):
                    index.add_document(f"doc{i}_chunk{j}", chunk, result["metadata"])

            bm25_results = index.score("transformer language processing", top_k=1)
            assert "doc0" in bm25_results[0]["id"]

            vector_results = vector_db.query_documents("pipeline_col", "image recognition", top_k=1)
            assert len(vector_results) == 1
        finally:
            for p in paths:
                os.unlink(p)


class TestHybridRetrievePipeline:
    def test_query_retrieve_returns_rrf_shaped_dicts(self, vector_db, mock_embedding):
        """End-to-end retrieve() uses HybridRetriever; results expose to_legacy_dict()."""
        index = BM25Index()
        meta = {"title": "doc.txt", "file_type": ".txt"}
        index.add_document(
            "chunk0",
            "python asyncio concurrency patterns",
            meta,
            index_text=BM25Index.compose_index_text("python asyncio concurrency patterns", meta),
        )
        index.add_document(
            "chunk1",
            "unrelated content about gardening soil ph",
            meta,
            index_text=BM25Index.compose_index_text("unrelated content about gardening soil ph", meta),
        )

        vector_db.create_collection(query_mod.COLLECTION_NAME)
        vector_db.add_documents(
            query_mod.COLLECTION_NAME,
            [
                {"id": "chunk0", "text": "python asyncio concurrency patterns", **meta},
                {"id": "chunk1", "text": "unrelated content about gardening soil ph", **meta},
            ],
        )

        qp = QueryProcessor()
        rows = query_mod.retrieve("asyncio python", index, vector_db, qp, top_k=2)
        legacy = [r.to_legacy_dict() for r in rows]
        assert len(legacy) == 2
        assert all("score" in r for r in legacy)
        assert legacy[0]["id"] == "chunk0"
        assert "sources" in legacy[0]
