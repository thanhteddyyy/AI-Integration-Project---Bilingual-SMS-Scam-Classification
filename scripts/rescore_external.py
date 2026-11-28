"""Re-score the external_test split with already-trained classical models (no retraining).

Use after an external dataset changed (e.g. new crawl rows) while train / validation / test did
not: verify that first (compare modeling_data.csv before/after). The script refuses to run if the
saved model's training_rows differs from the current train split size.

Overwrites in artifacts/<config>/<model>/: metrics_external_test.json, predictions_external_test.csv,
confusion_matrix_external_test.png, and the external_test entry of metrics_all_splits.json;
rewrites reports/<config>/model_comparison.csv.

Usage: PYTHONPATH=src python scripts/rescore_external.py --config configs/vietnamese_balanced.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.config import load_config  # noqa: E402
from scam_baseline.data.pipeline import load_modeling_data  # noqa: E402
from scam_baseline.evaluation import evaluate_predictions  # noqa: E402
from scam_baseline.io_utils import write_json  # noqa: E402
from scam_baseline.models.classical import predict_classical  # noqa: E402
from scam_baseline.reporting import write_model_comparison  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--models", nargs="+", default=["svm", "naive_bayes"])
    args = parser.parse_args()

    config = load_config(args.config)
    frame = load_modeling_data(config)
    external = frame[frame["split"].eq("external_test")]
    n_train = int(frame["split"].eq("train").sum())
    artifacts = Path(config["paths"]["artifacts_dir"])

    all_metrics = {}
    for model_name in args.models:
        model_dir = artifacts / model_name
        meta = json.loads((model_dir / "training_metadata.json").read_text(encoding="utf-8"))
        if int(meta["training_rows"]) != n_train:
            raise SystemExit(f"{model_dir}: trained on {meta['training_rows']} rows but train split now has "
                             f"{n_train} -> data changed, retrain instead of re-scoring")
        predictions = predict_classical(model_dir / "model.joblib", external["text_clean"].astype(str).tolist())
        metrics = evaluate_predictions(external, predictions, model_name=model_name, split_name="external_test",
                                       class_order=config["data"]["class_order"], output_dir=model_dir)
        all_path = model_dir / "metrics_all_splits.json"
        saved = json.loads(all_path.read_text(encoding="utf-8"))
        saved["external_test"] = metrics
        write_json(saved, all_path)
        all_metrics[model_name] = saved
        for source, m in metrics["by_source"].items():
            print(f"{model_name:12s} {source:16s} scam {m.get('scam_support')} recall {m['scam_recall']:.3f} "
                  f"ci {m.get('scam_recall_ci95')} fpr {m.get('scam_fpr')}")
    write_model_comparison(all_metrics, config)


if __name__ == "__main__":
    main()
