"""Shared test fixtures."""

from __future__ import annotations

import pytest

BASE_URL = "http://linkwarden.test"


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
    monkeypatch.delenv("LINKWARDEN_WRITE", raising=False)
    monkeypatch.delenv("LINKWARDEN_DELETE", raising=False)
    monkeypatch.delenv("LINKWARDEN_DELETE_COLLECTIONS", raising=False)
    monkeypatch.delenv("LINKWARDEN_MAX_BULK", raising=False)
    yield
    reset_state()
    reset_registration()
