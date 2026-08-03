"""list_resources + registration + runtime scope guards (offline)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.config import reset_state
from linkwarden_mcp.scopes import ScopeConfigError, WritePolicy, WritesDeniedError
from linkwarden_mcp.server import mcp, register_all_tools, reset_registration
from linkwarden_mcp.task_tools import require_write_scopes


async def _call(name: str) -> dict:
    result = await mcp.call_tool(name, {})
    # FastMCP may wrap structured content
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    if isinstance(result, dict):
        return result
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None)
    if content and hasattr(content[0], "text"):
        import json

        return json.loads(content[0].text)
    raise AssertionError(f"Unexpected tool result: {result!r}")


def _register_from_env() -> None:
    reset_state()
    reset_registration()
    register_all_tools()


def test_list_resources_read_only_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_MCP_WRITE_SCOPES", raising=False)
    monkeypatch.delenv("LINKWARDEN_MCP_DELETE_SCOPES", raising=False)
    _register_from_env()
    out = asyncio.run(_call("list_resources"))
    assert out["read_only"] is True
    assert out["write_scopes"] == []
    assert out["delete_scopes"] == []
    assert out["effective_write_scopes"] == []
    assert "read-only" in out["boundary"].casefold()


def test_list_resources_reports_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_MCP_WRITE_SCOPES", "links,collections")
    monkeypatch.setenv("LINKWARDEN_MCP_DELETE_SCOPES", "links")
    _register_from_env()
    out = asyncio.run(_call("list_resources"))
    assert out["read_only"] is False
    assert out["write_scopes"] == ["collections", "links"]
    assert out["delete_scopes"] == ["links"]
    assert out["effective_write_scopes"] == ["collections", "links"]


def test_write_tools_not_registered_without_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_MCP_WRITE_SCOPES", "collections")
    _register_from_env()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "save_link" not in names
    assert "create_collection" in names


def test_write_tools_registered_with_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_MCP_WRITE_SCOPES", "links")
    _register_from_env()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "save_link" in names
    assert "create_collection" not in names


def test_task_tool_runtime_scope_error() -> None:
    policy = WritePolicy(frozenset({"collections"}), frozenset())
    with pytest.raises(WritesDeniedError, match="links"):
        require_write_scopes(policy, "links")


def test_legacy_env_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_MCP_ALLOW_WRITES", "true")
    with pytest.raises(ScopeConfigError, match="no longer supported"):
        WritePolicy.from_env()


@pytest.mark.asyncio
@respx.mock
async def test_client_authorize_blocks_missing_scope() -> None:
    client = LinkwardenClient(
        "http://example.test",
        "token",
        policy=WritePolicy(frozenset({"links"}), frozenset()),
    )
    with pytest.raises(WritesDeniedError, match="collections"):
        await client.post("/api/v1/collections", json={"name": "x"})
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_client_authorize_allows_scoped_write() -> None:
    respx.post("http://example.test/api/v1/links").mock(
        return_value=httpx.Response(200, json={"response": {"id": 1}})
    )
    client = LinkwardenClient(
        "http://example.test",
        "token",
        policy=WritePolicy(frozenset({"links"}), frozenset()),
    )
    assert await client.post("/api/v1/links", json={"url": "https://a.test"}) == {"id": 1}
    await client.aclose()
