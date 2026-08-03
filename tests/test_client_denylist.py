"""Client denylist regression tests."""

from __future__ import annotations

import pytest

from linkwarden_mcp.client import LinkwardenClient, deny_reason
from linkwarden_mcp.errors import DeniedPathError


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/tokens"),
        ("POST", "/api/v1/tokens"),
        ("GET", "/api/v1/session"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/users"),
        ("DELETE", "/api/v1/users/1"),
        ("POST", "/api/v1/migration"),
        ("GET", "/api/v1/migration"),
    ],
)
def test_denylist_blocks_sensitive_routes(method: str, path: str) -> None:
    assert deny_reason(method, path) is not None


def test_users_me_allowed() -> None:
    assert deny_reason("GET", "/api/v1/users/me") is None


def test_whole_instance_preservation_denied() -> None:
    assert deny_reason("POST", "/api/v1/worker/preservation", json={"action": "preserveAll"})


def test_archive_delete_without_link_ids_denied() -> None:
    assert deny_reason("DELETE", "/api/v1/links/archive", json={}) is not None
    assert deny_reason("DELETE", "/api/v1/links/archive", json={"linkIds": [1]}) is None


@pytest.mark.asyncio
async def test_client_raises_denied_path_error() -> None:
    client = LinkwardenClient("http://example.test", "token")
    with pytest.raises(DeniedPathError):
        await client.get("/api/v1/tokens")
    await client.aclose()
