"""List English messages whose label probably disagrees with definition_of_ham_spam_scam.md (Q8).

Nothing is changed: the output is a review file; fill ``review_label`` (legitimate / spam / scam /
keep) and a later step can apply it the same way as the Vietnamese v3 review.

Rules (suggestions only):
  R1 spam -> scam : fake prize / lottery ("won", "winner", "prize", "lucky draw", "claim" ...) with a
                    way to act (call, text, link, reply)                       – definition 3.3
  R2 spam -> scam : credential / account cues (verify, suspended, password, KYC ...) with a link  – 1.1
  R3 scam -> spam : promotional offer (half price, line rental, ringtone, free entry, subscription,
                    "txt STOP") with no prize / credential / impersonation cue  – 2.x
Usage: python scripts/flag_en_label_review.py   (needs data/processed/master_manifest.csv)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ["train", "validation", "test", "external_test"]

PRIZE = re.compile(r"(?i)\b(won|winner|winning|prize|lucky draw|lottery|jackpot|cash award|reward(?:ed)?|"
                   r"congratulations?|congrats|selected to receive|guaranteed (?:cash|prize|£|\$))\b")
ACTION = re.compile(r"(?i)\b(call|claim|text|txt|reply|click|visit|redeem)\b|<URL>|<PHONE>")
CREDENTIAL = re.compile(r"(?i)\b(verify|verification|suspend(?:ed)?|locked|password|pin|kyc|login|log in|"
                        r"unusual activity|confirm your (?:account|identity|details)|account (?:has been|will be))\b")
LINK = re.compile(r"(?i)<URL>|https?://|www\.")
PROMO = re.compile(r"(?i)\b(half price|line rental|ringtone|free entry|subscribe|subscription|offer|discount|"
                   r"sale|% off|txt stop|text stop|reply stop|opt ?out|unsubscribe|mobile update|camera phone)\b")
IMPERSONATION = re.compile(r"(?i)\b(bank|irs|hmrc|usps|fedex|dhl|royal mail|amazon|paypal|apple|netflix|"
                           r"customer care|police|tax)\b")


def suggest(label: str, text: str) -> tuple[str, str] | None:
    if label == "spam" and PRIZE.search(text) and ACTION.search(text):
        return "scam", "R1 fake prize/lottery + call-to-action (3.3)"
    if label == "spam" and CREDENTIAL.search(text) and LINK.search(text):
        return "scam", "R2 credential/account cue + link (1.1)"
    if (label == "scam" and PROMO.search(text) and not PRIZE.search(text)
            and not CREDENTIAL.search(text) and not IMPERSONATION.search(text)):
        return "spam", "R3 promotional offer, no prize/credential/impersonation (2.x)"
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = pd.read_csv(ROOT / "data" / "processed" / "master_manifest.csv", dtype=str, keep_default_na=False)
    active = manifest[manifest["split"].isin(ACTIVE)]
    rows = []
    for _, row in active.iterrows():
        hit = suggest(row["label_level_1"], row["text_clean"])
        if hit:
            rows.append({
                "sample_id": row["sample_id"], "source_dataset": row["source_dataset"], "split": row["split"],
                "group_id": row["group_id"], "text": row["text_clean"], "current_label": row["label_level_1"],
                "suggested_label": hit[0], "rule": hit[1], "review_label": "", "review_note": "",
            })
    out = pd.DataFrame(rows)
    path = ROOT / "data" / "review" / "en_label_review_candidates.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{len(out)} candidates -> {path}")
    if not out.empty:
        print(out.groupby(["rule", "source_dataset"]).size().to_string())
        print("unique groups:", out["group_id"].nunique())


if __name__ == "__main__":
    main()
