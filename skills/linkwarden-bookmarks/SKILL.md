---
name: linkwarden-bookmarks
description: >-
  Use when the user asks about Linkwarden bookmarks, collections, tags,
  save a link, search, unread/unsorted inbox, archive/preservation,
  triage, duplicates, overlap, or scoped save/organise/delete via
  linkwarden-mcp. Always call list_resources first.
---

# Linkwarden bookmarks

Pairs with the **linkwarden-mcp** MCP server.

## Discovery first

1. Call `list_resources`.
2. Trust its `read_only`, `write_scopes`, `delete_scopes`, `effective_write_scopes`, and `boundary`.
3. Prefer workflow tools (`smart_save_link`, `triage_links`, `get_sorting_dashboard`) over raw field edits when sorting or filing.

## Boundary

- Empty scopes → read-only tool set (**18** tools including `list_resources`).
- Mutations need `LINKWARDEN_MCP_WRITE_SCOPES` (create/update) and/or
  `LINKWARDEN_MCP_DELETE_SCOPES` (delete). Delete is never implied by write.
- Recommended write scopes: `links,collections` (not all domains).
- Valid domains: `links`, `collections`, `tags`, plus `raw` escape hatch.
- `raw` expands effective write scopes to all domain scopes.
- Never attempt tokens, session, auth, users (except `GET /api/v1/users/me`),
  migration, or whole-instance preservation endpoints.

## Config

- `LINKWARDEN_API_URL` — instance base URL (no `/api/v1` suffix)
- `LINKWARDEN_API_KEY` — Bearer access token; never echo
- Scope CSVs must match between local `.env` and the MCP host `env` block
- If a tool says Linkwarden is not reachable: tell the user to check URL/key
  and that the instance is up. Do not treat it as an MCP server crash.

## Precondition responses

When a tool returns setup guidance or a structured failure the user must fix:

1. Relay each item's `how_to_create` (or equivalent guidance) text to the user
   **verbatim**.
2. Stop. Do not invent a workaround or skip setup steps.

Also stop and relay verbatim for:

- Unknown / ambiguous collection or tag names (`UnknownNameError` /
  `AmbiguousNameError`) — list collections/tags first, or use an id.
- `BulkCapExceeded` — shrink the batch or raise `LINKWARDEN_MAX_BULK`.
- Dry-run payloads (`dry_run: true`) — do **not** apply until the user
  confirms `dry_run=false`.

## Task tools (prefer over raw CRUD)

Registered when required scopes are in `effective_write_scopes`:

| Tool | Scopes | Librarian sentence |
|------|--------|--------------------|
| `save_link` | WRITE `links` | Save this URL into a collection |
| `smart_save_link` | WRITE `links` | Save this URL with suggested collection/tags |
| `organise_links` | WRITE `links` | Move or retag these bookmarks |
| `update_link` | WRITE `links` | Edit this bookmark's fields |
| `queue_archive` | WRITE `links` | Queue preservation for these links (async) |
| `apply_triage_plan` | WRITE `links` | Apply this triage plan (`dry_run` default true) |
| `bulk_sort_by_rules` | WRITE `links` | Sort by domain rules (`dry_run` default true) |
| `create_collection` | WRITE `collections` | Create a collection |
| `auto_tag_by_domain` | WRITE `links` + `tags` | Tag by domain rules (`dry_run` default true) |
| `delete_links` | DELETE `links` | Delete these bookmarks |
| `delete_tags` | DELETE `tags` | Delete these tags |
| `merge_tags` | DELETE `tags` | Merge tags into one name |
| `delete_collection` | DELETE `collections` | Delete this collection and its links |

Prefer `smart_save_link` / `apply_triage_plan` / `bulk_sort_by_rules` over
manual `save_link` + `organise_links` when filing an inbox. Use `update_link`
only for targeted field edits.

## Verify after write

For any mutation:

1. Prefer `get_link` (or `search_links` / `list_collections` / `list_tags`) to
   confirm state before treating the change as done.
2. Mutate.
3. Re-fetch the affected link/collection/tag before reporting success.
4. If wrong and delete scope is enabled, `delete_*` / re-organise and retry.
5. Keep workflow writers at `dry_run=true` until the user explicitly asks to apply.

## Read tools

Match the user question to the tool:

| User asks… | Prefer |
|------------|--------|
| What can you do / are writes on? | `list_resources` |
| Find bookmarks about X / in a collection / tagged Y | `search_links` |
| Show one bookmark's metadata | `get_link` |
| What does the saved page say? | `read_link_content` |
| List folders / collections | `list_collections` |
| List tags | `list_tags` |
| Library totals / empty / unused | `get_library_overview` |
| Where should this URL go? | `suggest_collection_for_url` |
| What tags fit this link? | `suggest_tags_for_link` |
| What's in the unsorted inbox? | `find_unsorted_links` |
| Propose filing for these ids | `triage_links` |
| Any duplicate URLs? | `find_duplicate_links` |
| Best collection for this batch? | `recommend_collection_for_links` |
| What else belongs in this collection? | `suggest_links_for_collection` |
| Do these two collections overlap? | `analyze_collection_overlap` |
| Hygiene: empty / near-dup / overcrowded | `suggest_collection_structure` |
| Tags used on similar domains | `align_tags_with_similar_links` |
| One-shot triage snapshot | `get_sorting_dashboard` |

Always-registered reads: **18** tools (`list_resources` + 6 core + 11 workflows).
