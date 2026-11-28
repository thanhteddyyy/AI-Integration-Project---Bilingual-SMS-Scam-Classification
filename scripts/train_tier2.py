"""Train and evaluate tier 2 (Vietnamese scam_type, 9 classes) with NB, SVM and CharCNN.

Steps
  1. data   : all Tuan scam rows (incl. option-B drops), one row per text, split by template family
              so every class is in train / validation / test  -> data/processed_tier2_vi/
  2. train  : NB, SVM, CharCNN with the tier-1 trainers        -> artifacts/tier2_vi/<model>/
  3. eval   : validation / test (9 classes + definition groups), the NEXT crawl run (if present) by subset,
              chain tier 1 -> tier 2 on the crawl, grouped CV on train+validation (NB/SVM)
  4. report : reports/tier2_vi/summary.md (+ csv / json). SELECTION RULE (decision 2026-11-27): highest
              mean macro-F1 of 5-fold grouped CV on train+validation (one validation split of ~85 rows
              was too noisy); a gap smaller than one std counts as a tie -> prefer the simpler model.

Usage (from the repository root, Python 3.11):
  $env:PYTHONPATH="src"; py -3.11 scripts/train_tier2.py                 # all three models
  $env:PYTHONPATH="src"; py -3.11 scripts/train_tier2.py --models nb svm # skip CharCNN
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.config import load_config  # noqa: E402
from scam_baseline.data.scam_types import VI_TIER2_CLASSES  # noqa: E402
from scam_baseline.io_utils import ensure_dir, set_global_seed, write_json  # noqa: E402
from scam_baseline.models.classical import build_naive_bayes, build_svm, train_classical_model  # noqa: E402
from scam_baseline.tier2 import (  # noqa: E402
    assign_family_splits,
    build_tier2_frame,
    load_crawl_external,
    tier2_metrics,
    top_features,
)

MODEL_ALIASES = {"nb": "naive_bayes", "naive_bayes": "naive_bayes", "svm": "svm", "charcnn": "charcnn"}


def split_summary(frame: pd.DataFrame, class_order: list[str]) -> pd.DataFrame:
    rows = pd.crosstab(frame["label_level_1"], frame["split"]).reindex(index=class_order, fill_value=0)
    fams = frame.groupby(["label_level_1", "split"])["group_id"].nunique().unstack(fill_value=0)
    fams = fams.reindex(index=class_order, fill_value=0)
    out = pd.DataFrame(index=class_order)
    for split in ("train", "validation", "test"):
        out[f"{split}_rows"] = rows.get(split, 0)
        out[f"{split}_families"] = fams.get(split, 0)
    out.loc["TOTAL"] = out.sum()
    return out


def grouped_cv(frame: pd.DataFrame, config: dict, model_name: str, folds: int) -> dict:
    """Macro-F1 over K folds of train+validation (families never cross folds). Gives a spread
    that the small validation split (one number) cannot."""
    dev = frame[frame["split"].isin(["train", "validation"])].reset_index(drop=True)
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=int(config["seed"]))
    scores, accs = [], []
    for fold, (train_idx, val_idx) in enumerate(cv.split(dev["text_clean"], dev["label_level_1"], dev["group_id"])):
        if model_name == "charcnn":
            pred = _charcnn_fold(dev, train_idx, val_idx, config, fold)
        else:
            model = build_naive_bayes(config) if model_name == "naive_bayes" else build_svm(config)
            model.fit(dev.loc[train_idx, "text_clean"], dev.loc[train_idx, "label_level_1"])
            pred = model.predict(dev.loc[val_idx, "text_clean"])
        m = tier2_metrics(dev.loc[val_idx, "label_level_1"].tolist(), list(pred), config["data"]["class_order"])
        scores.append(m["macro_f1"])
        accs.append(m["accuracy"])
    return {"folds": folds, "macro_f1_mean": float(np.mean(scores)), "macro_f1_std": float(np.std(scores)),
            "accuracy_mean": float(np.mean(accs)), "macro_f1_per_fold": [float(s) for s in scores]}


def _charcnn_fold(dev: pd.DataFrame, train_idx, val_idx, config: dict, fold: int) -> list[str]:
    """One CV fold for CharCNN. Early stopping needs its own validation: 15% of the fold's TRAIN families
    (never the fold's test part, which would leak)."""
    from scam_baseline.models.charcnn import train_charcnn
    fold_train = dev.loc[train_idx].copy()
    inner = assign_family_splits(fold_train["label_level_1"], fold_train["group_id"],
                                 {"train": 0.85, "validation": 0.15, "test": 0.0}, int(config["seed"]) + fold)
    fold_train["split"] = inner.values
    fold_test = dev.loc[val_idx].assign(split="test")
    cfg = {**config, "paths": {**config["paths"],
                               "artifacts_dir": str(Path(config["paths"]["artifacts_dir"]) / "_cv_charcnn" / f"fold{fold}")}}
    train_charcnn(pd.concat([fold_train, fold_test], ignore_index=True), cfg)
    out = pd.read_csv(Path(cfg["paths"]["artifacts_dir"]) / "charcnn" / "predictions_test.csv")
    return out.set_index("sample_id").loc[fold_test["sample_id"], "prediction"].tolist()


def split_seed_check(config: dict, model_name: str, seeds: int) -> dict:
    """Re-split with other seeds and retrain: how much do validation / test move by luck of the split?"""
    val_scores, test_scores = [], []
    for seed in range(seeds):
        cfg = {**config, "seed": seed}
        frame, _ = build_tier2_frame(cfg)
        train = frame[frame["split"].eq("train")]
        model = build_naive_bayes(config) if model_name == "naive_bayes" else build_svm(config)
        model.fit(train["text_clean"], train["label_level_1"])
        for split, bucket in (("validation", val_scores), ("test", test_scores)):
            part = frame[frame["split"].eq(split)]
            bucket.append(tier2_metrics(part["label_level_1"].tolist(), list(model.predict(part["text_clean"])),
                                        config["data"]["class_order"])["macro_f1"])
    return {"seeds": seeds,
            "validation_macro_f1_mean": float(np.mean(val_scores)), "validation_macro_f1_std": float(np.std(val_scores)),
            "test_macro_f1_mean": float(np.mean(test_scores)), "test_macro_f1_std": float(np.std(test_scores)),
            "test_macro_f1_min": float(np.min(test_scores)), "test_macro_f1_max": float(np.max(test_scores))}


def read_predictions(artifact_dir: Path, split: str) -> pd.DataFrame:
    return pd.read_csv(artifact_dir / f"predictions_{split}.csv")[["sample_id", "prediction"]]


def fmt(x: float | None) -> str:
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.1f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(ROOT / "configs" / "tier2_vietnamese.yaml"))
    parser.add_argument("--models", nargs="+", default=["nb", "svm", "charcnn"], choices=list(MODEL_ALIASES))
    parser.add_argument("--cv-folds", type=int, default=5, help="grouped CV folds on train+validation, used to SELECT the model (0 = skip)")
    parser.add_argument("--no-final", action="store_true",
                        help="do not retrain the selected model on all rows (artifacts/tier2_vi/final/)")
    parser.add_argument("--split-seeds", type=int, default=0,
                        help="re-split with N seeds to measure split luck, NB/SVM only (0 = skip)")
    args = parser.parse_args()

    config = load_config(args.config)
    set_global_seed(int(config["seed"]))
    class_order = config["data"]["class_order"]
    if sorted(class_order) != sorted(VI_TIER2_CLASSES):
        raise SystemExit("data.class_order must list exactly the classes of VI_TIER2_CLASSES")
    processed = ensure_dir(config["paths"]["processed_dir"])
    reports = ensure_dir(config["paths"]["reports_dir"])
    artifacts = Path(config["paths"]["artifacts_dir"])

    # 1. data -------------------------------------------------------------------------------
    frame, crawl_skipped = build_tier2_frame(config)
    train_texts = frame.loc[frame["split"].eq("train"), "text_clean"].tolist()
    crawl = load_crawl_external(config, train_texts)
    frame.to_csv(processed / "tier2_data.csv", index=False, encoding="utf-8-sig")
    crawl_skipped.to_csv(processed / "crawl_train_skipped.csv", index=False, encoding="utf-8-sig")
    summary_table = split_summary(frame, class_order)
    summary_table.to_csv(processed / "split_summary.csv", encoding="utf-8-sig")
    print("Split (rows / families):\n", summary_table.to_string(), "\n")
    crawl_train_rows = int((~frame["source_dataset"].str.startswith("spamscam")).sum())
    print(f"Crawl scams added to train: {crawl_train_rows}; skipped: "
          f"{crawl_skipped['skip_reason'].value_counts().to_dict() if len(crawl_skipped) else {}}")
    stale = [processed / "tier2_crawl_external.csv", reports / "crawl_predictions.csv"]
    if crawl is None:
        print("External test (next crawl run) not found -> external / chain evaluation skipped\n")
        for path in stale:
            path.unlink(missing_ok=True)
        full = frame
    else:
        crawl.to_csv(stale[0], index=False, encoding="utf-8-sig")
        print("External crawl scams by subset:", crawl["subset"].value_counts().to_dict(), "\n")
        full = pd.concat([frame, crawl], ignore_index=True)

    tier1 = None
    tier1_path = Path(config["paths"]["tier1_model"])
    if crawl is not None and tier1_path.exists():
        tier1 = joblib.load(tier1_path)
        crawl["tier1_prediction"] = tier1.predict(crawl["text_clean"].astype(str))
    elif crawl is not None:
        print(f"WARNING: tier-1 model not found ({tier1_path}); chain evaluation skipped")

    # 2-3. train + evaluate -----------------------------------------------------------------
    models = list(dict.fromkeys(MODEL_ALIASES[m] for m in args.models))
    results: dict[str, dict] = {}
    crawl_out = crawl.drop(columns=["text_raw"]).copy() if crawl is not None else None
    per_class_rows = []
    for name in models:
        print(f"Training {name}...")
        if name == "charcnn":
            from scam_baseline.models.charcnn import train_charcnn
            train_charcnn(full, config)
        else:
            train_classical_model(full, config, name)
        model_dir = artifacts / name
        res: dict = {}
        for split in ("validation", "test"):
            part = frame[frame["split"].eq(split)][["sample_id", "label_level_1"]]
            merged = part.merge(read_predictions(model_dir, split), on="sample_id", how="left")
            res[split] = tier2_metrics(merged["label_level_1"].tolist(), merged["prediction"].tolist(), class_order)
        if crawl_out is not None:
            merged = crawl_out[["sample_id", "label_level_1"]].merge(
                read_predictions(model_dir, "external_test"), on="sample_id", how="left")
            res["external_test"] = tier2_metrics(merged["label_level_1"].tolist(), merged["prediction"].tolist(), class_order)
            crawl_out[f"{name}_prediction"] = crawl_out["sample_id"].map(merged.set_index("sample_id")["prediction"])
            correct = crawl_out[f"{name}_prediction"].eq(crawl_out["label_level_1"])
            res["crawl_by_subset"] = {
                subset: {"rows": int(len(g)), "accuracy": float(correct[g.index].mean())}
                for subset, g in crawl_out.groupby("subset")
            }
            if tier1 is not None:
                passed = crawl_out["tier1_prediction"].eq("scam")
                res["chain"] = {
                    "rows": int(len(crawl_out)),
                    "tier1_scam_recall": float(passed.mean()),
                    "tier2_accuracy_when_tier1_passes": float(correct[passed].mean()) if passed.any() else None,
                    "chain_accuracy": float((passed & correct).mean()),
                    "by_subset": {
                        subset: {"rows": int(len(g)), "chain_accuracy": float((passed & correct)[g.index].mean())}
                        for subset, g in crawl_out.groupby("subset")
                    },
                }
        if args.cv_folds > 1:
            res["grouped_cv"] = grouped_cv(frame, config, name, args.cv_folds)
        if name != "charcnn" and args.split_seeds > 1:
            res["split_seed_check"] = split_seed_check(config, name, args.split_seeds)
        if name != "charcnn":
            top_features(joblib.load(model_dir / "model.joblib"), class_order).to_csv(
                reports / f"top_features_{name}.csv", index=False, encoding="utf-8-sig")
        for split in ("validation", "test"):
            for label, row in res[split]["per_class"].items():
                per_class_rows.append({"model": name, "split": split, "class": label, **{
                    k: row[k] for k in ("support", "precision", "recall", "f1")}, "recall_ci95": row["recall_ci95"]})
        results[name] = res

    # 4. report -----------------------------------------------------------------------------
    write_json(results, reports / "metrics_tier2.json")
    pd.DataFrame(per_class_rows).to_csv(reports / "per_class.csv", index=False, encoding="utf-8-sig")
    if crawl_out is not None:
        crawl_out.to_csv(reports / "crawl_predictions.csv", index=False, encoding="utf-8-sig")
    comparison = pd.DataFrame([
        {
            "model": name,
            "val_macro_f1": r["validation"]["macro_f1"],
            "val_accuracy": r["validation"]["accuracy"],
            "cv_macro_f1_mean": r.get("grouped_cv", {}).get("macro_f1_mean"),
            "cv_macro_f1_std": r.get("grouped_cv", {}).get("macro_f1_std"),
            "test_macro_f1": r["test"]["macro_f1"],
            "test_accuracy": r["test"]["accuracy"],
            "test_group_macro_f1": r["test"]["group_level"]["macro_f1"],
            "crawl_accuracy": r.get("external_test", {}).get("accuracy"),
            "chain_accuracy": r.get("chain", {}).get("chain_accuracy"),
        }
        for name, r in results.items()
    ])
    comparison.to_csv(reports / "comparison.csv", index=False, encoding="utf-8-sig")
    tie = str(config["evaluation"].get("tie_breaker", "accuracy"))
    ranked = comparison.sort_values(["cv_macro_f1_mean", f"val_{tie}"], ascending=False).reset_index(drop=True)
    proposal = ranked.iloc[0]["model"]
    if len(ranked) > 1 and ranked.iloc[0]["cv_macro_f1_mean"] - ranked.iloc[1]["cv_macro_f1_mean"] < ranked.iloc[0]["cv_macro_f1_std"]:
        proposal += f" (ngang {ranked.iloc[1]['model']}: chênh < 1 std, chọn model đơn giản hơn)"
    skipped = crawl_skipped["skip_reason"].value_counts().to_dict() if len(crawl_skipped) else {}
    crawl_note = (f"Train gồm cả **{crawl_train_rows} tin scam crawl thật** (đợt 1–2, mọi kênh – chỉ lấy tin lừa đảo chính). "
                  f"Validation/test chỉ có tin của Tuấn, giữ nguyên. Tin crawl không đưa vào: {skipped or 'không có'} "
                  "(chi tiết `data/processed_tier2_vi/crawl_train_skipped.csv`).")
    write_summary(reports / "summary.md", summary_table, crawl_out, results, comparison, class_order, proposal,
                  crawl_note)
    print(comparison.to_string(index=False))
    print(f"\nSelected by CV macro-F1: {proposal}")
    print(f"Report: {reports / 'summary.md'}")
    if not args.no_final:
        train_final_model(frame, config, ranked.iloc[0]["model"], comparison)


def train_final_model(frame: pd.DataFrame, config: dict, model_name: str, comparison: pd.DataFrame) -> None:
    """A4: retrain the selected model on ALL tier-2 rows (train + validation + test + crawl runs 1-2) for the
    demo / predict_pipeline. Its numbers are the CV / test numbers above – this model has no held-out data."""
    if model_name == "charcnn":
        print("Final model: CharCNN selected – train it with train_charcnn on a copy where every row is train")
        return
    model = build_naive_bayes(config) if model_name == "naive_bayes" else build_svm(config)
    model.fit(frame["text_clean"].astype(str), frame["label_level_1"].astype(str))
    out = ensure_dir(Path(config["paths"]["artifacts_dir"]) / "final")
    joblib.dump(model, out / "model.joblib")
    row = comparison.set_index("model").loc[model_name]
    write_json({
        "model": model_name,
        "trained_on": "all tier-2 rows: train + validation + test + crawl runs 1-2",
        "training_rows": int(len(frame)),
        "classes": [str(c) for c in model.classes_],
        "class_counts": frame["label_level_1"].value_counts().to_dict(),
        "selection": "highest 5-fold grouped CV macro-F1 on train+validation",
        "cv_macro_f1_mean": float(row["cv_macro_f1_mean"]),
        "cv_macro_f1_std": float(row["cv_macro_f1_std"]),
        "test_macro_f1_seed_split": float(row["test_macro_f1"]),
        "input": "text_clean = scam_baseline.data.clean.clean_text(raw message)",
        "config_path": config["_config_path"],
    }, out / "training_metadata.json")
    print(f"Final {model_name} trained on {len(frame)} rows -> {out / 'model.joblib'}")


def write_summary(path, split_table, crawl, results, comparison, class_order, proposal, crawl_note) -> None:
    external = ("Tập external (đợt crawl mới, không dùng để train): " + f"{len(crawl)} tin scam – " + ", ".join(
        f"{k}: {v}" for k, v in crawl["subset"].value_counts().items())) if crawl is not None else (
        "Tập external: **chưa có** (chờ đợt crawl tiếp theo, `data/raw/vi_crawl_tier2_external.csv`) → "
        "chưa có mục tin thật và chuỗi tầng 1 → tầng 2.")
    lines = ["# Tầng 2 tiếng Việt – kết quả train và đánh giá", "",
             "Sinh tự động bởi `scripts/train_tier2.py`. Số liệu là %, trừ cột số tin.", "",
             "## 1. Dữ liệu (số tin / số khuôn)", "", split_table.to_markdown(), "",
             crawl_note, "", external, "",
             "## 2. So sánh model", "",
             "**Quy tắc chọn (chốt 27/11): CV macro-F1 trung bình cao nhất** – 5 lượt, chia theo khuôn trên train+val; "
             "chênh nhau ít hơn 1 độ lệch thì coi như ngang, chọn model đơn giản hơn. Val 1 lần chỉ để tham khảo "
             "(~85 tin, dao động mạnh). Test, crawl và chuỗi chỉ để báo cáo, không dùng để chọn.", "",
             "| Model | Val macro-F1 | Val acc | CV macro-F1 (±std) | Test macro-F1 | Test acc | Test macro-F1 mức nhóm | Crawl acc | Chuỗi T1→T2 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in comparison.itertuples():
        cv = f"{fmt(r.cv_macro_f1_mean)} ± {fmt(r.cv_macro_f1_std)}" if r.cv_macro_f1_mean is not None and not pd.isna(r.cv_macro_f1_mean) else "–"
        lines.append(f"| {r.model} | {fmt(r.val_macro_f1)} | {fmt(r.val_accuracy)} | {cv} | {fmt(r.test_macro_f1)} | "
                     f"{fmt(r.test_accuracy)} | {fmt(r.test_group_macro_f1)} | {fmt(r.crawl_accuracy)} | {fmt(r.chain_accuracy)} |")
    checks = {n: r["split_seed_check"] for n, r in results.items() if "split_seed_check" in r}
    if checks:
        k = next(iter(checks.values()))["seeds"]
        lines += ["", f"**Độ nhạy theo cách chia** (chia lại với {k} seed, train lại; chỉ NB/SVM): validation và test chỉ ~85 tin "
                  "mỗi tập nên một lần chia có thể may/rủi.", "",
                  "| Model | Val macro-F1 (TB ± std) | Test macro-F1 (TB ± std) | Test min–max |", "|---|---|---|---|"]
        for n, c in checks.items():
            lines.append(f"| {n} | {fmt(c['validation_macro_f1_mean'])} ± {fmt(c['validation_macro_f1_std'])} | "
                         f"{fmt(c['test_macro_f1_mean'])} ± {fmt(c['test_macro_f1_std'])} | "
                         f"{fmt(c['test_macro_f1_min'])}–{fmt(c['test_macro_f1_max'])} |")
    lines += ["", f"**Model được chọn theo CV macro-F1: `{proposal}`**", "",
              "## 3. F1 từng lớp trên test (recall: k/n, khoảng tin cậy 95%)", ""]
    header = "| Lớp | n | " + " | ".join(results) + " |"
    lines += [header, "|---|---|" + "---|" * len(results)]
    for label in class_order:
        n = next(iter(results.values()))["test"]["per_class"][label]["support"]
        cells = []
        for r in results.values():
            row = r["test"]["per_class"][label]
            ci = row["recall_ci95"]
            hits = round(row["recall"] * row["support"])
            cells.append(f"F1 {fmt(row['f1'])} · R {hits}/{n}" + (f" [{fmt(ci[0])}–{fmt(ci[1])}]" if ci else ""))
        lines.append(f"| {label} | {n} | " + " | ".join(cells) + " |")
    subsets = sorted(crawl["subset"].unique()) if crawl is not None else []
    if crawl is not None:
        lines += ["", "## 4. Tin crawl thật – tập external (accuracy tầng 2, tầng 2 chạy riêng)", "",
                  "Khuôn = đã có / chưa có trong train tầng 2 (kể cả tin crawl đợt 1–2 đã đưa vào train).", ""]
        lines += ["| Model | Tất cả (n=" + str(len(crawl)) + ") | " +
                  " | ".join(f"{s} (n={int((crawl['subset'] == s).sum())})" for s in subsets) + " |",
                  "|---|---|" + "---|" * len(subsets)]
        for name, r in results.items():
            by = r["crawl_by_subset"]
            lines.append(f"| {name} | {fmt(r['external_test']['accuracy'])} | " +
                         " | ".join(fmt(by[s]["accuracy"]) for s in subsets) + " |")
    if any("chain" in r for r in results.values()):
        lines += ["", "## 5. Chuỗi tầng 1 → tầng 2 trên tin crawl thật", "",
                  "Đúng = tầng 1 báo scam **và** tầng 2 đoán đúng loại. Tầng 1 để lọt thì tính là sai.", ""]
        first = next(r["chain"] for r in results.values() if "chain" in r)
        lines.append(f"Tầng 1 bắt được {fmt(first['tier1_scam_recall'])}% tin scam crawl.")
        lines += ["", "| Model tầng 2 | Tầng 2 đúng khi tầng 1 cho qua | Cả chuỗi | " +
                  " | ".join(subsets) + " |", "|---|---|---|" + "---|" * len(subsets)]
        for name, r in results.items():
            c = r.get("chain")
            if c:
                lines.append(f"| {name} | {fmt(c['tier2_accuracy_when_tier1_passes'])} | {fmt(c['chain_accuracy'])} | " +
                             " | ".join(fmt(c["by_subset"][s]["chain_accuracy"]) for s in subsets) + " |")
    lines += ["", "## 6. File chi tiết", "",
              "- `metrics_tier2.json`: mọi chỉ số, ma trận nhầm lẫn 9 lớp và mức nhóm",
              "- `per_class.csv`: precision/recall/F1 từng lớp (validation, test)",
              "- `crawl_predictions.csv`: dự đoán từng tin crawl (tầng 1 + mỗi model tầng 2)",
              "- `top_features_<model>.csv`: từ/cụm từ đặc trưng nhất của từng lớp (kiểm tra lối tắt)",
              "- `artifacts/tier2_vi/<model>/`: model, dự đoán, ảnh ma trận nhầm lẫn"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
