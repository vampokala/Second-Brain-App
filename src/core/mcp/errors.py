"""MCP-layer typed errors."""

from __future__ import annotations


class McpAuthError(RuntimeError):
    """Raised when an MCP OAuth flow fails, expires, or receives a bad callback."""
