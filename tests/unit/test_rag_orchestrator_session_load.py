"""RAGOrchestrator._load_components: session-only must not require global BM25."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.core.bm25_index import BM25Index
from src.core.rag_orchestrator import (
    BM25_INDEX_PATH,
    CHROMA_PATH,
    QueryRequest,
    RAGOrchestrator,
)
from src.utils.config import load_config


@pytest.fixture
def orchestrator() -> RAGOrchestrator:
    cfg_path = Path(__file__).resolve().parents[2] / "config.yaml"
    return RAGOrchestrator(load_config(str(cfg_path)))


def _save_minimal_bm25(path: Path) -> None:
    idx = BM25Index()
    idx.add_document("d1", "alpha beta gamma", {"source": "t.txt"})
    idx.save(str(path))


def test_session_scope_skips_missing_global_bm25(orchestrator: RAGOrchestrator, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.core.rag_orchestrator.BM25_INDEX_PATH",
        str(tmp_path / "nonexistent_global_bm25.json"),
    )
    sess_bm25 = tmp_path / "sess" / "bm25_index.json"
    sess_bm25.parent.mkdir(parents=True)
    _save_minimal_bm25(sess_bm25)
    sess_chroma = tmp_path / "sess" / "chroma"

    index, db, _qp, session_pair, effective = orchestrator._load_components(
        QueryRequest(
            query_text="q",
            knowledge_scope="session",
            session_bm25_index_path=str(sess_bm25),
            session_collection_name="sess_test",
            session_chroma_path=str(sess_chroma),
        )
    )

    assert effective == "session"
    assert session_pair is not None
    assert len(index.documents) == 0
    assert db._chroma_path == CHROMA_PATH
    s_idx, s_db = session_pair
    assert len(s_idx.documents) == 1
    assert s_db._chroma_path == str(sess_chroma)


def test_both_scope_downgrades_when_global_bm25_missing(
    orchestrator: RAGOrchestrator, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "src.core.rag_orchestrator.BM25_INDEX_PATH",
        str(tmp_path / "missing_global.json"),
    )
    sess_bm25 = tmp_path / "sess" / "bm25_index.json"
    sess_bm25.parent.mkdir(parents=True)
    _save_minimal_bm25(sess_bm25)

    index, _db, _qp, session_pair, effective = orchestrator._load_components(
        QueryRequest(
            query_text="q",
            knowledge_scope="both",
            session_bm25_index_path=str(sess_bm25),
            session_collection_name="sess_test",
            session_chroma_path=str(tmp_path / "sess" / "chroma"),
        )
    )

    assert effective == "session"
    assert session_pair is not None
    assert len(index.documents) == 0


def test_global_scope_still_loads_default_path(orchestrator: RAGOrchestrator):
    if not Path(BM25_INDEX_PATH).is_file():
        pytest.skip("Global BM25 fixture not present")
    index, db, _qp, session_pair, effective = orchestrator._load_components(
        QueryRequest(query_text="q", knowledge_scope="global")
    )
    assert effective == "global"
    assert session_pair is None
    assert len(index.documents) >= 0
    assert db._chroma_path == CHROMA_PATH


def test_global_scope_raises_when_index_missing(orchestrator: RAGOrchestrator, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.core.rag_orchestrator.BM25_INDEX_PATH",
        str(tmp_path / "nowhere.json"),
    )
    with pytest.raises(FileNotFoundError):
        orchestrator._load_components(QueryRequest(query_text="q", knowledge_scope="global"))
