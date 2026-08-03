"""Config and scope startup tests."""

from __future__ import annotations

import pytest

from linkwarden_mcp.config import Settings, get_policy
from linkwarden_mcp.errors import ConfigError
from linkwarden_mcp.scopes import ScopeConfigError, WritePolicy


def test_import_without_credentials() -> None:
    import linkwarden_mcp.server  # noqa: F401


def test_settings_default_max_bulk(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings.from_env()
    assert s.max_bulk == 25


def test_policy_default_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_MCP_WRITE_SCOPES", raising=False)
    monkeypatch.delenv("LINKWARDEN_MCP_DELETE_SCOPES", raising=False)
    policy = WritePolicy.from_env()
    assert not policy.any_enabled


def test_runtime_requires_url_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_API_URL", raising=False)
    monkeypatch.delenv("LINKWARDEN_API_KEY", raising=False)
    monkeypatch.delenv("LINKWARDEN_URL", raising=False)
    monkeypatch.delenv("LINKWARDEN_TOKEN", raising=False)
    s = Settings.from_env()
    with pytest.raises(ConfigError, match="LINKWARDEN_API_URL"):
        s.validate_runtime()


def test_settings_accept_legacy_url_token_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_API_URL", raising=False)
    monkeypatch.delenv("LINKWARDEN_API_KEY", raising=False)
    monkeypatch.setenv("LINKWARDEN_URL", "http://legacy.test")
    monkeypatch.setenv("LINKWARDEN_TOKEN", "legacy-token")
    s = Settings.from_env()
    assert s.url == "http://legacy.test"
    assert s.token == "legacy-token"


def test_legacy_write_flag_hard_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_MCP_ALLOW_WRITES", "1")
    with pytest.raises(ScopeConfigError, match="no longer supported"):
        get_policy()


def test_help_does_not_require_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from linkwarden_mcp import server

    assert server.mcp.name == "linkwarden-mcp"
