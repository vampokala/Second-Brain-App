"""
Observability layer for RAG pipeline instrumentation.
Provides decorators and context managers for LangFuse tracing.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

try:
    from langfuse import Langfuse as _Langfuse
except ImportError:
    _Langfuse = None

logger = logging.getLogger(__name__)


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
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Args:
            enabled: If False, all tracing is no-op (demo mode, tests)
            public_key: LangFuse public key (defaults to LANGFUSE_PUBLIC_KEY env var)
            secret_key: LangFuse secret key (defaults to LANGFUSE_SECRET_KEY env var)
        """
        self.enabled = enabled
        self.client: Any | None = None

        if self.enabled:
            if _Langfuse is None:
                logger.warning("langfuse package not installed; observability disabled")
                self.enabled = False
                return

            try:
                resolved_public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
                resolved_secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")

                if resolved_public_key and resolved_secret_key:
                    self.client = _Langfuse(
                        public_key=resolved_public_key,
                        secret_key=resolved_secret_key,
                        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
                    )
                    logger.info("LangFuse observability enabled")
                else:
                    self.enabled = False
                    logger.warning("LangFuse keys not found; observability disabled")
            except Exception as e:
                logger.error(f"Failed to initialize LangFuse: {e}; observability disabled")
                self.enabled = False

    @contextmanager
    def trace_request(
        self,
        name: str,
        query: str = "",
        metadata: Optional[Dict[str, Any]] = None,
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

        trace = self.client.trace(
            name=name,
            input={"query": query},
            metadata=metadata or {},
        )
        start = time.time()
        try:
            yield trace
        except Exception as e:
            trace.update(
                output={"error": str(e)},
                metadata={**(metadata or {}), "total_ms": (time.time() - start) * 1000},
            )
            raise
        finally:
            trace.update(
                metadata={**(metadata or {}), "total_ms": round((time.time() - start) * 1000, 2)},
            )

    @contextmanager
    def trace_step(
        self,
        trace,
        step_name: str,
        input_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for a child span within a request trace.
        Attach to the trace returned by trace_request().

        Args:
            trace: The top-level trace object from trace_request()
            step_name: Name of the pipeline step (e.g. "retrieval", "generation")
            input_data: Optional input metadata for this step
        """
        output: Dict[str, Any] = {}
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
        Flush pending traces to LangFuse in a background thread.
        Call this after the HTTP response is sent — never block the hot path.

        In FastAPI, use a BackgroundTask:
            from fastapi import BackgroundTasks
            background_tasks.add_task(observer.flush_async)
        """
        if not self.client:
            return
        import threading

        threading.Thread(target=self.client.flush, daemon=True).start()

    def flush(self) -> None:
        """Synchronous flush — only use in shutdown/test contexts, not request handlers."""
        if self.client:
            self.client.flush()


# Global observer instance
_observer_instance: Optional[RAGObserver] = None


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
