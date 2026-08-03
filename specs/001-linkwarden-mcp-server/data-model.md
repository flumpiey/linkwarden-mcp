# Data Model: Linkwarden MCP Server

**Feature**: `001-linkwarden-mcp-server`

This document maps Linkwarden API entities to MCP tool inputs/outputs. The MCP server is stateless — it does not persist data locally.

## Remote entities (Linkwarden)

### Link

| Field | Use in MCP |
|-------|------------|
| `id` | Tool argument / result identifier |
| `name`, `url`, `description` | `get_link`, search results |
| `note` | `get_link`, `update_link` |
| `collectionId` | Resolved from collection name on write |
| `tags[]` | Search filter, organise, update |
| `textContent` | `read_link_content` primary path |
| `readable` | null / `"unavailable"` → plain unavailable message |
| `pinned` | Search filter |
| Preservation fields | `queue_archive` status messaging |

**Invariant (test)**: Each link belongs to exactly one collection — enables summing `_count.links` for library total.

### Collection

| Field | Use in MCP |
|-------|------------|
| `id`, `name` | Name ↔ id resolution |
| `parent.id`, `parent.name` | Nesting in `list_collections`, overview depth |
| `_count.links` | Overview totals, empty collection detection |
| `members[]` | Nested structure from `GET /collections` |

**Invariant**: Only `"Unorganized"` gets find-or-create on API; all other names must be resolved to id before create to avoid duplicates.

### Tag

| Field | Use in MCP |
|-------|------------|
| `id`, `name` | Name ↔ id resolution, merge input |
| `_count.links` | Overview unused-tag detection, sort 4/5 |

**Pagination**: Tag list uses instance `paginationTakeCount`; overview must cursor through or declare partial stats.

### Archive (Readability JSON, format 3)

Raw JSON file body (not wrapped). Fields used by MCP:

- `textContent` — plain text returned to agent
- `title`, `excerpt`, `byline`, `content`, `length`, `siteName` — optional metadata in structured tool output

### Readability status values

| `readable` | MCP behavior |
|------------|--------------|
| Completed preservation | Return textContent or archive fallback |
| null / `"unavailable"` | Plain message: not preserved or unsafe URL |
| In progress / failed | Plain message with status |

## Local configuration (env)

| Variable | Required | Purpose |
|----------|----------|---------|
| `LINKWARDEN_URL` | Yes (at runtime) | Instance base URL |
| `LINKWARDEN_TOKEN` | Yes (at runtime) | Bearer token |
| `LINKWARDEN_WRITE` | No | Enables 5 write tools |
| `LINKWARDEN_DELETE` | No | Enables delete_links, delete_tags, merge_tags |
| `LINKWARDEN_DELETE_COLLECTIONS` | No | Enables delete_collection |
| `LINKWARDEN_MAX_BULK` | No (default 25) | Max records per bulk operation |

Invalid values (`*`, `all`, globs, unknown names) → startup abort with valid list.

## MCP tool registry (15 tools)

### Read (always registered)

| Tool | Primary API |
|------|-------------|
| `search_links` | `GET /api/v1/search` |
| `get_link` | `GET /api/v1/links/{id}` |
| `read_link_content` | link `textContent`, then `GET /api/v1/archives/{id}?format=3` |
| `list_collections` | `GET /api/v1/collections` |
| `list_tags` | `GET /api/v1/tags` |
| `get_library_overview` | collections + tags (composed) |

### Write (`LINKWARDEN_WRITE`)

| Tool | Primary API |
|------|-------------|
| `save_link` | `POST /api/v1/links` (after collection id resolve) |
| `organise_links` | `PUT /api/v1/links` (bulk) |
| `create_collection` | `POST /api/v1/collections` |
| `update_link` | read-modify-write `GET` + `PUT /api/v1/links/{id}` |
| `queue_archive` | `PUT /api/v1/links/{id}/archive` |

### Delete (`LINKWARDEN_DELETE` / `LINKWARDEN_DELETE_COLLECTIONS`)

| Tool | Permission | Primary API |
|------|------------|-------------|
| `delete_links` | DELETE | `DELETE /api/v1/links` |
| `delete_tags` | DELETE | `DELETE /api/v1/tags` |
| `merge_tags` | DELETE | `PUT /api/v1/tags/merge` |
| `delete_collection` | DELETE_COLLECTIONS | `DELETE /api/v1/collections/{id}` |

## Sort word mapping

| Word | API integer |
|------|-------------|
| newest | 0 |
| oldest | 1 |
| name / name_asc | 2 |
| name_desc | 3 |
| tag_count_desc | 4 |
| tag_count_asc | 5 |

## Library overview output shape

```text
total_collections: int
total_links: int          # sum of collection _count.links
total_tagged_links: int   # from tag counts (may be partial)
max_nesting_depth: int
empty_collections: list   # name + id, _count.links == 0
unused_tags: list         # name + id, _count.links == 0
unorganized_link_count: int
tags_partial: bool        # true if tag pagination incomplete
```
