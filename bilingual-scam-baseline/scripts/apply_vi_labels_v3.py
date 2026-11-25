"""Apply the v3 manual label review to the Vietnamese raw data (and template-family cleaning).

Inputs (never modified):
  data/raw/full_dataset_spamscam.csv            Tuan dataset with message_id
  data/raw/train_dataset_spamscam.csv           Tuan's official train split (message, label)
  data/raw/test_dataset_spamscam.csv            Tuan's official test split
  data/raw/corpus_dataset_vie-spam-sms-filtering.txt   vie_sms_corpus (Pham & Le-Hong 2017)
  data/review/vi_tuan_label1_review_v3.csv      final labels for Tuan label-1 messages
  data/review/vi_tuan_label0_review.csv         Tuan label-0 messages whose label changed
  data/review/vi_external_spam_review_v3.csv    vie_sms_corpus spam groups (by sample_id)
  data/review/vi_external_legit_overrides.csv   vie_sms_corpus ham overrides (by sample_id)
  data/review/vi_external_spam_conflict_overrides.csv  12 raw 'spam' rows that are obvious ham (OTP, "Ok")
  data/review/vi_scam_type_overrides.csv        scam_type corrections for Stage 2 (by message_ids)

Outputs:
  data/raw/train_dataset_spamscam_v3.csv        train, v3 labels, minus rows sharing a template family with test
  data/raw/test_dataset_spamscam_v3.csv         test, v3 labels (Tuan's split, unchanged rows)
  data/raw/vie_sms_corpus_v3.csv                vie_sms_corpus, v3 labels, 'drop' rows removed, column vie_half
  data/raw/vie_sms_corpus_dev_v3.csv            half usable for train/validation (fixes the "diacritics = scam" shortcut)
  data/raw/vie_sms_corpus_holdout_v3.csv        locked half = external test (false-alarm rate)
  data/review/vi_tuan_train_removed_family_overlap.csv   log of train rows removed (option B)
  data/review/vi_labels_v3_summary.json         counts for the report

Template family (option B): two messages are in the same family when the Jaccard similarity of their
word 3-gram sets is >= FAMILY_JACCARD after lower-casing, removing diacritics, placeholders, URLs and
digits. Families are the connected components (union-find). Any train row whose family contains a
test row is removed, so every test message is "unseen" at template level.

Usage:  python scripts/apply_vi_labels_v3.py [--family-jaccard 0.5] [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.data.clean import clean_text, stable_hash, template_duplicate_key  # noqa: E402

RAW = ROOT / "data" / "raw"
REVIEW = ROOT / "data" / "review"
VIE_SOURCE = "vie_sms_corpus"
VALID_LABELS = {"legitimate", "spam", "scam"}
FAMILY_JACCARD = 0.5


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def split_ids(value: object) -> list[str]:
    return [part.strip() for part in re.split(r"[;|,\s]+", str(value)) if part.strip()]


# family logic is shared with the pipeline (deduplication.family_jaccard)
from scam_baseline.data.family import normalize_for_family, shingles, template_families  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Tuan dataset
# ---------------------------------------------------------------------------
def tuan_final_labels(full: pd.DataFrame) -> pd.DataFrame:
    """Return full with final label_3class / scam_type / label_source per message_id."""
    out = full.copy()
    out["label_3class"] = out["label"].map({0: "legitimate", 1: None})
    out["scam_type"] = "none"
    out["label_source"] = "original"
    known = set(out["message_id"])

    reviews = [
        ("review_v3_label1", REVIEW / "vi_tuan_label1_review_v3.csv"),
        ("review_label0", REVIEW / "vi_tuan_label0_review.csv"),
    ]
    for source, path in reviews:
        review = pd.read_csv(path, encoding="utf-8-sig")
        for _, row in review.iterrows():
            label = str(row["review_label"]).strip()
            if label not in VALID_LABELS:
                raise ValueError(f"{path.name}: unexpected review_label {label!r} for {row['message_ids']}")
            ids = split_ids(row["message_ids"])
            missing = [i for i in ids if i not in known]
            if missing:
                raise ValueError(f"{path.name}: message_ids not found in full dataset: {missing}")
            stype = row.get("review_scam_type")
            stype = str(stype).strip() if label == "scam" and isinstance(stype, str) and stype.strip() else (
                "other_scam" if label == "scam" else "none")
            mask = out["message_id"].isin(ids)
            out.loc[mask, ["label_3class", "scam_type", "label_source"]] = [label, stype, source]

    # scam_type corrections for Stage 2 (2026-11-25): only touch rows that are scam after the reviews
    type_path = REVIEW / "vi_scam_type_overrides.csv"
    if type_path.exists():
        types = pd.read_csv(type_path, encoding="utf-8-sig")
        for _, row in types.iterrows():
            ids = split_ids(row["message_ids"])
            missing = [i for i in ids if i not in known]
            if missing:
                raise ValueError(f"{type_path.name}: message_ids not found: {missing}")
            mask = out["message_id"].isin(ids)
            if not out.loc[mask, "label_3class"].eq("scam").all():
                raise ValueError(f"{type_path.name}: {ids} are not all scam – fix the override")
            out.loc[mask, "scam_type"] = row["scam_type"]

    unresolved = out["label_3class"].isna()
    if unresolved.any():
        raise ValueError(
            f"{int(unresolved.sum())} label-1 messages have no v3 review, e.g. "
            f"{out.loc[unresolved, 'message_id'].head(5).tolist()}"
        )
    conflicts = out.groupby("message")["label_3class"].nunique()
    if (conflicts > 1).any():
        raise ValueError(f"{int((conflicts > 1).sum())} identical texts received different v3 labels")
    return out


def attach_ids(split: pd.DataFrame, full: pd.DataFrame, name: str) -> pd.DataFrame:
    """Give each split row a message_id from full (same text, ids handed out in file order)."""
    pool: dict[str, list[str]] = defaultdict(list)
    for mid, msg in zip(full["message_id"], full["message"]):
        pool[msg].append(mid)
    ids = []
    for msg in split["message"]:
        if not pool.get(msg):
            raise ValueError(f"{name}: text not found (or more copies than in full dataset): {msg[:80]!r}")
        ids.append(pool[msg].pop(0))
    result = split.copy()
    result.insert(0, "message_id", ids)
    return result


def build_tuan(threshold: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    full = pd.read_csv(RAW / "full_dataset_spamscam.csv", encoding="utf-8-sig")
    train = pd.read_csv(RAW / "train_dataset_spamscam.csv", encoding="utf-8-sig")
    test = pd.read_csv(RAW / "test_dataset_spamscam.csv", encoding="utf-8-sig")
    if len(train) + len(test) != len(full):
        raise ValueError("train + test row count does not match full dataset")

    labelled = tuan_final_labels(full).set_index("message_id")
    # train/test ids are handed out from one shared pool so no id is used twice
    both = attach_ids(pd.concat([train.assign(_split="train"), test.assign(_split="test")], ignore_index=True),
                      full, "train+test")
    if both["message_id"].duplicated().any():
        raise ValueError("a message_id was assigned twice")
    cols = ["label_3class", "scam_type", "label_source", "date"]
    both = both.join(labelled[cols], on="message_id")
    if (both["label"] != both["message_id"].map(labelled["label"])).any():
        raise ValueError("original 0/1 label in split file disagrees with full dataset")

    both["family_id"] = [f"fam_{stable_hash(str(f), 8)}" for f in template_families(both["message"].tolist(), threshold)]
    test_families = set(both.loc[both["_split"] == "test", "family_id"])
    train_all = both[both["_split"] == "train"]
    overlap = train_all["family_id"].isin(test_families)

    out_cols = ["message_id", "message", "label", "label_3class", "scam_type", "label_source", "family_id", "date"]
    train_v3 = train_all.loc[~overlap, out_cols].reset_index(drop=True)
    test_v3 = both.loc[both["_split"] == "test", out_cols].reset_index(drop=True)
    removed = train_all.loc[overlap, out_cols].reset_index(drop=True)

    summary = {
        "family_jaccard": threshold,
        "families_total": int(both["family_id"].nunique()),
        "full_v3": both["label_3class"].value_counts().to_dict(),
        "train_before_family_filter": train_all["label_3class"].value_counts().to_dict(),
        "train_removed_family_overlap": removed["label_3class"].value_counts().to_dict(),
        "train_v3": train_v3["label_3class"].value_counts().to_dict(),
        "test_v3": test_v3["label_3class"].value_counts().to_dict(),
        "train_v3_scam_type": train_v3.loc[train_v3["label_3class"] == "scam", "scam_type"].value_counts().to_dict(),
        "test_v3_scam_type": test_v3.loc[test_v3["label_3class"] == "scam", "scam_type"].value_counts().to_dict(),
    }
    return train_v3, test_v3, removed, summary


# ---------------------------------------------------------------------------
# vie_sms_corpus
# ---------------------------------------------------------------------------
def build_vie_sms() -> tuple[pd.DataFrame, dict]:
    # identical read settings to configs/vietnamese_3class.yaml -> adapters.load_custom_dataset
    raw = pd.read_csv(RAW / "corpus_dataset_vie-spam-sms-filtering.txt", sep="\t", names=["label", "text"],
                      dtype="string", keep_default_na=True, encoding="utf-8")
    raw["text"] = raw["text"].fillna("").astype(str)
    raw["sample_id"] = [
        "sample_" + stable_hash(f"{VIE_SOURCE}|{VIE_SOURCE}:{idx}|{clean_text(text)}")
        for idx, text in zip(raw.index, raw["text"])
    ]
    raw["label_3class"] = raw["label"].str.strip().str.casefold().map({"ham": "legitimate", "spam": "spam"})
    raw["label_source"] = "original"
    sid_to_idx = dict(zip(raw["sample_id"], raw.index))

    reviews = [
        ("review_v3_spam", REVIEW / "vi_external_spam_review_v3.csv", "utf-8"),
        ("override_legit", REVIEW / "vi_external_legit_overrides.csv", "utf-8"),
        ("override_spam_conflict", REVIEW / "vi_external_spam_conflict_overrides.csv", "utf-8"),
    ]
    reviewed_rows: set[int] = set()
    for source, path, enc in reviews:
        review = pd.read_csv(path, encoding=enc)
        for _, row in review.iterrows():
            label = str(row["review_label"]).strip()
            if label not in VALID_LABELS | {"drop"}:
                raise ValueError(f"{path.name}: unexpected review_label {label!r}")
            ids = split_ids(row["group_member_ids"])
            missing = [i for i in ids if i not in sid_to_idx]
            if missing:
                raise ValueError(f"{path.name}: sample_ids not found in vie_sms_corpus: {missing[:5]}")
            idx = [sid_to_idx[i] for i in ids]
            raw.loc[idx, ["label_3class", "label_source"]] = [label, source]
            reviewed_rows.update(idx)

    # Rows the pipeline had excluded as duplicates were not in the review groups: copy the reviewed
    # label to every unreviewed row with the same template key (same text up to numbers/URLs).
    raw["_key"] = raw["text"].map(template_duplicate_key)
    reviewed_mask = raw.index.isin(list(reviewed_rows))
    key_labels = raw[reviewed_mask].groupby("_key")["label_3class"].agg(lambda s: set(s))
    propagated = conflicting = 0
    for idx in raw.index[~reviewed_mask]:
        labels = key_labels.get(raw.at[idx, "_key"])
        if not labels:
            continue
        if len(labels) > 1:
            conflicting += 1
            continue
        raw.loc[idx, ["label_3class", "label_source"]] = [next(iter(labels)), "propagated_duplicate"]
        propagated += 1
        reviewed_rows.add(idx)

    spam_unreviewed = int(((raw["label"] == "spam") & ~raw.index.isin(list(reviewed_rows))).sum())
    kept = raw[raw["label_3class"] != "drop"].copy()
    kept.insert(0, "record_index", kept.index)
    out = kept[["record_index", "sample_id", "text", "label", "label_3class", "label_source"]].reset_index(drop=True)
    out["vie_half"] = assign_halves(out["text"].tolist(), out["label_3class"].tolist())
    summary = {
        "rows_raw": int(len(raw)),
        "rows_dropped": int((raw["label_3class"] == "drop").sum()),
        "rows_label_propagated_from_duplicate": propagated,
        "rows_duplicate_key_conflict": conflicting,
        "spam_rows_not_reviewed": spam_unreviewed,
        "v3": out["label_3class"].value_counts().to_dict(),
        "label_source": out["label_source"].value_counts().to_dict(),
        "halves": {
            half: grp["label_3class"].value_counts().to_dict() for half, grp in out.groupby("vie_half")
        },
    }
    return out, summary


def assign_halves(texts: list[str], labels: list[str], threshold: float = FAMILY_JACCARD) -> list[str]:
    """Split vie_sms_corpus 50/50 into 'dev' (may be used for training) and 'holdout' (locked external).

    Whole template families go to one half (no near-duplicate crosses the line); families are
    stratified by their majority label and assigned alternately in a hash order, so the split is
    deterministic and does not depend on file order.
    """
    families = template_families(texts, threshold)
    frame = pd.DataFrame({"family": families, "label": labels, "text": texts})
    fam = frame.groupby("family").agg(label=("label", lambda s: s.mode().iat[0]), key=("text", "min"))
    fam["order"] = fam["key"].map(lambda t: stable_hash(t, 12))
    half_of: dict[int, str] = {}
    for _, group in fam.sort_values("order").groupby("label", sort=True):
        sizes = {"dev": 0, "holdout": 0}
        counts = frame.groupby("family").size()
        for family_id in group.index:
            target = "dev" if sizes["dev"] <= sizes["holdout"] else "holdout"
            half_of[family_id] = target
            sizes[target] += int(counts[family_id])
    return [half_of[f] for f in families]


# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--family-jaccard", type=float, default=FAMILY_JACCARD)
    parser.add_argument("--check", action="store_true", help="compute and print, write nothing")
    args = parser.parse_args()

    train_v3, test_v3, removed, tuan_summary = build_tuan(args.family_jaccard)
    vie_v3, vie_summary = build_vie_sms()
    summary = {"tuan": tuan_summary, VIE_SOURCE: vie_summary}

    # sanity: no test family left in train, no id overlap
    assert not set(train_v3["family_id"]) & set(test_v3["family_id"]), "family leakage train/test"
    assert not set(train_v3["message_id"]) & set(test_v3["message_id"]), "message_id in both splits"

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.check:
        return
    train_v3.to_csv(RAW / "train_dataset_spamscam_v3.csv", index=False, encoding="utf-8-sig")
    test_v3.to_csv(RAW / "test_dataset_spamscam_v3.csv", index=False, encoding="utf-8-sig")
    vie_v3.to_csv(RAW / "vie_sms_corpus_v3.csv", index=False, encoding="utf-8-sig")
    for half in ("dev", "holdout"):
        vie_v3[vie_v3["vie_half"] == half].to_csv(
            RAW / f"vie_sms_corpus_{half}_v3.csv", index=False, encoding="utf-8-sig")
    removed.to_csv(REVIEW / "vi_tuan_train_removed_family_overlap.csv", index=False, encoding="utf-8-sig")
    (REVIEW / "vi_labels_v3_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written: train/test_dataset_spamscam_v3.csv, vie_sms_corpus_v3.csv, removed log, summary json")


if __name__ == "__main__":
    main()
