"""Try the full pipeline (tier 1 -> language -> tier 2) on your own messages in the terminal.

Usage (from the repository root):
  $env:PYTHONPATH="src"; py -3.11 scripts/try_pipeline.py                      # interactive
  $env:PYTHONPATH="src"; py -3.11 scripts/try_pipeline.py --text "Tai khoan cua ban bi khoa..."
  $env:PYTHONPATH="src"; py -3.11 scripts/try_pipeline.py --text "..." --json  # raw dict (what the demo gets)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.predict import ScamDetector  # noqa: E402


def show(r: dict) -> None:
    if r.get("label") is None:
        print("  (tin rỗng)")
        return
    print(f"\n  Ngôn ngữ: {r['language']} ({r['language_confidence']:.2f})")
    print(f"  => {r['label_vi']}   [điểm: " + ", ".join(f"{k} {v:+.2f}" for k, v in
                                                       sorted(r["label_scores"].items(), key=lambda kv: -kv[1]))
          + f"; chênh {r['label_margin']:.2f}]")
    if r["tier1_top_words"]:
        print("     từ/cụm từ đẩy về phía này: " + ", ".join(f"'{w}'" for w, _ in r["tier1_top_words"]))
    if r["scam_type"]:
        print(f"  Loại lừa đảo: {r['scam_type_vi']}  ({r['scam_group_vi']}; chênh {r['scam_type_margin']:.2f})")
        if r["tier2_top_words"]:
            print("     từ/cụm từ đặc trưng: " + ", ".join(f"'{w}'" for w, _ in r["tier2_top_words"]))
        print(f"  Lời khuyên: {r['advice']}")
    for w in r["warnings"]:
        print(f"  ⚠ {w}")
    for n in r["notes"]:
        print(f"  ℹ {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text")
    parser.add_argument("--json", action="store_true", help="print the raw result dict")
    parser.add_argument("--artifacts", type=Path, help="models folder (default: <repo>/artifacts)")
    args = parser.parse_args()
    detector = ScamDetector(args.artifacts)
    if args.text:
        r = detector.predict(args.text)
        print(json.dumps(r, ensure_ascii=False, indent=2)) if args.json else show(r)
        return
    print("Nhập tin nhắn (Enter trống để thoát):")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            break
        if not text:
            break
        show(detector.predict(text))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
