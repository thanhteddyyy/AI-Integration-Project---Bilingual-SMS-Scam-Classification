from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from ..io_utils import ensure_dir, write_json
from .adapters import load_all_sources
from .clean import clean_text, stable_hash, text_quality_flags
from .dedup import assign_duplicate_groups
from .split import assert_no_group_leakage, assign_splits


MASTER_COLUMNS = [
    "sample_id",
    "source_dataset",
    "source_record_id",
    "text_raw",
    "text_clean",
    "language",
    "label_original",
    "label_level_1",
    "scam_type",
    "group_id",
    "split",
    "exclusion_reason",
    "exact_duplicate_rank",
    "exact_duplicate_count",
    "group_size",
    "label_conflict",
    "has_url",
    "has_email",
    "has_phone",
    "has_replacement_character",
    "metadata_json",
]


def prepare_data(config: dict) -> tuple[pd.DataFrame, dict]:
    frame = load_all_sources(config)
    frame["text_raw"] = frame["text_raw"].fillna("").astype(str)
    frame["text_clean"] = frame["text_raw"].map(clean_text)
    frame["sample_id"] = frame.apply(
        lambda row: "sample_"
        + stable_hash(f"{row['source_dataset']}|{row['source_record_id']}|{row['text_clean']}"),
        axis=1,
    )
    quality = frame["text_clean"].map(text_quality_flags).apply(pd.Series)
    frame = pd.concat([frame, quality], axis=1)
    frame, dedup_report = assign_duplicate_groups(frame, config)
    frame = assign_splits(frame, config)
    assert_no_group_leakage(frame)

    processed_dir = ensure_dir(config["paths"]["processed_dir"])
    reports_dir = ensure_dir(config["paths"]["reports_dir"])
    frame[MASTER_COLUMNS].to_csv(
        processed_dir / "master_manifest.csv", index=False, encoding="utf-8"
    )
    active = frame[frame["split"].isin(["train", "validation", "test", "external_test"])]
    active[MASTER_COLUMNS].to_csv(
        processed_dir / "modeling_data.csv", index=False, encoding="utf-8"
    )
    split_summary = (
        frame.groupby(["split", "source_dataset", "label_level_1"], dropna=False)
        .size()
        .rename("rows")
        .reset_index()
    )
    split_summary.to_csv(processed_dir / "split_summary.csv", index=False)

    report = build_quality_report(frame, dedup_report, config)
    write_json(report, reports_dir / "data_quality_report.json")
    exclusions = (
        frame.loc[frame["split"].eq("excluded"), "exclusion_reason"]
        .value_counts(dropna=False)
        .rename_axis("exclusion_reason")
        .reset_index(name="rows")
    )
    exclusions.to_csv(reports_dir / "exclusion_summary.csv", index=False)
    conflicts = frame[frame["label_conflict"]].copy()
    conflicts[
        [
            "group_id",
            "source_dataset",
            "source_record_id",
            "text_raw",
            "label_original",
            "label_level_1",
            "split",
            "exclusion_reason",
        ]
    ].to_csv(reports_dir / "label_conflicts.csv", index=False)

    mapping_source = Path(config["_project_root"]) / "configs" / "label_mapping.csv"
    if mapping_source.exists():
        shutil.copy2(mapping_source, reports_dir / "label_mapping_used.csv")
    return frame, report


def build_quality_report(frame: pd.DataFrame, dedup_report: dict, config: dict) -> dict:
    active_splits = ["train", "validation", "test", "external_test"]
    return {
        "scope": {
            "level": "level_1",
            "language": "en",
            "imc_language_filter": config["data"]["imc_language"],
            "class_order": config["data"]["class_order"],
            "external_dataset": config["data"]["external_dataset"],
        },
        "row_counts": {
            "all_loaded": len(frame),
            "active_modeling": int(frame["split"].isin(active_splits).sum()),
            "excluded": int(frame["split"].eq("excluded").sum()),
        },
        "source_counts": frame["source_dataset"].value_counts().to_dict(),
        "raw_label_counts_by_source": {
            source: group["label_original"].fillna("<NA>").value_counts().to_dict()
            for source, group in frame.groupby("source_dataset")
        },
        "split_label_counts": {
            split: group["label_level_1"].fillna("<NA>").value_counts().to_dict()
            for split, group in frame.groupby("split")
        },
        "split_source_counts": {
            split: group["source_dataset"].value_counts().to_dict()
            for split, group in frame.groupby("split")
        },
        "quality_flags": {
            column: int(frame[column].sum())
            for column in [
                "has_url",
                "has_email",
                "has_phone",
                "has_replacement_character",
            ]
        },
        "exclusion_counts": frame.loc[
            frame["split"].eq("excluded"), "exclusion_reason"
        ].value_counts().to_dict(),
        "deduplication": dedup_report,
        "leakage_check": "passed",
    }


def load_modeling_data(config: dict) -> pd.DataFrame:
    path = Path(config["paths"]["processed_dir"]) / "modeling_data.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Prepared data not found at {path}. Run the prepare command first."
        )
    return pd.read_csv(path, dtype={"text_clean": "string", "label_level_1": "string"})

