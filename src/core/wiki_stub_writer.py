"""Write idempotent wiki source stubs after raw/ markdown ingest."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path

import frontmatter

_section_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _section_lock(section: str) -> asyncio.Lock:
    async with _locks_guard:
        if section not in _section_locks:
            _section_locks[section] = asyncio.Lock()
        return _section_locks[section]


_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _derive_title(raw_path: Path, body_for_scan: str) -> str:
    m = _H1_RE.search(body_for_scan or "")
    if m:
        return m.group(1).strip()
    return raw_path.stem.replace("_", " ").strip() or raw_path.name


def _first_paragraph_summary(text: str, max_len: int = 160) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    para = re.split(r"\n\s*\n", s, maxsplit=1)[0]
    para = " ".join(para.split())
    if len(para) <= max_len:
        return para
    return para[: max_len - 1].rstrip() + "…"


def _stub_path_for_raw(vault_path: Path, raw_relpath: str) -> Path:
    rel = raw_relpath.replace("\\", "/").lstrip("/")
    if not rel.lower().startswith("raw/"):
        raise ValueError("stub writer expects paths under raw/")
    inner = rel[4:]  # strip raw/
    parts = Path(inner).parts
    section = parts[0].lower() if parts else "sources"
    filename = Path(inner).name
    if not filename.lower().endswith(".md"):
        filename = f"{Path(filename).stem}.md"
    return vault_path / "wiki" / "sources" / section / filename


async def write_stub(raw_path: Path, vault_path: Path, summary: str) -> Path:
    """Idempotent: re-writing is a no-op unless content changed.

    Skips if existing stub no longer has ``auto: true`` (human-expanded).
    Uses per-section asyncio.Lock for concurrent safety.
    """
    raw_path = raw_path.resolve()
    vault_path = vault_path.resolve()
    try:
        raw_relpath = str(raw_path.relative_to(vault_path)).replace("\\", "/")
    except ValueError as exc:
        raise ValueError("raw_path must be inside vault_path") from exc

    stub_path = _stub_path_for_raw(vault_path, raw_relpath)
    section = stub_path.parent.name

    body_only = ""
    title = ""
    if raw_path.suffix.lower() == ".md":
        body_scan = await asyncio.to_thread(raw_path.read_text, encoding="utf-8", errors="replace")
        fm_raw = frontmatter.loads(body_scan)
        body_only = fm_raw.content or ""
        title = str(fm_raw.metadata.get("title") or "") or _derive_title(raw_path, body_only)
    else:
        title = _derive_title(raw_path, "")
    today = date.today().isoformat()
    one_line = _first_paragraph_summary(summary or body_only)
    if not one_line:
        ext = raw_path.suffix.lstrip(".").upper() or "FILE"
        one_line = f"Ingested {ext} source."

    lock = await _section_lock(section)
    async with lock:

        def _write_sync() -> Path:
            stub_path.parent.mkdir(parents=True, exist_ok=True)
            created = today
            if stub_path.is_file():
                existing = frontmatter.load(stub_path)
                meta = dict(existing.metadata or {})
                if meta.get("auto") is not True:
                    return stub_path
                prev_created = meta.get("created")
                if isinstance(prev_created, str) and prev_created.strip():
                    created = prev_created.strip()
                new_body = (
                    f"> Auto-generated stub. Run `ingest <file>` in Claude to expand.\n\n"
                    f"**One-line summary**: {one_line}\n"
                )
                same = (
                    meta.get("title") == title
                    and meta.get("updated") == today
                    and (existing.content or "").strip() == new_body.strip()
                    and meta.get("sources") == [raw_relpath]
                )
                if same:
                    return stub_path

            post = frontmatter.Post(
                "\n".join(
                    [
                        f"> Auto-generated stub. Run `ingest <file>` in Claude to expand.",
                        "",
                        f"**One-line summary**: {one_line}",
                        "",
                    ]
                ),
            )
            post.metadata = {
                "title": title,
                "type": "source",
                "created": created,
                "updated": today,
                "sources": [raw_relpath],
                "section": section,
                "auto": True,
                "tags": ["auto-ingested"],
            }
            stub_path.write_text(frontmatter.dumps(post), encoding="utf-8")
            return stub_path

        return await asyncio.to_thread(_write_sync)
