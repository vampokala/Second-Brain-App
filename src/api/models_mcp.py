"""Pydantic models for MCP server routes."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class McpServerOut(BaseModel):
    id: str
    preset: str
    name: str
    url: str
    auth_mode: str
    connected: bool
    connector_types: list[str] = Field(default_factory=list)
    enabled: bool = True
    auth_email: str | None = None


class McpServerUpsertBody(BaseModel):
    preset: str
    name: str | None = None
    url: HttpUrl | None = None
    auth_mode: str = "oauth"
    token_env: str | None = None
    auth_email: str | None = None


class McpConnectResponse(BaseModel):
    authorization_url: str
    state: str


class McpToolOut(BaseModel):
    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)
