"""Cached collection/tag name resolution."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient, parse_tags_payload
from linkwarden_mcp.errors import AmbiguousNameError, UnknownNameError

UNORGANIZED = "Unorganized"


class NameResolver:
    def __init__(self, client: LinkwardenClient) -> None:
        self._client = client
        self._collections: list[dict[str, Any]] | None = None
        self._tags: list[dict[str, Any]] | None = None

    async def collections(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._collections is None or refresh:
            data = await self._client.get("/api/v1/collections")
            self._collections = data if isinstance(data, list) else []
        return self._collections

    async def tags(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._tags is None or refresh:
            raw = await self._client.get("/api/v1/tags")
            self._tags, _ = parse_tags_payload(raw)
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
