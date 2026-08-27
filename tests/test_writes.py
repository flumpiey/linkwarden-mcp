"""Write tool tests."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from conftest import BASE_URL, FULL_WRITE_POLICY

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.writes import organise_links, queue_archive, save_link, update_link


@pytest.mark.asyncio
@respx.mock
async def test_save_link_resolves_existing_collection(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 9, "name": "Homelab"}])
    )
    post = respx.post(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={"id": 100})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await save_link(
        client,
        NameResolver(client),
        url="https://new.example",
        collection="Homelab",
    )
    assert out["collection_id"] == 9
    assert out["collection_created"] is False
    assert json.loads(post.calls.last.request.content) == {
        "url": "https://new.example",
        "collection": {"id": 9},
    }
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
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
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
async def test_save_link_sends_tag_name_objects(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 9, "name": "Homelab"}])
    )
    post = respx.post(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={"id": 100})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    await save_link(
        client,
        NameResolver(client),
        url="https://tagged.example",
        collection="Homelab",
        tags=["k8s", "homelab"],
    )
    body = json.loads(post.calls.last.request.content)
    assert body["tags"] == [{"name": "k8s"}, {"name": "homelab"}]
    assert body["collection"] == {"id": 9}
    assert "collectionId" not in body
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_update_link_sends_id_and_collection_owner(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 4, "name": "Inbox", "ownerId": 7}],
        )
    )
    respx.get(f"{BASE_URL}/api/v1/links/50").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 50,
                "name": "Old",
                "url": "https://old.example",
                "description": "d",
                "note": "n",
                "collection": {"id": 1, "ownerId": 7},
                "tags": [{"id": 3, "name": "keep"}],
            },
        )
    )
    put = respx.put(f"{BASE_URL}/api/v1/links/50").mock(
        return_value=httpx.Response(
            200,
            json={"id": 50, "name": "New", "url": "https://old.example", "collection": {"name": "Inbox"}},
        )
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    await update_link(
        client,
        NameResolver(client),
        link_id=50,
        name="New",
        collection="Inbox",
        tags=["fresh"],
    )
    body = json.loads(put.calls.last.request.content)
    assert body["id"] == 50
    assert body["collection"] == {"id": 4, "ownerId": 7}
    assert body["tags"] == [{"name": "fresh"}]
    assert "collectionId" not in body
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_update_link_keeps_current_collection_and_tags(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/links/50").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 50,
                "name": "Old",
                "url": "https://old.example",
                "description": None,
                "note": None,
                "collection": {"id": 1, "ownerId": 7, "name": "Homelab"},
                "tags": [{"id": 3, "name": "keep"}, "skip-me"],
            },
        )
    )
    put = respx.put(f"{BASE_URL}/api/v1/links/50").mock(
        return_value=httpx.Response(
            200,
            json={"id": 50, "name": "Old", "url": "https://old.example", "collection": {"name": "Homelab"}},
        )
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    await update_link(client, NameResolver(client), link_id=50)
    body = json.loads(put.calls.last.request.content)
    assert body["id"] == 50
    assert body["collection"] == {"id": 1, "ownerId": 7}
    assert body["tags"] == [{"name": "keep"}]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_organise_links_collection_move_preserves_tags(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 9, "name": "Homelab"}])
    )
    put = respx.put(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    await organise_links(
        client,
        NameResolver(client),
        link_ids=[1, 2],
        collection="Homelab",
    )
    body = json.loads(put.calls.last.request.content)
    assert body == {
        "links": [{"id": 1}, {"id": 2}],
        "removePreviousTags": False,
        "newData": {"collectionId": 9},
    }
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_organise_links_replace_tags(auth_env: None) -> None:
    put = respx.put(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    await organise_links(
        client,
        NameResolver(client),
        link_ids=[8],
        tags=["a", "b"],
    )
    body = json.loads(put.calls.last.request.content)
    assert body == {
        "links": [{"id": 8}],
        "removePreviousTags": True,
        "newData": {"tags": [{"name": "a"}, {"name": "b"}]},
    }
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_organise_links_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
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
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    with pytest.raises(BulkCapExceeded):
        await queue_archive(client, link_ids=list(range(26)), max_bulk=25)
    await client.aclose()
