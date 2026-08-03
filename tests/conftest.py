"""Shared test fixtures."""

from __future__ import annotations

import pytest

from linkwarden_mcp.scopes import WritePolicy

BASE_URL = "http://linkwarden.test"

# Policy that allows all mutating API paths used in unit tests.
FULL_WRITE_POLICY = WritePolicy(
    frozenset({"links", "collections", "tags"}),
    frozenset({"links", "collections", "tags"}),
)


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKWARDEN_URL", BASE_URL)
    monkeypatch.setenv("LINKWARDEN_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    from linkwarden_mcp.config import reset_state
    from linkwarden_mcp.server import reset_registration

    reset_state()
    reset_registration()
    monkeypatch.delenv("LINKWARDEN_MCP_WRITE_SCOPES", raising=False)
    monkeypatch.delenv("LINKWARDEN_MCP_DELETE_SCOPES", raising=False)
    for name in (
        "LINKWARDEN_MCP_ALLOW_WRITES",
        "ALLOW_WRITES",
        "LINKWARDEN_MCP_WRITES",
        "LINKWARDEN_WRITE",
        "LINKWARDEN_DELETE",
        "LINKWARDEN_DELETE_COLLECTIONS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("LINKWARDEN_MAX_BULK", raising=False)
    yield
    reset_state()
    reset_registration()
