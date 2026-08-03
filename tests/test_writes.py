"""Write tool tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.writes import organise_links, queue_archive, save_link


@pytest.mark.asyncio
@respx.mock
async def test_save_link_resolves_existing_collection(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 9, "name": "Homelab"}])
    )
    post = respx.post(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={"id": 100})
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await save_link(
        client,
        NameResolver(client),
        url="https://new.example",
        collection="Homelab",
    )
    assert out["collection_id"] == 9
    assert out["collection_created"] is False
    assert post.calls.last.request.content
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_duplicate_url_plain_message(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Inbox"}])
    )
    respx.post(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(409, json={"message": "already exists"})
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await save_link(
        client,
        NameResolver(client),
        url="https://dup.example",
        collection="Inbox",
    )
    assert "already saved" in out["message"].lower()
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_organise_links_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    with pytest.raises(BulkCapExceeded) as exc:
        await organise_links(
            client,
            NameResolver(client),
            link_ids=list(range(30)),
            max_bulk=25,
        )
    assert exc.value.requested == 30
    assert exc.value.cap == 25
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_queue_archive_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    with pytest.raises(BulkCapExceeded):
        await queue_archive(client, link_ids=list(range(26)), max_bulk=25)
    await client.aclose()
