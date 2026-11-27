"""Cached collection/tag name resolution."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient, parse_tags_payload
from linkwarden_mcp.errors import AmbiguousNameError, UnknownNameError

UNORGANIZED = "Unorganized"
MAX_TAG_PAGES = 100


async def fetch_all_tags(
    client: LinkwardenClient, params: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """Walk the cursor-paged /api/v1/tags. Returns (tags, partial)."""
    cursor: Any | None = None
    all_tags: list[dict[str, Any]] = []
    for _ in range(MAX_TAG_PAGES):
        page_params = dict(params or {})
        if cursor is not None:
            page_params["cursor"] = cursor
        raw = await client.get("/api/v1/tags", params=page_params or None)
        batch, cursor = parse_tags_payload(raw)
        all_tags.extend(batch)
        if not batch or cursor is None:
            return all_tags, False
    return all_tags, True


class NameResolver:
    def __init__(self, client: LinkwardenClient) -> None:
        self._client = client
        self._collections: list[dict[str, Any]] | None = None
        self._tags: list[dict[str, Any]] | None = None
        self.tags_partial = False

    async def collections(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._collections is None or refresh:
            data = await self._client.get("/api/v1/collections")
            self._collections = data if isinstance(data, list) else []
        return self._collections

    async def tags(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._tags is None or refresh:
            self._tags, self.tags_partial = await fetch_all_tags(self._client)
        return self._tags

    async def collection_id(self, name: str) -> int:
        matches = [c for c in await self.collections() if c.get("name") == name]
        if len(matches) == 1:
            return int(matches[0]["id"])
        if len(matches) > 1:
            raise AmbiguousNameError("collection", name, len(matches))
        raise UnknownNameError("collection", name)

    async def collection_id_and_owner(self, name: str) -> tuple[int, int]:
        matches = [c for c in await self.collections() if c.get("name") == name]
        if len(matches) == 1:
            return int(matches[0]["id"]), int(matches[0]["ownerId"])
        if len(matches) > 1:
            raise AmbiguousNameError("collection", name, len(matches))
        raise UnknownNameError("collection", name)

    async def tag_id(self, name: str) -> int:
        matches = [t for t in await self.tags() if t.get("name") == name]
        if len(matches) == 1:
            return int(matches[0]["id"])
        if len(matches) > 1:
            raise AmbiguousNameError("tag", name, len(matches))
        raise UnknownNameError("tag", name)

    async def resolve_tag_ids(self, names: list[str]) -> list[int]:
        return [await self.tag_id(n) for n in names]

    async def find_or_create_unorganized(self) -> tuple[int, bool]:
        for c in await self.collections():
            if c.get("name") == UNORGANIZED:
                return int(c["id"]), False
        created = await self._client.post(
            "/api/v1/collections", json={"name": UNORGANIZED}
        )
        await self.collections(refresh=True)
        return int(created["id"]), True

    async def ensure_collection_id(self, name: str) -> tuple[int, bool]:
        if name == UNORGANIZED:
            return await self.find_or_create_unorganized()
        return await self.collection_id(name), False
