"""Persisted app settings (Postgres JSONB), env wins on conflicts."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.key_validator import validate_key
from src.api.llm_settings_overlay import apply_patch, boot_env_has, lock_was_captured
from src.api.settings_secrets import (
    ENV_PLAIN,
    ENV_WINS,
    extract_secret,
    hydrate_env_from_rows,
    hydrate_env_from_value,
    is_secret_setting_key,
    mask_secret,
    wrap_secret,
)
from src.core.personas import all_personas, student_grade_options
from src.db.models import AppSetting
from src.db.session import get_async_session

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    values: dict[str, Any]
    env_override_keys: list[str]


class SettingsUpdate(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)
    test_provider: str | None = None


class PersonasResponse(BaseModel):
    personas: list[dict[str, str]]
    grades: list[dict[str, str]]


def _mask_value(key: str, value: Any) -> Any:
    if not is_secret_setting_key(key):
        return value
    secret = extract_secret(value)
    if secret is None:
        return value
    return mask_secret(secret)


@router.get("/personas", response_model=PersonasResponse)
async def list_personas() -> PersonasResponse:
    return PersonasResponse(
        personas=[{"id": p.id, "label": p.label} for p in all_personas()],
        grades=[{"id": g.id, "label": g.label} for g in student_grade_options()],
    )


def _env_override_keys() -> list[str]:
    keys: list[str] = []
    for setting_key, env_name in ENV_WINS.items():
        if os.getenv(env_name):
            keys.append(setting_key)
    for setting_key, env_name in ENV_PLAIN.items():
        if boot_env_has(env_name):
            keys.append(setting_key)
    return sorted(set(keys))


def _is_env_locked_setting(setting_key: str) -> bool:
    """True when Docker/host env must win over a Settings PATCH."""
    env_name = ENV_WINS.get(setting_key) or ENV_PLAIN.get(setting_key)
    if not env_name:
        return False
    if boot_env_has(env_name):
        return True
    if lock_was_captured():
        # After startup lock: DB-hydrated values may be updated from the UI.
        return False
    return bool(os.getenv(env_name))


@router.get("", response_model=SettingsResponse)
async def get_settings(session: AsyncSession = Depends(get_async_session)) -> SettingsResponse:
    if not os.getenv("DATABASE_URL", "").strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL required.")
    res = await session.execute(select(AppSetting))
    rows = {r.key: r.value for r in res.scalars().all()}
    out: dict[str, Any] = {k: _mask_value(k, v) for k, v in rows.items()}
    for k, env in ENV_WINS.items():
        if os.getenv(env):
            out[k] = mask_secret(os.getenv(env) or "")
    for k, env in ENV_PLAIN.items():
        if boot_env_has(env) or k not in out and os.getenv(env):
            out[k] = os.getenv(env) or ""
    return SettingsResponse(values=out, env_override_keys=_env_override_keys())


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> SettingsResponse:
    if not os.getenv("DATABASE_URL", "").strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL required.")
    if body.test_provider:
        key_entry = body.patch.get(f"{body.test_provider}_api_key")
        key_str = extract_secret(key_entry) or ""
        ok, msg = await validate_key(body.test_provider, key_str)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

    existing_rows = await session.execute(select(AppSetting).where(AppSetting.key.in_(list(body.patch.keys()))))
    existing_map = {r.key: r.value for r in existing_rows.scalars().all()}
    applied: dict[str, Any] = {}

    for k, v in body.patch.items():
        if _is_env_locked_setting(k):
            continue
        if is_secret_setting_key(k):
            v = wrap_secret(v)
            hydrate_env_from_value(k, v, force=True)
        elif k in ENV_PLAIN:
            v = str(v or "").strip()
            hydrate_env_from_value(k, v, force=True)
        elif isinstance(v, dict) and isinstance(existing_map.get(k), dict):
            # Nested maps (e.g. default_model_by_provider): merge incrementally.
            merged = dict(existing_map[k])
            merged.update(v)
            v = merged
        session.merge(AppSetting(key=k, value=json.loads(json.dumps(v))))
        applied[k] = v
    await session.commit()
    if applied:
        apply_patch(applied)
    return await get_settings(session)


async def hydrate_secrets_from_db() -> list[str]:
    """Load secrets from app_settings into os.environ (skip keys already in env)."""
    if not os.getenv("DATABASE_URL", "").strip():
        return []
    from src.api.llm_settings_overlay import lock_existing_env
    from src.db.session import async_session_factory

    lock_existing_env()
    factory = async_session_factory()
    async with factory() as session:
        res = await session.execute(select(AppSetting))
        rows = {r.key: r.value for r in res.scalars().all()}
    return hydrate_env_from_rows(rows)
