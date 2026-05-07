"""HF Spaces entrypoint.

Bootstraps sample documents on cold-start, starts the FastAPI server in
a background thread (HF Spaces runs a single process), then delegates
to the Streamlit UI.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO)

# Ensure repo root is importable regardless of where HF Spaces runs this.
_repo_root = Path(__file__).parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Set demo mode so the UI shows the banner and disables uploads.
os.environ.setdefault("DOC_PROFILE", "demo")

# Disable auth so the demo doesn't require an API key header.
os.environ.setdefault("DOC_API_KEYS", "demo-key")

# No local Ollama daemon on Spaces — use sentence-transformers for embeddings.
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("DOC_EMBEDDING_PROVIDER", "sentence_transformers")
os.environ.setdefault("DOC_DEMO_UPLOADS", "1")
os.environ.setdefault("DOC_DEMO_SESSION_ROOT", "/tmp/doc-ingest-sessions")
os.environ.setdefault("DOC_DEMO_MAX_FILES", "3")
os.environ.setdefault("DOC_DEMO_MAX_FILE_MB", "3")
os.environ.setdefault("DOC_DEMO_MAX_SESSION_MB", "8")
os.environ.setdefault("DOC_DEMO_SESSION_TTL", "1800")

# Bootstrap sample documents on first run.
from spaces.bootstrap_demo import bootstrap_if_needed  # noqa: E402

bootstrap_if_needed()


def _start_api() -> None:
    """Run the FastAPI server in a background daemon thread."""
    import uvicorn  # type: ignore[import-untyped]
    from src.api.main import app as fastapi_app  # noqa: E402

    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")


def _wait_for_api_ready(timeout_seconds: float = 20.0) -> bool:
    """Poll the local health endpoint until API is ready or timeout elapses."""
    deadline = time.time() + timeout_seconds
    url = "http://127.0.0.1:8000/health"
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=1.5)
            if resp.ok:
                logging.info("FastAPI ready on %s", url)
                return True
        except Exception:
            pass
        time.sleep(0.5)
    logging.warning("FastAPI did not become ready within %.1f seconds", timeout_seconds)
    return False


_api_thread = threading.Thread(target=_start_api, daemon=True)
_api_thread.start()

# Wait for API readiness, but keep demo UI available even if API startup is slow.
_wait_for_api_ready()

# Hand off to the main Streamlit app.
from src.web.streamlit_app import main  # noqa: E402

main()
