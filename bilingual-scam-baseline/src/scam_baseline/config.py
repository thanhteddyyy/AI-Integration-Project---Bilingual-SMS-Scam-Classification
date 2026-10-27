from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Config must contain a YAML mapping: {path}")

    config = deepcopy(config)
    project_root = path.parent.parent
    config["_config_path"] = str(path)
    config["_project_root"] = str(project_root)
    for key, value in config.get("paths", {}).items():
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        config["paths"][key] = str(candidate.resolve())
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    required_paths = {
        "processed_dir",
        "reports_dir",
        "artifacts_dir",
    }
    missing = required_paths - set(config.get("paths", {}))
    if missing:
        raise ValueError(f"Missing required directory settings: {sorted(missing)}")

    has_default_sources = any(k in config.get("paths", {}) for k in ("sms_phishing", "smishx", "imc25"))
    has_extra_sources = bool(config.get("data", {}).get("extra_datasets"))
    if not (has_default_sources or has_extra_sources):
        raise ValueError("Config must provide either default datasets in paths or extra_datasets in data.")

    split = config.get("split", {})
    train_frac = float(split.get("train_fraction", 0))
    val_frac = float(split.get("validation_fraction", 0))
    test_frac = float(split.get("test_fraction", 0))

    if train_frac <= 0 or val_frac <= 0 or test_frac < 0:
        raise ValueError(
            "train_fraction and validation_fraction must be positive; "
            "test_fraction must be non-negative."
        )
    total_frac = train_frac + val_frac + test_frac
    if abs(total_frac - 1.0) > 1e-6:
        raise ValueError(f"Split fractions must sum to 1.0 (got {total_frac:.4f})")

    class_order = config.get("data", {}).get("class_order")
    if not class_order or not isinstance(class_order, list) or len(class_order) < 2:
        raise ValueError("data.class_order must be a list containing at least 2 distinct classes.")
    if len(class_order) != len(set(class_order)):
        raise ValueError("data.class_order cannot contain duplicate class names.")
