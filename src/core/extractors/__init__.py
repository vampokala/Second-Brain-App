"""Format-specific text extractors for vault ingest."""

from __future__ import annotations

from pathlib import Path

from src.core.supported_formats import (
    TEXT_CODE_EXTENSIONS,
    VISION_EXTENSIONS,
    is_supported,
)

__all__ = ["extract_for_path"]


def extract_for_path(
    path: Path | str,
    *,
    vision_enabled: bool = False,
    vision_max_bytes: int = 5_000_000,
    vision_max_edge: int = 4096,
) -> str:
    """Extract plain text from a supported non-PDF/DOCX/HTML path."""
    file_path = Path(path)
    ext = file_path.suffix.lower()
    if not is_supported(ext, vision_enabled=vision_enabled):
        msg = f"Unsupported file type: {ext!r}"
        raise ValueError(msg)

    if ext in VISION_EXTENSIONS:
        from src.core.extractors.vision import prepare_image

        return prepare_image(
            file_path,
            vision_enabled=vision_enabled,
            vision_max_bytes=vision_max_bytes,
            vision_max_edge=vision_max_edge,
        )
    if ext in {".csv", ".tsv"}:
        from src.core.extractors.tabular import extract_csv

        return extract_csv(file_path)
    if ext in {".xlsx", ".xlsm"}:
        from src.core.extractors.tabular import extract_xlsx

        return extract_xlsx(file_path)
    if ext == ".pptx":
        from src.core.extractors.pptx import extract_pptx

        return extract_pptx(file_path)
    if ext == ".ipynb":
        from src.core.extractors.notebook import extract_ipynb

        return extract_ipynb(file_path)
    if ext in TEXT_CODE_EXTENSIONS:
        from src.core.extractors.code_text import extract_code_or_config

        return extract_code_or_config(file_path)
    msg = f"No extractor registered for extension: {ext!r}"
    raise ValueError(msg)
