"""Scope parsing, denylist, and authorize matrix (no live Linkwarden)."""

from __future__ import annotations

import pytest

from linkwarden_mcp.scopes import (
    DOMAIN_SCOPES,
    ScopeConfigError,
    WritePolicy,
    WritesDeniedError,
    is_denylisted,
    parse_scope_csv,
    reject_legacy_write_envs,
)


def test_parse_empty() -> None:
    assert parse_scope_csv("", env_name="X") == frozenset()
    assert parse_scope_csv(None, env_name="X") == frozenset()


def test_parse_single() -> None:
    assert parse_scope_csv("links", env_name="X") == frozenset({"links"})


def test_parse_multiple_whitespace_casefold() -> None:
    assert parse_scope_csv(" Links , Collections ", env_name="X") == frozenset(
        {"links", "collections"}
    )


@pytest.mark.parametrize("bad", ["*", "all", "bookmarks", "link*", "links?"])
def test_parse_rejects_unknown_and_wildcards(bad: str) -> None:
    with pytest.raises(ScopeConfigError):
        parse_scope_csv(bad, env_name="LINKWARDEN_MCP_WRITE_SCOPES")


@pytest.mark.parametrize(
    "name",
    ["LINKWARDEN_MCP_ALLOW_WRITES", "ALLOW_WRITES", "LINKWARDEN_MCP_WRITES"],
)
def test_legacy_envs_hard_fail(name: str) -> None:
    with pytest.raises(ScopeConfigError, match="no longer supported"):
        reject_legacy_write_envs({name: "true"})


def test_from_env_combinations() -> None:
    policy = WritePolicy.from_env(
        {
            "LINKWARDEN_MCP_WRITE_SCOPES": "links,collections",
            "LINKWARDEN_MCP_DELETE_SCOPES": "links",
        }
    )
    assert policy.write_scopes == frozenset({"links", "collections"})
    assert policy.delete_scopes == frozenset({"links"})
    assert "tags" not in policy.effective_write_scopes


def test_delete_not_implied_by_write() -> None:
    policy = WritePolicy(write_scopes=frozenset({"links"}), delete_scopes=frozenset())
    with pytest.raises(WritesDeniedError, match="DELETE_SCOPES"):
        policy.authorize("DELETE", "/api/v1/links")
    policy.authorize("POST", "/api/v1/links")


def test_raw_expands_effective_scopes() -> None:
    policy = WritePolicy(write_scopes=frozenset({"raw"}), delete_scopes=frozenset({"raw"}))
    assert policy.effective_write_scopes == DOMAIN_SCOPES
    assert policy.effective_delete_scopes == DOMAIN_SCOPES
    policy.authorize("POST", "/api/v1/tags")
    policy.authorize("DELETE", "/api/v1/collections/1")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tokens",
        "/api/v1/tokens/1",
        "/api/v1/session",
        "/api/v1/auth/login",
        "/api/v1/users",
        "/api/v1/users/me",
        "/api/v1/migration",
        "/api/v1/worker/preservation",
    ],
)
def test_is_denylisted(path: str) -> None:
    assert is_denylisted(path)


def test_authorize_allowed_write() -> None:
    policy = WritePolicy(frozenset({"links"}), frozenset())
    policy.authorize("POST", "/api/v1/links")
    policy.authorize("PUT", "/api/v1/links/12")
    policy.authorize("PUT", "/api/v1/links/12/archive")


def test_authorize_denied_write() -> None:
    policy = WritePolicy(frozenset({"links"}), frozenset())
    with pytest.raises(WritesDeniedError, match="WRITE_SCOPES"):
        policy.authorize("POST", "/api/v1/collections")


def test_authorize_allowed_delete() -> None:
    policy = WritePolicy(frozenset(), frozenset({"tags"}))
    policy.authorize("DELETE", "/api/v1/tags")
    policy.authorize("PUT", "/api/v1/tags/merge")


def test_authorize_denied_delete() -> None:
    policy = WritePolicy(frozenset({"tags"}), frozenset())
    with pytest.raises(WritesDeniedError, match="DELETE_SCOPES"):
        policy.authorize("DELETE", "/api/v1/tags")
    with pytest.raises(WritesDeniedError, match="DELETE_SCOPES"):
        policy.authorize("PUT", "/api/v1/tags/merge")


def test_denylisted_always_fails() -> None:
    policy = WritePolicy(frozenset({"raw"}), frozenset({"raw"}))
    with pytest.raises(WritesDeniedError, match="denylist"):
        policy.authorize("POST", "/api/v1/tokens")


def test_from_env_unknown_scope() -> None:
    with pytest.raises(ScopeConfigError, match="unknown scope"):
        WritePolicy.from_env({"LINKWARDEN_MCP_WRITE_SCOPES": "bookmarks"})
