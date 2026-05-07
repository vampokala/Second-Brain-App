'''
- Structured logging with JSON format
- Performance metrics collection (delegates to src.monitoring.metrics)
- Error tracking and alerting
- Request/response logging
'''
import contextlib
import json
import logging
import time
from typing import Any, Dict, Iterator, Optional

from src.monitoring.metrics import get_metrics_collector


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_record.update(record.extra)
        return json.dumps(log_record)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class MetricsCollector:
    """
    Deprecated: use src.monitoring.metrics.MetricsCollector instead.
    This class now delegates to the new metrics collector for backward compatibility.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, list] = {}
        self._new_collector = get_metrics_collector()

    def record(self, name: str, value: float) -> None:
        self._metrics.setdefault(name, []).append(value)

    def summary(self) -> Dict[str, Dict[str, float]]:
        result = {}
        for name, values in self._metrics.items():
            result[name] = {
                "count": len(values),
                "total": sum(values),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }
        return result


metrics = MetricsCollector()


@contextlib.contextmanager
def track_duration(operation: str, logger: Optional[logging.Logger] = None) -> Iterator[None]:
    """Context manager that measures wall-clock duration and records it."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        metrics.record(operation, elapsed)
        if logger:
            _log_extra(
                logger,
                logging.DEBUG,
                f"{operation} completed",
                {"duration_seconds": round(elapsed, 4), "operation": operation},
            )


def log_request(logger: logging.Logger, method: str, path: str, extra: Optional[Dict] = None) -> None:
    payload = {"event": "request", "method": method, "path": path}
    if extra:
        payload.update(extra)
    _log_extra(logger, logging.INFO, f"{method} {path}", payload)


def log_response(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
    extra: Optional[Dict] = None,
) -> None:
    payload = {
        "event": "response",
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_seconds": round(duration_seconds, 4),
    }
    if extra:
        payload.update(extra)
    level = logging.WARNING if status_code >= 400 else logging.INFO
    _log_extra(logger, level, f"{method} {path} -> {status_code}", payload)


def log_error(
    logger: logging.Logger,
    message: str,
    exc: Optional[BaseException] = None,
    extra: Optional[Dict] = None,
) -> None:
    payload: Dict[str, Any] = {"event": "error"}
    if extra:
        payload.update(extra)
    logger.error(message, exc_info=exc, stack_info=exc is not None)
    if payload:
        _log_extra(logger, logging.ERROR, message, payload)


# --- internal helper ---

def _log_extra(logger: logging.Logger, level: int, message: str, extra: Dict) -> None:
    record = logger.makeRecord(
        logger.name, level, "(unknown)", 0, message, (), None
    )
    record.extra = extra  # type: ignore[attr-defined]
    logger.handle(record)
