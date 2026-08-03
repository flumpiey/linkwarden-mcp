"""Write/delete scope parsing, domain maps, and path denylist."""

from __future__ import annotations

import os
from dataclasses import dataclass

WRITE_SCOPES_ENV = "LINKWARDEN_MCP_WRITE_SCOPES"
DELETE_SCOPES_ENV = "LINKWARDEN_MCP_DELETE_SCOPES"
LEGACY_WRITE_ENVS = (
    "LINKWARDEN_MCP_ALLOW_WRITES",
    "ALLOW_WRITES",
    "LINKWARDEN_MCP_WRITES",
)

VALID_SCOPES = frozenset(
    {
        "links",
        "collections",
        "tags",
        # Escape hatch: effective_* expands to all DOMAIN_SCOPES.
        "raw",
    }
)

DOMAIN_SCOPES = VALID_SCOPES - {"raw"}

# resource_key -> scope
RESOURCE_SCOPE: dict[str, str] = {
    "links": "links",
    "collections": "collections",
    "tags": "tags",
}

# Normalized path (no trailing slash, numeric ids stripped) -> resource_key
PATH_TO_RESOURCE: dict[str, str] = {
    "/api/v1/links": "links",
    "/api/v1/links/archive": "links",
    "/api/v1/collections": "collections",
    "/api/v1/tags": "tags",
    "/api/v1/tags/merge": "tags",
}

_DENY_PREFIXES = (
    "/api/v1/tokens",
    "/api/v1/session",
    "/api/v1/auth",
    "/api/v1/migration",
    "/api/v1/worker/preservation",
)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ScopeConfigError(ValueError):
    """Invalid scope configuration (unknown names, wildcards, legacy envs)."""


class WritesDeniedError(RuntimeError):
    """Client refused a mutating request (denylist or missing scope)."""


def _normalize_path(path: str) -> str:
    p = path if path.startswith("/") else f"/{path}"
    p = p.split("?", 1)[0].rstrip("/") or "/"
    parts = p.split("/")
    # Strip numeric ids: /api/v1/links/12/archive -> /api/v1/links/archive
    out: list[str] = []
    for part in parts:
        if part.isdigit():
            continue
        out.append(part)
    return "/".join(out) if out and out[0] == "" else "/" + "/".join(out)


def is_denylisted(path: str) -> bool:
    norm = _normalize_path(path).casefold()
    for prefix in _DENY_PREFIXES:
        if norm == prefix or norm.startswith(prefix + "/"):
            return True
    return bool(norm.startswith("/api/v1/users"))


def path_to_resource(path: str) -> str | None:
    return PATH_TO_RESOURCE.get(_normalize_path(path))


def parse_scope_csv(raw: str | None, *, env_name: str) -> frozenset[str]:
    if raw is None or raw.strip() == "":
        return frozenset()
    tokens = [t.strip().casefold() for t in raw.split(",")]
    tokens = [t for t in tokens if t]
    if not tokens:
        return frozenset()
    for t in tokens:
        if t in {"*", "all"} or any(c in t for c in "*?"):
            raise ScopeConfigError(
                f"{env_name}: wildcards are not allowed ({t!r}). "
                f"Valid scopes: {', '.join(sorted(VALID_SCOPES))}"
            )
        if t not in VALID_SCOPES:
            raise ScopeConfigError(
                f"{env_name}: unknown scope {t!r}. "
                f"Valid scopes: {', '.join(sorted(VALID_SCOPES))}"
            )
    return frozenset(tokens)


def reject_legacy_write_envs(environ: dict[str, str] | None = None) -> None:
    env = environ if environ is not None else os.environ
    for name in LEGACY_WRITE_ENVS:
        raw = env.get(name)
        if raw is not None and raw.strip() != "":
            raise ScopeConfigError(
                f"{name} is no longer supported (was set to {raw.strip()!r}). "
                f"Use {WRITE_SCOPES_ENV} and {DELETE_SCOPES_ENV} "
                f"(comma-separated scopes, e.g. links,collections)."
            )


@dataclass(frozen=True)
class WritePolicy:
    write_scopes: frozenset[str]
    delete_scopes: frozenset[str]

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> WritePolicy:
        env = environ if environ is not None else os.environ
        reject_legacy_write_envs(env)
        return cls(
            write_scopes=parse_scope_csv(env.get(WRITE_SCOPES_ENV), env_name=WRITE_SCOPES_ENV),
            delete_scopes=parse_scope_csv(
                env.get(DELETE_SCOPES_ENV), env_name=DELETE_SCOPES_ENV
            ),
        )

    @property
    def any_enabled(self) -> bool:
        return bool(self.write_scopes or self.delete_scopes)

    @property
    def effective_write_scopes(self) -> frozenset[str]:
        if "raw" in self.write_scopes:
            return DOMAIN_SCOPES
        return self.write_scopes - {"raw"}

    @property
    def effective_delete_scopes(self) -> frozenset[str]:
        if "raw" in self.delete_scopes:
            return DOMAIN_SCOPES
        return self.delete_scopes - {"raw"}

    def authorize(self, method: str, path: str) -> None:
        method = method.upper()
        if method not in WRITE_METHODS:
            return
        if is_denylisted(path):
            raise WritesDeniedError(
                f"{method} {path} is permanently denied (denylist)."
            )
        # Destructive merge uses PUT but is gated by DELETE_SCOPES (like delete_tags).
        if _normalize_path(path) == "/api/v1/tags/merge":
            if "tags" not in self.effective_delete_scopes:
                raise WritesDeniedError(
                    f"{method} {path} requires scope 'tags' in {DELETE_SCOPES_ENV}."
                )
            return
        resource = path_to_resource(path)
        if resource is None:
            raise WritesDeniedError(
                f"{method} {path} is not a scoped writable resource."
            )
        scope = RESOURCE_SCOPE[resource]
        if method == "DELETE":
            if scope not in self.effective_delete_scopes:
                raise WritesDeniedError(
                    f"DELETE {path} requires scope {scope!r} in {DELETE_SCOPES_ENV}."
                )
            return
        if scope not in self.effective_write_scopes:
            raise WritesDeniedError(
                f"{method} {path} requires scope {scope!r} in {WRITE_SCOPES_ENV}."
            )
