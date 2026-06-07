"""
Observability layer for RAG pipeline instrumentation.
Provides decorators and context managers for LangSmith tracing.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any

try:
    from langsmith import Client as _LangSmithClient
    from langsmith.run_trees import RunTree as _LangSmithRunTree
except ImportError:
    _LangSmithClient = None
    _LangSmithRunTree = None

logger = logging.getLogger(__name__)


class _LangSmithTrace:
    """Small adapter that exposes span/update methods used by the orchestrator."""

    def __init__(self, run: Any):
        self._run = run
        self._ended = False

    def span(self, name: str, input: dict[str, Any] | None = None):
        child = self._run.create_child(
            name=name,
            run_type="tool",
            inputs=input or {},
        )
        child.post()
        return _LangSmithTrace(child)

    def update(
        self,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._ended:
            return
        self._run.end(outputs=output or {}, extra={"metadata": metadata or {}})
        self._run.patch()
        self._ended = True

    def end(
        self,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.update(output=output, metadata=metadata)


class RAGObserver:
    """
    Centralized observer for RAG pipeline.
    Manages LangFuse client and provides tracing context managers.

    Usage pattern — instrument inside RAGOrchestrator.run(), not in main.py:
        with observer.trace_request("rag_query", query=query_text) as trace:
            with observer.trace_step(trace, "retrieval") as span:
                result = hybrid_retriever.retrieve(...)
                span["output"] = {"chunks": len(result)}
    """

    def __init__(
        self,
        enabled: bool = True,
        api_key: str | None = None,
    ):
        """
        Args:
            enabled: If False, all tracing is no-op (demo mode, tests)
            api_key: LangSmith API key (defaults to LANGCHAIN_API_KEY env var)
        """
        self.enabled = enabled
        self.client: Any | None = None

        if self.enabled:
            if _LangSmithClient is None or _LangSmithRunTree is None:
                logger.warning("langsmith package not installed; observability disabled")
                self.enabled = False
                return

            try:
                resolved_api_key = (api_key or os.getenv("LANGCHAIN_API_KEY") or "").strip()
                if resolved_api_key:
                    self.client = _LangSmithClient(
                        api_key=resolved_api_key,
                        api_url=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
                    )
                    logger.info("LangSmith observability enabled")
                else:
                    self.enabled = False
                    logger.warning("LANGCHAIN_API_KEY not found; observability disabled")
            except Exception as e:
                logger.error(f"Failed to initialize LangSmith: {e}; observability disabled")
                self.enabled = False

    @contextmanager
    def trace_request(
        self,
        name: str,
        query: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        """
        Context manager for a top-level request trace.
        One trace per query request — child spans live inside this.

        IMPORTANT: This is the top-level trace object. Use trace.span() for
        individual pipeline steps. Never call client.trace() per step — that
        creates disconnected traces in the LangFuse UI.

        Usage:
            with observer.trace_request("rag_query", query=query_text) as trace:
                with observer.trace_step(trace, "retrieval") as span:
                    chunks = retriever.retrieve(query)
                    span["chunks_retrieved"] = len(chunks)
        """
        if not self.enabled or not self.client:
            yield None
            return

        project_name = (os.getenv("LANGCHAIN_PROJECT") or "default").strip() or "default"
        trace = _LangSmithRunTree(
            name=name,
            run_type="chain",
            inputs={"query": query},
            extra={"metadata": metadata or {}},
            project_name=project_name,
            client=self.client,
        )
        trace.post()
        trace_adapter = _LangSmithTrace(trace)
        start = time.time()
        try:
            yield trace_adapter
        except Exception as e:
            trace_adapter.update(
                output={"error": str(e)},
                metadata={**(metadata or {}), "total_ms": (time.time() - start) * 1000},
            )
            raise
        finally:
            trace_adapter.update(
                metadata={**(metadata or {}), "total_ms": round((time.time() - start) * 1000, 2)},
            )

    @contextmanager
    def trace_step(
        self,
        trace,
        step_name: str,
        input_data: dict[str, Any] | None = None,
    ):
        """
        Context manager for a child span within a request trace.
        Attach to the trace returned by trace_request().

        Args:
            trace: The top-level trace object from trace_request()
            step_name: Name of the pipeline step (e.g. "retrieval", "generation")
            input_data: Optional input metadata for this step
        """
        output: dict[str, Any] = {}
        start = time.time()

        if not self.enabled or trace is None:
            try:
                yield output
            finally:
                output["latency_ms"] = round((time.time() - start) * 1000, 2)
            return

        span = trace.span(name=step_name, input=input_data or {})
        try:
            yield output
        except Exception as e:
            span.end(
                output={"error": str(e)},
                metadata={"latency_ms": round((time.time() - start) * 1000, 2)},
            )
            raise
        finally:
            output["latency_ms"] = round((time.time() - start) * 1000, 2)
            span.end(output=output)

    def flush_async(self) -> None:
        """
        LangSmith posts runs eagerly; no explicit flush is required.
        Kept as a no-op to preserve call sites.
        """
        return

    def flush(self) -> None:
        """No-op for LangSmith-backed observer."""
        return


# Global observer instance
_observer_instance: RAGObserver | None = None


def get_observer() -> RAGObserver:
    """Singleton getter for RAGObserver."""
    global _observer_instance
    if _observer_instance is None:
        enabled = os.getenv("DOC_PROFILE") != "demo"
        _observer_instance = RAGObserver(enabled=enabled)
    return _observer_instance


def init_observer(enabled: bool = True) -> RAGObserver:
    """Initialize the observer (useful for testing)."""
    global _observer_instance
    _observer_instance = RAGObserver(enabled=enabled)
    return _observer_instance
