"""Read tool tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.reads import get_link, list_collections, list_tags, search_links
from linkwarden_mcp.resolve import NameResolver


@pytest.mark.asyncio
@respx.mock
async def test_search_links(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 3, "name": "Homelab"}])
    )
    route = respx.get(f"{BASE_URL}/api/v1/search").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "Pi-hole",
                    "url": "https://pi.hole",
                    "collection": {"name": "Homelab"},
                    "tags": [{"name": "dns"}],
                    "pinned": False,
                    "readable": "completed",
                }
            ],
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    resolver = NameResolver(client)
    out = await search_links(client, resolver, collection="Homelab", query="pi")
    assert out[0]["name"] == "Pi-hole"
    assert route.calls.last.request.url.params["collectionId"] == "3"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_link(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/links/7").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 7,
                "name": "Example",
                "url": "https://example.com",
                "description": "d",
                "note": "n",
                "collection": {"id": 1, "name": "Inbox"},
                "tags": [{"id": 2, "name": "read"}],
                "pinned": True,
                "readable": "completed",
                "textContent": "hello",
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await get_link(client, 7)
    assert out["note"] == "n"
    assert out["tags"][0]["name"] == "read"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_list_collections_and_tags(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 1, "name": "A", "parent": None, "_count": {"links": 2}}],
        )
    )
    respx.get(f"{BASE_URL}/api/v1/tags").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": 5, "name": "t", "_count": {"links": 1}}]}
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    cols = await list_collections(client)
    tags = await list_tags(client)
    assert cols[0]["link_count"] == 2
    assert tags[0]["link_count"] == 1
    await client.aclose()
