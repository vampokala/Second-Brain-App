from __future__ import annotations

import os
import threading
import time

from src.web import session_corpus


def test_get_or_create_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    sid = "abc123def456"
    a = session_corpus.get_or_create(sid)
    b = session_corpus.get_or_create(sid)
    assert a.session_id == sid
    assert b.upload_dir == a.upload_dir
    assert a.upload_dir.exists()
    assert a.chroma_path.exists()


def test_delete_session_missing_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    session_corpus.delete_session("missing")
    assert not (tmp_path / "missing").exists()


def test_janitor_sweep_evicts_ttl(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    monkeypatch.setenv("DOC_DEMO_SESSION_TTL", "1")
    sid = "ttl001"
    s = session_corpus.get_or_create(sid)
    old = time.time() - 10
    os.utime(s.upload_dir.parent / ".touched", (old, old))
    deleted = session_corpus.janitor_sweep(now=time.time())
    assert deleted >= 1
    assert not s.upload_dir.parent.exists()


def test_concurrent_get_or_create_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_DEMO_SESSION_ROOT", str(tmp_path))
    sid = "concur123456"
    errors: list[Exception] = []

    def _run():
        try:
            session_corpus.get_or_create(sid)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=_run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert (tmp_path / sid / "uploads").exists()
