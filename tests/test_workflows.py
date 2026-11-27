"""Workflow tool tests (respx-mocked)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from conftest import BASE_URL, FULL_WRITE_POLICY

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import BulkCapExceeded
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.workflows import (
    analyze_collection_overlap,
    apply_triage_plan,
    auto_tag_by_domain,
    bulk_sort_by_rules,
    find_duplicate_links,
    find_unsorted_links,
    get_sorting_dashboard,
    suggest_links_for_collection,
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


def _link_route(link_id: int, tags: list[str], url: str = "https://github.com/a/b") -> None:
    respx.get(f"{BASE_URL}/api/v1/links/{link_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": link_id,
                "name": f"L{link_id}",
                "url": url,
                "collection": {"id": 1, "name": "Unorganized"},
                "tags": [{"id": n, "name": t} for n, t in enumerate(tags)],
            },
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_apply_triage_plan_keeps_existing_tags(auth_env: None) -> None:
    _link_route(5, ["mine", "keep"])
    put = respx.put(f"{BASE_URL}/api/v1/links").mock(return_value=httpx.Response(200, json={}))
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await apply_triage_plan(
        client, NameResolver(client), plan=[{"link_id": 5, "tags": ["github"]}], dry_run=False
    )
    assert out["updated_count"] == 1
    body = json.loads(put.calls.last.request.content)
    assert body["newData"]["tags"] == [{"name": "mine"}, {"name": "keep"}, {"name": "github"}]
    await client.aclose()


def _search_links_route(*links: dict) -> None:
    respx.get(f"{BASE_URL}/api/v1/search").mock(
        return_value=httpx.Response(
            200, json={"data": {"links": list(links), "nextCursor": None}}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_bulk_sort_by_rules_merges_tags_and_collects_failures(auth_env: None) -> None:
    _collections_route()
    _search_links_route(
        {"id": 1, "url": "https://github.com/a", "tags": [{"name": "mine"}]},
        {"id": 2, "url": "https://gist.github.com/b", "tags": []},
        {"id": 3, "url": "https://digital.com/c", "tags": []},
    )
    put = respx.put(f"{BASE_URL}/api/v1/links").mock(
        side_effect=[httpx.Response(200, json={}), httpx.Response(500, json={"message": "boom"})]
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await bulk_sort_by_rules(
        client,
        NameResolver(client),
        rules=[{"domain_pattern": "github.com", "collection": "Programming", "tags": ["git"]}],
        dry_run=False,
    )
    assert put.call_count == 2
    assert json.loads(put.calls[0].request.content)["newData"]["tags"] == [
        {"name": "mine"},
        {"name": "git"},
    ]
    assert out["updated_count"] == 1
    assert out["failures"] == [{"link_id": 2, "error": "boom"}]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_auto_tag_by_domain_collects_failures(auth_env: None) -> None:
    _tags_route()
    _collections_route()
    _link_route(7, [])
    _link_route(8, ["x"])
    put = respx.put(f"{BASE_URL}/api/v1/links").mock(
        side_effect=[httpx.Response(500, json={"message": "down"}), httpx.Response(200, json={})]
    )
    client = LinkwardenClient(BASE_URL, "token", policy=FULL_WRITE_POLICY)
    out = await auto_tag_by_domain(client, NameResolver(client), link_ids=[7, 8], dry_run=False)
    assert put.call_count == 2
    assert out["updated_count"] == 1
    assert out["failures"] == [{"link_id": 7, "error": "down"}]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_unsorted_outside_unorganized_needs_a_real_reason(auth_env: None) -> None:
    _collections_route()
    _search_links_route(
        {
            "id": 1,
            "url": "https://a.test",
            "collection": {"name": "Programming"},
            "tags": [{"name": "t"}],
            "readable": "completed",
        },
        {"id": 2, "url": "https://b.test", "collection": {"name": "Programming"}, "tags": []},
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await find_unsorted_links(client, NameResolver(client), collection="Programming")
    assert [link["id"] for link in out["links"]] == [2]
    assert "in Unorganized" not in out["links"][0]["reasons"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_suggest_links_for_collection_without_favourites(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Unorganized", "_count": {"links": 1}},
                {"id": 2, "name": "Programming", "_count": {"links": 1}},
            ],
        )
    )
    _tags_route()
    _search_links_route({"id": 1, "url": "https://github.com/a", "tags": []})
    client = LinkwardenClient(BASE_URL, "token")
    out = await suggest_links_for_collection(client, NameResolver(client), collection="Programming")
    assert out["collection"] == "Programming"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_overlap_reason_matches_merge_flag(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200, json=[{"id": 1, "name": "Brightside"}, {"id": 2, "name": "BrightSide"}]
        )
    )
    respx.get(f"{BASE_URL}/api/v1/search").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"links": [{"id": 1, "url": "https://a.test"}]}}),
            httpx.Response(200, json={"data": {"links": [{"id": 2, "url": "https://b.test"}]}}),
        ]
    )
    client = LinkwardenClient(BASE_URL, "token")
    out = await analyze_collection_overlap(
        client, NameResolver(client), collection_a="Brightside", collection_b="BrightSide"
    )
    assert out["merge_recommended"] is False
    assert out["reason"] == "Little overlap; keep separate"
    await client.aclose()
