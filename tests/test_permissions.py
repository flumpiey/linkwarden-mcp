"""Tool registration permission matrix (scope-gated)."""

from __future__ import annotations

import asyncio

import pytest

from linkwarden_mcp.config import reset_state
from linkwarden_mcp.scopes import WritePolicy
from linkwarden_mcp.server import mcp, register_all_tools, reset_registration

READ_TOOLS = {
    "list_resources",
    "search_links",
    "get_link",
    "read_link_content",
    "list_collections",
    "list_tags",
    "get_library_overview",
}
WORKFLOW_READ_TOOLS = {
    "suggest_collection_for_url",
    "suggest_tags_for_link",
    "find_unsorted_links",
    "triage_links",
    "find_duplicate_links",
    "recommend_collection_for_links",
    "suggest_links_for_collection",
    "analyze_collection_overlap",
    "suggest_collection_structure",
    "align_tags_with_similar_links",
    "get_sorting_dashboard",
}
LINKS_WRITE = {
    "save_link",
    "organise_links",
    "update_link",
    "queue_archive",
    "smart_save_link",
    "apply_triage_plan",
    "bulk_sort_by_rules",
}
COLLECTIONS_WRITE = {"create_collection"}
TAGS_WRITE = {"auto_tag_by_domain"}
LINKS_DELETE = {"delete_links"}
TAGS_DELETE = {"delete_tags", "merge_tags"}
COLLECTIONS_DELETE = {"delete_collection"}


def _tool_names() -> set[str]:
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def _register(policy: WritePolicy) -> set[str]:
    reset_state()
    reset_registration()
    register_all_tools(policy)
    return _tool_names()


def test_default_eighteen_read_tools() -> None:
    names = _register(WritePolicy(frozenset(), frozenset()))
    assert READ_TOOLS | WORKFLOW_READ_TOOLS == names
    assert len(names) == 18
    mutating = (
        LINKS_WRITE
        | COLLECTIONS_WRITE
        | TAGS_WRITE
        | LINKS_DELETE
        | TAGS_DELETE
        | COLLECTIONS_DELETE
    )
    assert not mutating & names


def test_links_write_registers_seven_tools() -> None:
    names = _register(WritePolicy(frozenset({"links"}), frozenset()))
    assert LINKS_WRITE <= names
    assert not COLLECTIONS_WRITE & names
    assert not TAGS_WRITE & names


def test_links_and_tags_write_registers_auto_tag() -> None:
    names = _register(WritePolicy(frozenset({"links", "tags"}), frozenset()))
    assert TAGS_WRITE <= names


def test_collections_write_registers_create() -> None:
    names = _register(WritePolicy(frozenset({"collections"}), frozenset()))
    assert COLLECTIONS_WRITE <= names
    assert not LINKS_WRITE & names


def test_delete_scopes_register_tools() -> None:
    names = _register(
        WritePolicy(frozenset(), frozenset({"links", "tags", "collections"}))
    )
    assert LINKS_DELETE | TAGS_DELETE | COLLECTIONS_DELETE <= names
    assert not LINKS_WRITE & names


def test_full_scopes_thirty_one_tools() -> None:
    names = _register(
        WritePolicy(
            frozenset({"links", "collections", "tags"}),
            frozenset({"links", "collections", "tags"}),
        )
    )
    assert len(names) == 31


@pytest.mark.parametrize("name", sorted(LINKS_DELETE | TAGS_DELETE | COLLECTIONS_DELETE))
def test_destructive_tools_have_prefix(name: str) -> None:
    assert name.startswith(("delete_", "merge_"))


def test_destructive_annotations() -> None:
    _register(
        WritePolicy(
            frozenset({"links"}),
            frozenset({"links", "tags", "collections"}),
        )
    )
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in LINKS_DELETE | TAGS_DELETE | COLLECTIONS_DELETE:
        ann = tools[name].annotations
        assert ann.destructiveHint is True
