"""Environment parsing and lazy client factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from linkwarden_mcp.errors import ConfigError
from linkwarden_mcp.scopes import WritePolicy

if TYPE_CHECKING:
    from linkwarden_mcp.client import LinkwardenClient


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
    max_bulk: int

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        url = env.get("LINKWARDEN_API_URL", "").strip() or env.get("LINKWARDEN_URL", "").strip()
        token = (
            env.get("LINKWARDEN_API_KEY", "").strip() or env.get("LINKWARDEN_TOKEN", "").strip()
        )
        return cls(
            url=url,
            token=token,
            max_bulk=_parse_bulk_cap(env),
        )

    def validate_runtime(self) -> None:
        if not self.url:
            raise ConfigError("LINKWARDEN_API_URL is required")
        if not self.token:
            raise ConfigError("LINKWARDEN_API_KEY is required")


_settings: Settings | None = None
_client: LinkwardenClient | None = None
_policy: WritePolicy | None = None


def get_settings(environ: dict[str, str] | None = None) -> Settings:
    global _settings
    if environ is not None:
        return Settings.from_env(environ)
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def get_policy(environ: dict[str, str] | None = None) -> WritePolicy:
    global _policy
    if environ is not None:
        return WritePolicy.from_env(environ)
    if _policy is None:
        _policy = WritePolicy.from_env()
    return _policy


def reset_state() -> None:
    global _settings, _client, _policy
    _settings = None
    _client = None
    _policy = None


def get_client(environ: dict[str, str] | None = None) -> LinkwardenClient:
    global _client
    if environ is not None:
        settings = Settings.from_env(environ)
        settings.validate_runtime()
        from linkwarden_mcp.client import LinkwardenClient

        return LinkwardenClient(
            settings.url,
            settings.token,
            policy=WritePolicy.from_env(environ),
        )
    if _client is None:
        settings = get_settings()
        settings.validate_runtime()
        from linkwarden_mcp.client import LinkwardenClient

        _client = LinkwardenClient(
            settings.url, settings.token, policy=get_policy()
        )
    return _client
