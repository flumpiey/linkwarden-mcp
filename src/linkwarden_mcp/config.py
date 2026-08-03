"""Environment parsing, permissions, and lazy client factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from linkwarden_mcp.errors import ConfigError

if TYPE_CHECKING:
    from linkwarden_mcp.client import LinkwardenClient

VALID_PERMISSION_VALUES = frozenset({"1", "true", "yes", "on"})
INVALID_PERMISSION_VALUES = frozenset({"*", "all"})


def _parse_flag(name: str, environ: dict[str, str]) -> bool:
    raw = environ.get(name, "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if lowered in INVALID_PERMISSION_VALUES or "*" in raw or "?" in raw:
        raise ConfigError(
            f"Invalid value for {name}: {raw!r}. "
            "Valid permission values: 1, true, yes, or unset."
        )
    if lowered in VALID_PERMISSION_VALUES:
        return True
    raise ConfigError(
        f"Unrecognised value for {name}: {raw!r}. "
        "Valid permission values: 1, true, yes, or unset."
    )


def _parse_bulk_cap(environ: dict[str, str]) -> int:
    raw = environ.get("LINKWARDEN_MAX_BULK", "").strip()
    if not raw:
        return 25
    try:
        cap = int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Invalid LINKWARDEN_MAX_BULK: {raw!r}. Must be a positive integer."
        ) from exc
    if cap < 1:
        raise ConfigError("LINKWARDEN_MAX_BULK must be at least 1.")
    return cap


@dataclass(frozen=True)
class Settings:
    url: str
    token: str
    write: bool
    delete: bool
    delete_collections: bool
    max_bulk: int

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        return cls(
            url=env.get("LINKWARDEN_URL", "").strip(),
            token=env.get("LINKWARDEN_TOKEN", "").strip(),
            write=_parse_flag("LINKWARDEN_WRITE", env),
            delete=_parse_flag("LINKWARDEN_DELETE", env),
            delete_collections=_parse_flag("LINKWARDEN_DELETE_COLLECTIONS", env),
            max_bulk=_parse_bulk_cap(env),
        )

    def validate_runtime(self) -> None:
        if not self.url:
            raise ConfigError("LINKWARDEN_URL is required")
        if not self.token:
            raise ConfigError("LINKWARDEN_TOKEN is required")


_settings: Settings | None = None
_client: LinkwardenClient | None = None


def get_settings(environ: dict[str, str] | None = None) -> Settings:
    global _settings
    if environ is not None:
        return Settings.from_env(environ)
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_state() -> None:
    global _settings, _client
    _settings = None
    _client = None


def get_client(environ: dict[str, str] | None = None) -> LinkwardenClient:
    global _client
    if environ is not None:
        settings = Settings.from_env(environ)
        settings.validate_runtime()
        from linkwarden_mcp.client import LinkwardenClient

        return LinkwardenClient(settings.url, settings.token)
    if _client is None:
        settings = get_settings()
        settings.validate_runtime()
        from linkwarden_mcp.client import LinkwardenClient

        _client = LinkwardenClient(settings.url, settings.token)
    return _client
