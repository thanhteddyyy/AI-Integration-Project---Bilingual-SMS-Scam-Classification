"""Score the FULL Vietnamese crawl set with already-trained models (no retraining, no split).

Why a separate script: data/raw/vi_crawl_external_full.csv keeps crawl rows that share a template
family with Tuan's data (tuan_family=True). Declaring it as a pipeline external dataset would make
the pipeline drop Tuan train/test rows of those families (split.external_overlap_policy), i.e.
change the training data. Here we only predict and count.

Report (decision 2026-11-26):
  * main number  = pipeline external 'vi_crawl' (clean: SMS, new template families only)
  * extra number = this script: scam recall on real scams split by
        family  : new (not in Tuan)  vs  known (same family as a Tuan message -> template memory)
        channel : sms                vs  chat (zalo / messenger / other apps)
    with Wilson 95% intervals, plus false alarms on the few legitimate crawl rows.

Usage:
  python scripts/score_vi_crawl_full.py                      # every VI-capable model found
  python scripts/score_vi_crawl_full.py --models artifacts/vietnamese_balanced/svm/model.joblib
Outputs: reports/vi_crawl_full/{summary.csv, predictions.csv}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.data.clean import clean_text  # noqa: E402
from scam_baseline.evaluation import wilson_interval  # noqa: E402
from scam_baseline.models.charcnn import predict_charcnn  # noqa: E402  (torch imported lazily)
from scam_baseline.models.classical import predict_classical  # noqa: E402

DEFAULT_MODEL_DIRS = ["vietnamese_balanced", "vietnamese_3class", "bilingual"]


def default_models() -> list[Path]:
    found = []
    for name in DEFAULT_MODEL_DIRS:
        for model, file in (("svm", "model.joblib"), ("naive_bayes", "model.joblib"), ("charcnn", "model.pt")):
            path = ROOT / "artifacts" / name / model / file
            if path.exists():
                found.append(path)
    return found


def predict(path: Path, texts: list[str]) -> list[str]:
    return predict_charcnn(path, texts) if path.suffix == ".pt" else predict_classical(path, texts)


def subsets(df: pd.DataFrame) -> dict[str, pd.Series]:
    sms = df.channel.eq("sms")
    known = df.tuan_family.astype(str).str.lower().eq("true")
    return {
        "all": pd.Series(True, index=df.index),
        "sms": sms,
        "chat": ~sms,
        "new_family": ~known,
        "known_family": known,
        "sms_new_family": sms & ~known,   # = pipeline external 'vi_crawl' (clean set)
        "sms_known_family": sms & known,
        "chat_new_family": ~sms & ~known,
        "chat_known_family": ~sms & known,
    }


def score(df: pd.DataFrame, pred: pd.Series, model_id: str) -> list[dict]:
    rows = []
    for name, mask in subsets(df).items():
        part = df[mask]
        scam = part.label_3class.eq("scam")
        caught = int((pred[mask][scam] == "scam").sum())
        legit = ~scam
        false_alarm = int((pred[mask][legit] == "scam").sum())
        ci = wilson_interval(caught, int(scam.sum())) if scam.any() else None
        rows.append({
            "model": model_id, "subset": name,
            "n_scam": int(scam.sum()), "scam_caught": caught,
            "scam_recall": round(caught / scam.sum(), 3) if scam.any() else None,
            "recall_ci95": f"{ci[0]:.2f}-{ci[1]:.2f}" if ci else "",
            "n_not_scam": int(legit.sum()), "flagged_scam": false_alarm,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "vi_crawl_external_full.csv")
    parser.add_argument("--models", nargs="*", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "vi_crawl_full")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    texts = df.message.map(clean_text).tolist()
    models = args.models or default_models()
    if not models:
        raise SystemExit("no trained model (model.joblib / model.pt) found under artifacts/")

    summary, preds = [], df[["crawl_id", "channel", "tuan_family", "label_3class", "scam_type", "message"]].copy()
    for path in models:
        model_id = f"{path.parent.parent.name}/{path.parent.name}"
        pred = pd.Series(predict(path, texts), index=df.index)
        preds[model_id] = pred
        summary += score(df, pred, model_id)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(summary)
    table.to_csv(args.out_dir / "summary.csv", index=False, encoding="utf-8-sig")
    preds.to_csv(args.out_dir / "predictions.csv", index=False, encoding="utf-8-sig")
    print(table.to_string(index=False))
    print(f"-> {args.out_dir}")


if __name__ == "__main__":
    main()
