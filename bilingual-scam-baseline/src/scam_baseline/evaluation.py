from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
)

# F-beta for the positive (scam/risky) class. beta=2 weighs recall twice as much as precision:
# missing a scam costs the user more than a false alarm.
SCAM_F_BETA = 2.0


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for a proportion (e.g. scam recall on a small external set)."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [float(max(0.0, centre - half)), float(min(1.0, centre + half))]


def positive_label_for(class_order: list[str]) -> str:
    if "scam" in class_order:
        return "scam"
    if "risky" in class_order:
        return "risky"
    return class_order[-1]

from .io_utils import ensure_dir, write_json


def compute_metrics(
    y_true: Iterable[str], y_pred: Iterable[str], class_order: list[str]
) -> dict:
    truth = list(y_true)
    prediction = list(y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        prediction,
        labels=class_order,
        zero_division=0,
    )
    per_class = {
        label: {
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(class_order)
    }
    positive_label = positive_label_for(class_order)
    scam_f2 = fbeta_score(
        truth,
        prediction,
        beta=SCAM_F_BETA,
        labels=[positive_label],
        average=None,
        zero_division=0,
    )
    # MCC is undefined (sklearn returns 0) when only one class is present in truth and prediction.
    mcc = matthews_corrcoef(truth, prediction) if len(set(truth) | set(prediction)) > 1 else 0.0
    positives = [p for t, p in zip(truth, prediction) if t == positive_label]
    negatives = [p for t, p in zip(truth, prediction) if t != positive_label]
    false_alarms = sum(p == positive_label for p in negatives)
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, average="macro", zero_division=0)),
        "weighted_f1": float(
            f1_score(truth, prediction, average="weighted", zero_division=0)
        ),
        "mcc": float(mcc),
        "positive_label": positive_label,
        "scam_support": per_class.get(positive_label, {}).get("support", 0),
        "scam_precision": per_class.get(positive_label, {}).get("precision", 0.0),
        "scam_recall": per_class.get(positive_label, {}).get("recall", 0.0),
        "scam_f1": per_class.get(positive_label, {}).get("f1", 0.0),
        "scam_f2": float(scam_f2[0]),
        "scam_recall_ci95": wilson_interval(
            sum(p == positive_label for p in positives), len(positives)
        ),
        # share of non-scam messages flagged as scam (false alarm rate)
        "scam_fpr": float(false_alarms / len(negatives)) if negatives else 0.0,
        "scam_fpr_ci95": wilson_interval(false_alarms, len(negatives)),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(
            truth, prediction, labels=class_order
        ).tolist(),
        "classification_report": classification_report(
            truth,
            prediction,
            labels=class_order,
            output_dict=True,
            zero_division=0,
        ),
    }


def evaluate_predictions(
    frame: pd.DataFrame,
    predictions: Iterable[str],
    *,
    model_name: str,
    split_name: str,
    class_order: list[str],
    output_dir: str | Path,
) -> dict:
    output = ensure_dir(output_dir)
    result = frame.copy()
    result["prediction"] = list(predictions)
    result["is_correct"] = result["label_level_1"].eq(result["prediction"])
    metrics = compute_metrics(
        result["label_level_1"], result["prediction"], class_order
    )
    metrics["model"] = model_name
    metrics["split"] = split_name
    metrics["rows"] = len(result)
    metrics["by_language"] = {
        language: compute_metrics(
            group["label_level_1"], group["prediction"], class_order
        )
        for language, group in result.groupby("language")
    }
    # external_test mixes sources with different roles (e.g. vi_crawl = scam recall,
    # vie_sms_corpus = false alarms), so report each one separately.
    metrics["by_source"] = {
        source: compute_metrics(group["label_level_1"], group["prediction"], class_order)
        for source, group in result.groupby("source_dataset")
    }
    write_json(metrics, output / f"metrics_{split_name}.json")
    result[
        [
            "sample_id",
            "source_dataset",
            "source_record_id",
            "language",
            "text_clean",
            "label_level_1",
            "prediction",
            "is_correct",
            "group_id",
            "split",
        ]
    ].to_csv(output / f"predictions_{split_name}.csv", index=False)
    _save_confusion_matrix(
        np.asarray(metrics["confusion_matrix"]),
        class_order,
        output / f"confusion_matrix_{split_name}.png",
        title=f"{model_name}: {split_name}",
    )
    return metrics


def _save_confusion_matrix(
    matrix: np.ndarray, labels: list[str], path: Path, title: str
) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 5.4))
    image = axis.imshow(matrix, interpolation="nearest", cmap="Blues")
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    axis.set(
        xticks=np.arange(len(labels)),
        yticks=np.arange(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        ylabel="True label",
        xlabel="Predicted label",
        title=title,
    )
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
            )
    figure.tight_layout()
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)
