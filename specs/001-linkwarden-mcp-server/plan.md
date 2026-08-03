# Implementation Plan: Linkwarden MCP Server

**Branch**: `001-linkwarden-mcp-server` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-linkwarden-mcp-server/spec.md`

## Summary

Replace the Docker-based Linkwarden MCP with a uvx-installable Python server exposing 15 workflow-shaped tools over stdio. Reads are always on; writes and deletes are gated by three env flags. An internal HTTP client enforces a source-tree-derived denylist before any request. Repository layout follows [manager-mcp](https://github.com/flumpiey/manager-mcp) with two additions: `resolve.py` (shared name↔id cache) and `spec/DIVERGENCES.md` beside the vendored OpenAPI document.

## Technical Context

**Language/Version**: Python ≥3.10  
**Primary Dependencies**: FastMCP 2.x (`fastmcp>=2.0`), httpx  
**Build**: hatchling (not uv_build)  
**Dev Dependencies**: pytest, pytest-asyncio, respx, ruff, hatchling, hatch  
**Storage**: N/A (stateless HTTP client; in-memory name-resolution cache per process)  
**Testing**: pytest + respx — **all tests mocked**, no live-instance integration suite  
**Target Platform**: Windows/macOS/Linux via uvx; stdio MCP transport  
**Entry Point**: `[project.scripts] linkwarden-mcp = "linkwarden_mcp.server:main"`  
**Project Type**: Single-package MCP server (manager-mcp layout)  
**Performance Goals**: Responsive for ~948 links / ~90 collections; overview may paginate tags (correctness over speed)  
**Constraints**: Lazy client (no credentials for import/`--help`); bulk cap default 25; PyPI description final on first release  
**Scale/Scope**: 15 tools, FR-001–FR-017, 3 permission flags + bulk cap

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Project constitution (`.specify/memory/constitution.md`) is still the Spec Kit template — not ratified. **Gate waived**; FR requirements and manager-mcp conventions govern.

Post-design re-check: Single package, flat module layout, no integration tests, hatchling sdist from first commit — aligned with manager-mcp proven patterns.

## Project Structure

### Documentation (this feature)

```text
specs/001-linkwarden-mcp-server/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── mcp-tools.md
│   ├── denylist.md
│   └── packaging.md
├── spec.md
├── checklists/
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root — mirrors manager-mcp)

```text
src/linkwarden_mcp/
├── __init__.py
├── server.py            # FastMCP app, conditional tool registration, main()
├── client.py            # httpx client, denylist, error translation
├── config.py            # env parse, permission flags, lazy client factory
├── resolve.py           # collection/tag name↔id cache (shared by search, save, organise, overview)
├── errors.py
├── sort.py
├── reads.py             # 6 read tools
├── writes.py            # 5 write tools
├── deletes.py           # 4 delete tools (incl. merge_tags)
└── spec/
    ├── linkwarden.openapi.json   # vendored (provenance only; runtime uses live API)
    └── DIVERGENCES.md            # source-wins divergences from published spec

tests/
├── conftest.py          # respx fixtures
├── test_sdist_contents.py
├── test_config.py
├── test_client_denylist.py
├── test_resolve.py
├── test_overview.py
├── test_read_content.py
├── test_permissions.py
└── test_*.py            # remaining tool tests (all respx-mocked)

.github/workflows/
└── publish.yml          # filename MUST match PyPI trusted publisher registration

pyproject.toml           # hatchling, sdist include list, final description
README.md
LICENSE
```

**Structure Decision**: Flat package modules like manager-mcp (`client.py`, `server.py`, domain modules at package root). No `tools/` subpackage. Vendored spec lives under `src/linkwarden_mcp/spec/` (ships in wheel via hatch `packages`).

## Packaging & PyPI (carry-over traps)

See [contracts/packaging.md](./contracts/packaging.md). Non-negotiables from manager-mcp:

1. **`[tool.hatch.build.targets.sdist] include`** — explicit list from first commit (`src/`, `tests/`, `README.md`, `LICENSE`, `pyproject.toml`). Without it, hatch omits paths and produces empty/broken sdists.
2. **Workflow filename** — `.github/workflows/publish.yml` must match the PyPI trusted publisher registration exactly.
3. **`permissions: id-token: write`** on the publish job for OIDC.
4. **GitHub environment `pypi`** — create under repo Settings → Environments before first publish run.
5. **Description is immutable per version** — set `project.description` correctly before `0.1.0` upload; PyPI never allows re-uploading a version.

**Proposed description** (finalize before first tag):

> MCP server for Linkwarden bookmarks: read-first search and preserved content, with opt-in write, delete, and collection-delete tools.

## Implementation Phases

### Phase A — Project baseline (first commit)

1. `pyproject.toml` — hatchling, Python ≥3.10, FastMCP 2.x, dev deps, scripts entry, sdist include, ruff `py310`
2. `LICENSE`, `README.md`, `.github/workflows/publish.yml` (publish environment + OIDC)
3. `src/linkwarden_mcp/spec/` — placeholder openapi + seed `DIVERGENCES.md`
4. `tests/test_sdist_contents.py` — forbidden-path assertions (copy pattern from manager-mcp)

### Phase B — Core infrastructure

5. `config.py` — permission parsing (FR-002), lazy client (FR-003)
6. `client.py` — denylist from source tree (FR-004), bearer auth, API errors (FR-013)
7. `resolve.py` — cached collections/tags (shared FR-006, FR-008, FR-017)
8. `errors.py`, `sort.py`

### Phase C — Read tools

9. `reads.py` — search, get_link, list_*, get_library_overview (FR-017), read_link_content (FR-014)
10. `server.py` — register reads unconditionally; `main()` → `mcp.run()`

### Phase D — Write & delete tools

11. `writes.py` — save, organise, create_collection, update_link, queue_archive (FR-008–FR-011)
12. `deletes.py` — delete_links, delete_tags, merge_tags (FR-016), delete_collection
13. Conditional registration per FR-001; bulk cap helper (FR-005)

### Phase E — Test suite & spec docs

14. Full respx test suite — SC-007, denylist, permissions, overview invariants, merge PUT not POST
15. Complete `DIVERGENCES.md` from clarify findings (FR-015)

## Complexity Tracking

No constitution violations requiring justification.

## Generated Artifacts

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Tool contracts | [contracts/mcp-tools.md](./contracts/mcp-tools.md) |
| Denylist contract | [contracts/denylist.md](./contracts/denylist.md) |
| Packaging contract | [contracts/packaging.md](./contracts/packaging.md) |
| Quickstart | [quickstart.md](./quickstart.md) |

**Next command**: `/speckit-tasks`
