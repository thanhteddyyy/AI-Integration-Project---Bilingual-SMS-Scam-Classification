"""Try the tier-1 model (ham / spam / scam) on your own messages in the terminal.

Shows the predicted label, the SVM score of each class (higher = more likely; the largest wins)
and the words / phrases that pushed the message towards the predicted class.

Usage (from bilingual-scam-baseline/):
  PYTHONPATH=src python scripts/try_tier1.py                       # interactive, type messages
  PYTHONPATH=src python scripts/try_tier1.py --text "Tai khoan cua ban bi khoa..."
  PYTHONPATH=src python scripts/try_tier1.py --setup vietnamese_balanced
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.data.clean import clean_text  # noqa: E402

LABEL_VI = {"legitimate": "HAM (tin bình thường)", "spam": "SPAM (quảng cáo/rác)", "scam": "SCAM (lừa đảo)"}


class Tier1:
    def __init__(self, setup: str):
        path = ROOT / "artifacts" / setup / "svm" / "model.joblib"
        self.model = joblib.load(path)
        self.features = self.model.named_steps["features"]
        self.classifier = self.model.named_steps["classifier"]
        self.classes = list(self.classifier.classes_)
        # feature names of the word part only (readable); char n-grams are counted but not listed
        word = dict(self.features.transformer_list)["word_tfidf"]
        self.word_names = np.asarray(word.get_feature_names_out())
        self.n_word = len(self.word_names)

    def explain(self, text: str, top: int = 6) -> dict:
        text = clean_text(text)
        x = self.features.transform([text])
        scores = self.classifier.decision_function(x)[0]
        label = self.classes[int(np.argmax(scores))]
        row = x.tocsr()[0]
        idx, val = row.indices, row.data
        coef = self.classifier.coef_[self.classes.index(label)]
        contrib = val * coef[idx]
        word_mask = idx < self.n_word
        order = np.argsort(-contrib[word_mask])
        words = [(self.word_names[idx[word_mask][i]], float(contrib[word_mask][i]))
                 for i in order[:top] if contrib[word_mask][i] > 0]
        return {"text": text, "label": label, "scores": dict(zip(self.classes, map(float, scores))), "words": words}


def show(result: dict) -> None:
    print(f"\n  => {LABEL_VI.get(result['label'], result['label'])}")
    ranked = sorted(result["scores"].items(), key=lambda kv: -kv[1])
    print("  Điểm từng lớp: " + "  ".join(f"{k} {v:+.2f}" for k, v in ranked))
    if result["words"]:
        print("  Từ/cụm từ đẩy về phía này: " + ", ".join(f"'{w}'" for w, _ in result["words"]))
    print()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup", default="bilingual", help="bilingual (default) | vietnamese_balanced | english_balanced")
    parser.add_argument("--text", help="one message; omit for interactive mode")
    args = parser.parse_args()

    tier1 = Tier1(args.setup)
    if args.text:
        show(tier1.explain(args.text))
        return
    print(f"Tầng 1 – Linear SVM ({args.setup}). Gõ tin nhắn rồi Enter; gõ q để thoát.")
    while True:
        try:
            text = input("Tin nhắn> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"q", "quit", "exit"}:
            break
        if text:
            show(tier1.explain(text))


if __name__ == "__main__":
    main()
