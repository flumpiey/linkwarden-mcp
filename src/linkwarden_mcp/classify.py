"""Stdlib heuristics for collection/tag suggestions.

# ponytail: O(n) scan per collection; fine for ~90 collections / 948 links.
# Upgrade: inverted domain index if library grows past ~5k links.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

# Seeded from common library shapes; only applied when the named collection exists.
DOMAIN_COLLECTION_HINTS: dict[str, str] = {
    "github.com": "Programming",
    "gitlab.com": "Programming",
    "npmjs.com": "Libraries",
    "pypi.org": "Libraries",
    "stackoverflow.com": "Programming",
    "docs.python.org": "Programming",
    "developer.mozilla.org": "WebDev",
    "react.dev": "WebDev",
    "nextjs.org": "WebDev",
    "figma.com": "UI Tools",
    "dribbble.com": "UI Inspiration",
    "behance.net": "UI Inspiration",
    "youtube.com": "Resources",
    "youtu.be": "Resources",
    "medium.com": "Resources",
    "dev.to": "Programming",
    "reddit.com": "Resources",
    "wikipedia.org": "Reference",
    "amazon.com": "Shop",
    "amazon.co.uk": "Shop",
    "takealot.com": "Shop",
}

DOMAIN_TAG_RULES: dict[str, list[str]] = {
    "github.com": ["github", "dev"],
    "gitlab.com": ["git", "dev"],
    "npmjs.com": ["npm", "js"],
    "pypi.org": ["python"],
    "stackoverflow.com": ["stackoverflow"],
    "youtube.com": ["video"],
    "youtu.be": ["video"],
    "figma.com": ["design"],
}

_UTM_PREFIX = "utm_"
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_url(url: str) -> str:
    """Canonical form for duplicate detection: lowercase host, no utm_*, no trailing slash."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or ""
    kept = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith(_UTM_PREFIX)
    ]
    query = urlencode(kept)
    base = f"{host}{path}"
    return f"{base}?{query}" if query else base


def url_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def _tokens(*parts: str | None) -> set[str]:
    out: set[str] = set()
    for part in parts:
        if not part:
            continue
        out.update(t.lower() for t in _TOKEN_RE.findall(part) if len(t) > 1)
    return out


def score_collections(
    url: str,
    title: str | None,
    collections: list[dict[str, Any]],
    tag_names: list[str] | None = None,
    *,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Return top collection suggestions with scores and reasons."""
    domain = url_domain(url)
    path = urlparse(url if "://" in url else f"https://{url}").path
    haystack = _tokens(url, title, path, " ".join(tag_names or []))
    names = {str(c.get("name") or "") for c in collections if c.get("name")}
    hint = DOMAIN_COLLECTION_HINTS.get(domain)
    if hint is None:
        for host, target in DOMAIN_COLLECTION_HINTS.items():
            if domain.endswith("." + host) or domain == host:
                hint = target
                break

    scored: list[dict[str, Any]] = []
    for coll in collections:
        name = str(coll.get("name") or "")
        if not name:
            continue
        score = 0.0
        reasons: list[str] = []
        name_l = name.lower()
        name_tokens = _tokens(name)

        if hint and name == hint and name in names:
            score += 0.55
            reasons.append(f"domain {domain} maps to {name}")

        overlap = haystack & name_tokens
        if overlap:
            score += min(0.35, 0.12 * len(overlap))
            reasons.append(f"token overlap: {', '.join(sorted(overlap)[:4])}")

        ratio = SequenceMatcher(None, name_l, " ".join(sorted(haystack))[:80]).ratio()
        if ratio >= 0.35:
            score += ratio * 0.25
            reasons.append(f"name similarity {ratio:.2f}")

        if domain and domain.split(".")[0] in name_l:
            score += 0.15
            reasons.append("domain stem in collection name")

        if score <= 0:
            continue
        scored.append(
            {
                "name": name,
                "score": round(min(score, 1.0), 3),
                "reason": "; ".join(reasons) if reasons else "weak match",
            }
        )

    scored.sort(key=lambda x: (-x["score"], x["name"].lower()))
    return scored[:top_n]


def suggest_tags_from_vocabulary(
    url: str,
    title: str | None,
    existing_tags: list[str] | None,
    tag_vocabulary: list[str],
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Suggest tags that already exist in the library vocabulary only."""
    vocab = {t: t for t in tag_vocabulary if t}
    vocab_l = {t.lower(): t for t in vocab}
    domain = url_domain(url)
    haystack = _tokens(url, title, domain)
    haystack.update(t.lower() for t in (existing_tags or []))

    scored: list[dict[str, Any]] = []
    for rule_domain, tags in DOMAIN_TAG_RULES.items():
        if domain == rule_domain or domain.endswith("." + rule_domain):
            for tag in tags:
                canonical = vocab_l.get(tag.lower())
                if canonical:
                    scored.append(
                        {
                            "name": canonical,
                            "score": 0.7,
                            "reason": f"domain rule for {domain}",
                        }
                    )

    for tag_l, canonical in vocab_l.items():
        if any(s["name"] == canonical for s in scored):
            continue
        if tag_l in haystack or any(tag_l in tok or tok in tag_l for tok in haystack if len(tok) > 2):
            score = 0.45 if tag_l in haystack else 0.3
            scored.append(
                {
                    "name": canonical,
                    "score": score,
                    "reason": "token match against vocabulary",
                }
            )

    # Deduplicate keeping highest score
    best: dict[str, dict[str, Any]] = {}
    for item in scored:
        prev = best.get(item["name"])
        if prev is None or item["score"] > prev["score"]:
            best[item["name"]] = item
    out = sorted(best.values(), key=lambda x: (-x["score"], x["name"].lower()))
    return out[:top_n]


def fuzzy_collection_pairs(
    names: list[str],
    *,
    threshold: float = 0.82,
) -> list[dict[str, Any]]:
    """Near-duplicate collection name pairs (e.g. BrightSide / Brightside)."""
    clean = sorted({n for n in names if n})
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(clean):
        for b in clean[i + 1 :]:
            if a.lower() == b.lower():
                sim = 1.0
            else:
                sim = SequenceMatcher(None, a.lower(), b.lower()).ratio()
            if sim >= threshold:
                pairs.append({"a": a, "b": b, "similarity": round(sim, 3)})
    pairs.sort(key=lambda x: (-x["similarity"], x["a"].lower(), x["b"].lower()))
    return pairs


def match_domain_rules(url: str, rules: dict[str, list[str]] | None = None) -> list[str]:
    """Return tag names from domain rules that match the URL host."""
    domain = url_domain(url)
    table = rules or DOMAIN_TAG_RULES
    for host, tags in table.items():
        if domain == host or domain.endswith("." + host):
            return list(tags)
    return []


def match_sort_rules(
    url: str,
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """First matching bulk-sort rule: {domain_pattern, collection?, tags?}."""
    domain = url_domain(url)
    for rule in rules:
        pattern = str(rule.get("domain_pattern") or "").lower().strip()
        if not pattern:
            continue
        if domain == pattern or domain.endswith("." + pattern) or pattern in domain:
            return rule
    return None
