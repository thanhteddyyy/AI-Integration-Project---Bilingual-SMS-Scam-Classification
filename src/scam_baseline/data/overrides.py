"""Manual label corrections applied while loading (``data.label_overrides`` in the config).

Override CSV columns: ``source_record_id`` (e.g. ``imc25:1234``), ``text`` (the cleaned text that was
reviewed – used as a safety check), ``review_label`` (legitimate / spam / scam / drop) and optional
``review_scam_type``. The new label is also given to every other row with the same text (strict
duplicate key), so an exact copy elsewhere in the data cannot keep the old label and create a
label conflict. ``drop`` rows (and their copies) are removed.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .clean import clean_text, strict_duplicate_key

VALID = {"legitimate", "spam", "scam", "drop"}


def apply_label_overrides(frame: pd.DataFrame, paths: list[str | Path], project_root: str | Path) -> tuple[pd.DataFrame, dict]:
    result = frame.copy()
    keys = result["text_raw"].fillna("").map(lambda t: strict_duplicate_key(clean_text(t)))
    by_record = dict(zip(result["source_record_id"], result.index))
    new_label: dict[str, str] = {}
    new_type: dict[str, str] = {}
    report = {"override_rows": 0, "rows_relabelled": 0, "rows_dropped": 0, "files": []}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(project_root) / path
        table = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        report["files"].append(path.name)
        for _, row in table.iterrows():
            label = row["review_label"].strip()
            if label not in VALID:
                raise ValueError(f"{path.name}: invalid review_label {label!r} for {row['source_record_id']}")
            index = by_record.get(row["source_record_id"])
            if index is None:
                raise ValueError(f"{path.name}: source_record_id not found: {row['source_record_id']}")
            if "text" in table.columns and row["text"]:
                if strict_duplicate_key(row["text"]) != keys[index]:
                    raise ValueError(
                        f"{path.name}: text of {row['source_record_id']} changed since review – re-review it"
                    )
            key = keys[index]
            if new_label.get(key, label) != label:
                raise ValueError(f"{path.name}: identical text given two labels ({row['source_record_id']})")
            new_label[key] = label
            new_type[key] = row.get("review_scam_type", "") or ""
            report["override_rows"] += 1
    if not new_label:
        return result, report
    target = keys.map(new_label)  # NaN where no override applies
    hit = target.notna()
    drop = hit & target.eq("drop")
    relabel = hit & ~drop & result["label_level_1"].astype("string").ne(target)
    report["rows_relabelled"] = int(relabel.sum())
    report["rows_dropped"] = int(drop.sum())

    keep_hit = hit & ~drop
    result.loc[keep_hit, "label_level_1"] = target[keep_hit]
    wanted_type = keys.map(new_type).fillna("")
    to_scam = keep_hit & target.eq("scam") & wanted_type.ne("")
    result.loc[to_scam, "scam_type"] = wanted_type[to_scam]
    result.loc[keep_hit & target.ne("scam"), "scam_type"] = "unknown"
    return result[~drop].reset_index(drop=True), report
