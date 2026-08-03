# Feature Specification: Linkwarden MCP Server

**Feature Branch**: `001-linkwarden-mcp-server`

**Created**: 2026-08-03

**Status**: Ready for implementation

**Input**: User description: "A Python MCP server for Linkwarden, installable with uvx, that replaces the Docker-based Linkwarden MCP. Exposes a curated set of tools shaped around actual bookmark-library workflows rather than mirroring every API operation. Serves a library of ~948 links across ~90 collections on a self-hosted instance."

## Clarifications

### Session 2026-08-03

- Q: How should preserved page content (`read_link_content`) be retrieved given archive format uncertainty? → A: All 15 tools ship in v1. Primary path: plain text from the link's `textContent` field when present. Fallback: archive fetch with integer format `3` (Readability JSON — fields include `title`, `byline`, `content`, `textContent`, `excerpt`, `length`, `siteName`) as a raw file body with no response envelope. When no preserved content exists, report plainly why rather than returning an empty string. Archive format enum confirmed from source: 0 PNG, 1 JPEG, 2 PDF, 3 Readability JSON, 4 Monolith HTML. Live probe retained for version verification only, not as an implementation gate.
- Q: What route and method should `merge_tags` call? → A: `PUT /api/v1/tags/merge` with body `{ newTagName, tagIds }` (`tagIds` requires at least one entry). Confirmed from source (`apps/web/pages/api/v1/tags/merge.ts`). POST is not valid — the handler only branches on PUT; POST returns 200 with an empty body and performs no merge. Operation is destructive: deletes every tag in `tagIds`, creates a new tag with `newTagName`, connects it to affected links, and nulls `indexVersion` on them. No connectOrCreate — an existing `newTagName` creates a duplicate tag rather than merging into it. Gated behind delete permission, not write permission.
- Q: How should `get_library_overview` gather library state? → A: Compose from `GET /api/v1/collections` and `GET /api/v1/tags` (two calls, shared with name-resolution cache). Do not call either dashboard endpoint — v1 dashboard returns a fixed 20-item activity feed with no statistics; v2 dashboard returns UI layout configuration. Collections response includes `_count.links`, nesting, and member list; tags response includes `_count.links` and supports link-count sort. Total link count derived by summing collection link counts (one link per collection). Tag list may paginate — overview must follow cursor or state figures are partial.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and read saved knowledge (Priority: P1)

As someone who saves articles and references into Linkwarden, I want to search my library by topic, collection, or tag and read preserved page content so I can ask questions about what I have saved rather than only seeing link metadata.

**Why this priority**: Reading preserved content is the primary gap in the current Docker MCP. Without it, the bookmark library cannot answer "what did that article say?" — only "what links exist?"

**Independent Test**: Can be fully tested by searching for a known topic, opening a link by id, listing collections and tags, and reading preserved text — all with read-only permissions and no write access granted.

**Acceptance Scenarios**:

1. **Given** a library with links about Postgres tuning, **When** I search for "Postgres tuning", **Then** I receive matching links with enough detail to identify the right one.
2. **Given** a collection named Homelab with docker-tagged links, **When** I search within Homelab filtered by tag docker, **Then** I receive only links in that collection with that tag.
3. **Given** a known link id, **When** I request link details, **Then** I receive title, url, collection, tags, notes, and preservation status.
4. **Given** a link with a completed preservation, **When** I request its preserved content, **Then** I receive plain text suitable for summarisation, preferring the link's stored text content and falling back to the Readability archive when needed.
5. **Given** a link with no preservation or a rejected url, **When** I request its preserved content, **Then** I receive a plain explanation of why content is unavailable — not an empty string.
6. **Given** any configured instance, **When** I list collections, **Then** I see collection names and nesting.
7. **Given** any configured instance, **When** I list tags, **Then** I see tags I actually use.
8. **Given** any configured instance, **When** I request a library overview, **Then** I receive total collections, total links (summed from collection counts), nesting depth, empty collections, unused tags, and Unorganized collection size — without calling a dashboard endpoint.
9. **Given** a library whose tag count exceeds one paginated page, **When** I request a library overview, **Then** the overview either paginates through all tags or states plainly that tag figures are partial.

---

### User Story 2 - Capture and organise links (Priority: P2)

As someone building a personal knowledge library, I want to save new links into named collections, tag them, move groups of links, and update metadata so my library stays organised without manual UI work.

**Why this priority**: Capture and retrieval carry equal product weight, but writes depend on name resolution that search already requires. Reads ship first; writes follow once discovery works.

**Independent Test**: Can be tested by enabling write permission, saving a link to a named collection, organising a batch into another collection with tags, creating a nested collection, updating a link's title and note, and queueing re-preservation — each operation confirmed in the response. Tag merge is tested separately under delete permission (User Story 3).

**Acceptance Scenarios**:

1. **Given** write permission enabled and a url not yet saved, **When** I save it to collection "Reading List" tagged rust, **Then** the link appears in that collection with the rust tag.
2. **Given** write permission and collection "Reading List" already exists, **When** I save another link to "Reading List", **Then** the link joins the existing collection and no duplicate collection is created.
3. **Given** write permission and collection "Rust" does not exist under "Programming", **When** I create collection Rust under Programming, **Then** the new nested collection exists and the response names what was created.
4. **Given** write permission and five link ids, **When** I organise them into Homelab with tag docker, **Then** all five move and receive the tag.
5. **Given** write permission and link 412, **When** I update only its name and note, **Then** other fields remain unchanged.
6. **Given** write permission and links with broken snapshots, **When** I queue archive for those links, **Then** the response states preservation was queued, not completed.

---

### User Story 3 - Controlled deletion (Priority: P3)

As a library owner, I want destructive operations gated separately from ordinary writes so an agent cannot accidentally delete collections (which cascade to every link inside) or bulk-delete more than I intend.

**Why this priority**: Deletion is recoverable only in the sense that bookmarks can be re-added; cascading collection deletion can destroy hundreds of links from one mistaken id. Separate gating reduces blast radius.

**Independent Test**: Can be tested by enabling delete permissions individually, attempting deletes and tag merges without permission (refused), attempting bulk operations over the cap (refused with counts), and successful small-batch deletes and merges when permitted.

**Acceptance Scenarios**:

1. **Given** only read and write permissions (no delete), **When** I attempt to delete links or merge tags, **Then** those tools are not available.
2. **Given** delete permission and four link ids, **When** I delete those links, **Then** they are removed and the response confirms count.
3. **Given** delete permission and unused tags, **When** I delete those tags, **Then** they are removed from the library.
4. **Given** delete permission and tags k8s and kubernetes naming fewer links than the bulk cap, **When** I merge k8s into kubernetes, **Then** source tags are deleted, a new kubernetes tag is created, affected links are retagged, and the response names the new tag id and link count moved.
5. **Given** delete-collection permission and collection Scratch, **When** I delete that collection, **Then** the collection and all links inside it are removed.
6. **Given** any permission level, **When** I attempt to affect more records than the configured bulk cap, **Then** the operation is refused outright with both the requested count and the cap named — nothing is partially applied.

---

### User Story 4 - Safe, minimal setup (Priority: P1)

As someone running MCP clients on Windows or elsewhere, I want to install and start the server on demand without Docker, with read-only as the default and clear errors when configuration is wrong.

**Why this priority**: Replacing Docker is a primary motivation. Default read-only and startup validation prevent accidental writes and cryptic runtime failures.

**Independent Test**: Can be tested by installing via package runner with only url and token set, confirming read tools appear and write/delete tools do not; setting invalid permission values and confirming startup aborts with valid options listed.

**Acceptance Scenarios**:

1. **Given** only instance url and access token configured, **When** I start the server, **Then** read tools are available and write/delete tools are not registered.
2. **Given** write permission enabled, **When** I start the server, **Then** save, organise, create, update, and queue-archive tools are available; delete, merge, and delete-collection tools remain unavailable unless their respective delete permissions are set.
3. **Given** an invalid permission value such as `*` or `all`, **When** I start the server, **Then** startup aborts with a message listing valid permission values.
4. **Given** a missing required configuration value, **When** I start the server, **Then** startup aborts naming the missing variable.
5. **Given** no credentials configured, **When** I import the package or run help, **Then** no network connection is attempted.

---

### Edge Cases

- What happens when a save attempt hits duplicate-url detection? The user sees a plain message that the link is already saved, not a bare error code.
- What happens when a collection name matches multiple existing collections? Name resolution MUST fail with an explicit ambiguity error naming how many collections matched and instructing the caller to use a collection id — it MUST NOT pick an arbitrary match or create a duplicate.
- What happens when search sort is requested in human terms (newest, oldest, name A–Z, name Z–A)? Results follow that order without the caller supplying numeric sort codes.
- What happens when an agent attempts to reach authentication, session, token, user-administration, migration, or whole-instance preservation endpoints? The request is refused inside the client layer regardless of tool or permission — not merely omitted from the tool list.
- What happens when preserved content is requested but archiving is incomplete or failed? The tool returns a clear status indicating content is not yet available.
- What happens when the link's `readable` field is null or `"unavailable"`? The tool reports that preservation never ran or the url was rejected as unsafe — not an empty string.
- What happens when stored text was truncated by an instance-level content limit? The tool returns the truncated text available on the link record; callers may not receive the full article without using the archive fallback.
- What happens when `merge_tags` is called with a `newTagName` that already exists? The tool warns that a duplicate tag will be created rather than merging into the existing one.
- What happens when a tag merge would affect more links than the bulk cap allows? The tool counts affected links before calling and refuses outright, naming both the link count and the cap.
- What happens when library overview totals links by summing collection counts? This is correct only while each link belongs to exactly one collection; a regression test must assert this invariant.
- What happens when the tag list spans multiple pages? The overview follows the pagination cursor for complete figures, or reports that tag statistics are partial.
- What happens when the same instance url points to self-hosted or cloud Linkwarden? One code path serves both without separate configuration modes.

## Requirements *(mandatory)*

### Functional Requirements

**Permission and configuration**

- **FR-001**: The server MUST register read tools unconditionally. Write tools (save, organise, create collection, update link, queue archive) MUST register only when write permission is granted. Delete tools (delete links, delete tags, merge tags) MUST register only when delete permission is granted. Delete collection MUST register only when delete-collection permission is granted. With no optional permissions configured, the server MUST operate read-only.
- **FR-002**: Permission parsing MUST reject wildcards and glob patterns (`all`, `*`, or any glob character) with a message listing valid values. An unrecognised permission name MUST abort startup rather than failing on first tool call.
- **FR-003**: Configuration MUST be validated at startup, naming any missing required variable. The remote client MUST be created lazily so importing the package or displaying help requires no credentials.

**Safety guarantees**

- **FR-004**: A denylist of forbidden remote operations MUST be enforced inside the internal API client before any request is built. The denylist MUST be derived from the Linkwarden source tree, not from the published OpenAPI document alone — undocumented routes such as tag merge are absent from the spec and would evade a prefix list built from documentation. No permission combination MAY reach a denied path, and no future tool MAY bypass the denylist by accident. Denied categories: token management, session management, authentication flows, user administration (except identity confirmation for the current user), library migration import/export, whole-instance re-preservation, and bulk archive deletion without explicit link ids.
- **FR-005**: Any operation affecting more than one record MUST respect a configurable bulk cap. Exceeding the cap MUST fail with both the requested count and the cap named. The call MUST be refused outright — never truncated to the first N records.

**Read behaviour**

- **FR-006**: Search MUST accept collection and tag as human-readable names and resolve them internally. Sort MUST be expressed in words (e.g. newest, oldest, name) rather than raw numeric codes.
- **FR-014**: Read preserved link content MUST return plain text from the link's stored text content field where present, falling back to the Readability archive (integer format `3`) for the full article object. When a link has no preserved content, the tool MUST say so and name why rather than returning an empty string. The archive endpoint returns a raw file body, not the response envelope used elsewhere on the service.
- **FR-017**: Library overview MUST compose its answer from `GET /api/v1/collections` and `GET /api/v1/tags`, both of which return `_count.links`. It MUST report total collections, total links (summed across collections), total tagged links, collection nesting depth, collections holding no links, tags applied to no links, and the size of the Unorganized collection. It MUST NOT call either dashboard endpoint: v1 dashboard returns a fixed 20-item activity feed with no statistics; v2 dashboard returns UI layout configuration. Total link count is not directly exposed — summing `_count.links` across collections is correct because a link belongs to exactly one collection; this invariant MUST be covered by a regression test. Tag listing paginates per instance configuration; the overview MUST follow the cursor for complete tag figures or state plainly that tag statistics are partial. Prefer slow and correct over a confident wrong number. Both endpoints are shared with name-resolution caching.

**Write behaviour**

- **FR-008**: Saving a link MUST accept a collection by name. When the name matches an existing collection, the link MUST go into that collection. When it does not exist, the server MUST create the collection and state plainly in the result that it was created, naming the collection.
- **FR-009**: Saving a link MUST NEVER pass a bare collection name to link creation without first resolving the name to an existing collection id. This prevents silent duplicate collections with the same display name. When more than one collection shares the same display name, resolution MUST fail with an explicit ambiguity error naming the match count and instructing the caller to use a collection id — it MUST NOT pick an arbitrary match.
- **FR-010**: Updating a link MUST read the current record, merge requested changes, and write the complete record back so callers MAY change one field without supplying the rest.
- **FR-011**: Queue archive MUST report that preservation has been queued. It MUST NEVER report that archiving completed, because completion is asynchronous.

**Delete and destructive behaviour**

- **FR-016**: Merge tags MUST call `PUT /api/v1/tags/merge` with `{ newTagName, tagIds }` where `tagIds` contains at least one entry. It MUST be gated behind delete permission, not write permission, because the operation deletes every source tag. Before calling, the tool MUST count links carrying those tags and MUST refuse when that count exceeds the bulk cap — measured in affected links, not tag count. The result MUST name the new tag id and the number of links moved. When `newTagName` matches an existing tag, the tool MUST warn that a duplicate will be created.

**Tool design and errors**

- **FR-012**: Tool names MUST carry explicit verbs (`create_`, `update_`, `delete_`, `save_`, etc.) so MCP clients can raise approval prompts and regression tests can assert which verb classes exist.
- **FR-013**: Every error MUST surface the remote service's own message in plain language (e.g. duplicate link reads as "this link is already saved", not a bare status code).

**Documentation integrity**

- **FR-015**: A vendored API description MUST ship at `src/linkwarden_mcp/spec/` with `DIVERGENCES.md` recording every place the published specification contradicts the running Linkwarden service, with source code taking precedence over the published spec. Runtime does not load the vendored file — it is provenance for maintainers.

### Key Entities

- **Link**: A saved url with title, description, notes, collection membership, tags, pin state, preservation/archive status, stored plain-text content (`textContent`), and readability status (`readable`).
- **Collection**: A named container for links; may nest under a parent collection. Names are user-facing; duplicate names fragment the library if created carelessly.
- **Tag**: A label attached to links. Merging tags deletes source tags, creates a new tag by name, and retags affected links — it does not fold into an existing tag name.
- **Preserved content / archive**: Asynchronous snapshot of a link's page text, queued and processed by a background worker. Readable text may live on the link record directly; the Readability archive (format `3`) holds a JSON article object with plain and HTML content fields. Archive fetch returns raw file bytes, not a wrapped response object.
- **Library**: The user's full set of links, collections, and tags on one Linkwarden instance (~948 links / ~90 collections in the target deployment).
- **Permission flag**: Independent enablement for write (save, organise, create, update, queue archive), delete links/tags/merge tags, and delete collections; plus a bulk cap limit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can start the server with only instance url and access token configured and interact with read tools within one minute of first install, without running a container daemon.
- **SC-002**: With default configuration, zero write or delete tools are exposed. Enabling write permission exposes exactly five write-class tools and no delete tools. Enabling delete permission additionally exposes exactly three delete tools: delete links, delete tags, and merge tags — not delete collection. Enabling delete-collection permission additionally exposes exactly one delete_collection tool. With all optional permissions enabled, exactly fifteen tools are registered (six read, five write, four delete).
- **SC-003**: Attempting a forbidden remote operation through the internal API client directly (bypassing tools) is refused, proving safety holds below the tool layer.
- **SC-004**: An invalid permission value prevents server startup 100% of the time, with valid values listed in the error message.
- **SC-005**: Saving to an existing collection by name places the link in that collection and creates zero new collections.
- **SC-006**: A bulk operation requesting more records than the cap allows is refused 100% of the time, naming both requested count and cap.
- **SC-007**: The full automated test suite passes with no live instance and no credentials present.
- **SC-008**: The same instance url configuration works for self-hosted and cloud Linkwarden without separate code paths or modes.
- **SC-009**: Capture, retrieval, and maintenance tool groups are all available in v1 — no group ships without the others.
- **SC-010**: All 15 curated tools — including `read_link_content` — are available in v1 with no tool deferred pending live instance probes.

## Assumptions

- The target library size (~948 links, ~90 collections) justifies name-based resolution, bulk caps, and strict collection deduplication on save.
- Link creation is atomic: collection resolution and tag creation by name happen in one request; no client-side rollback policy is needed for save.
- The deprecated list endpoint MUST NOT be used for reading; search accepts collection, tag, and pinned filters even where the published spec omits them.
- Link and collection updates require full-record write-back because the remote API marks several fields required on update.
- Collection creation uses a create endpoint without a parent id in the path (published spec path differs from running service).
- Archive/preservation is asynchronous: queue returns immediately; fields are cleared until a worker completes.
- Sort orders map to: newest first, oldest first, name A–Z, name Z–A; tag sort adds link-count high-to-low and low-to-high.
- v1 excludes: highlights, RSS subscriptions, dashboard layout editing, avatars, file uploads, public collection browsing, migration import/export, and auth/session/token/user administration beyond current-user identity check.
- Archive format integer enum confirmed from Linkwarden source: 0 PNG, 1 JPEG, 2 PDF, 3 Readability JSON, 4 Monolith HTML. GET accepts all five; upload accepts all except 3.
- `read_link_content` prefers the link's stored `textContent`; archive format `3` is the Readability JSON fallback. Live instance probe is for version verification, not an implementation gate.
- Instance `TEXT_CONTENT_LIMIT` may truncate stored plain text; archive fallback may still hold the full Readability object.
- Tag merge route confirmed from source: `PUT /api/v1/tags/merge` with `{ newTagName, tagIds }`. Undocumented in OpenAPI. Destructive — deletes source tags and creates a new tag; no connectOrCreate on name.
- Library overview composes from collections and tags endpoints (two calls, cache-shared with name resolution). Dashboard endpoints excluded — v1 is an activity feed only; v2 is UI layout.
- API token behaviour defaults to long-lived with no refresh.
- Self-hosted instances may or may not serve their own API spec; vendored copy is diffed manually on release.
