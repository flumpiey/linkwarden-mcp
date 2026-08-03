# linkwarden-mcp

MCP server for [Linkwarden](https://linkwarden.app/) bookmarks: read-first search and preserved content, with opt-in write, delete, and collection-delete tools, plus heuristic triage workflows.

## Install

```bash
uvx linkwarden-mcp
```

Local development:

```bash
uv sync --dev
uv run linkwarden-mcp
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `LINKWARDEN_URL` | Yes (at runtime) | Linkwarden instance base URL |
| `LINKWARDEN_TOKEN` | Yes (at runtime) | Bearer API token |
| `LINKWARDEN_WRITE` | No | Enable write tools (`1`, `true`, or `yes`) |
| `LINKWARDEN_DELETE` | No | Enable delete tools including tag merge |
| `LINKWARDEN_DELETE_COLLECTIONS` | No | Enable `delete_collection` |
| `LINKWARDEN_MAX_BULK` | No | Max records per bulk op (default `25`) |

Without write/delete flags: **17** tools (6 read CRUD + 11 workflow read). With `LINKWARDEN_WRITE`: **26**. Full flags: **30**.

See [quickstart](specs/001-linkwarden-mcp-server/quickstart.md) for smoke tests and MCP client config.

## Tools

**Read (always):** `search_links`, `get_link`, `read_link_content`, `list_collections`, `list_tags`, `get_library_overview`

**Workflow read (always):** `suggest_collection_for_url`, `suggest_tags_for_link`, `find_unsorted_links`, `triage_links`, `find_duplicate_links`, `recommend_collection_for_links`, `suggest_links_for_collection`, `analyze_collection_overlap`, `suggest_collection_structure`, `align_tags_with_similar_links`, `get_sorting_dashboard`

**Write (`LINKWARDEN_WRITE`):** `save_link`, `organise_links`, `create_collection`, `update_link`, `queue_archive`

**Workflow write (`LINKWARDEN_WRITE`, `dry_run` default true):** `smart_save_link`, `apply_triage_plan`, `auto_tag_by_domain`, `bulk_sort_by_rules`

**Delete:** `delete_links`, `delete_tags`, `merge_tags` (`LINKWARDEN_DELETE`); `delete_collection` (`LINKWARDEN_DELETE_COLLECTIONS`)

## Cursor skills

| Skill | Use for |
|-------|---------|
| `linkwarden-save` | Bookmark a URL with suggestions |
| `linkwarden-triage` | Sort Unorganized / inbox |
| `linkwarden-hygiene` | Duplicates, overlap, empty collections |

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/smoke_mcp.py
```
