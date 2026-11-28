"""Mask numbers the way the TRAINING data was masked, so a raw message typed in the demo looks like the data
the models learned from.

* Vietnamese (`mask_vi`): same placeholders as the Tuan set and the crawled scams ([NUMBER] [MONEY] [TIME]
  [DATE]); URLs are kept because they are features. A copy of `mask_pii` in scripts/crawl_vi_scam.py (the
  crawler must stay a single standalone file for Kaggle); tests/test_masking.py checks both agree.
* English: `scam_baseline.data.adapters.normalize_en_placeholders` (<URL> <PHONE> <EMAIL> <DATE_TIME> <NUMBER>).
"""
from __future__ import annotations

import re

URL_PATTERN = (
    r"(?:https?://\S+|www\.\S+|\b[a-z0-9][a-z0-9-]{1,62}(?:\.[a-z0-9-]{2,62})*"
    r"\.(?:vn|com|net|org|info|top|xyz|vip|online|site|link|cc|me|io|shop|club|icu|live|app|"
    r"asia|tech|store|bond|buzz|sbs|cfd|ly|gl)\b(?:/\S*)?)"
)
URL_RE = re.compile(URL_PATTERN, re.IGNORECASE)
URL_SPLIT_RE = re.compile(f"({URL_PATTERN})", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<![\w/])(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?![\w/])")
BANK_ACC_RE = re.compile(r"(?i)((?:stk|số tài khoản|so tai khoan|tk)\s*[:.]?\s*)\d[\d\s.\-]{6,20}\d")
MONEY_RE = re.compile(
    r"(?i)\b\d[\d.,]*\s*(?:đồng|dong|vnđ|vnd|đ|d|triệu|trieu|tr|tỷ|ty|nghìn|nghin|k)(?!\w)")
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d(?:[:][0-5]\d)?\b")
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
LONG_NUMBER_RE = re.compile(r"(?<![\w\[])\d{6,}(?![\w\]])")

# every placeholder used by any source (Vietnamese [X], English <X>)
PLACEHOLDER_RE = re.compile(r"\[[A-Z_]+\]|<[A-Z_]+>")


def mask_vi(text: str) -> str:
    """Vietnamese masking, identical to the crawler's mask_pii (Tuan-set placeholders, URLs untouched)."""
    masked = []
    for part in URL_SPLIT_RE.split(str(text)):
        if not part:
            continue
        if URL_RE.fullmatch(part):
            masked.append(part)
            continue
        part = BANK_ACC_RE.sub(lambda m: m.group(1) + "[NUMBER]", part)
        part = PHONE_RE.sub("[NUMBER]", part)
        part = MONEY_RE.sub("[MONEY]", part)
        part = TIME_RE.sub("[TIME]", part)
        part = DATE_RE.sub("[DATE]", part)
        part = LONG_NUMBER_RE.sub("[NUMBER]", part)
        masked.append(part)
    return "".join(masked)
