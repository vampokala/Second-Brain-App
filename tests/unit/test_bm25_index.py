import json
import os
import tempfile

import pytest
from src.core.bm25_index import BM25Index


@pytest.fixture
def index_with_docs():
    idx = BM25Index()
    idx.add_document("doc1", "the quick brown fox jumps over the lazy dog", {"source": "a"})
    idx.add_document("doc2", "the fox went to the market to buy bread", {"source": "b"})
    idx.add_document("doc3", "machine learning is a subset of artificial intelligence", {"source": "c"})
    return idx


class TestAddDocument:
    def test_document_count(self, index_with_docs):
        assert len(index_with_docs.documents) == 3

    def test_avg_doc_length_updates(self):
        idx = BM25Index()
        idx.add_document("d1", "one two three", {})
        idx.add_document("d2", "one two three four five", {})
        assert idx.avg_doc_length == pytest.approx(4.0)

    def test_inverted_index_populated(self, index_with_docs):
        assert "fox" in index_with_docs.inverted_index
        assert len(index_with_docs.inverted_index["fox"]) == 2  # appears in doc1 and doc2

    def test_term_frequency_recorded(self, index_with_docs):
        postings = {p["doc_id"]: p["term_freq"] for p in index_with_docs.inverted_index["the"]}
        assert postings["doc1"] >= 2  # "the" appears multiple times in doc1


class TestScore:
    def test_relevant_doc_ranks_higher(self, index_with_docs):
        results = index_with_docs.score("fox")
        ids = [r["id"] for r in results]
        assert "doc1" in ids
        assert "doc2" in ids
        assert "doc3" not in ids  # "fox" not in doc3

    def test_top_k_limits_results(self, index_with_docs):
        results = index_with_docs.score("the fox", top_k=1)
        assert len(results) == 1

    def test_no_match_returns_empty(self, index_with_docs):
        results = index_with_docs.score("zzznomatch")
        assert results == []

    def test_scores_are_positive(self, index_with_docs):
        results = index_with_docs.score("fox")
        assert all(r["score"] > 0 for r in results)

    def test_results_sorted_descending(self, index_with_docs):
        results = index_with_docs.score("fox market")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_unrelated_query_matches_only_relevant_doc(self, index_with_docs):
        results = index_with_docs.score("machine learning intelligence")
        assert results[0]["id"] == "doc3"


class TestComposeIndexText:
    def test_title_terms_match_when_absent_from_chunk(self):
        chunk = "obscure xyzzy content here"
        meta = {"title": "specialtitle token", "file_type": ".md"}
        composed = BM25Index.compose_index_text(chunk, meta, title_weight=2)
        idx = BM25Index()
        idx.add_document("d1", chunk, meta, index_text=composed)
        hits = idx.score("specialtitle", top_k=1)
        assert hits and hits[0]["id"] == "d1"
        assert hits[0]["text"] == chunk


class TestTokenize:
    def test_lowercases(self):
        tokens = BM25Index._tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_strips_punctuation(self):
        tokens = BM25Index._tokenize("hello, world!")
        assert tokens == ["hello", "world"]

    def test_handles_empty_string(self):
        assert BM25Index._tokenize("") == []


class TestPersistence:
    def test_save_and_load_roundtrip(self, index_with_docs):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            index_with_docs.save(path)
            loaded = BM25Index.load(path)

            assert len(loaded.documents) == len(index_with_docs.documents)
            assert loaded.k1 == index_with_docs.k1
            assert loaded.b == index_with_docs.b
            assert loaded.avg_doc_length == pytest.approx(index_with_docs.avg_doc_length)

            original_results = index_with_docs.score("fox")
            loaded_results = loaded.score("fox")
            assert [r["id"] for r in original_results] == [r["id"] for r in loaded_results]
        finally:
            os.unlink(path)

    def test_saved_file_is_valid_json(self, index_with_docs):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            index_with_docs.save(path)
            with open(path) as f:
                data = json.load(f)
            assert "inverted_index" in data
            assert "documents" in data
        finally:
            os.unlink(path)


class TestCustomParameters:
    def test_custom_k1_b(self):
        idx = BM25Index(k1=1.2, b=0.5)
        assert idx.k1 == 1.2
        assert idx.b == 0.5

    def test_empty_index_score(self):
        idx = BM25Index()
        assert idx.score("anything") == []
