# Tasks: Linkwarden MCP Server

**Input**: Design documents from `/specs/001-linkwarden-mcp-server/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — spec SC-007 requires full mocked test suite passing without credentials.

**Organization**: By user story (US1–US4 from spec.md). US4 (safe setup) is partially satisfied in Phase 2 (config/import tests); permission matrix completes in Phase 6 after all tools register.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories

## Path Conventions

Single Python package at `src/linkwarden_mcp/`, tests at `tests/` (manager-mcp layout).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Packaging baseline — first commit must include sdist include list and publish workflow.

- [X] T001 Rewrite `pyproject.toml` for hatchling, Python ≥3.10, FastMCP 2.x, final description, sdist include, ruff py310 in `pyproject.toml`
- [X] T002 Add `LICENSE` (MIT, match manager-mcp)
- [X] T003 Update `README.md` with uvx install, env vars, and link to `specs/001-linkwarden-mcp-server/quickstart.md`
- [X] T004 [P] Add `.github/workflows/publish.yml` with `name: publish`, `pypi` environment, `id-token: write` per `contracts/packaging.md`
- [X] T005 [P] Create package skeleton `src/linkwarden_mcp/__init__.py` and `src/linkwarden_mcp/spec/` directory
- [X] T006 [P] Seed `src/linkwarden_mcp/spec/DIVERGENCES.md` with clarify findings (archive format, tag merge PUT, dashboard, collection create path)
- [X] T007 [P] Add vendored OpenAPI placeholder `src/linkwarden_mcp/spec/linkwarden.openapi.json`
- [X] T008 [P] Add `tests/test_sdist_contents.py` mirroring manager-mcp forbidden-path assertions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: HTTP client, config, name resolution — blocks all tools.

**⚠️ CRITICAL**: No user story tool work until this phase completes.

- [X] T009 Implement exception types in `src/linkwarden_mcp/errors.py` (DeniedPathError, ApiError, BulkCapExceeded)
- [X] T010 [P] Implement sort word→integer mapping in `src/linkwarden_mcp/sort.py`
- [X] T011 Implement env parsing, permission flags, lazy client factory, startup validation in `src/linkwarden_mcp/config.py` (FR-002, FR-003)
- [X] T012 Implement httpx client with source-tree denylist and API message extraction in `src/linkwarden_mcp/client.py` (FR-004, FR-013)
- [X] T013 Implement cached collection/tag name↔id resolution with ambiguity error when duplicate collection names match in `src/linkwarden_mcp/resolve.py` (FR-009)
- [X] T014 Add shared bulk-cap guard in `src/linkwarden_mcp/errors.py` or `src/linkwarden_mcp/config.py` (FR-005)
- [X] T015 Add respx fixtures and mock Linkwarden responses in `tests/conftest.py`
- [X] T016 [P] Add permission, startup validation, and import/`--help` no-network tests in `tests/test_config.py` (FR-003, US4 scenario 5)
- [X] T017 [P] Add parametrized denylist refusal tests for all denied categories in `contracts/denylist.md` (`tokens`, `session`, `auth`, `users` except `GET .../me`, `migration`, whole-instance `worker/preservation`, archive DELETE without linkIds) in `tests/test_client_denylist.py` (SC-003)
- [X] T018 [P] Add name resolution cache tests including ambiguous duplicate collection names (fail with match count, no arbitrary pick) in `tests/test_resolve.py` (FR-009)
- [X] T019 Create FastMCP app skeleton and `main()` entry in `src/linkwarden_mcp/server.py`

**Checkpoint**: Client, config, resolve importable; denylist tests pass; no tools registered yet.

---

## Phase 3: User Story 1 — Discover and Read (Priority: P1) 🎯 MVP

**Goal**: Six read tools — search, get link, read content, list collections/tags, library overview.

**Independent Test**: Start with url+token only; call all six read tools against respx mocks; no write/delete tools visible.

### Tests for User Story 1

- [X] T020 [P] [US1] Add search/get/list tool tests in `tests/test_reads.py`
- [X] T021 [P] [US1] Add textContent + archive format 3 fallback tests in `tests/test_read_content.py` (FR-014)
- [X] T022 [P] [US1] Add overview sum-invariant and tag-pagination tests in `tests/test_overview.py` (FR-017)

### Implementation for User Story 1

- [X] T023 [US1] Implement `search_links`, `get_link`, `list_collections`, `list_tags` in `src/linkwarden_mcp/reads.py` (FR-006)
- [X] T024 [US1] Implement `read_link_content` with textContent primary and format=3 fallback in `src/linkwarden_mcp/reads.py` (FR-014)
- [X] T025 [US1] Implement `get_library_overview` composing collections+tags in `src/linkwarden_mcp/reads.py` (FR-017)
- [X] T026 [US1] Register read tools unconditionally with `readOnlyHint` in `src/linkwarden_mcp/server.py`

**Checkpoint**: MVP — read-only MCP server runnable via `uv run linkwarden-mcp`.

---

## Phase 4: User Story 2 — Capture and Organise (Priority: P2)

**Goal**: Five write tools gated by `LINKWARDEN_WRITE`.

**Independent Test**: Enable write flag; save to existing collection by name creates no duplicate; organise, create, update, queue archive work via mocks.

### Tests for User Story 2

- [X] T027 [P] [US2] Add write tool tests including collection dedup on save, duplicate-url plain message, and bulk-cap refusal for `organise_links` and `queue_archive` in `tests/test_writes.py` (FR-008, FR-009, FR-013, SC-005, SC-006)

### Implementation for User Story 2

- [X] T028 [US2] Implement `save_link` with collection name resolve-before-create in `src/linkwarden_mcp/writes.py` (FR-008, FR-009)
- [X] T029 [US2] Implement `organise_links` and `create_collection` in `src/linkwarden_mcp/writes.py`
- [X] T030 [US2] Implement `update_link` read-modify-write in `src/linkwarden_mcp/writes.py` (FR-010)
- [X] T031 [US2] Implement `queue_archive` queued-not-completed messaging in `src/linkwarden_mcp/writes.py` (FR-011)
- [X] T032 [US2] Register write tools when `LINKWARDEN_WRITE` set in `src/linkwarden_mcp/server.py` (FR-001)

**Checkpoint**: Read + write server; delete tools still absent without delete flag.

---

## Phase 5: User Story 3 — Controlled Deletion (Priority: P3)

**Goal**: Four delete tools — links, tags, merge tags, delete collection — with separate gating.

**Independent Test**: Enable delete flags individually; bulk cap refuses with both counts; merge_tags uses PUT, delete-gated, link-count cap.

### Tests for User Story 3

- [X] T033 [P] [US3] Add delete and merge_tags tests (PUT not POST, duplicate-name warning, link bulk cap) plus bulk-cap refusal for `delete_links` and `delete_tags` in `tests/test_deletes.py` (FR-016, SC-006)

### Implementation for User Story 3

- [X] T034 [US3] Implement `delete_links` and `delete_tags` in `src/linkwarden_mcp/deletes.py`
- [X] T035 [US3] Implement `merge_tags` via `PUT /api/v1/tags/merge` with pre-checks in `src/linkwarden_mcp/deletes.py` (FR-016)
- [X] T036 [US3] Implement `delete_collection` in `src/linkwarden_mcp/deletes.py`
- [X] T037 [US3] Register delete tools when `LINKWARDEN_DELETE` / `LINKWARDEN_DELETE_COLLECTIONS` set with `destructiveHint` in `src/linkwarden_mcp/server.py` (FR-001)

**Checkpoint**: All 15 tools available with full permission flags enabled.

---

## Phase 6: User Story 4 — Safe Minimal Setup (Priority: P1)

**Goal**: Default read-only; invalid permissions abort startup; import/`--help` needs no credentials.

**Independent Test**: No flags → 6 read tools only; bad permission → startup error listing valid values; `python -c "import linkwarden_mcp"` no HTTP.

### Tests for User Story 4

- [X] T038 [P] [US4] Add tool registration matrix tests covering all flag combinations (default → 6 read; +WRITE → 11; +DELETE → 14; +DELETE_COLLECTIONS → 15) and `destructiveHint` on delete tools in `tests/test_permissions.py` (SC-002, FR-001, FR-002)

### Implementation for User Story 4

- [X] T039 [US4] Finalize conditional tool registration and startup identity check via `GET /users/me` in `src/linkwarden_mcp/server.py` and `src/linkwarden_mcp/config.py`

**Checkpoint**: Permission model fully enforced at registration and startup.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs, DIVERGENCES completeness, full suite green.

- [X] T040 Complete `src/linkwarden_mcp/spec/DIVERGENCES.md` with all source-vs-OpenAPI entries (FR-015)
- [X] T041 [P] Verify all tool names use verb prefixes for regression assertion in `tests/test_permissions.py` (FR-012)
- [X] T042 Run `uv run pytest` — full suite passes with zero credentials (SC-007)
- [X] T043 [P] Run `uv run ruff check src tests` and fix any issues
- [X] T044 [P] Run `uv run hatch build` and confirm `tests/test_sdist_contents.py` passes
- [X] T045 Validate manual smoke steps in `specs/001-linkwarden-mcp-server/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** → **Phase 2** → **Phases 3–6** (US1 can start immediately after Phase 2; US2–US4 need prior phases for registration wiring)
- **Phase 7** after Phases 3–6

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 (read) | Phase 2 | MVP — no write/delete |
| US2 (write) | Phase 2, US1 server wiring | Uses resolve.py from Phase 2 |
| US3 (delete) | Phase 2, server from US1–US2 | merge_tags delete-gated |
| US4 (setup) | Phase 2 (partial), all tool modules for matrix | T016 early; T038–T039 complete matrix |

### Parallel Opportunities

**Phase 1**: T004–T008 in parallel after T001–T003  
**Phase 2**: T010, T016–T018 in parallel after T009  
**US1 tests**: T020–T022 in parallel, then T023–T025 sequential in reads.py  
**US2–US3**: Test files parallel before implementation in same phase

### Parallel Example: User Story 1

```bash
# Tests first (parallel):
tests/test_reads.py
tests/test_read_content.py
tests/test_overview.py

# Then reads.py tools (sequential — one file):
search_links → read_link_content → get_library_overview

# Then server registration:
src/linkwarden_mcp/server.py
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 + Phase 2 (setup + foundation)
2. Phase 3 (US1 read tools)
3. **STOP** — demo read-only via MCP Inspector / Cursor config

### Incremental Delivery

1. US1 → read-only uvx server  
2. US2 → capture and organise  
3. US3 → gated deletion  
4. US4 verification + Phase 7 polish → release `0.1.0`

### Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| 1 Setup | T001–T008 (8) | — |
| 2 Foundational | T009–T019 (11) | — |
| 3 US1 Read | T020–T026 (7) | US1 |
| 4 US2 Write | T027–T032 (6) | US2 |
| 5 US3 Delete | T033–T037 (5) | US3 |
| 6 US4 Setup | T038–T039 (2) | US4 |
| 7 Polish | T040–T045 (6) | — |
| **Total** | **45** | |

**MVP scope**: Phases 1–3 (26 tasks) → read-only server with 6 tools.

---

## Notes

- Replace stub `hello()` in current `src/linkwarden_mcp/__init__.py` during T005
- Switch build backend from `uv_build` to `hatchling` in T001 before first PyPI publish
- Create GitHub `pypi` environment before running publish workflow
- All HTTP tests use respx — no live Linkwarden instance in CI
