"""Tier-2 experiments with the chosen model (SVM), decided 2026-11-27 (docs/NHAT_KY_TANG2.md section 5).

A2  leave-one-family-out for social_impersonation: each social template family in turn is removed from
    training and predicted -> how well does the model recognise a social template it has never seen?
    (the single test family "Sếp nhờ chút..." gave one test only)
A3  mask the PAYEE bank name ("chuyển vào STK [NUMBER] Vietcombank" -> "... [PAYEE_BANK]") before features:
    does it remove the shortcut "STK + bank name = banking_finance"? Compared with / without the mask on
    grouped CV (selection metric), per-class CV F1, the seed-42 test split and A2.

Usage: $env:PYTHONPATH="src"; py -3.11 scripts/tier2_experiments.py   -> reports/tier2_vi/experiments.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.config import load_config  # noqa: E402
from scam_baseline.io_utils import ensure_dir, write_json  # noqa: E402
from scam_baseline.models.classical import build_svm  # noqa: E402
from scam_baseline.tier2 import build_tier2_frame, mask_payee_bank, tier2_metrics  # noqa: E402

SOCIAL = "social_impersonation"


def fit_predict(config, train_text, train_y, test_text):
    model = build_svm(config)
    model.fit(train_text, train_y)
    return list(model.predict(test_text))


def cv_eval(dev: pd.DataFrame, config: dict, text_col: str, folds: int = 5) -> dict:
    order = config["data"]["class_order"]
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=int(config["seed"]))
    scores, truth_all, pred_all = [], [], []
    for tr, va in cv.split(dev[text_col], dev["label_level_1"], dev["group_id"]):
        pred = fit_predict(config, dev.loc[tr, text_col], dev.loc[tr, "label_level_1"], dev.loc[va, text_col])
        truth = dev.loc[va, "label_level_1"].tolist()
        scores.append(tier2_metrics(truth, pred, order)["macro_f1"])
        truth_all += truth
        pred_all += pred
    per_class = f1_score(truth_all, pred_all, labels=order, average=None, zero_division=0)
    return {"macro_f1_mean": float(np.mean(scores)), "macro_f1_std": float(np.std(scores)),
            "per_class_f1_pooled": dict(zip(order, map(float, per_class)))}


def leave_one_social_family_out(data: pd.DataFrame, config: dict, text_col: str) -> pd.DataFrame:
    rows = []
    for fam, part in data[data["label_level_1"].eq(SOCIAL)].groupby("group_id"):
        train = data[data["group_id"].ne(fam)]
        pred = fit_predict(config, train[text_col], train["label_level_1"], part[text_col])
        rows.append({"family": fam, "rows": len(part), "correct": int(sum(p == SOCIAL for p in pred)),
                     "predicted_as": pd.Series(pred).value_counts().to_dict(),
                     "example": part["text_clean"].iloc[0][:90]})
    return pd.DataFrame(rows)


def main() -> None:
    config = load_config(ROOT / "configs" / "tier2_vietnamese.yaml")
    order = config["data"]["class_order"]
    reports = ensure_dir(config["paths"]["reports_dir"])
    frame, _ = build_tier2_frame(config)
    frame["text_masked"] = frame["text_clean"].map(mask_payee_bank)
    touched = frame[frame["text_masked"].ne(frame["text_clean"])]["label_level_1"].value_counts().to_dict()
    dev = frame[frame["split"].isin(["train", "validation"])].reset_index(drop=True)
    train = frame[frame["split"].eq("train")]
    test = frame[frame["split"].eq("test")]

    results, lofo = {}, {}
    for variant, col in (("no_mask", "text_clean"), ("mask_payee_bank", "text_masked")):
        cv = cv_eval(dev, config, col)
        pred = fit_predict(config, train[col], train["label_level_1"], test[col])
        test_m = tier2_metrics(test["label_level_1"].tolist(), pred, order)
        lo = leave_one_social_family_out(frame, config, col)
        lofo[variant] = lo
        results[variant] = {"cv": cv, "test_macro_f1": test_m["macro_f1"],
                            "test_per_class_f1": {k: v["f1"] for k, v in test_m["per_class"].items()},
                            "lofo_social_recall": float(lo["correct"].sum() / lo["rows"].sum()),
                            "lofo_social_families_ok": int((lo["correct"] > 0).sum()), "lofo_social_families": len(lo)}
        print(variant, f"CV {100*cv['macro_f1_mean']:.1f}±{100*cv['macro_f1_std']:.1f}",
              f"test {100*test_m['macro_f1']:.1f}", f"LOFO social {lo['correct'].sum()}/{lo['rows'].sum()}")
    write_json({"rows_touched_by_mask": touched, **results}, reports / "experiments.json")

    a, b = results["no_mask"], results["mask_payee_bank"]
    pct = lambda x: f"{100 * x:.1f}"  # noqa: E731
    lines = ["# Tầng 2 – thí nghiệm A2 (giấu từng khuôn social) và A3 (che tên ngân hàng nhận tiền)", "",
             "Sinh bởi `scripts/tier2_experiments.py`. Model: SVM (đã chọn). Số liệu %.", "",
             f"Tin bị che (A3): {sum(touched.values())} – " + ", ".join(f"{k} {v}" for k, v in touched.items()), "",
             "## Tổng quan", "",
             "| | Không che | Che tên ngân hàng nhận tiền |", "|---|---|---|",
             f"| CV macro-F1 (5 lượt) | {pct(a['cv']['macro_f1_mean'])} ± {pct(a['cv']['macro_f1_std'])} | "
             f"{pct(b['cv']['macro_f1_mean'])} ± {pct(b['cv']['macro_f1_std'])} |",
             f"| Test macro-F1 (seed 42) | {pct(a['test_macro_f1'])} | {pct(b['test_macro_f1'])} |",
             f"| A2: social, giấu từng khuôn – tin đúng | {lofo['no_mask']['correct'].sum()}/{lofo['no_mask']['rows'].sum()} | "
             f"{lofo['mask_payee_bank']['correct'].sum()}/{lofo['mask_payee_bank']['rows'].sum()} |",
             f"| A2: số khuôn social nhận ra được (≥1 tin đúng) | {a['lofo_social_families_ok']}/{a['lofo_social_families']} | "
             f"{b['lofo_social_families_ok']}/{b['lofo_social_families']} |", "",
             "## F1 từng lớp (CV, gộp 5 lượt)", "", "| Lớp | Không che | Che | Chênh |", "|---|---|---|---|"]
    for k in order:
        x, y = a["cv"]["per_class_f1_pooled"][k], b["cv"]["per_class_f1_pooled"][k]
        lines.append(f"| {k} | {pct(x)} | {pct(y)} | {100*(y-x):+.1f} |")
    for variant, title in (("no_mask", "không che"), ("mask_payee_bank", "có che")):
        lines += ["", f"## A2 chi tiết – {title}", "", "| Khuôn | Số tin | Đúng | Bị đoán thành | Ví dụ |", "|---|---|---|---|---|"]
        for r in lofo[variant].itertuples():
            lines.append(f"| {r.family} | {r.rows} | {r.correct} | {r.predicted_as} | {r.example} |")
    (reports / "experiments.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("->", reports / "experiments.md")


if __name__ == "__main__":
    main()
