"""C1 – train and evaluate the vi / en language identifier (src/scam_baseline/langid.py).

Data: data/processed_bilingual/modeling_data.csv (the `language` label comes from the source of each row).
Train on the train split (+ every Vietnamese train text again without diacritics); report on validation,
test and external_test, with extra checks: Vietnamese WITHOUT diacritics, short messages, and a few
hand-written probes (mixed brand names, OTP messages).

Usage (from bilingual-scam-baseline/):
  $env:PYTHONPATH="src"; py -3.11 scripts/train_langid.py
Outputs: artifacts/langid/model.joblib (+ metrics.json, errors.csv), reports/langid/summary.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.evaluation import wilson_interval  # noqa: E402
from scam_baseline.io_utils import ensure_dir, write_json  # noqa: E402
from scam_baseline.langid import build_langid_model, langid_preprocess_one  # noqa: E402
from scam_baseline.models.classical import strip_vietnamese_accents  # noqa: E402

PROBES = [  # (text, expected) – typical demo inputs, written for this check (not training data)
    ("Tai khoan cua quy khach bi tam khoa, vui long xac thuc tai vcb-xacminh.com", "vi"),
    ("Vietcombank: Ma OTP cua ban la 482913. Khong chia se ma nay.", "vi"),
    ("Mẹ ơi con đang cấp cứu, chuyển giúp con 5 triệu vào STK 0123456789", "vi"),
    ("Chuc mung ban trung thuong iPhone 15, nhan tai bit.ly/abc", "vi"),
    ("ok e", "vi"),
    ("Your account has been locked. Verify now at secure-bank-login.com", "en"),
    ("Your OTP is 482913. Do not share it with anyone.", "en"),
    ("USPS: your package is on hold, update your address here", "en"),
    ("Congratulations! You won a $1000 Walmart gift card. Click to claim", "en"),
    ("Hi mum, I lost my phone, this is my new number", "en"),
]


def evaluate(truth: list[str], pred: list[str]) -> dict:
    truth, pred = np.asarray(truth), np.asarray(pred)
    out = {"rows": int(len(truth)), "accuracy": float((truth == pred).mean()) if len(truth) else None}
    for lang in ("vi", "en"):
        mask = truth == lang
        hits = int((pred[mask] == lang).sum())
        out[f"recall_{lang}"] = float(hits / mask.sum()) if mask.any() else None
        out[f"recall_{lang}_ci95"] = wilson_interval(hits, int(mask.sum()))
        out[f"n_{lang}"] = int(mask.sum())
    return out


def main() -> None:
    data = pd.read_csv(ROOT / "data" / "processed_bilingual" / "modeling_data.csv", low_memory=False)
    data = data[data["language"].isin(["vi", "en"]) & data["text_clean"].notna()].copy()
    data["prep"] = data["text_clean"].map(langid_preprocess_one)
    empty = data["prep"].eq("")
    print(f"rows with nothing left after removing placeholders/URLs/digits: {int(empty.sum())} (not used)")
    data = data[~empty]

    train = data[data["split"].eq("train")][["text_clean", "language"]]
    vi_plain = train[train["language"].eq("vi")].assign(text_clean=lambda d: d["text_clean"].map(strip_vietnamese_accents))
    train = pd.concat([train, vi_plain], ignore_index=True).drop_duplicates()
    model = build_langid_model()
    model.fit(train["text_clean"], train["language"])
    print(f"trained on {len(train)} texts (incl. {len(vi_plain)} Vietnamese without diacritics)")

    metrics, error_rows = {}, []
    for split in ("validation", "test", "external_test"):
        part = data[data["split"].eq(split)]
        if part.empty:
            continue
        pred = model.predict(part["text_clean"])
        metrics[split] = evaluate(part["language"].tolist(), list(pred))
        metrics[split]["by_source"] = {s: evaluate(g["language"].tolist(), list(model.predict(g["text_clean"])))
                                       for s, g in part.groupby("source_dataset")}
        vi = part[part["language"].eq("vi")]
        if len(vi):
            plain = vi["text_clean"].map(strip_vietnamese_accents)
            metrics[split]["vi_without_diacritics"] = evaluate(["vi"] * len(vi), list(model.predict(plain)))
        short = part[part["prep"].str.len() <= 30]
        if len(short):
            metrics[split]["short_messages_le30"] = evaluate(short["language"].tolist(), list(model.predict(short["text_clean"])))
        wrong = part[pred != part["language"].to_numpy()]
        error_rows.append(wrong.assign(predicted=pred[pred != part["language"].to_numpy()])[
            ["split", "source_dataset", "language", "predicted", "text_clean"]])

    probe_pred = model.predict([t for t, _ in PROBES])
    probe_proba = model.predict_proba([t for t, _ in PROBES])
    vi_col = list(model.classes_).index("vi")
    metrics["probes"] = [{"text": t, "expected": e, "predicted": p, "p_vi": float(pr[vi_col])}
                         for (t, e), p, pr in zip(PROBES, probe_pred, probe_proba)]

    art = ensure_dir(ROOT / "artifacts" / "langid")
    joblib.dump(model, art / "model.joblib")
    write_json(metrics, art / "metrics.json")
    errors = pd.concat(error_rows, ignore_index=True) if error_rows else pd.DataFrame()
    errors.to_csv(art / "errors.csv", index=False, encoding="utf-8-sig")
    write_report(metrics, errors, len(train), len(vi_plain))


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.2f}"


def write_report(metrics: dict, errors: pd.DataFrame, n_train: int, n_plain: int) -> None:
    rep = ensure_dir(ROOT / "reports" / "langid")
    lines = ["# C1 – Nhận diện ngôn ngữ (vi / en)", "",
             "Sinh bởi `scripts/train_langid.py`. Model: Naive Bayes trên cụm ký tự 1–3 (`char_wb`), bỏ ký hiệu che "
             "([NUMBER], <URL>…), link, email, chữ số trước khi học (các thứ này khác nhau theo **nguồn**, không theo ngôn ngữ). "
             f"Train: {n_train} tin, gồm {n_plain} tin tiếng Việt được thêm bản **bỏ dấu**.", "",
             "| Tập | Số tin | Accuracy | Recall vi | Recall en | Tiếng Việt bỏ dấu | Tin ngắn (≤ 30 ký tự) |", "|---|---|---|---|---|---|---|"]
    for split in ("validation", "test", "external_test"):
        m = metrics.get(split)
        if not m:
            continue
        plain = m.get("vi_without_diacritics", {}).get("accuracy")
        short = m.get("short_messages_le30", {})
        lines.append(f"| {split} | {m['rows']} | {pct(m['accuracy'])} | {pct(m['recall_vi'])} (n={m['n_vi']}) | "
                     f"{pct(m['recall_en'])} (n={m['n_en']}) | {pct(plain)} | {pct(short.get('accuracy'))} (n={short.get('rows', 0)}) |")
    lines += ["", "## Theo nguồn", "", "| Tập | Nguồn | Số tin | Accuracy |", "|---|---|---|---|"]
    for split in ("validation", "test", "external_test"):
        for src, m in metrics.get(split, {}).get("by_source", {}).items():
            lines.append(f"| {split} | {src} | {m['rows']} | {pct(m['accuracy'])} |")
    lines += ["", "## Câu thử viết tay", "", "| Tin | Mong đợi | Dự đoán | P(vi) |", "|---|---|---|---|"]
    for p in metrics["probes"]:
        mark = "" if p["predicted"] == p["expected"] else " ❌"
        lines.append(f"| {p['text']} | {p['expected']} | {p['predicted']}{mark} | {p['p_vi']:.3f} |")
    lines += ["", f"## Tin đoán sai ({len(errors)}) – xem `artifacts/langid/errors.csv`", ""]
    for r in errors.head(25).itertuples():
        lines.append(f"- [{r.split}/{r.source_dataset}] nhãn {r.language} → đoán {r.predicted}: {str(r.text_clean)[:110]}")
    (rep / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("->", rep / "summary.md")


if __name__ == "__main__":
    main()
