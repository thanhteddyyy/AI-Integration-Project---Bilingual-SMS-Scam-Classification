"""Tier 2 (Vietnamese): which kind of scam is it? 9 classes of data/scam_types.py.

Tier 2 only sees messages that are scam, so its data is the scam rows of the Tuan set. It has its own
split (decision 2026-11-27): tier 1 must keep Tuan's test split to compare with the original work,
tier 2 is a new task without that constraint. All 641 Tuan scam rows are used, including the train rows
dropped by "option B", deduplicated by exact text and split by TEMPLATE FAMILY so every class has at
least one family in train, validation and test and no family crosses splits.

The frame uses the column names of tier 1 so the same trainers work unchanged:
  label_level_1 = scam_type (the tier-2 class), group_id = template family.

Real scams crawled from news (decision 2026-11-27):
  * runs 1-2 (data/raw/vi_crawl_tier2_train.csv, every channel – only the main scam message is kept, so a
    chat message counts like an SMS) are ADDED TO TRAIN; validation / test stay Tuan-only and unchanged;
  * a later run is the external test (data.crawl_external, skipped while the file does not exist),
    reported by "template seen in tier-2 train or not", plus the chain tier 1 -> tier 2 (a scam that
    tier 1 misses counts as a chain failure).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data.clean import clean_text, stable_hash, strict_duplicate_key
from .data.family import template_families
from .data.scam_types import VI_TIER2_CLASSES, VI_TIER2_GROUPS, merge_vi_scam_type
from .evaluation import compute_metrics, wilson_interval

SPLITS = ("train", "validation", "test")


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load_tuan_scams(config: dict) -> pd.DataFrame:
    """Scam rows of every Tuan file listed in data.extra_datasets, one row per distinct text."""
    root = Path(config["_project_root"])
    frames = []
    for spec in config["data"]["extra_datasets"]:
        raw = pd.read_csv(root / spec["path"], encoding=spec.get("encoding", "utf-8-sig"))
        raw = raw[raw[spec["label_column"]].eq("scam")]
        frames.append(pd.DataFrame({
            "source_dataset": spec["name"],
            "source_record_id": raw[spec.get("id_column", "message_id")].astype(str),
            "text_raw": raw[spec["text_column"]].astype(str),
            "label_level_1": raw[spec["scam_type_column"]].astype(str).map(merge_vi_scam_type),
        }))
    data = pd.concat(frames, ignore_index=True)
    data["text_clean"] = data["text_raw"].map(clean_text)
    data = data[data["text_clean"].str.len() > 0]
    unknown = set(data["label_level_1"]) - set(VI_TIER2_CLASSES)
    if unknown:
        raise ValueError(f"scam_type outside the tier-2 classes: {sorted(unknown)}")

    key = data["text_clean"].map(strict_duplicate_key)
    if (data.groupby(key)["label_level_1"].nunique() > 1).any():
        raise ValueError("identical texts carry different scam_type labels")
    data = (
        data.assign(_key=key)
        .groupby("_key", sort=False)
        .agg(
            source_dataset=("source_dataset", "first"),
            source_record_id=("source_record_id", lambda ids: ";".join(ids)),
            text_raw=("text_raw", "first"),
            text_clean=("text_clean", "first"),
            label_level_1=("label_level_1", "first"),
            copies=("text_clean", "size"),
        )
        .reset_index(drop=True)
    )
    data["sample_id"] = ["t2_" + stable_hash(t, 12) for t in data["text_clean"]]
    data["language"] = "vi"
    return data


def assign_family_splits(
    labels: pd.Series, families: pd.Series, fractions: dict[str, float], seed: int
) -> pd.Series:
    """Split whole families, per class, to the target row fractions; val and test each get at
    least one family of every class that has >= 3 families. Deterministic for a given seed."""
    rng = np.random.default_rng(seed)
    info = pd.DataFrame({"label": labels.values, "family": families.values}).groupby("family").agg(
        label=("label", "first"), size=("label", "size")
    )
    if (pd.DataFrame({"l": labels.values, "f": families.values}).groupby("f")["l"].nunique() > 1).any():
        raise ValueError("a template family mixes scam types; fix the labels first")
    family_split: dict = {}
    for _, fams in info.groupby("label", sort=True):
        fams = fams.sort_index()
        order = fams.assign(_tie=rng.random(len(fams))).sort_values(["size", "_tie"], ascending=[False, True])
        total = float(fams["size"].sum())
        current = {s: 0 for s in SPLITS}
        members: dict[str, list] = {s: [] for s in SPLITS}
        for fam, row in order.iterrows():
            # largest relative deficit first (classic greedy for balanced bins)
            target = max(SPLITS, key=lambda s: fractions[s] * total - current[s])
            current[target] += int(row["size"])
            members[target].append(fam)
        if len(fams) >= 3:
            for needed in ("test", "validation"):
                if fractions[needed] > 0 and not members[needed]:
                    donor = "train" if len(members["train"]) > 1 else ("validation" if needed == "test" else "test")
                    smallest = min(members[donor], key=lambda f: info.loc[f, "size"])
                    members[donor].remove(smallest)
                    members[needed].append(smallest)
        for split, fam_list in members.items():
            for fam in fam_list:
                family_split[fam] = split
    return families.map(family_split)


def build_tier2_frame(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(tier-2 frame, crawl rows not added to train with the reason)."""
    data = load_tuan_scams(config)
    threshold = float(config["deduplication"]["family_jaccard"])
    data["group_id"] = [f"fam_{i}" for i in template_families(data["text_clean"].tolist(), threshold)]
    split_cfg = config["split"]
    fractions = {
        "train": float(split_cfg["train_fraction"]),
        "validation": float(split_cfg["validation_fraction"]),
        "test": float(split_cfg["test_fraction"]),
    }
    data["split"] = assign_family_splits(data["label_level_1"], data["group_id"], fractions, int(config["seed"]))
    data["channel"] = "sms"
    skipped_all = []
    for spec in config["data"].get("crawl_train", []):
        crawl = load_crawl_scams(Path(config["_project_root"]) / spec["path"], spec["name"])
        data, skipped = add_crawl_to_train(data, crawl, threshold)
        skipped_all.append(skipped)
    skipped = pd.concat(skipped_all, ignore_index=True) if skipped_all else pd.DataFrame()
    return data, skipped


def load_crawl_scams(path: Path, source: str) -> pd.DataFrame:
    """Scam rows of a crawl file built by scripts/build_vi_crawl_external.py (--full-out format)."""
    raw = pd.read_csv(path, encoding="utf-8-sig")
    raw = raw[raw["label_3class"].eq("scam")].reset_index(drop=True)
    crawl = pd.DataFrame({
        "sample_id": raw["crawl_id"].astype(str),
        "source_dataset": source,
        "source_record_id": raw["crawl_id"].astype(str),
        "language": "vi",
        "text_raw": raw["message"].astype(str),
        "text_clean": raw["message"].map(clean_text),
        "label_level_1": raw["scam_type"].astype(str).map(merge_vi_scam_type),
        "channel": raw["channel"].astype(str),
        "tuan_family": raw["tuan_family"].astype(str).str.lower().eq("true"),
    })
    unknown = set(crawl["label_level_1"]) - set(VI_TIER2_CLASSES)
    if unknown:
        raise ValueError(f"{path.name}: scam_type outside the tier-2 classes: {sorted(unknown)}")
    return crawl


def add_crawl_to_train(frame: pd.DataFrame, crawl: pd.DataFrame, threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add crawl scams to TRAIN (decision 2026-11-27: runs 1-2 train tier 2, a later run is its external test).

    Validation / test stay exactly as before. A crawl row is NOT added when it is an exact copy of a Tuan
    message, or when it shares a template family with a validation / test message (that would leak the
    template into train). Returns (frame with the added rows, log of skipped crawl rows)."""
    keys = set(frame["text_clean"].map(strict_duplicate_key))
    crawl = crawl.copy()
    crawl["skip_reason"] = np.where(crawl["text_clean"].map(strict_duplicate_key).isin(keys), "exact_copy_of_tuan", "")
    texts = frame["text_clean"].tolist() + crawl["text_clean"].tolist()
    joint = template_families(texts, threshold)
    n = len(frame)
    split_of_joint: dict[int, set] = {}
    tuan_group_of_joint: dict[int, str] = {}
    for fam, split, group in zip(joint[:n], frame["split"], frame["group_id"]):
        split_of_joint.setdefault(fam, set()).add(split)
        tuan_group_of_joint.setdefault(fam, group)
    crawl_fams = joint[n:]
    leak = [bool(split_of_joint.get(f, set()) & {"validation", "test"}) for f in crawl_fams]
    crawl.loc[(crawl["skip_reason"] == "") & pd.Series(leak, index=crawl.index), "skip_reason"] = "family_in_tier2_val_or_test"
    # a crawl row joins its Tuan family's group (grouped CV keeps them together), else a new group
    crawl["group_id"] = [tuan_group_of_joint.get(f, f"crawl_fam_{f}") for f in crawl_fams]
    label_of_group = frame.groupby("group_id")["label_level_1"].first()
    tuan_label = crawl["group_id"].map(label_of_group)
    conflict = tuan_label.notna() & tuan_label.ne(crawl["label_level_1"]) & crawl["skip_reason"].eq("")
    if conflict.any():
        rows = crawl.loc[conflict, ["sample_id", "label_level_1"]].assign(tuan_label=tuan_label[conflict])
        raise ValueError("crawl rows share a template with Tuan rows of ANOTHER scam_type – fix one of the labels "
                         f"(data/review/vi_scam_type_overrides.csv or the crawl review file):\n{rows.to_string()}")
    added = crawl[crawl["skip_reason"].eq("")].assign(split="train", copies=1)
    cols = list(frame.columns)
    out = pd.concat([frame, added[[c for c in cols if c in added.columns]]], ignore_index=True)
    return out, crawl[crawl["skip_reason"].ne("")]


def load_crawl_external(config: dict, train_texts: list[str]) -> pd.DataFrame | None:
    """External test = a crawl run NOT used for training (config data.crawl_external), or None if absent."""
    spec = config["data"].get("crawl_external") or {}
    path = Path(config["_project_root"]) / spec["path"] if spec.get("path") else None
    if path is None or not path.exists():
        return None
    crawl = load_crawl_scams(path, "vi_crawl_external")
    if crawl.empty:
        return None
    crawl["split"] = "external_test"
    # same template as a TIER-2 TRAIN message (incl. crawl runs used for training)
    threshold = float(config["deduplication"]["family_jaccard"])
    fams = template_families(list(train_texts) + crawl["text_clean"].tolist(), threshold)
    train_fams = set(fams[: len(train_texts)])
    crawl["in_tier2_train_family"] = [f in train_fams for f in fams[len(train_texts):]]
    crawl["group_id"] = [f"crawl_fam_{f}" for f in fams[len(train_texts):]]
    # channel is not a split criterion any more (decision 2026-11-27): only the main scam message is kept,
    # so a chat message is treated like an SMS; subsets = template already seen in tier-2 train or not
    crawl["subset"] = np.where(crawl["in_tier2_train_family"], "known template", "new template")
    return crawl


# ---------------------------------------------------------------------------
# experiment A3 (2026-11-27): bank name of the PAYEE account
# ---------------------------------------------------------------------------
BANK_NAME_RE = (r"vietcombank|vcb|techcombank|techcom6ank|bidv|agribank|vietinbank|vietin|mb ?bank|vpbank|acb|sacombank|"
                r"tpbank|hdbank|shb|ocb|eximbank|seabank|msb|vib|momo|zalopay")
# "chuyển (giúp con) vào STK [NUMBER] Vietcombank", "vào [NUMBER] (Sacombank)", "STK 0123 ACB": the bank only says
# where the money goes. A bank-impersonation scam names the bank as the SENDER ("[Vietcombank] Tài khoản ...").
PAYEE_BANK_RE = __import__("re").compile(
    rf"(?i)((?:\bstk\b|số tài khoản|so tai khoan|\btk\b|chuyển[^.]{{0,25}}?vào|chuyen[^.]{{0,25}}?vao)"
    rf"[^.\n]{{0,30}}?(?:\[NUMBER\]|\d{{6,}})\s*\(?\s*)({BANK_NAME_RE})\b"
)


def mask_payee_bank(text: str) -> str:
    return PAYEE_BANK_RE.sub(lambda m: m.group(1) + "[PAYEE_BANK]", str(text))


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def group_labels(values) -> list[str]:
    return [VI_TIER2_GROUPS.get(v, v) for v in values]


def tier2_metrics(truth: list[str], prediction: list[str], class_order: list[str]) -> dict:
    """Class-level metrics, recall CI per class and the coarse (definition group) level."""
    fine = compute_metrics(truth, prediction, class_order)
    for label, row in fine["per_class"].items():
        hits = sum(t == label and p == label for t, p in zip(truth, prediction))
        row["recall_ci95"] = wilson_interval(hits, row["support"])
    groups = sorted(set(VI_TIER2_GROUPS.values()))
    coarse = compute_metrics(group_labels(truth), group_labels(prediction), groups)
    keep = ("accuracy", "macro_f1", "weighted_f1", "per_class", "confusion_matrix")
    return {
        "rows": len(truth),
        "accuracy": fine["accuracy"],
        "macro_f1": fine["macro_f1"],
        "weighted_f1": fine["weighted_f1"],
        "per_class": fine["per_class"],
        "confusion_matrix": fine["confusion_matrix"],
        "group_level": {k: coarse[k] for k in keep} | {"groups": groups},
    }


def top_features(model, class_order: list[str], top: int = 15) -> pd.DataFrame:
    """Most indicative word n-grams per class (SVM: weights, NB: log-prob above the class mean)."""
    rows = []
    if "features" in model.named_steps:  # SVM
        word = dict(model.named_steps["features"].transformer_list)["word_tfidf"]
        names = np.asarray(word.get_feature_names_out())
        clf = model.named_steps["classifier"]
        weights = clf.coef_[:, : len(names)]
    else:  # NB
        names = np.asarray(model.named_steps["tfidf"].get_feature_names_out())
        clf = model.named_steps["classifier"]
        log_prob = clf.feature_log_prob_
        weights = log_prob - log_prob.mean(axis=0, keepdims=True)
    classes = list(clf.classes_)
    for label in class_order:
        if label not in classes:
            continue
        w = weights[classes.index(label)]
        for rank, idx in enumerate(np.argsort(-w)[:top], start=1):
            rows.append({"class": label, "rank": rank, "feature": names[idx], "weight": float(w[idx])})
    return pd.DataFrame(rows)
