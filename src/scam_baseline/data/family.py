"""Template families: messages written from the same template (only names, links, amounts changed).

Two messages are in the same family when the Jaccard similarity of their word 3-gram sets is
>= threshold after lower-casing, removing diacritics, placeholders ([MONEY], <PHONE> ...), URLs
and digits. Families are connected components, so "A~B and B~C" puts A, B and C together.

Used to keep a whole family in one split (no near-copy of a test message in train) – a looser
notion than the pipeline's duplicate groups (exact / template key / fuzzy >= 0.95).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Iterable, Sequence

DEFAULT_JACCARD = 0.5
MAX_POSTING = 200  # 3-grams shared by more messages than this are too generic to link families


def normalize_for_family(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("đ", "d")
    text = re.sub(r"\[[a-z_]+\]|<[a-z_]+>", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " url ", text)
    text = re.sub(r"\d+", " ", text)
    return re.sub(r"\W+", " ", text).strip()


def shingles(text: str) -> frozenset:
    words = normalize_for_family(text).split()
    if len(words) < 3:
        return frozenset({tuple(words)})
    return frozenset(zip(words, words[1:], words[2:]))


def template_families(
    texts: Sequence[str],
    threshold: float = DEFAULT_JACCARD,
    link_groups: Iterable[str] | None = None,
) -> list[int]:
    """Family index per text. ``link_groups`` (optional, same length) forces rows with the same
    value (e.g. the pipeline's group_id) into the same family."""
    sets = [shingles(t) for t in texts]
    parent = list(range(len(sets)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    postings: dict[tuple, list[int]] = defaultdict(list)
    for i, s in enumerate(sets):
        for g in s:
            postings[g].append(i)
    for i, s in enumerate(sets):
        shared: Counter = Counter()
        for g in s:
            if len(postings[g]) <= MAX_POSTING:
                shared.update(postings[g])
        for j, inter in shared.items():
            if j > i and inter / len(s | sets[j]) >= threshold:
                union(i, j)
    if link_groups is not None:
        first: dict[str, int] = {}
        for i, g in enumerate(link_groups):
            union(i, first.setdefault(g, i))
    roots = [find(i) for i in range(len(sets))]
    remap: dict[int, int] = {}
    return [remap.setdefault(r, len(remap)) for r in roots]
