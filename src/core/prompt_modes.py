"""Grounding-mode instructions for chat (corpus / web / general)."""

from __future__ import annotations


def mode_instructions(
    grounding_mode: str,
    include_web: bool,
    hit_count: int,
    has_web: bool,
) -> str:
    """Four variants mirroring Lite ``mode_block``.

    ``grounding_mode`` is ``corpus_only`` or ``allow_general``.
    Corpus-only maps to Lite's wiki-sources-only path.
    """
    corpus = grounding_mode != "allow_general"
    if corpus and not include_web:
        extra = ""
        if hit_count == 0:
            extra = (
                "\nNo knowledge excerpts were retrieved — say clearly that the vault did not "
                "surface matches; do not invent vault-specific facts.\n"
            )
        return (
            "Answer using the **retrieved knowledge excerpts**. Ground vault-specific "
            f"statements in those excerpts.{extra}"
        )
    if corpus and include_web:
        web_label = "yes" if has_web else "none"
        return (
            "You have **two** evidence types: (1) **Retrieved knowledge excerpts** — ground "
            "vault-specific statements here; (2) **Web search results** — ground statements "
            "about the wider web here. Never attribute web-only facts to the vault, or "
            f"vault-only facts to the web. Label provenance when it matters. "
            f"Corpus hits this turn: {hit_count}. Web pages fetched: {web_label}."
        )
    if not corpus and include_web:
        web_label = "yes" if has_web else "none"
        return (
            "Corpus retrieval is **off** for this message; use **Web search results**. "
            f"Do not claim content came from vault files. Web pages fetched: {web_label}."
        )
    return (
        "For this message the user disabled **corpus retrieval** and **web search**. "
        "Do not pretend answers came from retrieved vault pages or fetched web pages. "
        "You may help with general reasoning, drafting, or tasks that do not require "
        "vault-specific or live-web grounding."
    )
