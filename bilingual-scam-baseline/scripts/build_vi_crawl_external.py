"""Turn reviewed crawl files into the Vietnamese real-scam external test set.

Inputs (default: every data/review/vi_crawl_run*_clean.csv / *_reviewed.csv):
  * run-1 format  (data/review/vi_crawl_run1_clean.csv): message, review_label, review_scam_type,
    review_channel, use_for_external (yes / maybe / no)
  * crawler v2 format (vi_scam_candidates.csv exported from review.html): message, review_label,
    review_scam_type, review_channel (or channel_suggested), reject_reason

Rules:
  * keep rows whose review_label is scam / spam / legitimate (empty or 'drop' rows are skipped)
  * keep only the channels in --channels (default: sms). Zalo/Messenger stay in the review files.
  * run-1 rows need use_for_external == yes (add --include-maybe for 'maybe')
  * mask PII exactly like the crawler / Tuan set ([NUMBER] [MONEY] [TIME] [DATE]; URLs kept)
  * drop duplicates inside the crawl (pipeline template key)
  * drop rows of the same template family as ANY Tuan message (train or test): word 3-gram
    Jaccard >= --family-jaccard, the same rule as apply_vi_labels_v3.py (option B)

Outputs:
  data/raw/vi_crawl_external.csv                 rows for the pipeline (dataset name: vi_crawl)
  data/review/vi_crawl_external_excluded.csv     every skipped row with the reason
"""
from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from scam_baseline.data.clean import template_duplicate_key  # noqa: E402
from apply_vi_labels_v3 import FAMILY_JACCARD, shingles  # noqa: E402


def _import_mask_pii():
    """mask_pii lives in the crawler, which imports requests/bs4 at module level (not needed here)."""
    for name, attrs in (("requests", {"Session": object}), ("bs4", {"BeautifulSoup": object})):
        if name not in sys.modules:
            try:
                __import__(name)
            except ModuleNotFoundError:
                stub = types.ModuleType(name)
                for key, value in attrs.items():
                    setattr(stub, key, value)
                sys.modules[name] = stub
    from crawl_vi_scam import mask_pii
    return mask_pii


mask_pii = _import_mask_pii()

REVIEW = ROOT / "data" / "review"
VALID = {"scam", "spam", "legitimate"}


def default_inputs() -> list[Path]:
    return sorted(set(REVIEW.glob("vi_crawl_run*_clean.csv")) | set(REVIEW.glob("vi_crawl_run*_reviewed.csv")))


def load_input(path: Path, include_maybe: bool) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    out = pd.DataFrame({
        "crawl_id": df.get("candidate_id", pd.Series(range(len(df)))).astype(str),
        "message_in": df["message"],
        "label_3class": df.get("review_label", "").str.strip().str.lower(),
        "scam_type": df.get("review_scam_type", "").str.strip(),
        "channel": (df["review_channel"] if "review_channel" in df else df.get("channel_suggested", "")).str.strip().str.lower(),
        "source_url": df.get("source_url", ""),
        "input_file": path.name,
    })
    out["skip_reason"] = ""
    if "use_for_external" in df:
        allowed = {"yes", "maybe"} if include_maybe else {"yes"}
        out.loc[~df["use_for_external"].str.strip().str.lower().isin(allowed), "skip_reason"] = "use_for_external_not_yes"
    return out


def build(inputs: list[Path], channels: set[str], include_maybe: bool, threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [load_input(p, include_maybe) for p in inputs]
    if not frames:
        raise SystemExit("no reviewed crawl files found in data/review/")
    df = pd.concat(frames, ignore_index=True)
    df.loc[(df.skip_reason == "") & ~df.label_3class.isin(VALID), "skip_reason"] = "not_labelled_or_drop"
    df.loc[(df.skip_reason == "") & ~df.channel.isin(channels), "skip_reason"] = "channel_not_" + "_".join(sorted(channels))
    df["message"] = df["message_in"].map(lambda t: mask_pii(str(t)).strip())
    df.loc[(df.skip_reason == "") & (df.message == ""), "skip_reason"] = "empty"
    df.loc[df.label_3class != "scam", "scam_type"] = "none"

    keys = df["message"].map(template_duplicate_key)
    dup = keys.duplicated() & (df.skip_reason == "")
    # only count a duplicate against rows that are themselves kept
    seen: set[str] = set()
    for idx in df.index:
        if df.at[idx, "skip_reason"]:
            continue
        if keys[idx] in seen:
            df.at[idx, "skip_reason"] = "duplicate_in_crawl"
        seen.add(keys[idx])

    tuan = pd.read_csv(ROOT / "data" / "raw" / "full_dataset_spamscam.csv", encoding="utf-8-sig")
    tuan_sets = [shingles(t) for t in tuan["message"]]
    best_sim, best_text = [], []
    for text in df["message"]:
        s = shingles(text)
        sims = [len(s & t) / len(s | t) if s | t else 0.0 for t in tuan_sets]
        i = max(range(len(sims)), key=sims.__getitem__)
        best_sim.append(round(sims[i], 3))
        best_text.append(tuan["message"].iat[i][:160])
    df["overlap_tuan_sim"] = best_sim
    df["overlap_tuan_nearest"] = best_text
    df.loc[(df.skip_reason == "") & (df.overlap_tuan_sim >= threshold), "skip_reason"] = "same_family_as_tuan"

    kept = df[df.skip_reason == ""].reset_index(drop=True)
    cols = ["crawl_id", "message", "label_3class", "scam_type", "channel", "source_url", "input_file", "overlap_tuan_sim"]
    return kept[cols], df[df.skip_reason != ""].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", nargs="*", type=Path, help="reviewed crawl CSVs (default: data/review/vi_crawl_run*)")
    parser.add_argument("--channels", nargs="+", default=["sms"])
    parser.add_argument("--include-maybe", action="store_true")
    parser.add_argument("--family-jaccard", type=float, default=FAMILY_JACCARD)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "raw" / "vi_crawl_external.csv")
    args = parser.parse_args()

    inputs = args.inputs or default_inputs()
    kept, excluded = build(inputs, set(args.channels), args.include_maybe, args.family_jaccard)
    kept.to_csv(args.out, index=False, encoding="utf-8-sig")
    excluded.to_csv(REVIEW / "vi_crawl_external_excluded.csv", index=False, encoding="utf-8-sig")
    print("inputs:", [p.name for p in inputs])
    print(f"kept {len(kept)} rows -> {args.out}")
    print("  by label:", kept["label_3class"].value_counts().to_dict())
    print("  scam_type:", kept.loc[kept.label_3class == "scam", "scam_type"].value_counts().to_dict())
    print("excluded:", excluded["skip_reason"].value_counts().to_dict())


if __name__ == "__main__":
    main()
