"""Bootstrap script for HF Spaces cold-start.

Run once before launching the Streamlit app to ensure sample documents
are ingested into Chroma + BM25 if the index is not already present.

Called from spaces/app.py at import time.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("spaces.bootstrap")


def bootstrap_if_needed() -> None:
    """Ingest sample documents if the vector index does not yet exist."""
    index_marker = Path("data/embeddings/bm25_index.json")
    if index_marker.exists():
        logger.info("Index already exists — skipping bootstrap")
        return

    sample_dir = Path("data/sample")
    if not sample_dir.exists() or not list(sample_dir.glob("*.md")):
        logger.warning("No sample documents found at data/sample/ — skipping bootstrap")
        return

    logger.info("Running demo bootstrap: ingesting sample documents...")
    try:
        # Ensure the repo root is on the path when running from spaces/
        repo_root = Path(__file__).parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        from src.ingest import ingest  # type: ignore[import-untyped]

        ingest(str(sample_dir))
        logger.info("Bootstrap complete — sample documents ingested")
    except Exception as exc:
        logger.error("Bootstrap failed: %s", exc)
        # Non-fatal: the app can still start, just with empty results.
