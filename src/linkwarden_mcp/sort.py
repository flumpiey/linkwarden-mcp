"""Sort word to Linkwarden API integer mapping."""

from __future__ import annotations

# Upstream `Sort` enum (links); 4 is Custom order, not exposed.
LINK_SORT_WORDS: dict[str, int] = {
    "newest": 0,
    "oldest": 1,
    "name": 2,
    "name_asc": 2,
    "name_desc": 3,
}

# Upstream `TagSort` enum adds link-count ordering.
TAG_SORT_WORDS: dict[str, int] = {
    **LINK_SORT_WORDS,
    "link_count_desc": 4,
    "link_count_asc": 5,
}


def sort_to_int(word: str | None, words: dict[str, int] = LINK_SORT_WORDS) -> int | None:
    if word is None:
        return None
    key = word.strip().lower()
    if key not in words:
        raise ValueError(f"Unknown sort {word!r}. Valid: {', '.join(sorted(words))}")
    return words[key]
