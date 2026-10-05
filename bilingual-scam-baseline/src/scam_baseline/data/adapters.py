from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


LEVEL1_MAP = {
    "ham": "legitimate",
    "legitimate": "legitimate",
    "spam": "spam",
    "smishing": "scam",
}

IMC_SCAM_TYPE_MAP = {
    "banking": "banking_finance",
    "delivery": "delivery_logistics",
    "government": "government_services",
    "telecom": "telecom_account",
    "wrong number": "social_impersonation",
    "hey mum/dad": "social_impersonation",
    "others": "other_scam",
}


def _metadata_json(row: pd.Series, columns: list[str]) -> str:
    data = {
        column: None if pd.isna(row.get(column)) else str(row.get(column))
        for column in columns
    }
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _base_frame(
    raw: pd.DataFrame,
    *,
    source_dataset: str,
    text_column: str,
    label_column: str,
    language: str,
    metadata_columns: list[str],
) -> pd.DataFrame:
    output = pd.DataFrame(index=raw.index)
    output["source_dataset"] = source_dataset
    output["source_record_id"] = [f"{source_dataset}:{idx}" for idx in raw.index]
    output["text_raw"] = raw[text_column].astype("string")
    output["language"] = language
    output["label_original"] = raw[label_column].astype("string")
    output["metadata_json"] = raw.apply(
        _metadata_json, axis=1, columns=metadata_columns
    )
    return output.reset_index(drop=True)


def load_sms_phishing(path: str | Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype="string", keep_default_na=True)
    required = {"LABEL", "TEXT", "URL", "EMAIL", "PHONE"}
    _require_columns(raw, required, "SMS Phishing")
    output = _base_frame(
        raw,
        source_dataset="sms_phishing",
        text_column="TEXT",
        label_column="LABEL",
        language="en",
        metadata_columns=["URL", "EMAIL", "PHONE"],
    )
    normalized = output["label_original"].str.strip().str.casefold()
    output["label_level_1"] = normalized.map(LEVEL1_MAP)
    output["scam_type"] = "unknown"
    return output


def load_smishx(path: str | Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype="string", keep_default_na=True)
    required = {"SMS", "label", "if_URL", "if_phone", "if_email"}
    _require_columns(raw, required, "SmishX")
    output = _base_frame(
        raw,
        source_dataset="smishx",
        text_column="SMS",
        label_column="label",
        language="en",
        metadata_columns=["if_URL", "if_phone", "if_email"],
    )
    normalized = output["label_original"].str.strip().str.casefold()
    output["label_level_1"] = normalized.map(LEVEL1_MAP)
    output["scam_type"] = "unknown"
    return output


def load_imc25(path: str | Path, language_filter: str = "English") -> pd.DataFrame:
    raw = pd.read_csv(path, dtype="string", keep_default_na=True, low_memory=False)
    required = {
        "text",
        "language",
        "scam_type",
        "time",
        "sender_id",
        "telephone_number_type",
        "original_network_name",
        "original_network_country",
        "url_shortener",
        "named_entity",
        "lure_principles",
    }
    _require_columns(raw, required, "IMC25")
    selected = raw[
        raw["language"].str.strip().str.casefold().eq(language_filter.casefold())
    ].copy()
    selected = selected.reset_index().rename(columns={"index": "_source_index"})
    output = pd.DataFrame(index=selected.index)
    output["source_dataset"] = "imc25"
    output["source_record_id"] = selected["_source_index"].map(
        lambda idx: f"imc25:{idx}"
    )
    output["text_raw"] = selected["text"].astype("string")
    output["language"] = "en"
    output["label_original"] = selected["scam_type"].astype("string")
    original = output["label_original"].str.strip().str.casefold()
    output["label_level_1"] = original.where(original.eq("spam"), "scam")
    output.loc[original.isna(), "label_level_1"] = pd.NA
    output["scam_type"] = original.map(IMC_SCAM_TYPE_MAP).fillna("unknown")
    metadata_columns = [
        "time",
        "sender_id",
        "telephone_number_type",
        "original_network_name",
        "original_network_country",
        "url_shortener",
        "named_entity",
        "lure_principles",
    ]
    output["metadata_json"] = selected.apply(
        _metadata_json, axis=1, columns=metadata_columns
    )
    return output.reset_index(drop=True)


def load_custom_dataset(spec: dict[str, Any], project_root: str | Path) -> pd.DataFrame:
    """Load a future Vietnamese or other CSV through a config mapping.

    Expected spec keys: name, path, text_column, label_column, language, and
    label_mapping. This route is intentionally inactive until extra_datasets is
    populated in the config.
    """

    required = {
        "name",
        "path",
        "text_column",
        "label_column",
        "language",
        "label_mapping",
    }
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Custom dataset spec missing keys: {sorted(missing)}")
    path = Path(spec["path"])
    if not path.is_absolute():
        path = Path(project_root) / path
    raw = pd.read_csv(path, dtype="string", keep_default_na=True)
    _require_columns(
        raw,
        {spec["text_column"], spec["label_column"]},
        str(spec["name"]),
    )
    output = _base_frame(
        raw,
        source_dataset=str(spec["name"]),
        text_column=str(spec["text_column"]),
        label_column=str(spec["label_column"]),
        language=str(spec["language"]),
        metadata_columns=list(spec.get("metadata_columns", [])),
    )
    mapping = {
        str(key).strip().casefold(): str(value)
        for key, value in spec["label_mapping"].items()
    }
    normalized = output["label_original"].str.strip().str.casefold()
    output["label_level_1"] = normalized.map(mapping)
    output["scam_type"] = "unknown"
    return output


def load_all_sources(config: dict[str, Any]) -> pd.DataFrame:
    paths = config["paths"]
    data_cfg = config["data"]
    frames = [
        load_sms_phishing(paths["sms_phishing"]),
        load_smishx(paths["smishx"]),
        load_imc25(paths["imc25"], language_filter=data_cfg["imc_language"]),
    ]
    for spec in data_cfg.get("extra_datasets", []):
        frames.append(load_custom_dataset(spec, config["_project_root"]))
    return pd.concat(frames, ignore_index=True)


def _require_columns(
    frame: pd.DataFrame, required: set[str], dataset_name: str
) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"{dataset_name} is missing required columns: {sorted(missing)}"
        )
