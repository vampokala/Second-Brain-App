"""Plain UTF-8 source/config file extraction."""

from __future__ import annotations

from pathlib import Path

from src.core.supported_formats import is_iac_extension


def extract_code_or_config(path: Path | str) -> str:
    """Read a text source file; prefix IaC files for retrieval context."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if is_iac_extension(path.suffix):
        return f"IaC source:\n\n{text}"
    return text
