"""Delete tool tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from conftest import BASE_URL, FULL_WRITE_POLICY

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.deletes import delete_collection, delete_links, delete_tags, merge_tags
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.scopes import WritePolicy, WritesDeniedError


def _collections_payload(*rows: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=list(rows))


def _search_payload(*link_ids: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "links": [
                    {"id": i, "name": f"L{i}", "url": f"https://ex.test/{i}", "collection": {}}
                    for i in link_ids
                ]
            }
        },
    )


@pytest.mark.asyncio
@respx.mock
async def test_delete_links_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    with pytest.raises(BulkCapExceeded):
        await delete_links(client, link_ids=list(range(30)), max_bulk=25)
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_tags_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
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
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
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
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await merge_tags(
        client,
        NameResolver(client),
        new_tag_name="merged",
        tag_ids=[1],
        max_bulk=25,
    )
    assert "warning" in out
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_empty_collection(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 0}}
        )
    )
    delete_route = respx.delete(f"{BASE_URL}/api/v1/collections/10").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload())
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(client, NameResolver(client), collection="Scratch")
    assert delete_route.called
    assert out["links_disposition"] == "none"
    assert out["collection_id"] == 10
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_needs_user_input_without_on_links(
    auth_env: None,
) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 2}}
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(1, 2))
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(client, NameResolver(client), collection="Scratch")
    assert out["needs_user_input"] is True
    assert out["link_count"] == 2
    assert any(o["id"] == "delete" for o in out["options"])
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_on_links_delete(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 2}}
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(1, 2))
    links_del = respx.delete(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={})
    )
    coll_del = respx.delete(f"{BASE_URL}/api/v1/collections/10").mock(
        return_value=httpx.Response(200, json={})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(
        client, NameResolver(client), collection="Scratch", on_links="delete"
    )
    assert links_del.called
    assert coll_del.called
    assert out["links_disposition"] == "deleted"
    assert out["links_removed_count"] == 2
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_on_links_move(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 1}},
            {"id": 90, "name": "Unorganized", "_count": {"links": 0}},
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(5))
    move = respx.put(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={})
    )
    coll_del = respx.delete(f"{BASE_URL}/api/v1/collections/10").mock(
        return_value=httpx.Response(200, json={})
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(
        client, NameResolver(client), collection="Scratch", on_links="move"
    )
    assert move.called
    assert coll_del.called
    assert out["links_disposition"] == "moved:Unorganized"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_cancel(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 1}}
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(5))
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(
        client, NameResolver(client), collection="Scratch", on_links="cancel"
    )
    assert out["cancelled"] is True
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_elicit_delete_links(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 1}}
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(7))
    links_del = respx.delete(f"{BASE_URL}/api/v1/links").mock(
        return_value=httpx.Response(200, json={})
    )
    coll_del = respx.delete(f"{BASE_URL}/api/v1/collections/10").mock(
        return_value=httpx.Response(200, json={})
    )

    class _Accepted:
        action = "accept"
        data = "delete_links"

    ctx = AsyncMock()
    ctx.elicit = AsyncMock(return_value=_Accepted())
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await delete_collection(
        client, NameResolver(client), collection="Scratch", ctx=ctx
    )
    ctx.elicit.assert_awaited()
    assert links_del.called and coll_del.called
    assert out["links_disposition"] == "deleted"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_delete_collection_move_requires_write_links(auth_env: None) -> None:
    policy = WritePolicy(frozenset(), frozenset({"collections", "links"}))
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=_collections_payload(
            {"id": 10, "name": "Scratch", "_count": {"links": 1}}
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_search_payload(5))
    client = LinkwardenClient(BASE_URL, "token", policy=policy)
    with pytest.raises(WritesDeniedError, match="WRITE_SCOPES"):
        await delete_collection(
            client, NameResolver(client), collection="Scratch", on_links="move"
        )
    await client.aclose()
