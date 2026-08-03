"""Scope guards shared by mutating MCP tools."""

from __future__ import annotations

from linkwarden_mcp.scopes import (
    DELETE_SCOPES_ENV,
    WRITE_SCOPES_ENV,
    WritePolicy,
    WritesDeniedError,
)


def require_write_scopes(policy: WritePolicy, *scopes: str) -> None:
    missing = [s for s in scopes if s not in policy.effective_write_scopes]
    if missing:
        raise WritesDeniedError(
            f"Requires {', '.join(repr(s) for s in missing)} in {WRITE_SCOPES_ENV}."
        )


def require_delete_scope(policy: WritePolicy, scope: str) -> None:
    if scope not in policy.effective_delete_scopes:
        raise WritesDeniedError(
            f"Requires {scope!r} in {DELETE_SCOPES_ENV}."
        )
