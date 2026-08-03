"""Library overview tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.reads import get_library_overview
from linkwarden_mcp.resolve import NameResolver


@pytest.mark.asyncio
@respx.mock
async def test_overview_sum_invariant(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": [
                    {"id": 1, "name": "A", "_count": {"links": 3}, "parent": None},
                    {"id": 2, "name": "Unorganized", "_count": {"links": 2}, "parent": None},
                    {"id": 3, "name": "Empty", "_count": {"links": 0}, "parent": None},
                ]
            },
        )
    )
    respx.get(f"{BASE_URL}/api/v1/tags").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": 10, "name": "used", "_count": {"links": 4}},
                    {"id": 11, "name": "unused", "_count": {"links": 0}},
                ],
                "total": 2,
            },
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    overview = await get_library_overview(NameResolver(client))
    assert overview["total_links"] == 5
    assert overview["total_collections"] == 3
    assert overview["unorganized_link_count"] == 2
    assert any(c["name"] == "Empty" for c in overview["empty_collections"])
    assert any(t["name"] == "unused" for t in overview["unused_tags"])
    assert overview["tags_partial"] is False
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_tag_pagination_partial(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json={"response": []})
    )

    def tag_handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        if not cursor:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "tags": [
                            {"id": i, "name": f"t{i}", "_count": {"links": 0}} for i in range(20)
                        ],
                        "nextCursor": "page2",
                    }
                },
            )
        return httpx.Response(
            200,
            json={"data": {"tags": [{"id": 99, "name": "t99", "_count": {"links": 0}}]}},
        )

    respx.get(f"{BASE_URL}/api/v1/tags").mock(side_effect=tag_handler)
    client = LinkwardenClient(BASE_URL, "token")
    overview = await get_library_overview(NameResolver(client))
    assert overview["total_tagged_links"] == 0
    assert overview["tags_partial"] is False
    await client.aclose()
