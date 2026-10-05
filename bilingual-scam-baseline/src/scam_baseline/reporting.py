from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io_utils import ensure_dir, write_json


def write_model_comparison(
    all_metrics: dict[str, dict[str, dict]], config: dict
) -> pd.DataFrame:
    rows = []
    for model_name, split_metrics in all_metrics.items():
        for split_name, metrics in split_metrics.items():
            rows.append(
                {
                    "model": model_name,
                    "split": split_name,
                    "rows": metrics["rows"],
                    "accuracy": metrics["accuracy"],
                    "macro_f1": metrics["macro_f1"],
                    "weighted_f1": metrics["weighted_f1"],
                    "scam_precision": metrics["scam_precision"],
                    "scam_recall": metrics["scam_recall"],
                }
            )
    comparison = pd.DataFrame(rows).sort_values(["split", "macro_f1"], ascending=[True, False])
    reports_dir = ensure_dir(config["paths"]["reports_dir"])
    comparison.to_csv(reports_dir / "model_comparison.csv", index=False)
    validation = comparison[comparison["split"].eq("validation")]
    if validation.empty:
        best_model = None
    else:
        best_row = validation.sort_values(
            ["macro_f1", "scam_recall"], ascending=False
        ).iloc[0]
        best_model = {
            "model": best_row["model"],
            "selection_split": "validation",
            "selection_metric": "macro_f1",
            "validation_macro_f1": float(best_row["macro_f1"]),
            "tie_breaker": "scam_recall",
        }
    write_json(
        {"best_model": best_model, "models_compared": sorted(all_metrics)},
        reports_dir / "best_model.json",
    )
    return comparison

