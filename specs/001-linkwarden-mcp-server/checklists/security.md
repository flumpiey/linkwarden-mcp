# Security Requirements Checklist: Linkwarden MCP Server

**Purpose**: Validate security and permission requirements are complete, clear, and consistent before implementation  
**Created**: 2026-08-03  
**Feature**: [spec.md](../spec.md)

**Note**: Unit tests for requirements writing — evaluates what the spec says, not whether code works.

## Permission Model

- [ ] CHK001 - Are all three permission tiers (write, delete, delete-collection) explicitly defined with which tools each enables? [Completeness, Spec §FR-001]
- [ ] CHK002 - Is the default read-only posture stated when no optional permissions are configured? [Clarity, Spec §FR-001]
- [ ] CHK003 - Are the exact write-class tools enumerated (five tools) separately from delete-class tools? [Completeness, Spec §SC-002]
- [ ] CHK004 - Is `merge_tags` requirement explicitly gated under delete permission rather than write permission, with rationale documented? [Clarity, Spec §FR-016]
- [ ] CHK005 - Are wildcard and glob rejection rules specified with examples of invalid values (`all`, `*`, globs)? [Clarity, Spec §FR-002]
- [ ] CHK006 - Is startup-abort behaviour defined for unrecognised permission names (not deferred to first tool call)? [Completeness, Spec §FR-002]
- [ ] CHK007 - Are valid permission values listed in the error message requirement? [Measurability, Spec §SC-004]

## Denylist & Client-Layer Safety

- [ ] CHK008 - Is client-layer denylist enforcement required independently of tool registration (not tool omission alone)? [Completeness, Spec §FR-004, §SC-003]
- [ ] CHK009 - Is the denylist source of truth specified as Linkwarden source tree rather than OpenAPI alone? [Clarity, Spec §FR-004]
- [ ] CHK010 - Are all denied route categories documented (tokens, session, auth, users, migration, whole-instance preservation, bulk archive delete)? [Completeness, Spec §FR-004]
- [ ] CHK011 - Is the sole allowed exception to user-admin denylist (`GET /users/me`) explicitly stated? [Clarity, contracts/denylist.md]
- [ ] CHK012 - Are requirements defined for maintaining denylist when Linkwarden adds new sensitive routes? [Coverage, Gap, contracts/denylist.md §Maintenance]
- [ ] CHK013 - Is the threat of undocumented routes (e.g. tag merge absent from OpenAPI) addressed in requirements? [Coverage, Spec §FR-004]

## Destructive Operations & Blast Radius

- [ ] CHK014 - Is collection deletion called out as separately gated due to cascade behaviour? [Clarity, Spec §FR-001, User Story 3]
- [ ] CHK015 - Are merge-tags destructive semantics documented (deletes source tags, creates new tag, no connectOrCreate)? [Completeness, Spec §FR-016, Key Entities §Tag]
- [ ] CHK016 - Is the duplicate-tag warning requirement specified when `newTagName` matches an existing tag? [Edge Case, Spec §FR-016]
- [ ] CHK017 - Is the silent-failure risk of wrong HTTP method on tag merge (POST vs PUT) captured in assumptions or divergences? [Coverage, Clarifications §Session 2026-08-03]
- [ ] CHK018 - Are tool verb-prefix requirements defined so MCP clients can surface approval prompts for destructive tools? [Clarity, Spec §FR-012]

## Bulk Cap & Partial-Apply Prevention

- [ ] CHK019 - Is the bulk cap default value (25) and configurability documented? [Clarity, Key Entities §Permission flag]
- [ ] CHK020 - Is outright refusal (never truncate to first N) explicitly required when cap exceeded? [Clarity, Spec §FR-005]
- [ ] CHK021 - Are both requested count and cap required in refusal messages? [Measurability, Spec §FR-005, §SC-006]
- [ ] CHK022 - Is bulk-cap measurement for `merge_tags` specified as affected links (not tag count)? [Clarity, Spec §FR-016]
- [ ] CHK023 - Are all multi-record tools in scope for bulk cap (organise, delete, queue_archive, merge)? [Coverage, contracts/mcp-tools.md §Bulk cap]

## Configuration & Credential Handling

- [ ] CHK024 - Is lazy client creation required so import and help need no credentials? [Completeness, Spec §FR-003]
- [ ] CHK025 - Are missing required configuration variables named at startup (not at first API call)? [Clarity, Spec §FR-003]
- [ ] CHK026 - Are required vs optional environment variables distinguished in requirements or data model? [Completeness, data-model.md §Local configuration]
- [ ] CHK027 - Is long-lived API token assumed with no refresh flow documented as an explicit assumption? [Assumption, Spec §Assumptions]

## Error Disclosure & Agent Safety

- [ ] CHK028 - Are plain-language error message requirements defined (not bare status codes)? [Clarity, Spec §FR-013]
- [ ] CHK029 - Are duplicate-link and unavailable-content scenarios specified to avoid empty or misleading responses? [Edge Case, Spec §Edge Cases]
- [ ] CHK030 - Is partial tag-statistics disclosure required when pagination cannot complete (`tags_partial`)? [Clarity, Spec §FR-017]

## Acceptance Criteria & Traceability

- [ ] CHK031 - Does SC-003 require denylist enforcement below the tool layer (direct client call)? [Measurability, Spec §SC-003]
- [ ] CHK032 - Are permission-to-tool-count outcomes measurable in SC-002 (5 write, 3 delete-class with merge)? [Measurability, Spec §SC-002]
- [ ] CHK033 - Is offline test-suite pass without credentials a stated success criterion? [Coverage, Spec §SC-007]

## Notes

- Focus: permission gating, denylist, destructive ops, bulk caps (pre-implementation security review)
- Depth: standard PR gate
- Complements [requirements.md](./requirements.md) (general spec quality)
- Resolve any unchecked items in spec before `/speckit-tasks`
