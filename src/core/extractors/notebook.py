"""Jupyter .ipynb → plain text (sources + capped stream output)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_OUTPUT_LINES = 40


def _source_to_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part for part in value if isinstance(part, str))
    return str(value)


def _append_capped_lines(
    out: list[str],
    text: str,
    lines_used: int,
    max_lines: int,
) -> int:
    for line in text.splitlines():
        if lines_used >= max_lines:
            out.append("… [output truncated]")
            return lines_used
        out.append(line)
        lines_used += 1
    return lines_used


def extract_ipynb(path: Path | str, *, output_lines: int = _DEFAULT_OUTPUT_LINES) -> str:
    """Extract notebook cells with capped stdout/stderr output."""
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    cells = raw.get("cells") or []
    sections: list[str] = []
    for index, cell in enumerate(cells, start=1):
        cell_type = str(cell.get("cell_type") or "unknown")
        section = [f"### Cell {index} ({cell_type})", _source_to_string(cell.get("source"))]
        outputs = cell.get("outputs") or []
        if cell_type == "code" and outputs:
            section.append("")
            section.append("#### Output (capped)")
            lines_used = 0
            output_lines_buf: list[str] = []
            for output in outputs:
                if lines_used >= output_lines:
                    break
                text_value = output.get("text")
                if text_value is None:
                    continue
                text = _source_to_string(text_value)
                lines_used = _append_capped_lines(output_lines_buf, text, lines_used, output_lines)
            section.extend(output_lines_buf)
        sections.append("\n".join(section))
    return "\n\n".join(sections).strip()
