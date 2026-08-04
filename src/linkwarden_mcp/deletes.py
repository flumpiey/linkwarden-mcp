"""Delete MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from linkwarden_mcp import reads, writes
from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import UnknownNameError, check_bulk_cap
from linkwarden_mcp.resolve import UNORGANIZED, NameResolver
from linkwarden_mcp.scopes import (
    DELETE_SCOPES_ENV,
    WRITE_SCOPES_ENV,
    WritesDeniedError,
)

OnLinksAction = Literal["delete", "move", "cancel"]

_ELICIT_CHOICES = [
    "delete_links",
    "move_to_unorganized",
    "move_to_other_collection",
    "cancel",
]


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


def _needs_user_input(
    *,
    collection_id: int,
    collection_name: str,
    link_count: int,
    link_ids: list[int],
) -> dict[str, Any]:
    return {
        "needs_user_input": True,
        "collection_id": collection_id,
        "collection_name": collection_name,
        "link_count": link_count,
        "link_ids_sample": link_ids[:10],
        "question": (
            f"Collection {collection_name!r} (id {collection_id}) contains "
            f"{link_count} link(s). Deleting the collection does not safely dispose "
            "of those links by itself — choose how to proceed."
        ),
        "options": [
            {
                "id": "delete",
                "label": "Delete all links in the collection, then delete the collection",
                "requires": f"'links' in {DELETE_SCOPES_ENV}",
            },
            {
                "id": "move",
                "label": (
                    "Move links to another collection (pass move_to; default "
                    f"{UNORGANIZED!r}), then delete the collection"
                ),
                "requires": f"'links' in {WRITE_SCOPES_ENV}",
            },
            {
                "id": "cancel",
                "label": "Cancel — do not delete the collection",
            },
        ],
        "how_to_proceed": (
            "Ask the user which option to use (MCP elicitation when the client "
            "supports it). Then call delete_collection again with "
            "on_links='delete'|'move'|'cancel' and move_to=<collection name> "
            "when moving."
        ),
    }


async def _resolve_on_links_via_elicit(
    ctx: Any,
    *,
    collection_name: str,
    collection_id: int,
    link_count: int,
) -> tuple[OnLinksAction | None, str | None, dict[str, Any] | None]:
    """Return (on_links, move_to, early_return)."""
    try:
        result = await ctx.elicit(
            (
                f"Collection {collection_name!r} (id {collection_id}) has "
                f"{link_count} link(s). How should those links be handled before "
                "deleting the collection?"
            ),
            response_type=_ELICIT_CHOICES,
        )
    except Exception:  # noqa: BLE001 — client may lack elicitation support
        return None, None, None

    action = getattr(result, "action", None)
    if action != "accept":
        return (
            "cancel",
            None,
            {
                "cancelled": True,
                "collection_id": collection_id,
                "collection_name": collection_name,
                "message": "Collection delete cancelled by user.",
            },
        )

    choice = result.data
    if choice == "cancel":
        return (
            "cancel",
            None,
            {
                "cancelled": True,
                "collection_id": collection_id,
                "collection_name": collection_name,
                "message": "Collection delete cancelled by user.",
            },
        )
    if choice == "delete_links":
        return "delete", None, None
    if choice == "move_to_unorganized":
        return "move", UNORGANIZED, None
    if choice == "move_to_other_collection":
        try:
            dest = await ctx.elicit(
                "Move links to which collection name before deleting?",
                response_type=str,
            )
        except Exception:  # noqa: BLE001 — client may lack elicitation support
            return None, None, None
        if getattr(dest, "action", None) != "accept" or not str(dest.data or "").strip():
            return (
                "cancel",
                None,
                {
                    "cancelled": True,
                    "collection_id": collection_id,
                    "collection_name": collection_name,
                    "message": "Collection delete cancelled (no move target).",
                },
            )
        return "move", str(dest.data).strip(), None
    return None, None, None


async def delete_collection(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection: str | int,
    on_links: OnLinksAction | None = None,
    move_to: str | None = None,
    max_bulk: int = 25,
    ctx: Any | None = None,
) -> dict[str, Any]:
    """Delete a collection after explicitly disposing of its links.

    When the collection has links and ``on_links`` is omitted, ask the user via
    MCP elicitation (``ctx.elicit``) when available; otherwise return a
    ``needs_user_input`` payload for the agent to relay and re-call.
    """
    collections = await resolver.collections(refresh=True)
    if isinstance(collection, int):
        collection_id = collection
        match = next((c for c in collections if int(c.get("id", -1)) == collection_id), None)
        if match is None:
            raise UnknownNameError("collection", str(collection_id))
        collection_name = str(match.get("name") or collection_id)
    else:
        collection_name = collection
        collection_id = await resolver.collection_id(collection)
        match = next((c for c in collections if int(c.get("id", -1)) == collection_id), None)

    links = await reads.fetch_links(
        client, resolver, collection=collection_name, limit=max_bulk + 1
    )
    link_ids = [int(link["id"]) for link in links if link.get("id") is not None]
    link_count = len(link_ids)
    meta_count = (match.get("_count") or {}).get("links", 0) if match else 0
    if meta_count and meta_count > link_count:
        # Cap scrape may be incomplete; refuse rather than partially dispose.
        check_bulk_cap(int(meta_count), max_bulk)

    if link_count == 0:
        await client.delete(f"/api/v1/collections/{collection_id}")
        await resolver.collections(refresh=True)
        return {
            "collection_id": collection_id,
            "collection_name": collection_name,
            "links_removed_count": 0,
            "links_disposition": "none",
            "message": f"Deleted empty collection {collection_name!r}.",
        }

    check_bulk_cap(link_count, max_bulk)

    resolved_on_links = on_links
    resolved_move_to = move_to

    if resolved_on_links is None and ctx is not None:
        elicited, elicited_move, early = await _resolve_on_links_via_elicit(
            ctx,
            collection_name=collection_name,
            collection_id=collection_id,
            link_count=link_count,
        )
        if early is not None:
            return early
        if elicited is not None:
            resolved_on_links = elicited
            if elicited_move is not None:
                resolved_move_to = elicited_move

    if resolved_on_links is None:
        return _needs_user_input(
            collection_id=collection_id,
            collection_name=collection_name,
            link_count=link_count,
            link_ids=link_ids,
        )

    if resolved_on_links == "cancel":
        return {
            "cancelled": True,
            "collection_id": collection_id,
            "collection_name": collection_name,
            "link_count": link_count,
            "message": "Collection delete cancelled.",
        }

    if resolved_on_links == "delete":
        if "links" not in client.policy.effective_delete_scopes:
            raise WritesDeniedError(
                f"Deleting collection links requires 'links' in {DELETE_SCOPES_ENV}."
            )
        await delete_links(client, link_ids=link_ids, max_bulk=max_bulk)
        disposition = "deleted"
        disposed = len(link_ids)
    elif resolved_on_links == "move":
        if "links" not in client.policy.effective_write_scopes:
            raise WritesDeniedError(
                f"Moving collection links requires 'links' in {WRITE_SCOPES_ENV}."
            )
        target = (resolved_move_to or UNORGANIZED).strip() or UNORGANIZED
        if target == collection_name:
            raise ValueError(
                f"move_to must differ from the collection being deleted ({collection_name!r})."
            )
        await writes.organise_links(
            client,
            resolver,
            link_ids=link_ids,
            collection=target,
            max_bulk=max_bulk,
        )
        disposition = f"moved:{target}"
        disposed = len(link_ids)
    else:
        raise ValueError("on_links must be one of: 'delete', 'move', 'cancel'.")

    await client.delete(f"/api/v1/collections/{collection_id}")
    await resolver.collections(refresh=True)
    return {
        "collection_id": collection_id,
        "collection_name": collection_name,
        "links_removed_count": disposed,
        "links_disposition": disposition,
        "message": (
            f"Disposed {disposed} link(s) via {disposition}, "
            f"then deleted collection {collection_name!r}."
        ),
    }
