---
name: linkwarden-bookmarks
description: >-
  Use when the user asks about Linkwarden bookmarks, collections, tags,
  triage, duplicates, or scoped save/organise/delete via linkwarden-mcp.
  Always call list_resources first when mutating.
---

# Linkwarden bookmarks

Pairs with the **linkwarden-mcp** MCP server.

## Discovery first

1. Call `list_resources`.
2. Trust its `read_only`, `write_scopes`, `delete_scopes`, `effective_write_scopes`, and `boundary`.
3. Prefer workflow tools (`smart_save_link`, `triage_links`, `get_sorting_dashboard`) over raw CRUD when available.

## Boundary

- Empty scopes → read-only tool set (18 tools including `list_resources`).
- Mutations need `LINKWARDEN_MCP_WRITE_SCOPES` (create/update) and/or
  `LINKWARDEN_MCP_DELETE_SCOPES` (delete). Delete is never implied by write.
- Recommended write scopes: `links,collections` (not all domains).
- `raw` expands effective scopes to all domain scopes (escape hatch).
- Never attempt tokens, session, auth, users (except GET me), migration, or
  whole-instance preservation endpoints.

## Config

- `LINKWARDEN_URL` — instance base URL
- `LINKWARDEN_TOKEN` — Bearer token; never echo
- Scope CSVs must match between local `.env` and the MCP host `env` block

## Task / tool ↔ scope map

| Tool | Scope env |
|------|-----------|
| `save_link`, `update_link`, `organise_links`, `queue_archive` | WRITE `links` |
| `smart_save_link`, `apply_triage_plan`, `bulk_sort_by_rules` | WRITE `links` |
| `create_collection` | WRITE `collections` |
| `auto_tag_by_domain` | WRITE `links` + `tags` |
| `delete_links` | DELETE `links` |
| `delete_tags`, `merge_tags` | DELETE `tags` |
| `delete_collection` | DELETE `collections` |
