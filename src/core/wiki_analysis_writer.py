"""Save chat answers as wiki analysis notes."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from pathlib import Path

from src.core.log_appender import append_log

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_INDEX_SECTION = "## Analyses"


def slug_from_title(title: str) -> str:
    raw = (title or "").strip().lower()
    slug = _SLUG_RE.sub("-", raw).strip("-")
    return slug or "analysis"


def _unique_path(analyses_dir: Path, slug: str) -> Path:
    candidate = analyses_dir / f"{slug}.md"
    if not candidate.exists():
        return candidate
    for i in range(2, 1000):
        alt = analyses_dir / f"{slug}-{i}.md"
        if not alt.exists():
            return alt
    return analyses_dir / f"{slug}-{date.today().strftime('%Y%m%d')}.md"


def _yaml_dump(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}: {json.dumps(value)}")
        elif isinstance(value, str):
            escaped = value.replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _ensure_analyses_index(index_path: Path, title: str, rel_link: str) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if not index_path.is_file():
        index_path.write_text(f"# Wiki index\n\n{_INDEX_SECTION}\n\n", encoding="utf-8")
    text = index_path.read_text(encoding="utf-8", errors="replace")
    bullet = f"- [{title}]({rel_link})"
    if bullet in text:
        return
    if _INDEX_SECTION not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n{_INDEX_SECTION}\n\n{bullet}\n"
    else:
        parts = text.split(_INDEX_SECTION, 1)
        rest = parts[1]
        text = parts[0] + _INDEX_SECTION + f"\n\n{bullet}" + rest
        if not text.endswith("\n"):
            text += "\n"
    index_path.write_text(text, encoding="utf-8")


async def save_answer_to_wiki(
    *,
    vault_path: Path,
    title: str,
    body_markdown: str,
    sources: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Write ``wiki/analyses/{slug}.md``, update index, append log. Return vault-relative path."""
    vault = vault_path.resolve()
    analyses = vault / "wiki" / "analyses"
    clean_title = (title or "").strip() or "Chat analysis"
    slug = slug_from_title(clean_title)
    today = date.today().isoformat()
    src_list = list(sources or [])
    tag_list = list(tags or ["chat-export"])

    def _write_sync() -> str:
        analyses.mkdir(parents=True, exist_ok=True)
        path = _unique_path(analyses, slug)
        meta = {
            "title": clean_title,
            "type": "analysis",
            "created": today,
            "updated": today,
            "sources": src_list,
            "tags": tag_list,
        }
        content = f"{_yaml_dump(meta)}\n\n{(body_markdown or '').strip()}\n"
        path.write_text(content, encoding="utf-8")
        rel = str(path.relative_to(vault)).replace("\\", "/")
        index_path = vault / "wiki" / "index.md"
        link = f"analyses/{path.name}"
        _ensure_analyses_index(index_path, clean_title, link)
        return rel

    relpath = await asyncio.to_thread(_write_sync)
    await append_log(vault, relpath, kind="chat-export")
    return relpath
