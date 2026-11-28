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
                    "mcc": metrics.get("mcc"),
                    "scam_support": metrics.get("scam_support"),
                    "scam_precision": metrics["scam_precision"],
                    "scam_recall": metrics["scam_recall"],
                    "scam_f1": metrics.get("scam_f1"),
                    "scam_f2": metrics.get("scam_f2"),
                    "scam_fpr": metrics.get("scam_fpr"),
                }
            )
    eval_cfg = config.get("evaluation", {})
    selection_metric = eval_cfg.get("selection_metric", "scam_f2")
    tie_breaker = eval_cfg.get("tie_breaker", "macro_f1")
    comparison = pd.DataFrame(rows).sort_values(
        ["split", selection_metric], ascending=[True, False]
    )
    reports_dir = ensure_dir(config["paths"]["reports_dir"])
    comparison.to_csv(reports_dir / "model_comparison.csv", index=False)
    by_source_rows = [
        {
            "model": model_name,
            "split": split_name,
            "source_dataset": source,
            "rows": int(sum(m["per_class"][c]["support"] for c in m["per_class"])),
            "scam_support": m.get("scam_support"),
            "scam_recall": m["scam_recall"],
            "scam_recall_ci95": m.get("scam_recall_ci95"),
            "scam_fpr": m.get("scam_fpr"),
            "scam_fpr_ci95": m.get("scam_fpr_ci95"),
            "scam_f2": m.get("scam_f2"),
            "macro_f1": m["macro_f1"],
        }
        for model_name, split_metrics in all_metrics.items()
        for split_name, metrics in split_metrics.items()
        for source, m in metrics.get("by_source", {}).items()
    ]
    if by_source_rows:
        pd.DataFrame(by_source_rows).to_csv(reports_dir / "model_comparison_by_source.csv", index=False)
    validation = comparison[comparison["split"].eq("validation")]
    if validation.empty:
        best_model = None
    else:
        best_row = validation.sort_values(
            [selection_metric, tie_breaker], ascending=False
        ).iloc[0]
        best_model = {
            "model": best_row["model"],
            "selection_split": "validation",
            "selection_metric": selection_metric,
            f"validation_{selection_metric}": float(best_row[selection_metric]),
            "tie_breaker": tie_breaker,
            f"validation_{tie_breaker}": float(best_row[tie_breaker]),
        }
    write_json(
        {"best_model": best_model, "models_compared": sorted(all_metrics)},
        reports_dir / "best_model.json",
    )
    return comparison

