"""Rolling memory read / paste rollup."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.api.models_chats import MemoryResponse, MemoryUpdateResponse
from src.core.rolling_memory import load_memory_excerpt, memory_path, roll_up_from_text
from src.utils.config import load_config
from src.utils.sb_env import load_second_brain_settings

router = APIRouter(tags=["memory"])


class MemoryRollupBody(BaseModel):
    content: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


@router.get("/memory", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    vault = load_second_brain_settings().vault_path
    path = memory_path(vault)
    return MemoryResponse(content=load_memory_excerpt(vault, max_chars=50_000), path=str(path))


@router.post("/memory/rollup", response_model=MemoryUpdateResponse)
async def rollup_memory(body: MemoryRollupBody, request: Request) -> MemoryUpdateResponse:
    vault = load_second_brain_settings().vault_path
    cfg = getattr(request.app.state, "config", None) or load_config("config.yaml")
    provider = body.provider or cfg.llm.default_provider
    model = body.model or cfg.llm.resolve_model(provider, None)
    text = await roll_up_from_text(
        content=body.content,
        vault_path=vault,
        provider=provider,
        model=model,
        llm_cfg=cfg.llm,
    )
    return MemoryUpdateResponse(content=text)
