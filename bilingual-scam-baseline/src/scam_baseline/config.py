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
        "sms_phishing",
        "smishx",
        "imc25",
        "processed_dir",
        "reports_dir",
        "artifacts_dir",
    }
    missing = required_paths - set(config.get("paths", {}))
    if missing:
        raise ValueError(f"Missing path settings: {sorted(missing)}")

    split = config.get("split", {})
    fractions = [
        float(split.get("train_fraction", 0)),
        float(split.get("validation_fraction", 0)),
        float(split.get("test_fraction", 0)),
    ]
    if any(value <= 0 for value in fractions):
        raise ValueError("All internal split fractions must be positive")
    if abs(sum(fractions) - 1.0) > 1e-8:
        raise ValueError("train/validation/test fractions must sum to 1.0")

    class_order = config.get("data", {}).get("class_order")
    if class_order != ["legitimate", "spam", "scam"]:
        raise ValueError(
            "This Level-1 baseline expects class_order: [legitimate, spam, scam]"
        )

