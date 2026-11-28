"""Tier-1 (ham / spam / scam) model comparison: Naive Bayes vs Linear SVM vs CharCNN.

Reads artifacts/<setup>/<model>/metrics_all_splits.json for the three setups
  vietnamese_balanced (VI model), english_balanced (EN model), bilingual (one model for both)
and, when present, reports/vi_crawl_full/summary.csv (real Vietnamese scams, full set).

Selection rule (fixed before looking at test/external, see docs/NHAT_KY_THAY_DOI_DU_LIEU.md 2.7):
  best model of a setup = highest VALIDATION scam F2, ties -> validation macro F1.
Test and external numbers are only reported, never used to choose.

Outputs: reports/tier1/tier1_comparison.csv, reports/tier1/tier1_selection.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SETUPS = {"vietnamese_balanced": "Tiếng Việt", "english_balanced": "Tiếng Anh", "bilingual": "Song ngữ"}
MODELS = {"naive_bayes": "Naive Bayes", "svm": "Linear SVM", "charcnn": "CharCNN"}
OUT = ROOT / "reports" / "tier1"


def pct(value) -> str:
    return "" if value is None or pd.isna(value) else f"{100 * float(value):.1f}"


def source(metrics: dict, name: str, key: str):
    return metrics.get("external_test", {}).get("by_source", {}).get(name, {}).get(key)


def load_rows() -> pd.DataFrame:
    crawl = None
    crawl_path = ROOT / "reports" / "vi_crawl_full" / "summary.csv"
    if crawl_path.exists():
        crawl = pd.read_csv(crawl_path, encoding="utf-8-sig")
    rows = []
    for setup, setup_vi in SETUPS.items():
        for model, model_vi in MODELS.items():
            path = ROOT / "artifacts" / setup / model / "metrics_all_splits.json"
            if not path.exists():
                continue
            m = json.loads(path.read_text(encoding="utf-8"))
            val, test = m.get("validation", {}), m.get("test", {})
            row = {
                "setup": setup, "Thiết lập": setup_vi, "model": model, "Mô hình": model_vi,
                "val_scam_f2": val.get("scam_f2"), "val_macro_f1": val.get("macro_f1"),
                "test_scam_precision": test.get("scam_precision"), "test_scam_recall": test.get("scam_recall"),
                "test_scam_f2": test.get("scam_f2"), "test_macro_f1": test.get("macro_f1"), "test_mcc": test.get("mcc"),
                "test_scam_fpr": test.get("scam_fpr"),
                # external: real-world checks with separate roles
                "smishx_scam_recall": source(m, "smishx", "scam_recall"),
                "smishx_scam_fpr": source(m, "smishx", "scam_fpr"),
                "vi_crawl_scam_recall": source(m, "vi_crawl", "scam_recall"),
                "vi_crawl_recall_ci95": source(m, "vi_crawl", "scam_recall_ci95"),
                "vie_sms_scam_fpr": source(m, "vie_sms_holdout", "scam_fpr"),
            }
            for lang in ("vi", "en"):
                lm = test.get("by_language", {}).get(lang)
                if lm and setup == "bilingual":
                    row[f"test_{lang}_scam_f2"] = lm.get("scam_f2")
                    row[f"test_{lang}_scam_recall"] = lm.get("scam_recall")
            if crawl is not None:
                key = f"{setup}/{model}"
                for subset in ("sms_known_family", "chat"):
                    hit = crawl[(crawl.model == key) & (crawl.subset == subset)]
                    if len(hit):
                        row[f"vi_full_{subset}_recall"] = hit.scam_recall.iat[0]
            rows.append(row)
    return pd.DataFrame(rows)


def select(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["selected"] = False
    for setup, group in df.groupby("setup"):
        best = group.sort_values(["val_scam_f2", "val_macro_f1"], ascending=False).index[0]
        df.loc[best, "selected"] = True
    return df


def markdown(df: pd.DataFrame) -> str:
    lines = ["# Tầng 1 – so sánh NB / SVM / CharCNN", "",
             "Quy tắc chọn (cố định trước): **F2 lớp scam cao nhất trên validation**, hòa thì macro-F1. "
             "Test / external chỉ để báo cáo.", ""]
    for setup, setup_vi in SETUPS.items():
        g = df[df.setup == setup]
        if g.empty:
            continue
        lines += [f"## {setup_vi} (`{setup}`)", "",
                  "| Mô hình | Val F2 scam | Test P / R / F2 scam | Test MCC | External: recall scam | External: báo nhầm |",
                  "|---|---|---|---|---|---|"]
        for _, r in g.iterrows():
            ext_r, ext_f = [], []
            if pd.notna(r.get("vi_crawl_scam_recall")):
                ext_r.append(f"VI crawl {pct(r.vi_crawl_scam_recall)}")
            if pd.notna(r.get("smishx_scam_recall")):
                ext_r.append(f"SmishX {pct(r.smishx_scam_recall)}")
            if pd.notna(r.get("vie_sms_scam_fpr")):
                ext_f.append(f"vie_sms {pct(r.vie_sms_scam_fpr)}")
            if pd.notna(r.get("smishx_scam_fpr")):
                ext_f.append(f"SmishX {pct(r.smishx_scam_fpr)}")
            name = f"**{r['Mô hình']} ✅**" if r.selected else r["Mô hình"]
            lines.append(f"| {name} | {pct(r.val_scam_f2)} | {pct(r.test_scam_precision)} / {pct(r.test_scam_recall)} / "
                         f"{pct(r.test_scam_f2)} | {r.test_mcc:.3f} | {', '.join(ext_r)} | {', '.join(ext_f)} |")
        lines.append("")
    chosen = df[df.selected]
    lines += ["## Kết luận tầng 1", ""]
    for _, r in chosen.iterrows():
        lines.append(f"- {r['Thiết lập']}: **{r['Mô hình']}** (val F2 scam {pct(r.val_scam_f2)})")
    lines += ["", "Đơn vị: %. External VI crawl = tập sạch (SMS, khuôn mới); chi tiết tập đầy đủ ở `reports/vi_crawl_full/`."]
    return "\n".join(lines) + "\n"


def main() -> None:
    df = load_rows()
    if df.empty:
        raise SystemExit("no metrics found under artifacts/ – train the models first")
    df = select(df)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "tier1_comparison.csv", index=False, encoding="utf-8-sig")
    text = markdown(df)
    (OUT / "tier1_selection.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
