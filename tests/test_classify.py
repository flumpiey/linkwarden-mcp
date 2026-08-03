"""Pure classify heuristic tests (no network)."""

from __future__ import annotations

from linkwarden_mcp.classify import (
    fuzzy_collection_pairs,
    match_domain_rules,
    match_sort_rules,
    normalize_url,
    score_collections,
    suggest_tags_from_vocabulary,
    url_domain,
)


def test_normalize_url_strips_utm_and_slash() -> None:
    assert (
        normalize_url("https://WWW.Example.com/path/?utm_source=x&id=1")
        == "example.com/path?id=1"
    )


def test_url_domain() -> None:
    assert url_domain("https://www.github.com/foo") == "github.com"


def test_score_collections_domain_hint() -> None:
    collections = [
        {"name": "Programming"},
        {"name": "Baking"},
        {"name": "Shop"},
    ]
    out = score_collections("https://github.com/acme/repo", "Cool repo", collections)
    assert out
    assert out[0]["name"] == "Programming"
    assert out[0]["score"] > 0


def test_suggest_tags_only_existing_vocabulary() -> None:
    out = suggest_tags_from_vocabulary(
        "https://github.com/x/y",
        "My project",
        [],
        ["github", "baking", "python"],
    )
    names = {t["name"] for t in out}
    assert "github" in names
    assert "invented" not in names


def test_fuzzy_collection_pairs() -> None:
    pairs = fuzzy_collection_pairs(["BrightSide", "Brightside", "Shop"], threshold=0.82)
    assert any({p["a"], p["b"]} == {"BrightSide", "Brightside"} for p in pairs)


def test_match_domain_rules() -> None:
    assert "github" in match_domain_rules("https://github.com/a/b")


def test_match_sort_rules() -> None:
    rules = [{"domain_pattern": "npmjs.com", "collection": "Libraries", "tags": ["npm"]}]
    hit = match_sort_rules("https://www.npmjs.com/package/foo", rules)
    assert hit is not None
    assert hit["collection"] == "Libraries"
