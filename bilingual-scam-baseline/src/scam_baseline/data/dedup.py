from __future__ import annotations

import hashlib
from collections import defaultdict
from difflib import SequenceMatcher

import pandas as pd

from .clean import stable_hash, strict_duplicate_key, template_duplicate_key


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def _union_equal_keys(keys: list[str], union_find: UnionFind, min_length: int = 1) -> None:
    first_index: dict[str, int] = {}
    for index, key in enumerate(keys):
        if not key or len(key) < min_length:
            continue
        previous = first_index.setdefault(key, index)
        union_find.union(index, previous)


def _simhash64(text: str) -> int:
    padded = f"  {text[:1000]}  "
    shingles = {padded[index : index + 4] for index in range(max(1, len(padded) - 3))}
    vector = [0] * 64
    for shingle in shingles:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            vector[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            result |= 1 << bit
    return result


def _union_fuzzy(
    keys: list[str],
    union_find: UnionFind,
    *,
    min_characters: int,
    threshold: float,
    max_candidates_per_bucket: int,
) -> int:
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    fingerprints: list[int | None] = [None] * len(keys)
    matches = 0
    for index, key in enumerate(keys):
        if len(key) < min_characters:
            continue
        fingerprint = _simhash64(key)
        fingerprints[index] = fingerprint
        candidates: set[int] = set()
        for band in range(4):
            band_value = (fingerprint >> (band * 16)) & 0xFFFF
            candidates.update(buckets[(band, band_value)][-max_candidates_per_bucket:])
        for other in sorted(candidates):
            other_key = keys[other]
            length_ratio = min(len(key), len(other_key)) / max(len(key), len(other_key))
            if length_ratio < 0.80:
                continue
            ratio = SequenceMatcher(None, key, other_key, autojunk=False).ratio()
            if ratio >= threshold:
                union_find.union(index, other)
                matches += 1
        for band in range(4):
            band_value = (fingerprint >> (band * 16)) & 0xFFFF
            buckets[(band, band_value)].append(index)
    return matches


def assign_duplicate_groups(
    frame: pd.DataFrame, config: dict
) -> tuple[pd.DataFrame, dict[str, int | float | bool]]:
    result = frame.copy().reset_index(drop=True)
    dedup_cfg = config["deduplication"]
    result["strict_duplicate_key"] = result["text_clean"].map(strict_duplicate_key)
    result["template_duplicate_key"] = result["text_clean"].map(
        lambda text: template_duplicate_key(
            text,
            mask_urls=bool(dedup_cfg.get("mask_urls", True)),
            mask_emails=bool(dedup_cfg.get("mask_emails", True)),
            mask_numbers=bool(dedup_cfg.get("mask_numbers", True)),
        )
    )
    strict_keys = result["strict_duplicate_key"].tolist()
    template_keys = result["template_duplicate_key"].tolist()
    union_find = UnionFind(len(result))
    _union_equal_keys(strict_keys, union_find)
    _union_equal_keys(
        template_keys,
        union_find,
        min_length=int(dedup_cfg.get("template_min_characters", 12)),
    )
    fuzzy_matches = 0
    if dedup_cfg.get("fuzzy_enabled", True):
        fuzzy_matches = _union_fuzzy(
            template_keys,
            union_find,
            min_characters=int(dedup_cfg.get("fuzzy_min_characters", 35)),
            threshold=float(dedup_cfg.get("fuzzy_threshold", 0.96)),
            max_candidates_per_bucket=int(
                dedup_cfg.get("fuzzy_max_candidates_per_bucket", 120)
            ),
        )

    root_to_key: dict[int, str] = {}
    for index in range(len(result)):
        root = union_find.find(index)
        member_hash = stable_hash(strict_keys[index] or f"empty:{index}")
        if root not in root_to_key or member_hash < root_to_key[root]:
            root_to_key[root] = member_hash
    result["group_id"] = [
        f"grp_{root_to_key[union_find.find(index)]}" for index in range(len(result))
    ]
    result["exact_duplicate_rank"] = (
        result.groupby("strict_duplicate_key", sort=False).cumcount() + 1
    )
    result["exact_duplicate_count"] = result.groupby(
        "strict_duplicate_key", sort=False
    )["strict_duplicate_key"].transform("size")
    result["group_size"] = result.groupby("group_id", sort=False)[
        "group_id"
    ].transform("size")
    result["group_label_count"] = result.groupby("group_id", sort=False)[
        "label_level_1"
    ].transform("nunique")
    result["label_conflict"] = result["group_label_count"] > 1

    report: dict[str, int | float | bool] = {
        "rows": len(result),
        "strict_duplicate_rows": int((result["exact_duplicate_count"] > 1).sum()),
        "strict_duplicate_groups": int(
            result.loc[result["exact_duplicate_count"] > 1, "strict_duplicate_key"].nunique()
        ),
        "near_duplicate_groups": int((result.groupby("group_id").size() > 1).sum()),
        "label_conflict_groups": int(
            result.loc[result["label_conflict"], "group_id"].nunique()
        ),
        "fuzzy_enabled": bool(dedup_cfg.get("fuzzy_enabled", True)),
        "fuzzy_pair_matches": fuzzy_matches,
    }
    return result, report

