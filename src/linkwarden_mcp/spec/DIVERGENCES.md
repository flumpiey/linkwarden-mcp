# Linkwarden API divergences (source wins over OpenAPI)

Vendored OpenAPI is reference-only. Runtime behavior follows Linkwarden source tree.

## API response envelope

- **OpenAPI / mocks**: Often show bare arrays or objects.
- **Live instance**: Most routes return `{"response": ...}`; tags use `{"data": {"tags": [...], "nextCursor": ...}}`; search uses `{"data": {"links": [...]}}`.
- **MCP client**: Unwraps `response` in `client.py`; tags via `parse_tags_payload()`; search via `parse_links_payload()`.

## Archive content (`read_link_content`)

- **OpenAPI**: May omit archive format details.
- **Source**: `GET /api/v1/archives/{linkId}?format=3` returns raw Readability JSON (no envelope). Format enum: 0 PNG, 1 JPEG, 2 PDF, 3 Readability JSON, 4 Monolith HTML.

## Tag merge (`merge_tags`)

- **OpenAPI**: Route often absent from published spec.
- **Source**: `PUT /api/v1/tags/merge` with `{ newTagName, tagIds }`. POST returns 200 empty body (silent no-op). Destructive: deletes source tags.

## Collection create path

- **Source**: Only `"Unorganized"` gets find-or-create; other names must resolve to existing id before create to avoid duplicates.

## Dashboard

- **OpenAPI / UI**: `/api/v1/dashboard` is a 20-item activity feed, not library statistics.
- **MCP**: `get_library_overview` composes `GET /collections` + `GET /tags` instead.

## Tag update

- **Source**: Tag merge uses PUT, not POST.

## Workflow scans

- Workflow tools (`find_unsorted_links`, `find_duplicate_links`, overlap/structure helpers) scan at most **500 links** per collection query via `search` `take`.
- Suggestions are local heuristics (domain table + `difflib`); they do not call Linkwarden AI tagging APIs.
