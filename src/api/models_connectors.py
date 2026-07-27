"""Pydantic models for the connectors API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ConnectorType = Literal[
    "github",
    "jira",
    "confluence",
    "slack",
    "mcp_jira",
    "mcp_confluence",
    "mcp_github",
    "mcp_gmail",
    "mcp_gchat",
    "mcp_custom",
]


class ConnectorUpsertBody(BaseModel):
    connector_type: ConnectorType
    resource_id: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    # Auto-sync cadence in minutes; None/0 = manual only.
    sync_interval_min: int | None = Field(default=None, ge=0)


class ConnectorOut(BaseModel):
    id: str
    connector_type: str
    resource_id: str
    config: dict[str, Any]
    enabled: bool
    sync_interval_min: int | None = None
    cursor: dict[str, Any] | None = None
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    item_count: int = 0


class ConnectorTestResult(BaseModel):
    ok: bool
    message: str


class ConnectorSyncResponse(BaseModel):
    status: Literal["started", "failed"]
    detail: str | None = None
