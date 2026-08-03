"""Tool registration permission matrix."""

from __future__ import annotations

import asyncio

import pytest

from linkwarden_mcp.config import Settings, reset_state
from linkwarden_mcp.server import mcp, register_all_tools, reset_registration

READ_TOOLS = {
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
WRITE_TOOLS = {
    "save_link",
    "organise_links",
    "create_collection",
    "update_link",
    "queue_archive",
}
WORKFLOW_WRITE_TOOLS = {
    "smart_save_link",
    "apply_triage_plan",
    "auto_tag_by_domain",
    "bulk_sort_by_rules",
}
DELETE_TOOLS = {"delete_links", "delete_tags", "merge_tags"}
DELETE_COLLECTION_TOOLS = {"delete_collection"}


def _tool_names() -> set[str]:
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def _register(settings: Settings) -> set[str]:
    reset_state()
    reset_registration()
    register_all_tools(settings)
    return _tool_names()


def test_default_seventeen_read_tools() -> None:
    names = _register(Settings("", "", False, False, False, 25))
    assert READ_TOOLS | WORKFLOW_READ_TOOLS == names
    assert len(names) == 17
    assert not (WRITE_TOOLS | WORKFLOW_WRITE_TOOLS | DELETE_TOOLS | DELETE_COLLECTION_TOOLS) & names


def test_write_flag_adds_nine_tools() -> None:
    names = _register(Settings("", "", True, False, False, 25))
    assert (
        READ_TOOLS | WORKFLOW_READ_TOOLS | WRITE_TOOLS | WORKFLOW_WRITE_TOOLS == names
    )
    assert len(names) == 26


def test_delete_flag_adds_three_tools() -> None:
    names = _register(Settings("", "", False, True, False, 25))
    assert READ_TOOLS | WORKFLOW_READ_TOOLS | DELETE_TOOLS == names


def test_all_flags_thirty_tools() -> None:
    names = _register(Settings("", "", True, True, True, 25))
    assert len(names) == 30


@pytest.mark.parametrize("name", sorted(DELETE_TOOLS | DELETE_COLLECTION_TOOLS))
def test_destructive_tools_have_prefix(name: str) -> None:
    assert name.startswith(("delete_", "merge_"))


def test_destructive_annotations() -> None:
    _register(Settings("", "", True, True, True, 25))
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in DELETE_TOOLS | DELETE_COLLECTION_TOOLS:
        ann = tools[name].annotations
        assert ann.destructiveHint is True
