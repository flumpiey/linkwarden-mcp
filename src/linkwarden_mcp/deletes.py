"""Delete MCP tools."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import check_bulk_cap
from linkwarden_mcp.resolve import NameResolver


async def delete_links(
    client: LinkwardenClient,
    *,
    link_ids: list[int],
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    await client.delete("/api/v1/links", json={"linkIds": link_ids})
    return {"deleted_count": len(link_ids)}


async def delete_tags(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    tag_ids: list[int] | None = None,
    tag_names: list[str] | None = None,
    max_bulk: int = 25,
) -> dict[str, Any]:
    ids = list(tag_ids or [])
    if tag_names:
        ids.extend(await resolver.resolve_tag_ids(tag_names))
    check_bulk_cap(len(ids), max_bulk)
    await client.delete("/api/v1/tags", json={"tagIds": ids})
    return {"deleted_count": len(ids)}


async def merge_tags(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    new_tag_name: str,
    tag_ids: list[int],
    max_bulk: int = 25,
) -> dict[str, Any]:
    if not tag_ids:
        raise ValueError("tag_ids must contain at least one id.")
    tags = await resolver.tags()
    affected = sum(
        (t.get("_count") or {}).get("links", 0)
        for t in tags
        if int(t.get("id", -1)) in set(tag_ids)
    )
    check_bulk_cap(affected, max_bulk)
    warning = None
    if any(t.get("name") == new_tag_name for t in tags):
        warning = f"Tag {new_tag_name!r} already exists; merge will replace source tags."
    result = await client.put(
        "/api/v1/tags/merge",
        json={"newTagName": new_tag_name, "tagIds": tag_ids},
    )
    out: dict[str, Any] = {
        "new_tag_id": result.get("id") if isinstance(result, dict) else None,
        "links_moved": affected,
    }
    if warning:
        out["warning"] = warning
    return out


async def delete_collection(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection: str | int,
) -> dict[str, Any]:
    if isinstance(collection, int):
        collection_id = collection
        collections = await resolver.collections()
        match = next((c for c in collections if int(c.get("id", -1)) == collection_id), None)
        link_count = (match.get("_count") or {}).get("links", 0) if match else 0
    else:
        collection_id = await resolver.collection_id(collection)
        collections = await resolver.collections()
        match = next((c for c in collections if int(c.get("id", -1)) == collection_id), None)
        link_count = (match.get("_count") or {}).get("links", 0) if match else 0
    await client.delete(f"/api/v1/collections/{collection_id}")
    return {"collection_id": collection_id, "links_removed_count": link_count}
