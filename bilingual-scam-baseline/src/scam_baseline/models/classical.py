from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from ..evaluation import evaluate_predictions
from ..io_utils import ensure_dir, write_json


def build_naive_bayes(config: dict) -> Pipeline:
    model_cfg = config["models"]["naive_bayes"]
    vectorizer = TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents=None,
        ngram_range=tuple(model_cfg["word_ngram_range"]),
        min_df=model_cfg["min_df"],
        max_df=model_cfg["max_df"],
        max_features=model_cfg["max_features"],
        sublinear_tf=bool(model_cfg.get("sublinear_tf", True)),
        dtype=np.float32,
    )
    return Pipeline(
        [
            ("tfidf", vectorizer),
            ("classifier", MultinomialNB(alpha=float(model_cfg["alpha"]))),
        ]
    )


def build_svm(config: dict) -> Pipeline:
    model_cfg = config["models"]["svm"]
    features = FeatureUnion(
        [
            (
                "word_tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    lowercase=True,
                    strip_accents=None,
                    ngram_range=tuple(model_cfg["word_ngram_range"]),
                    min_df=model_cfg["min_df"],
                    max_df=model_cfg["max_df"],
                    max_features=model_cfg["word_max_features"],
                    sublinear_tf=bool(model_cfg.get("sublinear_tf", True)),
                    dtype=np.float32,
                ),
            ),
            (
                "char_tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    strip_accents=None,
                    ngram_range=tuple(model_cfg["char_ngram_range"]),
                    min_df=model_cfg["min_df"],
                    max_df=model_cfg["max_df"],
                    max_features=model_cfg["char_max_features"],
                    sublinear_tf=bool(model_cfg.get("sublinear_tf", True)),
                    dtype=np.float32,
                ),
            ),
        ]
    )
    class_weight = model_cfg.get("class_weight")
    if class_weight == "none":
        class_weight = None
    classifier = LinearSVC(
        C=float(model_cfg["C"]),
        class_weight=class_weight,
        random_state=int(config["seed"]),
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def train_classical_model(
    frame: pd.DataFrame, config: dict, model_name: str
) -> dict[str, dict]:
    if model_name not in {"naive_bayes", "svm"}:
        raise ValueError(f"Unsupported classical model: {model_name}")
    model = build_naive_bayes(config) if model_name == "naive_bayes" else build_svm(config)
    train = frame[frame["split"].eq("train")]
    model.fit(train["text_clean"].astype(str), train["label_level_1"].astype(str))

    artifact_dir = ensure_dir(Path(config["paths"]["artifacts_dir"]) / model_name)
    joblib.dump(model, artifact_dir / "model.joblib")
    write_json(
        {
            "model": model_name,
            "training_rows": len(train),
            "classes": list(model.classes_),
            "config_path": config["_config_path"],
        },
        artifact_dir / "training_metadata.json",
    )
    metrics: dict[str, dict] = {}
    for split_name in ["validation", "test", "external_test"]:
        subset = frame[frame["split"].eq(split_name)]
        if subset.empty:
            continue
        predictions = model.predict(subset["text_clean"].astype(str))
        metrics[split_name] = evaluate_predictions(
            subset,
            predictions,
            model_name=model_name,
            split_name=split_name,
            class_order=config["data"]["class_order"],
            output_dir=artifact_dir,
        )
    write_json(metrics, artifact_dir / "metrics_all_splits.json")
    return metrics


def predict_classical(model_path: str | Path, texts: list[str]) -> list[str]:
    model = joblib.load(model_path)
    return [str(value) for value in model.predict(texts)]
