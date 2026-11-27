# Changelog

All notable changes to this project are documented in this file.

## [0.1.7] - 2026-11-27

### Fixed

- Search: send the Linkwarden v2.17 query names (`searchQueryString`, `pinnedOnly`, `sort`) and follow `nextCursor` pages up to `limit` (default 50)
- Tags: resolve and list tags across all cursor pages, so `merge_tags` counts every affected link against the bulk cap
- `pinned` now reads `pinnedBy`; link and tag sort words map to the separate upstream `Sort` and `TagSort` enums
- `delete_collection`: refuse a collection with sub-collections or with more links than could be fetched; fetch links by id
- `bulk_sort_by_rules`: match exact host or subdomain only; it and `apply_triage_plan` keep existing tags
- `find_unsorted_links` adds "in Unorganized" only for links there; `suggest_links_for_collection` skips a missing "Favourites"
- `auto_tag_by_domain` and `bulk_sort_by_rules` report per-link `failures`; `save_link` treats only HTTP 409 as a duplicate
- Tag suggestions match whole tokens only

### Removed

- `note` parameter on `save_link`, `smart_save_link`, `update_link` and `note` in `get_link` output (Linkwarden has no such field)
- `sort` argument on `list_collections` (Linkwarden ignores it); tag sort words `tag_count_desc`/`tag_count_asc` (use `link_count_desc`/`link_count_asc` on `list_tags`)
- Empty vendored OpenAPI placeholder; one case-folded path denylist in `client.py` replaces the second list in `scopes.py`

### Changed

- Lock fastmcp 3.4.11 (pin unchanged, `<4.0`)

## [0.1.2] - 2026-08-03

### Fixed

- MCP Registry: shorten `server.json` description to satisfy ≤100 character limit

## [0.1.1] - 2026-08-03

### Fixed

- Claude Desktop extension: MCPB manifest 0.4 / uv type; drop system Python check

## [0.1.0] - 2026-08-03

### Added

- Initial Linkwarden MCP server with read-first tools and opt-in write/delete scopes
- Claude Desktop extension pack (`mcpb/`), Cursor plugin metadata, and MCP Registry `server.json`
