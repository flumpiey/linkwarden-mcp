"""Config and permission parsing tests."""

from __future__ import annotations

import pytest

from linkwarden_mcp.config import Settings
from linkwarden_mcp.errors import ConfigError


def test_import_without_credentials() -> None:
    import linkwarden_mcp.server  # noqa: F401


def test_settings_default_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_WRITE", raising=False)
    s = Settings.from_env()
    assert not s.write
    assert not s.delete
    assert not s.delete_collections
    assert s.max_bulk == 25


@pytest.mark.parametrize("bad", ["*", "all", "writ*", "yes?"])
def test_invalid_permission_values_abort(bad: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_WRITE", bad)
    with pytest.raises(ConfigError, match="Valid permission values"):
        Settings.from_env()


def test_unknown_permission_value_lists_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_DELETE", "maybe")
    with pytest.raises(ConfigError, match="Unrecognised value"):
        Settings.from_env()


def test_runtime_requires_url_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKWARDEN_URL", raising=False)
    monkeypatch.delenv("LINKWARDEN_TOKEN", raising=False)
    s = Settings.from_env()
    with pytest.raises(ConfigError, match="LINKWARDEN_URL"):
        s.validate_runtime()


def test_help_does_not_require_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from linkwarden_mcp import server

    assert server.mcp.name == "linkwarden-mcp"
