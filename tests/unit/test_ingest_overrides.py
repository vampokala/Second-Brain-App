from __future__ import annotations

import src.ingest as ingest_mod


class _FakeProcessor:
    def process_document(self, _path: str):
        return {
            "chunks": ["chunk one"],
            "metadata": {"title": "doc.md"},
        }


class _FakeDB:
    def __init__(self, mode: str, chroma_path: str):
        self.mode = mode
        self.chroma_path = chroma_path
        self.collections: list[str] = []
        self.added: list[tuple[str, list[dict]]] = []

    def create_collection(self, name: str):
        self.collections.append(name)

    def add_documents(self, collection_name: str, docs: list[dict]):
        self.added.append((collection_name, docs))

    def query_documents(self, collection_name: str, query_text: str, top_k: int = 5):
        return []


def test_ingest_respects_override_paths(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("hello world", encoding="utf-8")

    saved_paths: list[str] = []

    def _fake_save(self, path: str):
        saved_paths.append(path)

    monkeypatch.setattr(ingest_mod.BM25Index, "save", _fake_save)
    monkeypatch.setattr(ingest_mod, "VectorDatabase", _FakeDB)

    bm25_path = tmp_path / "custom" / "bm25.json"
    chroma_path = tmp_path / "custom" / "chroma"
    ingest_mod.ingest(
        str(docs),
        bm25_index_path=str(bm25_path),
        collection_name="sess_abc",
        chroma_path=str(chroma_path),
        processor=_FakeProcessor(),
    )
    assert saved_paths[-1] == str(bm25_path)


def test_ingest_defaults_still_work(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("hello world", encoding="utf-8")
    saved_paths: list[str] = []

    def _fake_save(self, path: str):
        saved_paths.append(path)

    monkeypatch.setattr(ingest_mod.BM25Index, "save", _fake_save)
    monkeypatch.setattr(ingest_mod, "VectorDatabase", _FakeDB)
    ingest_mod.ingest(str(docs), processor=_FakeProcessor())
    assert saved_paths[-1] == ingest_mod.BM25_INDEX_PATH
