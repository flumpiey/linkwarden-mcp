"""Write MCP tools (LINKWARDEN_MCP_WRITE_SCOPES)."""

from __future__ import annotations

from typing import Any

from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import ApiError, check_bulk_cap
from linkwarden_mcp.resolve import NameResolver


async def save_link(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    url: str,
    collection: str,
    tags: list[str] | None = None,
    name: str | None = None,
    description: str | None = None,
    note: str | None = None,
    max_bulk: int = 25,
) -> dict[str, Any]:
    collection_id, created = await resolver.ensure_collection_id(collection)
    body: dict[str, Any] = {"url": url, "collectionId": collection_id}
    if name:
        body["name"] = name
    if description:
        body["description"] = description
    if note:
        body["note"] = note
    if tags:
        body["tags"] = tags
    try:
        result = await client.post("/api/v1/links", json=body)
    except ApiError as exc:
        if exc.status == 409 or "already" in str(exc).lower():
            return {"message": "This URL is already saved.", "duplicate": True}
        raise
    return {
        "link_id": result.get("id"),
        "collection_id": collection_id,
        "collection_created": created,
        "message": "Link saved.",
    }


async def organise_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_ids: list[int],
    collection: str | None = None,
    tags: list[str] | None = None,
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    body: dict[str, Any] = {"linkIds": link_ids}
    if collection:
        body["collectionId"] = await resolver.collection_id(collection)
    if tags is not None:
        body["tags"] = tags
    await client.put("/api/v1/links", json=body)
    return {"updated_count": len(link_ids), "message": f"Updated {len(link_ids)} links."}


async def create_collection(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    name: str,
    parent: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name}
    if parent:
        body["parentId"] = await resolver.collection_id(parent)
    created = await client.post("/api/v1/collections", json=body)
    await resolver.collections(refresh=True)
    parent_obj = created.get("parent") or {}
    return {
        "id": created.get("id"),
        "name": created.get("name"),
        "parent_id": parent_obj.get("id") if isinstance(parent_obj, dict) else None,
        "created": True,
    }


async def update_link(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_id: int,
    name: str | None = None,
    url: str | None = None,
    description: str | None = None,
    note: str | None = None,
    collection: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    current = await client.get(f"/api/v1/links/{link_id}")
    body: dict[str, Any] = {
        "name": name if name is not None else current.get("name"),
        "url": url if url is not None else current.get("url"),
        "description": description if description is not None else current.get("description"),
        "note": note if note is not None else current.get("note"),
    }
    if collection is not None:
        body["collectionId"] = await resolver.collection_id(collection)
    else:
        coll = current.get("collection") or {}
        body["collectionId"] = coll.get("id")
    if tags is not None:
        body["tags"] = tags
    else:
        body["tags"] = [t.get("name") for t in (current.get("tags") or []) if isinstance(t, dict)]
    updated = await client.put(f"/api/v1/links/{link_id}", json=body)
    return _link_result(updated)


async def queue_archive(
    client: LinkwardenClient,
    *,
    link_ids: list[int],
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    for link_id in link_ids:
        await client.put(f"/api/v1/links/{link_id}/archive")
    return {
        "queued_count": len(link_ids),
        "message": f"Queued preservation for {len(link_ids)} link(s). Processing is asynchronous.",
    }


def _link_result(link: dict[str, Any]) -> dict[str, Any]:
    collection = link.get("collection") or {}
    return {
        "id": link.get("id"),
        "name": link.get("name"),
        "url": link.get("url"),
        "collection": collection.get("name") if isinstance(collection, dict) else None,
    }
