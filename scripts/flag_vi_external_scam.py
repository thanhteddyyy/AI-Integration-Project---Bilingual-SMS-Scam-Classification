"""A1 - Find scam messages hidden inside the Vietnamese external-test "spam" rows.

The two Vietnamese external sources (vie_sms_corpus, social_spam_post) were only
labelled spam/ham, so fraud messages were merged into "spam". This script scores
every external spam row for scam signals and writes a REVIEW FILE. Nothing is
relabelled automatically: a person confirms each row, then the reviewed file is
fed back into the pipeline.

Output (one row per duplicate group, so each template is reviewed once):
    data/review/vi_external_spam_review.csv

    python scripts/flag_vi_external_scam.py
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "processed_vi_3class" / "modeling_data.csv"
OUTPUT = ROOT / "data" / "review" / "vi_external_spam_review.csv"

SCAM_THRESHOLD = 3      # score >= 3  -> suggested "scam"
UNCERTAIN_THRESHOLD = 1  # 1..2        -> "uncertain" (review carefully)


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("đ", "d").replace("Đ", "D").lower()


def rx(pattern: str) -> re.Pattern:
    return re.compile(pattern)


# Rules run on accent-stripped lowercase text: (name, regex, weight, scam_type or "").
# Positive = fraud signal, negative = ordinary advertising signal.
RULES = [
    # Credential / account takeover
    ("credential_request", rx(r"dang nhap|xac thuc|xac minh|mat khau|\botp\b|ma pin|thong tin the|cap nhat thong tin|kich hoat lai"), 3, "banking_finance"),
    ("account_threat", rx(r"(khoa|tam ngung|vo hieu|thu hoi|cat) (tai khoan|sim|thue bao|dich vu)|bi khoa|se bi (khoa|cat|huy)"), 2, "telecom_account"),
    ("suspicious_domain", rx(r"\.(top|icu|xyz|vip|cc|online|site|club|buzz|link|tk|ml|ga|cf|gq|live|shop)\b|[a-z]+\.(com|vn)-[a-z0-9]+|-vn\.(com|net)"), 3, ""),
    ("short_link", rx(r"bit\.ly|tinyurl|goo\.gl|t\.ly|cutt\.ly|is\.gd"), 1, ""),
    ("bank_or_wallet", rx(r"vietcombank|\bvcb\b|vietinbank|techcombank|\bacb\b|mbbank|tpbank|sacombank|bidv|vpbank|agribank|\bshb\b|\bvib\b|hdbank|momo|zalopay|ngan hang"), 1, "banking_finance"),
    ("government", rx(r"cong an|canh sat|toa an|vien kiem sat|vneid|dich vu cong|bhxh|phat nguoi|vi pham giao thong|thue (thu nhap|tncn)|hoan thue|can cuoc"), 2, "government_services"),
    ("delivery", rx(r"buu (pham|kien|dien)|giao hang (that bai|khong thanh cong)|don hang (cua ban|bi)|phi (van chuyen|giao hang)"), 2, "delivery_logistics"),
    # Prize / advance-fee / premium-rate lures (common 2014-2016 Vietnamese SMS scams)
    ("prize_lure", rx(r"trung thuong|trung giai|nhan thuong|giai thuong|qua tang (tri an|dac biet)|duoc chon|chuc mung (ban|quy khach).{0,40}(trung|nhan|duoc)|gianh chien thang|da thang|giai (doc dac|nhat)"), 2, "prize_lottery"),
    ("advance_fee", rx(r"(nop|dong|chuyen) (phi|le phi|tien) (de|truoc|nhan|lam)|phi (nhan thuong|lam ho so|thu tuc)|dat coc|chuyen khoan truoc"), 3, "prize_lottery"),
    # Premium-rate lure: "someone sent you a song / a secret message, call 1900xxxx to hear it".
    ("premium_callback", rx(r"go[ij] (ngay )?(1900|0900|09\d{2}\s?\d{3})|1900\d{4}.{0,40}(nghe|loi nhan|bai hat|tam su)|(nghe|loi nhan|bai hat|tam su|nguoi ay|bi mat|muon noi).{0,80}(1900|8\d77)"), 3, "other_scam"),
    # Paid "guaranteed" lottery tips sold through premium SMS shortcodes.
    ("lottery_tip_fraud", rx(r"(bach thu|chot so|cau lo|song thu|dan de|lo de|cau qua vip).{0,120}(soan|gui)|(dam bao|chac chan|chac an|cam chac).{0,40}(trung|an|100|tien ve)"), 3, "other_scam"),
    ("job_task", rx(r"viec lam (tai nha|online)|cong tac vien|\bctv\b|hoa hong|lam nhiem vu|thu nhap (cao|hap dan|\d)|tuyen (gap|dung) .{0,30}(online|tai nha)"), 2, "job_task_scam"),
    ("investment", rx(r"dau tu|loi nhuan|tien ao|\bcoin\b|forex"), 1, "investment"),  # weak: real-estate ads say this too
    ("guaranteed_return", rx(r"cam ket (loi nhuan|lai \d|sinh loi)|loi nhuan \d+ ?% ?/? ?(ngay|tuan|thang)|lai suat \d+ ?% ?/? ?(ngay|tuan)"), 2, "investment"),
    ("impersonation_borrow", rx(r"(cho|cho em|cho anh|cho chi) muon|chuyen giup|nap giup|mua giup the|ma the cao"), 2, "social_impersonation"),
    # Ordinary advertising (lowers the score)
    ("ad_tag", rx(r"^\s*[\[(]?\s*(qc|tb|km|tb-km)\b|\bqc\b"), -1, ""),
    ("opt_out", rx(r"tu choi (qc|nhan)|soan (tc|no|huy|tuchoi) gui|de huy"), -2, ""),
    ("operator_promo", rx(r"nap the|goi cuoc|\bdata\b|\b(3g|4g)\b|\bkm\b|khuyen mai|uu dai|giam gia|mien phi .{0,15}(phut|sms|gb|mb)"), -1, ""),
]

# social_spam_post is a machine translation of the English UCI SMS Spam Collection
# (UK shortcodes, pounds, "FA Cup Final 87121" ...), the same corpus that is in the
# English sms_phishing train data. It was removed from the Vietnamese external test,
# so it is left out of the review file.
EXCLUDED_SOURCES = {"social_spam_post"}


def score_message(text: str) -> tuple[int, str, list[str]]:
    plain = strip_accents(text)
    score = 0
    reasons: list[str] = []
    type_votes: dict[str, int] = {}
    for name, pattern, weight, scam_type in RULES:
        if pattern.search(plain):
            score += weight
            reasons.append(f"{name}({weight:+d})")
            if weight > 0 and scam_type:
                type_votes[scam_type] = type_votes.get(scam_type, 0) + weight
    scam_type = max(type_votes, key=type_votes.get) if type_votes else "other_scam"
    return score, scam_type, reasons


def main() -> None:
    frame = pd.read_csv(INPUT, low_memory=False)
    spam = frame[
        (frame["split"] == "external_test")
        & (frame["label_level_1"] == "spam")
        & ~frame["source_dataset"].isin(EXCLUDED_SOURCES)
    ].copy()
    print(f"External-test Vietnamese spam rows: {len(spam):,} ({spam['group_id'].nunique():,} duplicate groups)")

    scored = spam["text_clean"].astype(str).map(score_message)
    spam["scam_score"] = [s for s, _, _ in scored]
    spam["scam_type_suggested"] = [t for _, t, _ in scored]
    spam["reasons"] = [" ".join(r) for _, _, r in scored]
    spam["suggested_label"] = pd.cut(
        spam["scam_score"],
        bins=[-100, UNCERTAIN_THRESHOLD - 1, SCAM_THRESHOLD - 1, 100],
        labels=["spam", "uncertain", "scam"],
    ).astype(str)
    spam.loc[spam["suggested_label"].eq("spam"), "scam_type_suggested"] = ""

    # One row per duplicate group: the reviewer labels a template once, the label
    # is later applied to every member of the group (keeps group_id consistent).
    spam["group_size"] = spam.groupby("group_id")["sample_id"].transform("size")
    spam["group_member_ids"] = spam.groupby("group_id")["sample_id"].transform(lambda s: ";".join(s))
    review = spam.sort_values("scam_score", ascending=False).drop_duplicates("group_id", keep="first")
    review["_rank"] = review["suggested_label"].map({"scam": 0, "uncertain": 1, "spam": 2})
    review = review.sort_values(["_rank", "scam_score"], ascending=[True, False])  # most likely scam first
    review["review_label"] = ""
    review["review_scam_type"] = ""
    review["review_note"] = ""
    columns = [
        "group_id", "group_size", "source_dataset", "text_clean",
        "scam_score", "suggested_label", "scam_type_suggested", "reasons",
        "review_label", "review_scam_type", "review_note", "group_member_ids",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    review[columns].to_csv(OUTPUT, index=False, encoding="utf-8-sig")  # BOM: opens cleanly in Excel

    print(f"\nReview file: {OUTPUT}  ({len(review):,} groups)")
    print("\nSuggested label by source (groups):")
    print(pd.crosstab(review["source_dataset"], review["suggested_label"], margins=True).to_string())
    print("\nSuggested scam_type (scam + uncertain groups):")
    print(review.loc[review["suggested_label"] != "spam", "scam_type_suggested"].value_counts().to_string())
    for label in ("scam", "uncertain"):
        print(f"\nTop examples - {label}:")
        for _, row in review[review["suggested_label"] == label].head(6).iterrows():
            print(f"  [{row['scam_score']:+d}] {row['source_dataset']:<16} {row['text_clean'][:120]}")


if __name__ == "__main__":
    main()
