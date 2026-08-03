"""read_link_content tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.reads import read_link_content


@pytest.mark.asyncio
@respx.mock
async def test_prefers_text_content(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/links/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 1,
                "name": "Article",
                "readable": "completed",
                "textContent": "Primary text",
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await read_link_content(client, 1)
    assert out["source"] == "textContent"
    assert out["text"] == "Primary text"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_archive_format_3_fallback(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/links/2").mock(
        return_value=httpx.Response(
            200,
            json={"id": 2, "name": "Article", "readable": "completed", "textContent": ""},
        )
    )
    respx.get(f"{BASE_URL}/api/v1/archives/2").mock(
        return_value=httpx.Response(
            200,
            json={"textContent": "From archive", "title": "T", "excerpt": "E"},
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await read_link_content(client, 2)
    assert out["source"] == "archive"
    assert out["text"] == "From archive"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_unavailable_readable(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/links/3").mock(
        return_value=httpx.Response(
            200, json={"id": 3, "readable": None, "textContent": None}
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await read_link_content(client, 3)
    assert "unavailable" in out
    await client.aclose()
