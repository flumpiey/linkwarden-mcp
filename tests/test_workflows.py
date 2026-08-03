"""Workflow tool tests (respx-mocked)."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.workflows import (
    apply_triage_plan,
    find_duplicate_links,
    find_unsorted_links,
    get_sorting_dashboard,
    triage_links,
)


def _collections_route() -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": [
                    {"id": 1, "name": "Unorganized", "_count": {"links": 2}},
                    {"id": 2, "name": "Programming", "_count": {"links": 10}},
                    {"id": 3, "name": "Favourites", "_count": {"links": 5}},
                ]
            },
        )
    )


def _tags_route() -> None:
    respx.get(f"{BASE_URL}/api/v1/tags").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "tags": [
                        {"id": 1, "name": "github", "_count": {"links": 3}},
                        {"id": 2, "name": "unused", "_count": {"links": 0}},
                    ],
                    "nextCursor": None,
                }
            },
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_triage_links_shape(auth_env: None) -> None:
    _collections_route()
    _tags_route()
    respx.get(f"{BASE_URL}/api/v1/links/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "id": 1,
                    "name": "Repo",
                    "url": "https://github.com/acme/x",
                    "collection": {"id": 1, "name": "Unorganized"},
                    "tags": [],
                    "readable": None,
                    "textContent": None,
                }
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await triage_links(client, NameResolver(client), link_ids=[1])
    assert out["count"] == 1
    plan = out["plans"][0]
    assert plan["id"] == 1
    assert plan["suggested_collection"] == "Programming"
    assert "github" in plan["suggested_tags"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_duplicate_links(auth_env: None) -> None:
    _collections_route()
    respx.get(f"{BASE_URL}/api/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "links": [
                        {
                            "id": 1,
                            "name": "A",
                            "url": "https://example.com/page?utm_source=x",
                            "collection": {"name": "Unorganized"},
                            "tags": [],
                        },
                        {
                            "id": 2,
                            "name": "B",
                            "url": "https://example.com/page/",
                            "collection": {"name": "Unorganized"},
                            "tags": [],
                        },
                        {
                            "id": 3,
                            "name": "C",
                            "url": "https://other.com/",
                            "collection": {"name": "Unorganized"},
                            "tags": [],
                        },
                    ]
                },
                "success": True,
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await find_duplicate_links(client, NameResolver(client))
    assert out["group_count"] == 1
    assert out["duplicate_groups"][0]["count"] == 2
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_apply_triage_plan_bulk_cap(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    plan = [{"link_id": i, "collection": "Programming"} for i in range(30)]
    with pytest.raises(BulkCapExceeded):
        await apply_triage_plan(
            client, NameResolver(client), plan=plan, dry_run=True, max_bulk=25
        )
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_apply_triage_plan_dry_run(auth_env: None) -> None:
    client = LinkwardenClient(BASE_URL, "token")
    out = await apply_triage_plan(
        client,
        NameResolver(client),
        plan=[{"link_id": 1, "collection": "Programming", "tags": ["github"]}],
        dry_run=True,
    )
    assert out["dry_run"] is True
    assert out["would_update"] == 1
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_unsorted_and_dashboard(auth_env: None) -> None:
    _collections_route()
    _tags_route()
    respx.get(f"{BASE_URL}/api/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "links": [
                        {
                            "id": 9,
                            "name": "Loose",
                            "url": "https://example.com/a",
                            "collection": {"name": "Unorganized"},
                            "tags": [],
                            "readable": None,
                        }
                    ]
                },
                "success": True,
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    unsorted = await find_unsorted_links(client, NameResolver(client), limit=10)
    assert unsorted["count"] >= 1
    dash = await get_sorting_dashboard(client, NameResolver(client))
    assert "unsorted_count" in dash
    assert "largest_collections" in dash
    await client.aclose()
