"""Load chat-related prefs from app_settings JSONB rows."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.settings_secrets import extract_secret
from src.core.chat_orchestrator import ChatPersonaPrefs
from src.core.personas import (
    DEFAULT_CHAT_PERSONA,
    DEFAULT_STUDENT_GRADE,
    normalize_chat_persona,
    resolved_student_grade_token,
)
from src.db.models import AppSetting


async def load_settings_map(session: AsyncSession) -> dict[str, Any]:
    res = await session.execute(select(AppSetting))
    return {r.key: r.value for r in res.scalars().all()}


def _str_setting(rows: dict[str, Any], key: str, default: str = "") -> str:
    val = rows.get(key)
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and "secret" in val:
        return extract_secret(val) or default
    if val is None:
        return default
    return str(val)


def _bool_setting(rows: dict[str, Any], key: str, default: bool = False) -> bool:
    val = rows.get(key)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "on"}
    return default


def persona_prefs_from_rows(rows: dict[str, Any]) -> ChatPersonaPrefs:
    persona_id = normalize_chat_persona(_str_setting(rows, "chat_persona", DEFAULT_CHAT_PERSONA))
    grade = resolved_student_grade_token(_str_setting(rows, "student_grade", DEFAULT_STUDENT_GRADE))
    addon = _str_setting(rows, "persona_prompt_addon", "") or None
    memory_on = _bool_setting(rows, "rolling_memory_enabled", True)
    return ChatPersonaPrefs(
        persona_id=persona_id,
        student_grade=grade,
        addon=addon,
        rolling_memory_enabled=memory_on,
    )


def brave_api_key_from_rows(rows: dict[str, Any]) -> str | None:
    env = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if env:
        return env
    return extract_secret(rows.get("brave_search_api_key")) or _str_setting(rows, "brave_search_api_key") or None


def vision_enabled_from_rows(rows: dict[str, Any]) -> bool:
    if os.getenv("VISION_INGEST_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        return True
    return _bool_setting(rows, "vision_ingest_enabled", False)
