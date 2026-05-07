"""Unit tests for observability module."""

from src.core.observability import RAGObserver, get_observer, init_observer


def test_observer_disabled_noop_on_trace_request():
    """Verify trace_request is a no-op when disabled — yields None."""
    observer = RAGObserver(enabled=False)

    with observer.trace_request("rag_query", query="test") as trace:
        assert trace is None  # no-op when disabled


def test_observer_disabled_noop_on_trace_step():
    """Verify trace_step yields empty dict when trace is None (disabled path)."""
    observer = RAGObserver(enabled=False)

    with observer.trace_step(None, "retrieval", {"query": "x"}) as output:
        output["chunks"] = 3  # should not raise
    assert output["chunks"] == 3  # returned value preserved even when disabled


def test_trace_step_records_latency():
    """Verify trace_step always populates latency_ms in the output dict."""
    observer = RAGObserver(enabled=False)

    with observer.trace_step(None, "generation") as output:
        output["provider"] = "anthropic"

    assert "latency_ms" in output
    assert output["latency_ms"] >= 0
    assert output["provider"] == "anthropic"


def test_nested_trace_and_step_no_exception():
    """Verify trace_request + trace_step nesting works without LangFuse keys."""
    observer = RAGObserver(enabled=False)

    with observer.trace_request("rag_query", query="hello") as trace:
        with observer.trace_step(trace, "retrieval") as s:
            s["chunks_retrieved"] = 5
        with observer.trace_step(trace, "generation") as s:
            s["provider"] = "ollama"
    # No exception = pass


def test_observer_singleton_getter():
    """Verify get_observer() returns singleton instance."""
    init_observer(enabled=False)
    obs1 = get_observer()
    obs2 = get_observer()
    assert obs1 is obs2


def test_observer_flush_async_no_exception():
    """Verify flush_async doesn't raise when client is None."""
    observer = RAGObserver(enabled=False)
    observer.flush_async()  # Should not raise


def test_observer_flush_no_exception():
    """Verify flush doesn't raise when client is None."""
    observer = RAGObserver(enabled=False)
    observer.flush()  # Should not raise
