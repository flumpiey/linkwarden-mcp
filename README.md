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

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `LINKWARDEN_URL` | Yes (at runtime) | Linkwarden instance base URL |
| `LINKWARDEN_TOKEN` | Yes (at runtime) | Bearer API token |
| `LINKWARDEN_MCP_WRITE_SCOPES` | No | Comma-separated write domains (empty = read-only) |
| `LINKWARDEN_MCP_DELETE_SCOPES` | No | Comma-separated delete domains (never implied by write) |
| `LINKWARDEN_MAX_BULK` | No | Max records per bulk op (default `25`) |

Empty/unset scopes: **18** tools (`list_resources` + 6 read + 11 workflow read). Full domain scopes in WRITE + DELETE: **31** tools.

See [quickstart](specs/001-linkwarden-mcp-server/quickstart.md) for smoke tests and MCP client config.

## Write scopes and task tools

Valid scopes: `links`, `collections`, `tags`, `raw`.

- `raw` expands `effective_*` to all domain scopes (escape hatch).
- DELETE is never implied by WRITE.
- Recommended narrow set: `LINKWARDEN_MCP_WRITE_SCOPES=links,collections` and `LINKWARDEN_MCP_DELETE_SCOPES=links`.
- Full write (discouraged): all three domain scopes in WRITE and matching DELETE (31 tools).
- Legacy `LINKWARDEN_MCP_ALLOW_WRITES` / `ALLOW_WRITES` / `LINKWARDEN_MCP_WRITES` hard-fail if set.

| Tool | Required scope |
|------|----------------|
| `save_link`, `update_link`, `organise_links`, `queue_archive` | WRITE `links` |
| `smart_save_link`, `apply_triage_plan`, `bulk_sort_by_rules` | WRITE `links` |
| `create_collection` | WRITE `collections` |
| `auto_tag_by_domain` | WRITE `links` + `tags` |
| `delete_links` | DELETE `links` |
| `delete_tags`, `merge_tags` | DELETE `tags` |
| `delete_collection` | DELETE `collections` |

Call `list_resources` to inspect `read_only`, scope lists, and the current boundary string.

## Tools

**Read (always):** `list_resources`, `search_links`, `get_link`, `read_link_content`, `list_collections`, `list_tags`, `get_library_overview`

**Workflow read (always):** `suggest_collection_for_url`, `suggest_tags_for_link`, `find_unsorted_links`, `triage_links`, `find_duplicate_links`, `recommend_collection_for_links`, `suggest_links_for_collection`, `analyze_collection_overlap`, `suggest_collection_structure`, `align_tags_with_similar_links`, `get_sorting_dashboard`

**Write / delete:** registered only when matching scopes are set (see table above).

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

## Releasing

Do **not** publish by pushing to `main` alone. Before creating a GitHub Release:

1. Bump version in `pyproject.toml`, `server.json`, `mcpb/manifest.json`, and `.cursor-plugin/plugin.json`
2. Commit, then tag and push: `git tag v0.1.0 && git push origin v0.1.0`
3. Create a GitHub Release from that tag — the `publish` workflow builds, uploads to PyPI (OIDC), then publishes to the MCP Registry

Requires a GitHub Environment named `pypi` and a PyPI trusted publisher for this repo + `publish.yml` (no `PYPI_TOKEN` secret).
