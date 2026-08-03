# Research: Linkwarden MCP Server

**Feature**: `001-linkwarden-mcp-server`  
**Date**: 2026-08-03

All specification clarifications resolved in `/speckit-clarify` session 2026-08-03. No open NEEDS CLARIFICATION items remain.

## Decision: Transport and framework

**Decision**: Python 3.13, FastMCP 3.x, stdio transport, `uvx linkwarden-mcp` entry point.

**Rationale**: Project already scaffolded with `fastmcp` and `httpx` in `pyproject.toml`. stdio is the standard for local MCP clients (Cursor, Claude Desktop). FastMCP handles tool schema generation and MCP annotations.

**Alternatives considered**: Raw MCP Python SDK (more boilerplate); TypeScript (user requirement is Python/uvx); Docker image (explicitly replaced).

## Decision: Archive / read_link_content

**Decision**: Primary path — `textContent` on `GET /api/v1/links/{id}`. Fallback — `GET /api/v1/archives/{linkId}?format=3` (Readability JSON, raw file body). Integer format enum: 0 PNG, 1 JPEG, 2 PDF, 3 Readability JSON, 4 Monolith HTML.

**Rationale**: Confirmed from Linkwarden worker source (`handleReadability.ts`). No response envelope on success path.

**Alternatives considered**: Dashboard or list endpoints (wrong shape); string format names like `markdown` (do not exist); defer tool to v2 (rejected — core read gap).

## Decision: Tag merge route and gating

**Decision**: `PUT /api/v1/tags/merge` with `{ newTagName, tagIds }` (min one id). Gated under `LINKWARDEN_DELETE`, not `LINKWARDEN_WRITE`. Bulk cap measured in affected links.

**Rationale**: Handler only accepts PUT; POST returns 200 empty body (silent no-op). Operation deletes source tags — destructive.

**Alternatives considered**: POST (wrong method); write permission gating (understates destructiveness); client-side retag workflow (more calls, no atomic merge).

## Decision: Library overview data source

**Decision**: Compose from `GET /api/v1/collections` + `GET /api/v1/tags` (two calls, shared with `resolve.py` cache). Sum `_count.links` across collections for total links. Paginate tags to completion or mark partial.

**Rationale**: v1 `/api/v1/dashboard` is a 20-item activity feed (`take: 10` pinned + 10 recent, hardcoded). v2 dashboard is UI layout config. Collections/tags already expose counts.

**Alternatives considered**: Dashboard endpoint (no statistics); three+ calls including search totals (unnecessary).

## Decision: Denylist source of truth

**Decision**: Denylist derived from Linkwarden source tree route inventory, not OpenAPI prefix list alone.

**Rationale**: Routes like `PUT /api/v1/tags/merge` are absent from published spec. OpenAPI-only denylist would miss undocumented paths; allowlist-style tool layer is insufficient alone (FR-004 requires client-layer enforcement).

**Alternatives considered**: Tool-only omission (bypassable); OpenAPI-generated allowlist (incomplete).

## Decision: Testing without live instance

**Decision**: `pytest` + `respx` to mock Linkwarden HTTP. No credentials in CI. Regression tests for denylist, permission gating, bulk cap, one-link-per-collection sum invariant, tag pagination behavior.

**Rationale**: SC-007 requires full suite passes offline.

**Alternatives considered**: VCR against live instance (fragile, needs secrets); skipping merge/archive tests (insufficient coverage).

## Decision: Name resolution cache

**Decision**: Single `resolve.py` module caches collections and tags after first fetch; shared by `search_links`, `save_link`, `get_library_overview`, and other name-based tools.

**Rationale**: 90 collections / 948 links — repeated list calls per tool invocation is wasteful. Overview and search already need the same data.

**Alternatives considered**: Per-tool fetch (duplicate traffic); persistent disk cache (YAGNI for MCP session lifetime).
