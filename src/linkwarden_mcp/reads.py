"""Read-only MCP tools."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient, parse_links_payload, parse_tags_payload
from linkwarden_mcp.resolve import UNORGANIZED, NameResolver
from linkwarden_mcp.sort import sort_to_int


def _link_summary(link: dict[str, Any]) -> dict[str, Any]:
    collection = link.get("collection") or {}
    tags = link.get("tags") or []
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "url": link.get("url"),
        "collection": collection.get("name") if isinstance(collection, dict) else None,
        "tags": [t.get("name") for t in tags if isinstance(t, dict)],
        "pinned": link.get("pinned"),
        "readable": link.get("readable"),
    }


async def search_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    query: str | None = None,
    collection: str | None = None,
    tag: str | None = None,
    pinned_only: bool | None = None,
    sort: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if query:
        params["search"] = query
    if collection:
        params["collectionId"] = await resolver.collection_id(collection)
    if tag:
        params["tagId"] = await resolver.tag_id(tag)
    if pinned_only:
        params["pinned"] = True
    sort_int = sort_to_int(sort) if sort else None
    if sort_int is not None:
        params["sortBy"] = sort_int
    if limit is not None:
        params["take"] = limit

    data = await client.get("/api/v1/search", params=params)
    return [_link_summary(link) for link in parse_links_payload(data)]


async def get_link(client: LinkwardenClient, link_id: int) -> dict[str, Any]:
    link = await client.get(f"/api/v1/links/{link_id}")
    collection = link.get("collection") or {}
    tags = link.get("tags") or []
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "url": link.get("url"),
        "description": link.get("description"),
        "note": link.get("note"),
        "collection": {
            "id": collection.get("id"),
            "name": collection.get("name"),
        },
        "tags": [{"id": t.get("id"), "name": t.get("name")} for t in tags if isinstance(t, dict)],
        "pinned": link.get("pinned"),
        "readable": link.get("readable"),
        "textContent": link.get("textContent"),
    }


async def read_link_content(client: LinkwardenClient, link_id: int) -> dict[str, Any]:
    link = await client.get(f"/api/v1/links/{link_id}")
    readable = link.get("readable")
    if readable in (None, "unavailable"):
        return {"unavailable": "Link is not preserved or URL is unsafe."}

    text = link.get("textContent")
    if isinstance(text, str) and text.strip():
        truncated = len(text) > 50000
        return {
            "text": text[:50000],
            "source": "textContent",
            "truncated": truncated,
            "title": link.get("name"),
        }

    archive = await client.get(f"/api/v1/archives/{link_id}", params={"format": 3})
    if isinstance(archive, str):
        try:
            import json

            archive = json.loads(archive)
        except json.JSONDecodeError:
            return {"unavailable": "Archive content could not be parsed."}
    if not isinstance(archive, dict):
        return {"unavailable": "No preserved text available for this link."}

    text = archive.get("textContent") or ""
    if not str(text).strip():
        return {"unavailable": "No preserved text available for this link."}

    text = str(text)
    truncated = len(text) > 50000
    return {
        "text": text[:50000],
        "source": "archive",
        "truncated": truncated,
        "title": archive.get("title") or link.get("name"),
        "excerpt": archive.get("excerpt"),
    }


async def list_collections(
    client: LinkwardenClient,
    *,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    sort_int = sort_to_int(sort) if sort else None
    if sort_int is not None:
        params["sortBy"] = sort_int
    data = await client.get("/api/v1/collections", params=params or None)
    collections = data if isinstance(data, list) else data.get("data", [])
    out: list[dict[str, Any]] = []
    for c in collections:
        parent = c.get("parent") or {}
        out.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "parent": parent.get("name") if isinstance(parent, dict) else None,
                "link_count": (c.get("_count") or {}).get("links", 0),
                "members": c.get("members"),
            }
        )
    return out


async def list_tags(
    client: LinkwardenClient,
    *,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    sort_int = sort_to_int(sort) if sort else None
    if sort_int is not None:
        params["sortBy"] = sort_int
    data = await client.get("/api/v1/tags", params=params or None)
    tags, _ = parse_tags_payload(data)
    return [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "link_count": (t.get("_count") or {}).get("links", 0),
        }
        for t in tags
    ]


def _nesting_depth(collections: list[dict[str, Any]]) -> int:
    by_id = {int(c["id"]): c for c in collections if c.get("id") is not None}

    def depth(cid: int, seen: set[int]) -> int:
        if cid in seen:
            return 0
        seen.add(cid)
        parent = by_id.get(cid, {}).get("parent")
        if not isinstance(parent, dict) or not parent.get("id"):
            return 1
        return 1 + depth(int(parent["id"]), seen)

    if not by_id:
        return 0
    return max(depth(int(cid), set()) for cid in by_id)


async def fetch_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection: str | None = None,
    query: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch links for workflow scans (capped at ``limit``, default 500)."""
    return await search_links(
        client,
        resolver,
        query=query,
        collection=collection,
        limit=limit,
    )


async def get_library_overview(resolver: NameResolver) -> dict[str, Any]:
    collections = await resolver.collections()
    tags, tags_partial = await _all_tags(resolver)

    total_links = sum((c.get("_count") or {}).get("links", 0) for c in collections)
    empty_collections = [
        {"id": c.get("id"), "name": c.get("name")}
        for c in collections
        if (c.get("_count") or {}).get("links", 0) == 0
    ]
    unused_tags = [
        {"id": t.get("id"), "name": t.get("name")}
        for t in tags
        if (t.get("_count") or {}).get("links", 0) == 0
    ]
    unorganized = next((c for c in collections if c.get("name") == UNORGANIZED), None)
    total_tagged = sum((t.get("_count") or {}).get("links", 0) for t in tags)

    return {
        "total_collections": len(collections),
        "total_links": total_links,
        "total_tagged_links": total_tagged,
        "max_nesting_depth": _nesting_depth(collections),
        "empty_collections": empty_collections,
        "unused_tags": unused_tags,
        "unorganized_link_count": (unorganized.get("_count") or {}).get("links", 0)
        if unorganized
        else 0,
        "tags_partial": tags_partial,
    }


async def _all_tags(resolver: NameResolver) -> tuple[list[dict[str, Any]], bool]:
    client = resolver._client
    cursor: Any | None = None
    all_tags: list[dict[str, Any]] = []
    tags_partial = False
    for _ in range(100):
        params = {"cursor": cursor} if cursor is not None else None
        raw = await client.get("/api/v1/tags", params=params)
        batch, cursor = parse_tags_payload(raw)
        all_tags.extend(batch)
        if not batch or cursor is None:
            break
    else:
        tags_partial = True
    return all_tags, tags_partial
