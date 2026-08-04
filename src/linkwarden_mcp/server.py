"""FastMCP server with scope-gated tool registration."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import Icon

from linkwarden_mcp import deletes, reads, workflows, writes
from linkwarden_mcp.config import Settings, get_client, get_policy, get_settings, reset_state
from linkwarden_mcp.errors import (
    AmbiguousNameError,
    ApiError,
    BulkCapExceeded,
    ConfigError,
    UnknownNameError,
)
from linkwarden_mcp.resolve import NameResolver
from linkwarden_mcp.scopes import DOMAIN_SCOPES, ScopeConfigError, WritePolicy, WritesDeniedError
from linkwarden_mcp.task_tools import require_delete_scope, require_write_scopes

_ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.png"
_ICON_HTTPS = (
    "https://raw.githubusercontent.com/flumpiey/linkwarden-mcp/main/docs/icon-512.png"
)


def server_icons() -> list[Icon]:
    """Icons for initialize serverInfo (data URI + public HTTPS fallback)."""
    icons: list[Icon] = []
    if _ICON_PATH.is_file():
        b64 = base64.standard_b64encode(_ICON_PATH.read_bytes()).decode("ascii")
        icons.append(
            Icon(
                src=f"data:image/png;base64,{b64}",
                mimeType="image/png",
                sizes=["512x512"],
            )
        )
    icons.append(Icon(src=_ICON_HTTPS, mimeType="image/png", sizes=["512x512"]))
    return icons


@asynccontextmanager
async def _server_lifespan(_server: FastMCP) -> AsyncIterator[None]:
    settings = get_settings()
    settings.validate_runtime()
    get_policy()
    client = get_client()
    try:
        await client.get("/api/v1/users/me")
        yield
    finally:
        await client.aclose()
        reset_state()


mcp = FastMCP(
    "linkwarden-mcp",
    website_url="https://linkwarden.app/",
    icons=server_icons(),
    lifespan=_server_lifespan,
)

READ_ANNOTATIONS = {"readOnlyHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False}
DESTRUCTIVE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": True}

_tools_registered = False


def _resolver() -> NameResolver:
    return NameResolver(get_client())


def _settings() -> Settings:
    return get_settings()


def register_list_resources() -> None:
    @mcp.tool(
        name="list_resources",
        annotations=READ_ANNOTATIONS,
        description=(
            "List Linkwarden MCP capabilities and current write/delete scope boundary. "
            "Call first when unsure whether mutations are enabled."
        ),
    )
    async def list_resources() -> dict[str, Any]:
        policy = get_policy()
        write_scopes = sorted(policy.write_scopes)
        delete_scopes = sorted(policy.delete_scopes)
        effective_write = sorted(policy.effective_write_scopes)
        read_only = not (write_scopes or delete_scopes)
        if read_only:
            boundary = (
                "Default is read-only: no write or delete tools are registered. "
                "Set LINKWARDEN_MCP_WRITE_SCOPES / LINKWARDEN_MCP_DELETE_SCOPES to enable "
                "mutations. Recommended write scopes: links,collections (not all domains)."
            )
        else:
            boundary = (
                f"Scoped writes enabled. effective_write_scopes={effective_write}. "
                "DELETE is never implied by WRITE. Prefer narrow scopes "
                "(links,collections) over raw or all domains."
            )
        return {
            "read_only": read_only,
            "write_scopes": write_scopes,
            "delete_scopes": delete_scopes,
            "effective_write_scopes": effective_write,
            "valid_scopes": sorted(DOMAIN_SCOPES | {"raw"}),
            "boundary": boundary,
        }


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


def register_links_write_tools() -> None:
    @mcp.tool(
        name="save_link",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Save a URL into a collection (by name). "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def save_link_tool(
        url: str,
        collection: str,
        tags: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
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

    @mcp.tool(
        name="organise_links",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Move or retag multiple links. "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def organise_links_tool(
        link_ids: list[int],
        collection: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
        return await writes.organise_links(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            collection=collection,
            tags=tags,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(
        name="update_link",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Update link fields (read-modify-write). "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def update_link_tool(
        link_id: int,
        name: str | None = None,
        url: str | None = None,
        description: str | None = None,
        note: str | None = None,
        collection: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
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

    @mcp.tool(
        name="queue_archive",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Queue link preservation (async; not immediate). "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def queue_archive_tool(link_ids: list[int]) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
        return await writes.queue_archive(
            get_client(), link_ids=link_ids, max_bulk=_settings().max_bulk
        )


def register_collections_write_tools() -> None:
    @mcp.tool(
        name="create_collection",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Create a new collection. "
            "Requires 'collections' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def create_collection_tool(
        name: str,
        parent: str | None = None,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "collections")
        return await writes.create_collection(
            get_client(), _resolver(), name=name, parent=parent
        )


def register_links_workflow_write_tools() -> None:
    @mcp.tool(
        name="smart_save_link",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Save a URL with optional heuristic collection/tags. "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def smart_save_link_tool(
        url: str,
        collection: str | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        note: str | None = None,
        auto_apply_suggestions: bool = False,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
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

    @mcp.tool(
        name="apply_triage_plan",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Apply [{link_id, collection?, tags?}]. Default dry_run=true; bulk-capped. "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def apply_triage_plan_tool(
        plan: list[dict[str, Any]],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
        return await workflows.apply_triage_plan(
            get_client(),
            _resolver(),
            plan=plan,
            dry_run=dry_run,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(
        name="bulk_sort_by_rules",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Match domain_pattern rules then organise. Default dry_run=true; bulk-capped. "
            "Requires 'links' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def bulk_sort_by_rules_tool(
        rules: list[dict[str, Any]],
        dry_run: bool = True,
        collection: str | None = "Unorganized",
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links")
        return await workflows.bulk_sort_by_rules(
            get_client(),
            _resolver(),
            rules=rules,
            dry_run=dry_run,
            collection=collection,
            max_bulk=_settings().max_bulk,
        )


def register_tags_workflow_write_tools() -> None:
    @mcp.tool(
        name="auto_tag_by_domain",
        annotations=WRITE_ANNOTATIONS,
        description=(
            "Apply domain→tag rules. Default dry_run=true; only existing tag names. "
            "Requires 'links' and 'tags' in LINKWARDEN_MCP_WRITE_SCOPES."
        ),
    )
    async def auto_tag_by_domain_tool(
        link_ids: list[int],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        require_write_scopes(get_policy(), "links", "tags")
        return await workflows.auto_tag_by_domain(
            get_client(),
            _resolver(),
            link_ids=link_ids,
            dry_run=dry_run,
            max_bulk=_settings().max_bulk,
        )


def register_links_delete_tools() -> None:
    @mcp.tool(
        name="delete_links",
        annotations=DESTRUCTIVE_ANNOTATIONS,
        description=(
            "Delete multiple links. "
            "Requires 'links' in LINKWARDEN_MCP_DELETE_SCOPES."
        ),
    )
    async def delete_links_tool(link_ids: list[int]) -> dict[str, Any]:
        require_delete_scope(get_policy(), "links")
        return await deletes.delete_links(
            get_client(), link_ids=link_ids, max_bulk=_settings().max_bulk
        )


def register_tags_delete_tools() -> None:
    @mcp.tool(
        name="delete_tags",
        annotations=DESTRUCTIVE_ANNOTATIONS,
        description=(
            "Delete tags by id or name. "
            "Requires 'tags' in LINKWARDEN_MCP_DELETE_SCOPES."
        ),
    )
    async def delete_tags_tool(
        tag_ids: list[int] | None = None,
        tag_names: list[str] | None = None,
    ) -> dict[str, Any]:
        require_delete_scope(get_policy(), "tags")
        return await deletes.delete_tags(
            get_client(),
            _resolver(),
            tag_ids=tag_ids,
            tag_names=tag_names,
            max_bulk=_settings().max_bulk,
        )

    @mcp.tool(
        name="merge_tags",
        annotations=DESTRUCTIVE_ANNOTATIONS,
        description=(
            "Merge tags into a new tag name (destructive). "
            "Requires 'tags' in LINKWARDEN_MCP_DELETE_SCOPES."
        ),
    )
    async def merge_tags_tool(new_tag_name: str, tag_ids: list[int]) -> dict[str, Any]:
        require_delete_scope(get_policy(), "tags")
        return await deletes.merge_tags(
            get_client(),
            _resolver(),
            new_tag_name=new_tag_name,
            tag_ids=tag_ids,
            max_bulk=_settings().max_bulk,
        )


def register_collections_delete_tools() -> None:
    @mcp.tool(
        name="delete_collection",
        annotations=DESTRUCTIVE_ANNOTATIONS,
        description=(
            "Delete a collection after disposing of its links. When the collection "
            "has links, asks the user (MCP elicitation) whether to delete those "
            "links, move them (move_to, default Unorganized), or cancel. Without "
            "elicitation, returns needs_user_input — ask the user, then re-call "
            "with on_links='delete'|'move'|'cancel'. Requires 'collections' in "
            "LINKWARDEN_MCP_DELETE_SCOPES; delete/move also need matching links "
            "delete/write scopes."
        ),
    )
    async def delete_collection_tool(
        collection: str | int,
        ctx: Context,
        on_links: str | None = None,
        move_to: str | None = None,
    ) -> dict[str, Any]:
        require_delete_scope(get_policy(), "collections")
        action: deletes.OnLinksAction | None = None
        if on_links is not None:
            normalized = on_links.strip().casefold()
            if normalized not in {"delete", "move", "cancel"}:
                raise ValueError("on_links must be one of: 'delete', 'move', 'cancel'.")
            action = normalized  # type: ignore[assignment]
        return await deletes.delete_collection(
            get_client(),
            _resolver(),
            collection=collection,
            on_links=action,
            move_to=move_to,
            max_bulk=_settings().max_bulk,
            ctx=ctx,
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


def register_all_tools(policy: WritePolicy | None = None) -> None:
    global _tools_registered
    if _tools_registered:
        return
    p = policy or get_policy()
    register_list_resources()
    register_read_tools()
    register_workflow_read_tools()
    ew = p.effective_write_scopes
    ed = p.effective_delete_scopes
    if "links" in ew:
        register_links_write_tools()
        register_links_workflow_write_tools()
    if "collections" in ew:
        register_collections_write_tools()
    if "links" in ew and "tags" in ew:
        register_tags_workflow_write_tools()
    if "links" in ed:
        register_links_delete_tools()
    if "tags" in ed:
        register_tags_delete_tools()
    if "collections" in ed:
        register_collections_delete_tools()
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
        policy = get_policy()
        register_all_tools(policy)
    except (ConfigError, ScopeConfigError) as exc:
        raise SystemExit(str(exc)) from exc

    mcp.run()


__all__ = [
    "AmbiguousNameError",
    "ApiError",
    "BulkCapExceeded",
    "ConfigError",
    "ScopeConfigError",
    "UnknownNameError",
    "WritesDeniedError",
    "get_policy",
    "main",
    "mcp",
    "register_all_tools",
    "reset_registration",
    "reset_state",
]
