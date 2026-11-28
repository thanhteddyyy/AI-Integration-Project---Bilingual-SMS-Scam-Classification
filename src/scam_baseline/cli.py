from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import audit_sources
from .config import load_config
from .data.clean import clean_text
from .data.pipeline import load_modeling_data, prepare_data
from .io_utils import set_global_seed
from .models.charcnn import predict_charcnn, train_charcnn
from .models.classical import predict_classical, train_classical_model
from .reporting import write_model_comparison


MODEL_ALIASES = {
    "nb": "naive_bayes",
    "naive_bayes": "naive_bayes",
    "svm": "svm",
    "charcnn": "charcnn",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scam-baseline",
        description="English Level-1 baseline for bilingual SMS scam detection",
    )
    parser.add_argument(
        "--config",
        default="configs/english.yaml",
        help="Path to YAML config (default: configs/english.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("audit", help="Audit schemas, labels, duplicates, and overlap")
    subparsers.add_parser("prepare", help="Build the traceable master table and splits")

    train_parser = subparsers.add_parser("train", help="Train one or more baselines")
    train_parser.add_argument(
        "--models",
        nargs="+",
        default=["nb", "svm", "charcnn"],
        choices=["nb", "naive_bayes", "svm", "charcnn"],
    )
    train_parser.add_argument(
        "--prepare-if-missing",
        action="store_true",
        help="Prepare data automatically if modeling_data.csv is absent",
    )

    run_parser = subparsers.add_parser("run-all", help="Audit, prepare, and train baselines")
    run_parser.add_argument(
        "--models",
        nargs="+",
        default=["nb", "svm", "charcnn"],
        choices=["nb", "naive_bayes", "svm", "charcnn"],
    )

    predict_parser = subparsers.add_parser("predict", help="Predict one SMS with a saved model")
    predict_parser.add_argument("--model", choices=["nb", "naive_bayes", "svm", "charcnn"], required=True)
    predict_parser.add_argument("--text", required=True)
    predict_parser.add_argument("--model-path", default=None)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    set_global_seed(int(config["seed"]))

    if args.command == "audit":
        report = audit_sources(config)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == "prepare":
        _, report = prepare_data(config)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == "train":
        try:
            frame = load_modeling_data(config)
        except FileNotFoundError:
            if not args.prepare_if_missing:
                raise
            frame, _ = prepare_data(config)
            frame = frame[frame["split"].isin(["train", "validation", "test", "external_test"])]
        metrics = _train_models(frame, config, args.models)
        comparison = write_model_comparison(metrics, config)
        print(comparison.to_string(index=False))
        return
    if args.command == "run-all":
        audit_sources(config)
        frame, _ = prepare_data(config)
        frame = frame[frame["split"].isin(["train", "validation", "test", "external_test"])]
        metrics = _train_models(frame, config, args.models)
        comparison = write_model_comparison(metrics, config)
        print(comparison.to_string(index=False))
        return
    if args.command == "predict":
        model_name = MODEL_ALIASES[args.model]
        if args.model_path:
            model_path = Path(args.model_path)
        elif model_name == "charcnn":
            model_path = Path(config["paths"]["artifacts_dir"]) / "charcnn" / "model.pt"
        else:
            model_path = Path(config["paths"]["artifacts_dir"]) / model_name / "model.joblib"
        text = clean_text(args.text)
        if model_name == "charcnn":
            prediction = predict_charcnn(model_path, [text])[0]
        else:
            prediction = predict_classical(model_path, [text])[0]
        print(json.dumps({"text": text, "prediction": prediction}, ensure_ascii=False))


def _train_models(frame, config, requested_models: list[str]) -> dict:
    normalized = []
    for model in requested_models:
        canonical = MODEL_ALIASES[model]
        if canonical not in normalized:
            normalized.append(canonical)
    results = {}
    for model_name in normalized:
        print(f"Training {model_name}...")
        if model_name == "charcnn":
            results[model_name] = train_charcnn(frame, config)
        else:
            results[model_name] = train_classical_model(frame, config, model_name)
    return results


if __name__ == "__main__":
    main()

