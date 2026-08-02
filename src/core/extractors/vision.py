"""Raster image placeholder text for vision-gated ingest (v1: no LLM caption)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = 5_000_000
_DEFAULT_MAX_EDGE = 4096


def _image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
    except ImportError:
        logger.debug("pillow_unavailable path=%s", path)
        return None
    try:
        with Image.open(path) as img:
            return img.size
    except OSError as exc:
        logger.warning("image_open_failed path=%s error=%s", path, exc)
        return None


def prepare_image(
    path: Path | str,
    *,
    vision_enabled: bool,
    vision_max_bytes: int = _DEFAULT_MAX_BYTES,
    vision_max_edge: int = _DEFAULT_MAX_EDGE,
) -> str:
    """Return chunkable placeholder text or a skip message for raster images."""
    path = Path(path)
    name = path.name
    if not vision_enabled:
        return f"[image skipped: vision ingest disabled — {name}]"

    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        logger.warning("image_stat_failed path=%s error=%s", path, exc)
        return f"[image skipped: unreadable file — {name}]"

    if size_bytes > vision_max_bytes:
        return f"[image skipped: exceeds vision_max_bytes " f"({size_bytes} > {vision_max_bytes}) — {name}]"

    dims = _image_dimensions(path)
    if dims is None:
        return f"[image skipped: could not read dimensions — {name}]"

    width, height = dims
    if width > vision_max_edge or height > vision_max_edge:
        return f"[image skipped: exceeds vision_max_edge " f"({width}x{height} > {vision_max_edge}px) — {name}]"

    return f"[image: {name} {width}x{height}]"
