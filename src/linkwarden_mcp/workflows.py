"""Workflow MCP tools: suggest/find (read) and apply (write, dry_run default)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from linkwarden_mcp import classify, reads, writes
from linkwarden_mcp.client import LinkwardenClient
from linkwarden_mcp.errors import check_bulk_cap
from linkwarden_mcp.resolve import UNORGANIZED, NameResolver

SCAN_LIMIT = 500


async def _load_library_context(
    resolver: NameResolver,
) -> tuple[list[dict[str, Any]], list[str]]:
    collections = await resolver.collections()
    tags = await resolver.tags()
    tag_names = [str(t.get("name")) for t in tags if t.get("name")]
    return collections, tag_names


async def _fetch_collection_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    collection: str | None = None,
    *,
    limit: int = SCAN_LIMIT,
) -> list[dict[str, Any]]:
    return await reads.fetch_links(
        client, resolver, collection=collection, limit=limit
    )


async def suggest_collection_for_url(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    url: str,
    title: str | None = None,
    excerpt: str | None = None,
) -> dict[str, Any]:
    collections, _ = await _load_library_context(resolver)
    suggestions = classify.score_collections(
        url, title or excerpt, collections, None, top_n=3
    )
    return {"url": url, "suggestions": suggestions}


async def suggest_tags_for_link(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_id: int | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    title: str | None = None
    existing: list[str] = []
    if link_id is not None:
        link = await reads.get_link(client, link_id)
        url = url or str(link.get("url") or "")
        title = str(link.get("name") or "") or None
        existing = [t["name"] for t in (link.get("tags") or []) if t.get("name")]
    if not url:
        raise ValueError("Provide link_id or url.")
    _, vocab = await _load_library_context(resolver)
    suggestions = classify.suggest_tags_from_vocabulary(
        url, title, existing, vocab, top_n=5
    )
    return {
        "link_id": link_id,
        "url": url,
        "existing_tags": existing,
        "suggestions": suggestions,
    }


async def smart_save_link(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    url: str,
    collection: str | None = None,
    tags: list[str] | None = None,
    name: str | None = None,
    description: str | None = None,
    note: str | None = None,
    auto_apply_suggestions: bool = False,
    max_bulk: int = 25,
) -> dict[str, Any]:
    collections, vocab = await _load_library_context(resolver)
    coll_suggestions = classify.score_collections(
        url, name or description, collections, tags, top_n=3
    )
    tag_suggestions = classify.suggest_tags_from_vocabulary(
        url, name, tags, vocab, top_n=5
    )
    chosen_collection = collection
    chosen_tags = list(tags or [])
    applied = False
    if auto_apply_suggestions:
        if not chosen_collection and coll_suggestions:
            chosen_collection = str(coll_suggestions[0]["name"])
        for s in tag_suggestions:
            if s["name"] not in chosen_tags:
                chosen_tags.append(s["name"])
        applied = True
    if not chosen_collection:
        return {
            "saved": False,
            "message": "No collection provided and none suggested strongly enough. "
            "Pass collection or set auto_apply_suggestions=true with suggestions.",
            "suggested_collections": coll_suggestions,
            "suggested_tags": tag_suggestions,
        }
    result = await writes.save_link(
        client,
        resolver,
        url=url,
        collection=chosen_collection,
        tags=chosen_tags or None,
        name=name,
        description=description,
        note=note,
        max_bulk=max_bulk,
    )
    return {
        **result,
        "saved": not result.get("duplicate"),
        "collection_used": chosen_collection,
        "tags_used": chosen_tags,
        "auto_applied": applied,
        "suggested_collections": coll_suggestions,
        "suggested_tags": tag_suggestions,
    }


async def find_unsorted_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    limit: int = 50,
    collection: str = UNORGANIZED,
) -> dict[str, Any]:
    links = await _fetch_collection_links(
        client, resolver, collection, limit=min(limit, SCAN_LIMIT)
    )
    unsorted = [
        {
            "id": link.get("id"),
            "name": link.get("name"),
            "url": link.get("url"),
            "tags": link.get("tags") or [],
            "readable": link.get("readable"),
            "reasons": _unsorted_reasons(link),
        }
        for link in links
        if _unsorted_reasons(link)
    ]
    return {
        "collection": collection,
        "count": len(unsorted),
        "links": unsorted[:limit],
        "scan_capped_at": SCAN_LIMIT,
    }


def _unsorted_reasons(link: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    tags = link.get("tags") or []
    if not tags:
        reasons.append("no tags")
    readable = link.get("readable")
    if readable in (None, "unavailable"):
        reasons.append("not preserved")
    # Links already in Unorganized always count as unsorted by location
    reasons.append("in Unorganized")
    return reasons


async def triage_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_ids: list[int],
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    collections, vocab = await _load_library_context(resolver)
    plans: list[dict[str, Any]] = []
    for link_id in link_ids:
        link = await reads.get_link(client, link_id)
        url = str(link.get("url") or "")
        title = str(link.get("name") or "") or None
        existing = [t["name"] for t in (link.get("tags") or []) if t.get("name")]
        colls = classify.score_collections(url, title, collections, existing, top_n=3)
        tags = classify.suggest_tags_from_vocabulary(
            url, title, existing, vocab, top_n=5
        )
        plans.append(
            {
                "id": link_id,
                "url": url,
                "name": title,
                "current_collection": (link.get("collection") or {}).get("name"),
                "suggested_collection": colls[0]["name"] if colls else None,
                "suggested_tags": [t["name"] for t in tags],
                "reasons": [c["reason"] for c in colls[:2]]
                + [t["reason"] for t in tags[:2]],
                "collection_suggestions": colls,
                "tag_suggestions": tags,
            }
        )
    return {"count": len(plans), "plans": plans}


async def apply_triage_plan(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    plan: list[dict[str, Any]],
    dry_run: bool = True,
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(plan), max_bulk)
    actions: list[dict[str, Any]] = []
    for item in plan:
        link_id = int(item["link_id"])
        collection = item.get("collection")
        tags = item.get("tags")
        actions.append(
            {
                "link_id": link_id,
                "collection": collection,
                "tags": tags,
            }
        )
    if dry_run:
        return {
            "dry_run": True,
            "would_update": len(actions),
            "actions": actions,
            "message": "Dry run only. Pass dry_run=false to apply (requires matching LINKWARDEN_MCP_WRITE_SCOPES).",
        }
    updated = 0
    failures: list[dict[str, Any]] = []
    # Group identical collection+tags for fewer API calls when possible
    for action in actions:
        try:
            await writes.organise_links(
                client,
                resolver,
                link_ids=[action["link_id"]],
                collection=action.get("collection"),
                tags=action.get("tags"),
                max_bulk=max_bulk,
            )
            updated += 1
        except Exception as exc:  # noqa: BLE001 — report per-item failure
            failures.append({"link_id": action["link_id"], "error": str(exc)})
    return {
        "dry_run": False,
        "updated_count": updated,
        "failures": failures,
        "message": f"Updated {updated} of {len(actions)} links.",
    }


async def find_duplicate_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection: str | None = None,
    limit: int = SCAN_LIMIT,
) -> dict[str, Any]:
    links = await _fetch_collection_links(
        client, resolver, collection, limit=min(limit, SCAN_LIMIT)
    )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        key = classify.normalize_url(str(link.get("url") or ""))
        if not key:
            continue
        groups[key].append(
            {
                "id": link.get("id"),
                "name": link.get("name"),
                "url": link.get("url"),
                "collection": link.get("collection"),
            }
        )
    dupes = [
        {"normalized_url": key, "count": len(items), "links": items}
        for key, items in groups.items()
        if len(items) >= 2
    ]
    dupes.sort(key=lambda g: (-g["count"], g["normalized_url"]))
    return {
        "duplicate_groups": dupes,
        "group_count": len(dupes),
        "scanned": len(links),
        "scan_capped_at": SCAN_LIMIT,
    }


async def recommend_collection_for_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_ids: list[int],
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    collections, _ = await _load_library_context(resolver)
    votes: Counter[str] = Counter()
    per_link: list[dict[str, Any]] = []
    for link_id in link_ids:
        link = await reads.get_link(client, link_id)
        url = str(link.get("url") or "")
        title = str(link.get("name") or "") or None
        suggestions = classify.score_collections(url, title, collections, None, top_n=1)
        top = suggestions[0]["name"] if suggestions else None
        if top:
            votes[top] += 1
        per_link.append(
            {
                "id": link_id,
                "url": url,
                "suggested_collection": top,
                "score": suggestions[0]["score"] if suggestions else 0,
            }
        )
    winner = votes.most_common(1)[0] if votes else None
    return {
        "recommended_collection": winner[0] if winner else None,
        "agreement_count": winner[1] if winner else 0,
        "total_links": len(link_ids),
        "votes": dict(votes),
        "per_link": per_link,
    }


async def suggest_links_for_collection(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection: str,
    limit: int = 25,
) -> dict[str, Any]:
    collections, _ = await _load_library_context(resolver)
    in_target = await _fetch_collection_links(client, resolver, collection, limit=200)
    domains = Counter(classify.url_domain(str(l.get("url") or "")) for l in in_target)
    top_domains = {d for d, _ in domains.most_common(10) if d}

    candidates: list[dict[str, Any]] = []
    for source in (UNORGANIZED, "Favourites"):
        if source == collection:
            continue
        outsiders = await _fetch_collection_links(client, resolver, source, limit=200)
        for link in outsiders:
            url = str(link.get("url") or "")
            domain = classify.url_domain(url)
            if domain not in top_domains:
                continue
            suggestions = classify.score_collections(
                url, link.get("name"), collections, link.get("tags"), top_n=1
            )
            if not suggestions or suggestions[0]["name"] != collection:
                continue
            candidates.append(
                {
                    "id": link.get("id"),
                    "name": link.get("name"),
                    "url": url,
                    "current_collection": link.get("collection") or source,
                    "score": suggestions[0]["score"],
                    "reason": suggestions[0]["reason"],
                }
            )
    candidates.sort(key=lambda x: (-x["score"], str(x.get("name") or "").lower()))
    return {
        "collection": collection,
        "profile_domains": sorted(top_domains),
        "candidates": candidates[:limit],
        "count": min(len(candidates), limit),
    }


async def analyze_collection_overlap(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    collection_a: str,
    collection_b: str,
) -> dict[str, Any]:
    links_a = await _fetch_collection_links(client, resolver, collection_a, limit=300)
    links_b = await _fetch_collection_links(client, resolver, collection_b, limit=300)
    domains_a = Counter(classify.url_domain(str(l.get("url") or "")) for l in links_a)
    domains_b = Counter(classify.url_domain(str(l.get("url") or "")) for l in links_b)
    shared_domains = sorted(set(domains_a) & set(domains_b) - {""})
    tags_a = Counter(t for l in links_a for t in (l.get("tags") or []))
    tags_b = Counter(t for l in links_b for t in (l.get("tags") or []))
    shared_tags = sorted(set(tags_a) & set(tags_b))
    norms_a = {classify.normalize_url(str(l.get("url") or "")) for l in links_a}
    norms_b = {classify.normalize_url(str(l.get("url") or "")) for l in links_b}
    shared_urls = sorted((norms_a & norms_b) - {""})
    merge_yes = (
        len(shared_domains) >= 3
        or len(shared_urls) >= 2
        or (
            classify.fuzzy_collection_pairs([collection_a, collection_b], threshold=0.82)
            and True
        )
    )
    return {
        "collection_a": collection_a,
        "collection_b": collection_b,
        "counts": {"a": len(links_a), "b": len(links_b)},
        "shared_domains": shared_domains[:20],
        "shared_tags": shared_tags[:20],
        "shared_normalized_urls": shared_urls[:20],
        "merge_recommended": bool(merge_yes and (shared_domains or shared_urls)),
        "reason": (
            "Overlapping domains/URLs or near-duplicate names"
            if merge_yes
            else "Little overlap; keep separate"
        ),
    }


async def suggest_collection_structure(
    client: LinkwardenClient,
    resolver: NameResolver,
) -> dict[str, Any]:
    overview = await reads.get_library_overview(resolver)
    collections = await resolver.collections()
    names = [str(c.get("name")) for c in collections if c.get("name")]
    fuzzy = classify.fuzzy_collection_pairs(names, threshold=0.82)
    overcrowded = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "link_count": (c.get("_count") or {}).get("links", 0),
        }
        for c in collections
        if (c.get("_count") or {}).get("links", 0) >= 40
    ]
    overcrowded.sort(key=lambda x: -x["link_count"])
    return {
        "empty_collections": overview.get("empty_collections") or [],
        "near_duplicate_names": fuzzy,
        "overcrowded_collections": overcrowded,
        "unused_tags": overview.get("unused_tags") or [],
        "totals": {
            "collections": overview.get("total_collections"),
            "links": overview.get("total_links"),
            "unorganized": overview.get("unorganized_link_count"),
        },
    }


async def auto_tag_by_domain(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_ids: list[int],
    dry_run: bool = True,
    max_bulk: int = 25,
) -> dict[str, Any]:
    check_bulk_cap(len(link_ids), max_bulk)
    _, vocab = await _load_library_context(resolver)
    vocab_l = {t.lower(): t for t in vocab}
    proposals: list[dict[str, Any]] = []
    for link_id in link_ids:
        link = await reads.get_link(client, link_id)
        url = str(link.get("url") or "")
        existing = [t["name"] for t in (link.get("tags") or []) if t.get("name")]
        raw_tags = classify.match_domain_rules(url)
        tags = [vocab_l[t.lower()] for t in raw_tags if t.lower() in vocab_l]
        # Also keep existing
        merged = list(dict.fromkeys(existing + tags))
        proposals.append(
            {
                "link_id": link_id,
                "url": url,
                "existing_tags": existing,
                "proposed_tags": tags,
                "merged_tags": merged,
            }
        )
    if dry_run:
        return {
            "dry_run": True,
            "proposals": proposals,
            "message": "Dry run only. Pass dry_run=false to apply tags.",
        }
    updated = 0
    for p in proposals:
        if not p["proposed_tags"]:
            continue
        await writes.organise_links(
            client,
            resolver,
            link_ids=[p["link_id"]],
            tags=p["merged_tags"],
            max_bulk=max_bulk,
        )
        updated += 1
    return {
        "dry_run": False,
        "updated_count": updated,
        "proposals": proposals,
        "message": f"Tagged {updated} links.",
    }


async def align_tags_with_similar_links(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    link_id: int,
    min_count: int = 2,
) -> dict[str, Any]:
    link = await reads.get_link(client, link_id)
    url = str(link.get("url") or "")
    domain = classify.url_domain(url)
    if not domain:
        return {"link_id": link_id, "suggestions": [], "message": "No domain on link."}
    # Search by domain stem
    stem = domain.split(".")[0]
    similar = await reads.search_links(
        client, resolver, query=stem, limit=100
    )
    tag_counts: Counter[str] = Counter()
    for other in similar:
        if other.get("id") == link_id:
            continue
        other_domain = classify.url_domain(str(other.get("url") or ""))
        if (
            other_domain != domain
            and not other_domain.endswith("." + domain)
            and domain not in other_domain
        ):
            continue
        for tag in other.get("tags") or []:
            if tag:
                tag_counts[str(tag)] += 1
    existing = {t["name"] for t in (link.get("tags") or []) if t.get("name")}
    suggestions = [
        {"name": name, "count": count, "reason": f"used on {count} similar-domain links"}
        for name, count in tag_counts.most_common()
        if count >= min_count and name not in existing
    ]
    return {
        "link_id": link_id,
        "domain": domain,
        "existing_tags": sorted(existing),
        "suggestions": suggestions[:10],
    }


async def bulk_sort_by_rules(
    client: LinkwardenClient,
    resolver: NameResolver,
    *,
    rules: list[dict[str, Any]],
    dry_run: bool = True,
    collection: str | None = UNORGANIZED,
    max_bulk: int = 25,
) -> dict[str, Any]:
    links = await _fetch_collection_links(
        client, resolver, collection, limit=SCAN_LIMIT
    )
    matches: list[dict[str, Any]] = []
    for link in links:
        url = str(link.get("url") or "")
        rule = classify.match_sort_rules(url, rules)
        if not rule:
            continue
        matches.append(
            {
                "link_id": link.get("id"),
                "url": url,
                "collection": rule.get("collection"),
                "tags": rule.get("tags"),
                "matched_pattern": rule.get("domain_pattern"),
            }
        )
    if dry_run:
        return {
            "dry_run": True,
            "match_count": len(matches),
            "matches": matches[: max_bulk * 2],
            "message": "Dry run only. Pass dry_run=false to apply (bulk-capped).",
            "scan_capped_at": SCAN_LIMIT,
        }
    check_bulk_cap(len(matches), max_bulk)
    updated = 0
    for m in matches:
        await writes.organise_links(
            client,
            resolver,
            link_ids=[int(m["link_id"])],
            collection=m.get("collection"),
            tags=m.get("tags"),
            max_bulk=max_bulk,
        )
        updated += 1
    return {
        "dry_run": False,
        "updated_count": updated,
        "matches": matches,
        "message": f"Sorted {updated} links by rules.",
    }


async def get_sorting_dashboard(
    client: LinkwardenClient,
    resolver: NameResolver,
) -> dict[str, Any]:
    overview = await reads.get_library_overview(resolver)
    unsorted = await find_unsorted_links(client, resolver, limit=50)
    dupes = await find_duplicate_links(client, resolver, limit=SCAN_LIMIT)
    structure = await suggest_collection_structure(client, resolver)
    collections = await resolver.collections()
    largest = sorted(
        [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "link_count": (c.get("_count") or {}).get("links", 0),
            }
            for c in collections
        ],
        key=lambda x: -x["link_count"],
    )[:10]
    return {
        "totals": {
            "collections": overview.get("total_collections"),
            "links": overview.get("total_links"),
            "unorganized": overview.get("unorganized_link_count"),
        },
        "unsorted_count": unsorted.get("count"),
        "duplicate_group_count": dupes.get("group_count"),
        "empty_collections": overview.get("empty_collections") or [],
        "unused_tags": overview.get("unused_tags") or [],
        "near_duplicate_names": structure.get("near_duplicate_names") or [],
        "largest_collections": largest,
        "message": "Triage entry point. Next: find_unsorted_links → triage_links → apply_triage_plan.",
    }
