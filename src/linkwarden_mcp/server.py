"""FastMCP server with conditional tool registration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from linkwarden_mcp import deletes, reads, workflows, writes
from linkwarden_mcp.config import Settings, get_client, get_settings, reset_state
from linkwarden_mcp.errors import (
    AmbiguousNameError,
    ApiError,
    BulkCapExceeded,
    ConfigError,
    UnknownNameError,
)
from linkwarden_mcp.resolve import NameResolver


@asynccontextmanager
async def _server_lifespan(_server: FastMCP) -> AsyncIterator[None]:
    settings = get_settings()
    settings.validate_runtime()
    client = get_client()
    try:
        await client.get("/api/v1/users/me")
        yield
    finally:
        await client.aclose()
        reset_state()


mcp = FastMCP("linkwarden-mcp", lifespan=_server_lifespan)

READ_ANNOTATIONS = {"readOnlyHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False}
DESTRUCTIVE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": True}

_tools_registered = False


def _resolver() -> NameResolver:
    return NameResolver(get_client())


def _settings() -> Settings:
    return get_settings()


def register_read_tools() -> None:
    @mcp.tool(name="search_links", annotations=READ_ANNOTATIONS)
    async def search_links_tool(
        query: str | None = None,
        collection: str | None = None,
        tag: str | None = None,
        pinned_only: bool | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search saved links by query, collection, tag, or pin status."""
        return await reads.search_links(
            get_client(),
            _resolver(),
            query=query,
            collection=collection,
            tag=tag,
            pinned_only=pinned_only,
            sort=sort,
            limit=limit,
        )

    @mcp.tool(name="get_link", annotations=READ_ANNOTATIONS)
    async def get_link_tool(link_id: int) -> dict[str, Any]:
        """Get full metadata for one link."""
        return await reads.get_link(get_client(), link_id)

    @mcp.tool(name="read_link_content", annotations=READ_ANNOTATIONS)
    async def read_link_content_tool(link_id: int) -> dict[str, Any]:
        """Read preserved plain text for a link (textContent or archive fallback)."""
        return await reads.read_link_content(get_client(), link_id)

    @mcp.tool(name="list_collections", annotations=READ_ANNOTATIONS)
    async def list_collections_tool(sort: str | None = None) -> list[dict[str, Any]]:
        """List collections with link counts."""
        return await reads.list_collections(get_client(), sort=sort)

    @mcp.tool(name="list_tags", annotations=READ_ANNOTATIONS)
    async def list_tags_tool(sort: str | None = None) -> list[dict[str, Any]]:
        """List tags with link counts."""
        return await reads.list_tags(get_client(), sort=sort)

    @mcp.tool(name="get_library_overview", annotations=READ_ANNOTATIONS)
    async def get_library_overview_tool() -> dict[str, Any]:
        """Summarise library totals, empty collections, and unused tags."""
        return await reads.get_library_overview(_resolver())


def register_write_tools() -> None:
    @mcp.tool(name="save_link", annotations=WRITE_ANNOTATIONS)
    async def save_link_tool(
        url: str,
        collection: str,
        tags: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Save a URL into a collection (by name)."""
        return await writes.save_link(
            get_client(),
            _resolver(),
            url=url,
            collection=collection,
            tags=tags,
            name=name,
            description=description,
            note=note,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="organise_links", annotations=WRITE_ANNOTATIONS)
    async def organise_links_tool(
        link_ids: list[int],
        collection: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Move or retag multiple links."""
        return await writes.organise_links(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            collection=collection,
            tags=tags,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="create_collection", annotations=WRITE_ANNOTATIONS)
    async def create_collection_tool(
        name: str,
        parent: str | None = None,
    ) -> dict[str, Any]:
        """Create a new collection."""
        return await writes.create_collection(
            get_client(), _resolver(), name=name, parent=parent
        )

    @mcp.tool(name="update_link", annotations=WRITE_ANNOTATIONS)
    async def update_link_tool(
        link_id: int,
        name: str | None = None,
        url: str | None = None,
        description: str | None = None,
        note: str | None = None,
        collection: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update link fields (read-modify-write)."""
        return await writes.update_link(
            get_client(),
            _resolver(),
            link_id=link_id,
            name=name,
            url=url,
            description=description,
            note=note,
            collection=collection,
            tags=tags,
        )

    @mcp.tool(name="queue_archive", annotations=WRITE_ANNOTATIONS)
    async def queue_archive_tool(link_ids: list[int]) -> dict[str, Any]:
        """Queue link preservation (async; not immediate)."""
        return await writes.queue_archive(
            get_client(), link_ids=link_ids, max_bulk=_settings().max_bulk
        )


def register_delete_tools() -> None:
    @mcp.tool(name="delete_links", annotations=DESTRUCTIVE_ANNOTATIONS)
    async def delete_links_tool(link_ids: list[int]) -> dict[str, Any]:
        """Delete multiple links."""
        return await deletes.delete_links(
            get_client(), link_ids=link_ids, max_bulk=_settings().max_bulk
        )

    @mcp.tool(name="delete_tags", annotations=DESTRUCTIVE_ANNOTATIONS)
    async def delete_tags_tool(
        tag_ids: list[int] | None = None,
        tag_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Delete tags by id or name."""
        return await deletes.delete_tags(
            get_client(),
            _resolver(),
            tag_ids=tag_ids,
            tag_names=tag_names,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="merge_tags", annotations=DESTRUCTIVE_ANNOTATIONS)
    async def merge_tags_tool(new_tag_name: str, tag_ids: list[int]) -> dict[str, Any]:
        """Merge tags into a new tag name (destructive)."""
        return await deletes.merge_tags(
            get_client(),
            _resolver(),
            new_tag_name=new_tag_name,
            tag_ids=tag_ids,
            max_bulk=_settings().max_bulk,
        )


def register_delete_collection_tool() -> None:
    @mcp.tool(name="delete_collection", annotations=DESTRUCTIVE_ANNOTATIONS)
    async def delete_collection_tool(collection: str | int) -> dict[str, Any]:
        """Delete a collection and all its links."""
        return await deletes.delete_collection(
            get_client(), _resolver(), collection=collection
        )


def register_workflow_read_tools() -> None:
    @mcp.tool(name="suggest_collection_for_url", annotations=READ_ANNOTATIONS)
    async def suggest_collection_for_url_tool(
        url: str,
        title: str | None = None,
        excerpt: str | None = None,
    ) -> dict[str, Any]:
        """Suggest top collections for a URL (heuristic; read-only)."""
        return await workflows.suggest_collection_for_url(
            get_client(), _resolver(), url=url, title=title, excerpt=excerpt
        )

    @mcp.tool(name="suggest_tags_for_link", annotations=READ_ANNOTATIONS)
    async def suggest_tags_for_link_tool(
        link_id: int | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Suggest existing-library tags for a link or URL (never invents new names)."""
        return await workflows.suggest_tags_for_link(
            get_client(), _resolver(), link_id=link_id, url=url
        )

    @mcp.tool(name="find_unsorted_links", annotations=READ_ANNOTATIONS)
    async def find_unsorted_links_tool(
        limit: int = 50,
        collection: str = "Unorganized",
    ) -> dict[str, Any]:
        """List unsorted links (default: Unorganized; scan capped at 500)."""
        return await workflows.find_unsorted_links(
            get_client(), _resolver(), limit=limit, collection=collection
        )

    @mcp.tool(name="triage_links", annotations=READ_ANNOTATIONS)
    async def triage_links_tool(link_ids: list[int]) -> dict[str, Any]:
        """Propose collection/tags for link ids (bulk-capped; no writes)."""
        return await workflows.triage_links(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="find_duplicate_links", annotations=READ_ANNOTATIONS)
    async def find_duplicate_links_tool(
        collection: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Group links with the same normalized URL (scan capped at 500)."""
        return await workflows.find_duplicate_links(
            get_client(), _resolver(), collection=collection, limit=limit
        )

    @mcp.tool(name="recommend_collection_for_links", annotations=READ_ANNOTATIONS)
    async def recommend_collection_for_links_tool(link_ids: list[int]) -> dict[str, Any]:
        """Consensus collection recommendation for a batch of links."""
        return await workflows.recommend_collection_for_links(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="suggest_links_for_collection", annotations=READ_ANNOTATIONS)
    async def suggest_links_for_collection_tool(
        collection: str,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Find links elsewhere that likely belong in a collection."""
        return await workflows.suggest_links_for_collection(
            get_client(), _resolver(), collection=collection, limit=limit
        )

    @mcp.tool(name="analyze_collection_overlap", annotations=READ_ANNOTATIONS)
    async def analyze_collection_overlap_tool(
        collection_a: str,
        collection_b: str,
    ) -> dict[str, Any]:
        """Compare two collections for shared domains, tags, and URLs."""
        return await workflows.analyze_collection_overlap(
            get_client(),
            _resolver(),
            collection_a=collection_a,
            collection_b=collection_b,
        )

    @mcp.tool(name="suggest_collection_structure", annotations=READ_ANNOTATIONS)
    async def suggest_collection_structure_tool() -> dict[str, Any]:
        """Hygiene report: empty collections, near-duplicate names, overcrowded."""
        return await workflows.suggest_collection_structure(get_client(), _resolver())

    @mcp.tool(name="align_tags_with_similar_links", annotations=READ_ANNOTATIONS)
    async def align_tags_with_similar_links_tool(
        link_id: int,
        min_count: int = 2,
    ) -> dict[str, Any]:
        """Suggest tags used on similar-domain links already in the library."""
        return await workflows.align_tags_with_similar_links(
            get_client(), _resolver(), link_id=link_id, min_count=min_count
        )

    @mcp.tool(name="get_sorting_dashboard", annotations=READ_ANNOTATIONS)
    async def get_sorting_dashboard_tool() -> dict[str, Any]:
        """One-shot triage dashboard: unsorted, duplicates, empty, largest."""
        return await workflows.get_sorting_dashboard(get_client(), _resolver())


def register_workflow_write_tools() -> None:
    @mcp.tool(name="smart_save_link", annotations=WRITE_ANNOTATIONS)
    async def smart_save_link_tool(
        url: str,
        collection: str | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        note: str | None = None,
        auto_apply_suggestions: bool = False,
    ) -> dict[str, Any]:
        """Save a URL with optional heuristic collection/tags (LINKWARDEN_WRITE)."""
        return await workflows.smart_save_link(
            get_client(),
            _resolver(),
            url=url,
            collection=collection,
            tags=tags,
            name=name,
            description=description,
            note=note,
            auto_apply_suggestions=auto_apply_suggestions,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="apply_triage_plan", annotations=WRITE_ANNOTATIONS)
    async def apply_triage_plan_tool(
        plan: list[dict[str, Any]],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply [{link_id, collection?, tags?}]. Default dry_run=true; bulk-capped."""
        return await workflows.apply_triage_plan(
            get_client(),
            _resolver(),
            plan=plan,
            dry_run=dry_run,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="auto_tag_by_domain", annotations=WRITE_ANNOTATIONS)
    async def auto_tag_by_domain_tool(
        link_ids: list[int],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply domain→tag rules. Default dry_run=true; only existing tag names."""
        return await workflows.auto_tag_by_domain(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            dry_run=dry_run,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(name="bulk_sort_by_rules", annotations=WRITE_ANNOTATIONS)
    async def bulk_sort_by_rules_tool(
        rules: list[dict[str, Any]],
        dry_run: bool = True,
        collection: str | None = "Unorganized",
    ) -> dict[str, Any]:
        """Match domain_pattern rules then organise. Default dry_run=true; bulk-capped."""
        return await workflows.bulk_sort_by_rules(
            get_client(),
            _resolver(),
            rules=rules,
            dry_run=dry_run,
            collection=collection,
            max_bulk=_settings().max_bulk,
        )


def register_all_tools(settings: Settings | None = None) -> None:
    global _tools_registered
    if _tools_registered:
        return
    cfg = settings or get_settings()
    register_read_tools()
    register_workflow_read_tools()
    if cfg.write:
        register_write_tools()
        register_workflow_write_tools()
    if cfg.delete:
        register_delete_tools()
    if cfg.delete_collections:
        register_delete_collection_tool()
    _tools_registered = True


def reset_registration() -> None:
    global _tools_registered
    _tools_registered = False
    import asyncio

    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        mcp.local_provider.remove_tool(tool.name)


def main() -> None:
    try:
        settings = get_settings()
        settings.validate_runtime()
        register_all_tools(settings)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc

    mcp.run()


__all__ = [
    "AmbiguousNameError",
    "ApiError",
    "BulkCapExceeded",
    "ConfigError",
    "UnknownNameError",
    "main",
    "mcp",
    "register_all_tools",
    "reset_registration",
    "reset_state",
]
