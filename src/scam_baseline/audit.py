from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data.adapters import load_all_sources
from .data.clean import clean_text, strict_duplicate_key, template_duplicate_key
from .io_utils import ensure_dir, write_json


def audit_sources(config: dict) -> dict:
    frame = load_all_sources(config)
    frame["text_clean"] = frame["text_raw"].fillna("").map(clean_text)
    frame["strict_key"] = frame["text_clean"].map(strict_duplicate_key)
    frame["template_key"] = frame["text_clean"].map(template_duplicate_key)
    source_reports = {}
    key_sets = {}
    for source, group in frame.groupby("source_dataset"):
        key_sets[source] = set(group["strict_key"])
        source_reports[source] = {
            "rows": len(group),
            "labels_original": group["label_original"].fillna("<NA>").value_counts().to_dict(),
            "labels_mapped": group["label_level_1"].fillna("<NA>").value_counts().to_dict(),
            "empty_clean_text": int(group["text_clean"].eq("").sum()),
            "replacement_character_rows": int(
                group["text_clean"].str.contains("\ufffd", regex=False).sum()
            ),
            "strict_duplicate_rows": int(group["strict_key"].duplicated(keep=False).sum()),
            "template_duplicate_rows": int(
                group["template_key"].duplicated(keep=False).sum()
            ),
        }
    overlap_rows = []
    sources = sorted(key_sets)
    for index, left in enumerate(sources):
        for right in sources[index + 1 :]:
            overlap_rows.append(
                {
                    "left_source": left,
                    "right_source": right,
                    "strict_normalized_overlap": len(key_sets[left] & key_sets[right]),
                }
            )
    reports_dir = ensure_dir(config["paths"]["reports_dir"])
    pd.DataFrame(overlap_rows).to_csv(
        reports_dir / "cross_dataset_overlap_audit.csv", index=False
    )
    report = {
        "sources": source_reports,
        "cross_dataset_overlap": overlap_rows,
        "note": "IMC25 counts reflect the configured English-only filter.",
    }
    write_json(report, reports_dir / "source_audit.json")
    return report

