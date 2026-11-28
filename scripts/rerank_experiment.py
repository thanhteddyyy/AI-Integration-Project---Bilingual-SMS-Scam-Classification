"""Rerank experiment: fuse Linear SVM + CharCNN scam scores for tier 1 (see docs/rerank_experiment.md).

No model is retrained. For each setup:
  * SVM scam score  = Platt-scaled decision_function (logistic fit on VALIDATION)
  * CharCNN score   = softmax probability of 'scam'
  * fused = w * svm + (1 - w) * cnn ; scam if fused >= t, else SVM's best of {legitimate, spam}
  * grid w in 0..1 step .1, t in .05..0.95 step .01, chosen on VALIDATION:
      constraint  val scam FPR <= SVM-alone val scam FPR
      objective   val scam F2, ties -> lower FPR -> higher macro F1 -> larger w
  * fused model accepted only if its val F2 beats SVM alone
Reports test / external / VI real-scam full set for SVM, CharCNN, OR, AND, fused.

Usage: PYTHONPATH=src python scripts/rerank_experiment.py
Outputs: reports/rerank/{grid_<setup>.csv, results.csv, summary.md}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.config import load_config  # noqa: E402
from scam_baseline.data.clean import clean_text  # noqa: E402
from scam_baseline.data.pipeline import load_modeling_data  # noqa: E402
from scam_baseline.evaluation import compute_metrics  # noqa: E402
from scam_baseline.models.charcnn import predict_charcnn_proba  # noqa: E402

SETUPS = ["bilingual", "vietnamese_balanced", "english_balanced"]  # first = main setup
WEIGHTS = np.round(np.arange(0.0, 1.0001, 0.1), 1)
THRESHOLDS = np.round(np.arange(0.05, 0.9501, 0.01), 2)
OUT = ROOT / "reports" / "rerank"


class Scorer:
    """Scores and decision rules of one setup; the SVM calibration is fitted on validation."""

    def __init__(self, setup: str):
        self.setup = setup
        config = load_config(ROOT / "configs" / f"{setup}.yaml")
        self.class_order = config["data"]["class_order"]
        self.svm = joblib.load(ROOT / "artifacts" / setup / "svm" / "model.joblib")
        self.cnn_path = ROOT / "artifacts" / setup / "charcnn" / "model.pt"
        self.frame = load_modeling_data(config)
        self.svm_classes = list(self.svm.classes_)
        val = self.frame[self.frame.split.eq("validation")]
        d = self._svm_decision(val.text_clean.astype(str).tolist())
        self.platt = LogisticRegression().fit(d[:, [self.svm_classes.index("scam")]], val.label_level_1.eq("scam"))

    def _svm_decision(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.svm.decision_function(texts))

    def score(self, texts: list[str]) -> dict:
        d = self._svm_decision(texts)
        scam_col = self.svm_classes.index("scam")
        non_scam = [i for i, c in enumerate(self.svm_classes) if c != "scam"]
        fallback = np.array(self.svm_classes)[np.array(non_scam)[d[:, non_scam].argmax(axis=1)]]
        proba, cnn_classes = predict_charcnn_proba(self.cnn_path, texts, device_name="cpu")
        return {
            "svm_label": np.array(self.svm_classes)[d.argmax(axis=1)],
            "svm_score": self.platt.predict_proba(d[:, [scam_col]])[:, 1],
            "cnn_label": np.array(cnn_classes)[proba.argmax(axis=1)],
            "cnn_score": proba[:, cnn_classes.index("scam")],
            "fallback": fallback,
        }


def rules(s: dict, w: float | None = None, t: float | None = None) -> dict[str, np.ndarray]:
    out = {
        "SVM": s["svm_label"],
        "CharCNN": s["cnn_label"],
        "OR": np.where(s["cnn_label"] == "scam", "scam", s["svm_label"]),
        "AND": np.where((s["svm_label"] == "scam") & (s["cnn_label"] != "scam"), s["cnn_label"], s["svm_label"]),
    }
    if w is not None:
        out["Rerank"] = fused(s, w, t)
    return out


def fused(s: dict, w: float, t: float) -> np.ndarray:
    score = w * s["svm_score"] + (1 - w) * s["cnn_score"]
    return np.where(score >= t, "scam", s["fallback"])


def search(setup: str, y_val: pd.Series, s_val: dict, class_order: list[str]) -> tuple[pd.DataFrame, dict]:
    base = compute_metrics(y_val, s_val["svm_label"], class_order)
    rows = []
    for w in WEIGHTS:
        for t in THRESHOLDS:
            m = compute_metrics(y_val, fused(s_val, w, t), class_order)
            rows.append({"w": w, "t": t, "val_scam_f2": m["scam_f2"], "val_scam_fpr": m["scam_fpr"],
                         "val_scam_recall": m["scam_recall"], "val_macro_f1": m["macro_f1"]})
    grid = pd.DataFrame(rows)
    grid["feasible"] = grid.val_scam_fpr <= base["scam_fpr"] + 1e-12
    ok = grid[grid.feasible].sort_values(["val_scam_f2", "val_scam_fpr", "val_macro_f1", "w"],
                                         ascending=[False, True, False, False])
    best = ok.iloc[0].to_dict()
    best["svm_val_scam_f2"], best["svm_val_scam_fpr"] = base["scam_f2"], base["scam_fpr"]
    best["accepted"] = bool(best["val_scam_f2"] > base["scam_f2"] + 1e-12)
    grid.to_csv(OUT / f"grid_{setup}.csv", index=False)
    return grid, best


def evaluate(setup: str, scorer: Scorer, best: dict) -> list[dict]:
    rows = []
    f = scorer.frame
    parts = [("validation", f[f.split.eq("validation")]), ("test", f[f.split.eq("test")])]
    if setup == "bilingual":
        test = f[f.split.eq("test")]
        parts += [("test_vi", test[test.language.eq("vi")]), ("test_en", test[test.language.eq("en")])]
    ext = f[f.split.eq("external_test")]
    parts += [(f"ext_{src}", g) for src, g in ext.groupby("source_dataset")]
    full_path = ROOT / "data" / "raw" / "vi_crawl_external_full.csv"
    if setup != "english_balanced" and full_path.exists():
        full = pd.read_csv(full_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        full = full.assign(text_clean=full.message.map(clean_text), label_level_1=full.label_3class)
        sms, known = full.channel.eq("sms"), full.tuan_family.str.lower().eq("true")
        parts += [("vi_real_sms_new", full[sms & ~known]), ("vi_real_sms_known", full[sms & known]),
                  ("vi_real_chat", full[~sms])]
    for name, part in parts:
        if part.empty:
            continue
        s = scorer.score(part.text_clean.astype(str).tolist())
        y = part.label_level_1.astype(str)
        for rule, pred in rules(s, best["w"], best["t"]).items():
            m = compute_metrics(y, pred, scorer.class_order)
            n_scam = int(y.eq("scam").sum())
            rows.append({"setup": setup, "subset": name, "rule": rule, "rows": len(part), "n_scam": n_scam,
                         "scam_caught": int(((pred == "scam") & y.eq("scam").to_numpy()).sum()),
                         "scam_recall": m["scam_recall"] if n_scam else None,
                         "scam_precision": m["scam_precision"], "scam_f2": m["scam_f2"] if n_scam else None,
                         "scam_fpr": m["scam_fpr"], "macro_f1": m["macro_f1"]})
    return rows


def pct(x) -> str:
    return "–" if x is None or pd.isna(x) else f"{100 * x:.1f}"


def summary_md(choices: dict, res: pd.DataFrame) -> str:
    lines = ["# Kết quả rerank SVM + CharCNN", ""]
    for setup, b in choices.items():
        lines += [f"## {setup}", "",
                  f"- Chọn trên validation: **w = {b['w']:.1f}** (trọng số SVM), **t = {b['t']:.2f}**; "
                  f"val F2 {pct(b['val_scam_f2'])} (SVM đơn {pct(b['svm_val_scam_f2'])}), "
                  f"val báo nhầm {pct(b['val_scam_fpr'])}% (SVM đơn {pct(b['svm_val_scam_fpr'])}%) → "
                  + ("**nhận bản kết hợp**" if b["accepted"] else "**không hơn SVM đơn → giữ SVM**"), "",
                  "| Tập | n scam | SVM | CharCNN | OR | AND | **Rerank** |", "|---|---|---|---|---|---|---|"]
        g = res[res.setup == setup]
        for subset in g.subset.unique():
            cells = []
            for rule in ["SVM", "CharCNN", "OR", "AND", "Rerank"]:
                r = g[(g.subset == subset) & (g.rule == rule)].iloc[0]
                rec = f"{r.scam_caught}/{r.n_scam}" if subset.startswith("vi_real") or subset.startswith("ext_vi_crawl") \
                    else f"R {pct(r.scam_recall)}"
                cells.append(f"{rec} · FPR {pct(r.scam_fpr)}" if r.n_scam else f"FPR {pct(r.scam_fpr)}")
            n = g[g.subset == subset].n_scam.iat[0]
            lines.append(f"| {subset} | {n} | " + " | ".join(cells) + " |")
        lines.append("")
    lines.append("R = recall lớp scam (%), FPR = tỉ lệ tin không phải scam bị báo scam (%).")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    choices, results = {}, []
    for setup in SETUPS:
        print(f"== {setup}")
        scorer = Scorer(setup)
        val = scorer.frame[scorer.frame.split.eq("validation")]
        s_val = scorer.score(val.text_clean.astype(str).tolist())
        _, best = search(setup, val.label_level_1.astype(str), s_val, scorer.class_order)
        choices[setup] = best
        print("  chosen:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()})
        results += evaluate(setup, scorer, best)
    res = pd.DataFrame(results)
    res.to_csv(OUT / "results.csv", index=False, encoding="utf-8-sig")
    (OUT / "choices.json").write_text(json.dumps(choices, indent=2, default=float), encoding="utf-8")
    text = summary_md(choices, res)
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
