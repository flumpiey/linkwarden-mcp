"""Name resolution cache tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import AmbiguousNameError, UnknownNameError
from linkwarden_mcp.resolve import NameResolver


@pytest.mark.asyncio
@respx.mock
async def test_collection_id_resolves(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Homelab"}])
    )
    client = LinkwardenClient(BASE_URL, "token")
    resolver = NameResolver(client)
    assert await resolver.collection_id("Homelab") == 1
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_ambiguous_collection_name_fails(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Dup"},
                {"id": 2, "name": "Dup"},
            ],
        )
    )
    client = LinkwardenClient(BASE_URL, "token")
    resolver = NameResolver(client)
    with pytest.raises(AmbiguousNameError, match="2 matches"):
        await resolver.collection_id("Dup")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_unknown_collection_name(auth_env: None) -> None:
    respx.get(f"{BASE_URL}/api/v1/collections").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = LinkwardenClient(BASE_URL, "token")
    resolver = NameResolver(client)
    with pytest.raises(UnknownNameError):
        await resolver.collection_id("Missing")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_tag_id_resolves_past_first_page(auth_env: None) -> None:
    route = respx.get(f"{BASE_URL}/api/v1/tags").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": {"tags": [{"id": i, "name": f"t{i}"} for i in range(50)],
                               "nextCursor": 49}},
            ),
            httpx.Response(
                200, json={"data": {"tags": [{"id": 77, "name": "late"}], "nextCursor": None}}
            ),
        ]
    )
    client = LinkwardenClient(BASE_URL, "token")
    assert await NameResolver(client).tag_id("late") == 77
    assert route.calls[1].request.url.params["cursor"] == "49"
    await client.aclose()
