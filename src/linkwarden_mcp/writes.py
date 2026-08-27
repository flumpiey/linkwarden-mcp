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
    body: dict[str, Any] = {"url": url, "collection": {"id": collection_id}}
    if name:
        body["name"] = name
    if description:
        body["description"] = description
    if note:
        body["note"] = note
    if tags:
        body["tags"] = [{"name": t} for t in tags]
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
    new_data: dict[str, Any] = {}
    if collection:
        new_data["collectionId"] = await resolver.collection_id(collection)
    if tags is not None:
        new_data["tags"] = [{"name": t} for t in tags]
    body: dict[str, Any] = {
        "links": [{"id": i} for i in link_ids],
        "removePreviousTags": tags is not None,
        "newData": new_data,
    }
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
    if collection is not None:
        coll_id, owner_id = await resolver.collection_id_and_owner(collection)
    else:
        coll = current.get("collection") or {}
        coll_id, owner_id = coll.get("id"), coll.get("ownerId")
    if tags is not None:
        tag_objs: list[dict[str, str]] = [{"name": t} for t in tags]
    else:
        tag_objs = [
            {"name": t.get("name")}
            for t in (current.get("tags") or [])
            if isinstance(t, dict) and t.get("name")
        ]
    body: dict[str, Any] = {
        "id": link_id,
        "name": name if name is not None else current.get("name"),
        "url": url if url is not None else current.get("url"),
        "description": description if description is not None else current.get("description"),
        "note": note if note is not None else current.get("note"),
        "collection": {"id": coll_id, "ownerId": owner_id},
        "tags": tag_objs,
    }
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
