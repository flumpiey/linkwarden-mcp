"""Read-only MCP tools."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient, parse_links_payload
from linkwarden_mcp.resolve import UNORGANIZED, NameResolver, fetch_all_tags
from linkwarden_mcp.sort import TAG_SORT_WORDS, sort_to_int

# Upstream /search returns fixed pages (PAGINATION_TAKE_COUNT, default 50).
DEFAULT_SEARCH_LIMIT = 50


def _link_summary(link: dict[str, Any]) -> dict[str, Any]:
    collection = link.get("collection") or {}
    tags = link.get("tags") or []
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "url": link.get("url"),
        "collection": collection.get("name") if isinstance(collection, dict) else None,
        "tags": [t.get("name") for t in tags if isinstance(t, dict)],
        "pinned": bool(link.get("pinnedBy")),
        "readable": link.get("readable"),
    }


async def search_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    query: str | None = None,
    collection: str | None = None,
    collection_id: int | None = None,
    tag: str | None = None,
    pinned_only: bool | None = None,
    sort: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search links, following ``nextCursor`` until ``limit`` links or no more pages."""
    params: dict[str, Any] = {}
    if query:
        params["searchQueryString"] = query
    if collection_id is not None:
        params["collectionId"] = collection_id
    elif collection:
        params["collectionId"] = await resolver.collection_id(collection)
    if tag:
        params["tagId"] = await resolver.tag_id(tag)
    if pinned_only:
        params["pinnedOnly"] = "true"
    sort_int = sort_to_int(sort) if sort else None
    if sort_int is not None:
        params["sort"] = sort_int

    wanted = DEFAULT_SEARCH_LIMIT if limit is None else limit
    links: list[dict[str, Any]] = []
    cursor: Any | None = None
    while len(links) < wanted:
        page_params = dict(params)
        if cursor is not None:
            page_params["cursor"] = cursor
        data = await client.get("/api/v1/search", params=page_params)
        batch, cursor = parse_links_payload(data)
        links.extend(batch)
        if not batch or cursor is None:
            break
    return [_link_summary(link) for link in links[:wanted]]


async def get_link(client: LinkwardenClient, link_id: int) -> dict[str, Any]:
    link = await client.get(f"/api/v1/links/{link_id}")
    collection = link.get("collection") or {}
    tags = link.get("tags") or []
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "url": link.get("url"),
        "description": link.get("description"),
        "collection": {
            "id": collection.get("id"),
            "name": collection.get("name"),
        },
        "tags": [{"id": t.get("id"), "name": t.get("name")} for t in tags if isinstance(t, dict)],
        "pinned": bool(link.get("pinnedBy")),
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


async def list_collections(client: LinkwardenClient) -> list[dict[str, Any]]:
    data = await client.get("/api/v1/collections")
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
    sort_int = sort_to_int(sort, TAG_SORT_WORDS) if sort else None
    tags, _ = await fetch_all_tags(
        client, {"sort": sort_int} if sort_int is not None else None
    )
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


async def get_library_overview(resolver: NameResolver) -> dict[str, Any]:
    collections = await resolver.collections()
    tags = await resolver.tags()

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
        "tags_partial": resolver.tags_partial,
    }

