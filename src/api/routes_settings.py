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
from src.db.models import AppSetting
from src.db.session import get_async_session

router = APIRouter(prefix="/settings", tags=["settings"])

_ENV_WINS = {
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
}


class SettingsResponse(BaseModel):
    values: dict[str, Any]
    env_override_keys: list[str]


class SettingsUpdate(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)
    test_provider: str | None = None


def _mask_secret(val: str) -> str:
    if len(val) <= 4:
        return "****"
    return "****" + val[-4:]


@router.get("", response_model=SettingsResponse)
async def get_settings(session: AsyncSession = Depends(get_async_session)) -> SettingsResponse:
    if not os.getenv("DATABASE_URL", "").strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL required.")
    res = await session.execute(select(AppSetting))
    rows = {r.key: r.value for r in res.scalars().all()}
    out: dict[str, Any] = {}
    for k, v in rows.items():
        if k.endswith("_api_key") and isinstance(v, dict) and "secret" in v:
            out[k] = _mask_secret(str(v.get("secret") or ""))
        elif k.endswith("_api_key") and isinstance(v, str):
            out[k] = _mask_secret(v)
        else:
            out[k] = v
    env_keys: list[str] = []
    for k, env in _ENV_WINS.items():
        if os.getenv(env):
            env_keys.append(k)
            out[k] = _mask_secret(os.getenv(env) or "")
    return SettingsResponse(values=out, env_override_keys=env_keys)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> SettingsResponse:
    if not os.getenv("DATABASE_URL", "").strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL required.")
    if body.test_provider:
        key_entry = body.patch.get(f"{body.test_provider}_api_key")
        key_str = ""
        if isinstance(key_entry, dict):
            key_str = str(key_entry.get("secret") or "")
        elif isinstance(key_entry, str):
            key_str = key_entry
        ok, msg = await validate_key(body.test_provider, key_str)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
    existing_rows = await session.execute(select(AppSetting).where(AppSetting.key.in_(list(body.patch.keys()))))
    existing_map = {r.key: r.value for r in existing_rows.scalars().all()}
    for k, v in body.patch.items():
        if k in _ENV_WINS and os.getenv(_ENV_WINS[k]):
            continue
        if k.endswith("_api_key") and not isinstance(v, dict):
            v = {"secret": v}
        # For nested settings maps (e.g., default_model_by_provider), merge incrementally
        # so callers can patch one provider without clobbering existing entries.
        if isinstance(v, dict) and isinstance(existing_map.get(k), dict):
            merged = dict(existing_map[k])
            merged.update(v)
            v = merged
        session.merge(AppSetting(key=k, value=json.loads(json.dumps(v))))
    await session.commit()
    return await get_settings(session)
