# Implementation Plan: Linkwarden MCP Server

**Branch**: `001-linkwarden-mcp-server` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-linkwarden-mcp-server/spec.md`

## Summary

Replace the Docker-based Linkwarden MCP with a uvx-installable Python server exposing 15 workflow-shaped tools over stdio. Reads are always on; writes and deletes are gated by three env flags. An internal HTTP client enforces a source-tree-derived denylist before any request. All clarifications resolved: archive format (FR-014), tag merge PUT route with delete gating (FR-016), library overview from collections+tags (FR-017).

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: FastMCP ≥3.4.5, httpx ≥0.28.1  
**Storage**: N/A (stateless HTTP client; in-memory name-resolution cache per process)  
**Testing**: pytest, pytest-asyncio, respx  
**Target Platform**: Windows/macOS/Linux via uvx; stdio MCP transport  
**Project Type**: CLI MCP server (single package)  
**Performance Goals**: Responsive for ~948 links / ~90 collections; overview may paginate tags (correctness over speed)  
**Constraints**: No credentials required for import/`--help`; full test suite offline; bulk cap default 25  
**Scale/Scope**: 15 tools, FR-001–FR-017, 3 permission flags + bulk cap

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Project constitution (`.specify/memory/constitution.md`) is still the Spec Kit template — not ratified for this repo. **Gate waived** with note: follow ponytail/minimal-diff principles and FR requirements as governing constraints until constitution is amended.

Post-design re-check: No constitution violations identified. Design stays single-package, test-first for non-trivial paths, no speculative abstractions.

## Project Structure

### Documentation (this feature)

```text
specs/001-linkwarden-mcp-server/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── mcp-tools.md
│   └── denylist.md
├── spec.md
├── checklists/
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/linkwarden_mcp/
├── __init__.py
├── server.py            # FastMCP app, conditional tool registration, main()
├── config.py            # env parse, permission flags, startup validation
├── client.py            # httpx async client, denylist, error translation
├── resolve.py           # collection/tag name↔id cache (shared)
├── errors.py            # DeniedPathError, ApiError, BulkCapExceeded
├── sort.py              # word → integer sort mapping
└── tools/
    ├── reads.py         # 6 read tools
    ├── writes.py        # 5 write tools
    └── deletes.py       # 4 delete tools (incl. merge_tags)

openapi/
├── linkwarden.openapi.json   # vendored
└── DIVERGENCES.md

tests/
├── conftest.py          # respx fixtures, fake config
├── test_config.py
├── test_client_denylist.py
├── test_resolve.py
├── test_overview.py     # sum invariant, tag pagination
├── test_read_content.py
├── test_permissions.py  # tool registration per flag
└── test_tools/          # per-tool respx tests
```

**Structure Decision**: Single Python package under `src/linkwarden_mcp/`. Three tool modules by permission class. No separate service layer — tools call `client` + `resolve` directly (ponytail: one indirection max).

## Implementation Phases

### Phase A — Core infrastructure

1. `config.py` — lazy client factory, permission parsing (FR-002, FR-003)
2. `client.py` — denylist from source inventory (FR-004), bearer auth, API message errors (FR-013)
3. `resolve.py` — cached collections/tags fetch
4. `errors.py`, `sort.py`

### Phase B — Read tools (ship first)

5. `tools/reads.py` — search, get_link, list_*, get_library_overview (FR-006, FR-017)
6. `read_link_content` with textContent + archive format 3 (FR-014)
7. `server.py` — register read tools unconditionally

### Phase C — Write tools

8. `tools/writes.py` — save (FR-008/009), organise, create_collection, update (FR-010), queue_archive (FR-011)
9. Conditional registration on `LINKWARDEN_WRITE`

### Phase D — Delete tools

10. `tools/deletes.py` — delete_links, delete_tags, delete_collection, merge_tags (FR-016)
11. Conditional registration on DELETE flags
12. Bulk cap enforcement helper shared by all multi-record tools (FR-005)

### Phase E — Packaging and docs

13. Vendored OpenAPI + `DIVERGENCES.md` (FR-015) — seed from clarify findings
14. `pyproject.toml` description, README quickstart pointer
15. Full respx test suite (SC-007)

## Complexity Tracking

No constitution violations requiring justification.

## Generated Artifacts

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Tool contracts | [contracts/mcp-tools.md](./contracts/mcp-tools.md) |
| Denylist contract | [contracts/denylist.md](./contracts/denylist.md) |
| Quickstart | [quickstart.md](./quickstart.md) |

**Next command**: `/speckit-tasks` to generate `tasks.md`
