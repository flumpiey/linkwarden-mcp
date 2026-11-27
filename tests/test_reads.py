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
                "collection": {"id": 1, "name": "Inbox"},
                "tags": [{"id": 2, "name": "read"}],
                "pinnedBy": [{"id": 1}],
                "readable": "completed",
                "textContent": "hello",
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await get_link(client, 7)
    assert "note" not in out
    assert out["pinned"] is True
    assert out["tags"][0]["name"] == "read"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_list_collections_and_tags(auth_env: None) -> None:
    cols_route = respx.get(f"{BASE_URL}/api/v1/collections").mock(
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
    # Upstream /collections reads no query; list_collections sends none.
    assert not cols_route.calls.last.request.url.params
    assert tags[0]["link_count"] == 1
    await client.aclose()


def _page(links: list[dict], cursor: int | None) -> httpx.Response:
    return httpx.Response(200, json={"data": {"links": links, "nextCursor": cursor}})


@pytest.mark.asyncio
@respx.mock
async def test_search_sends_upstream_query_names(auth_env: None) -> None:
    route = respx.get(f"{BASE_URL}/api/v1/search").mock(return_value=_page([], None))
    client = LinkwardenClient(BASE_URL, "token")
    await search_links(
        client, NameResolver(client), query="pi", pinned_only=True, sort="name_desc"
    )
    params = route.calls.last.request.url.params
    assert params["searchQueryString"] == "pi"
    assert params["pinnedOnly"] == "true"
    assert params["sort"] == "3"
    for stale in ("search", "pinned", "sortBy", "take"):
        assert stale not in params
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_follows_next_cursor_up_to_limit(auth_env: None) -> None:
    page1 = [{"id": i, "pinnedBy": []} for i in range(1, 51)]
    page2 = [{"id": i, "pinnedBy": [{"id": 9}]} for i in range(51, 101)]
    route = respx.get(f"{BASE_URL}/api/v1/search").mock(
        side_effect=[_page(page1, 50), _page(page2, 100), _page([{"id": 999}], None)]
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await search_links(client, NameResolver(client), limit=60)
    assert len(out) == 60
    assert route.call_count == 2
    assert "cursor" not in route.calls[0].request.url.params
    assert route.calls[1].request.url.params["cursor"] == "50"
    assert out[0]["pinned"] is False
    assert out[55]["pinned"] is True
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_list_tags_sends_sort_and_walks_pages(auth_env: None) -> None:
    route = respx.get(f"{BASE_URL}/api/v1/tags").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"tags": [{"id": 1, "name": "a"}], "nextCursor": 1}}),
            httpx.Response(200, json={"data": {"tags": [{"id": 2, "name": "b"}], "nextCursor": None}}),
        ]
    )
    client = LinkwardenClient(BASE_URL, "token")
    tags = await list_tags(client, sort="link_count_desc")
    assert [t["name"] for t in tags] == ["a", "b"]
    assert route.calls[0].request.url.params["sort"] == "4"
    assert "sortBy" not in route.calls[0].request.url.params
    assert route.calls[1].request.url.params["cursor"] == "1"
    await client.aclose()


def test_link_and_tag_sort_maps_are_separate() -> None:
    from linkwarden_mcp.sort import TAG_SORT_WORDS, sort_to_int

    assert sort_to_int("name_desc") == 3
    assert sort_to_int("link_count_asc", TAG_SORT_WORDS) == 5
    # Link Sort 4 is Custom order upstream; link-count words must not reach /search.
    for word in ("tag_count_desc", "link_count_desc"):
        with pytest.raises(ValueError, match="Unknown sort"):
            sort_to_int(word)
