"""Delete tool tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.deletes import delete_links, delete_tags, merge_tags
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver


@pytest.mark.asyncio
@respx.mock
async def test_delete_links_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    with pytest.raises(BulkCapExceeded):
        await delete_links(client, link_ids=list(range(30)), max_bulk=25)
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_tags_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    with pytest.raises(BulkCapExceeded):
        await delete_tags(client, NameResolver(client), tag_ids=list(range(30)), max_bulk=25)
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_merge_tags_uses_put(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/tags").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": 1, "name": "a", "_count": {"links": 2}},
                    {"id": 2, "name": "b", "_count": {"links": 1}},
                ]
            },
        )
    )
    route = respx.put(f"{BASE_URL}/api/v1/tags/merge").mock(
        return_value=httpx.Response(200, json={"id": 99})
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await merge_tags(
        client,
        NameResolver(client),
        new_tag_name="merged",
        tag_ids=[1, 2],
        max_bulk=25,
    )
    assert route.called
    assert out["links_moved"] == 3
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_merge_tags_duplicate_name_warning(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/tags").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": 1, "name": "merged", "_count": {"links": 1}}]},
        )
    )
    respx.put(f"{BASE_URL}/api/v1/tags/merge").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await merge_tags(
        client,
        NameResolver(client),
        new_tag_name="merged",
        tag_ids=[1],
        max_bulk=25,
    )
    assert "warning" in out
    await client.aclose()
