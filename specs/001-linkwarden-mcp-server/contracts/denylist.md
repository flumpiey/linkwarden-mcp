# HTTP Client Denylist Contract

**Enforcement layer**: `client.py` — every outbound request checked before build.  
**Source of truth**: Linkwarden source tree (`apps/web/pages/api/v1/**`), not OpenAPI alone.

## Always denied (any permission)

| Pattern / route | Reason |
|-----------------|--------|
| `/api/v1/tokens/**` | Token minting escapes permission model |
| `/api/v1/session/**` | Session escape vector |
| `/api/v1/auth/**` | Password reset, email verification |
| `/api/v1/users/**` except `GET .../users/me` | Account admin |
| `POST /api/v1/migration` | Full library duplication |
| `GET /api/v1/migration` | Full library export |
| `POST /api/v1/worker/preservation` with whole-instance actions | Re-preserve entire instance |
| `DELETE /api/v1/links/archive` without explicit linkIds | Optional linkIds → all archives |

## Explicitly allowed exceptions

| Route | Use |
|-------|-----|
| `GET /api/v1/users/me` | Startup identity confirmation |

## Test contract

Direct client call to any denied route MUST raise `DeniedPathError` (or equivalent) regardless of registered tools. Regression test required per SC-003.

## Maintenance

When vendoring OpenAPI or bumping Linkwarden version:

1. Diff `apps/web/pages/api/v1/` route files against denylist
2. Record divergences in `src/linkwarden_mcp/spec/DIVERGENCES.md`
3. Add test for any new sensitive route discovered
