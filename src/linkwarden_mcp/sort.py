"""Sort word to Linkwarden API integer mapping."""

from __future__ import annotations

SORT_WORDS: dict[str, int] = {
    "newest": 0,
    "oldest": 1,
    "name": 2,
    "name_asc": 2,
    "name_desc": 3,
    "tag_count_desc": 4,
    "tag_count_asc": 5,
}


def sort_to_int(word: str | None) -> int | None:
    if word is None:
        return None
    key = word.strip().lower()
    if key not in SORT_WORDS:
        raise ValueError(
            f"Unknown sort {word!r}. Valid: {', '.join(sorted(SORT_WORDS))}"
        )
    return SORT_WORDS[key]
