from __future__ import annotations

import hashlib
import html
import re
import unicodedata


URL_RE = re.compile(
    r"(?i)(?:https?://|www\.)\S+|"
    r"\b[a-z0-9][a-z0-9.-]+\.(?:com|org|net|io|co|ly|me|uk|vn|info|biz)"
    r"(?:/\S*)?"
)
EMAIL_RE = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{5,}\d)(?!\w)")
DIGIT_RE = re.compile(r"\d+")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: object) -> str:
    """Conservative model text cleaning.

    The function keeps URLs, digits, punctuation, and suspicious characters in
    the model input. URL/number masking is only used for duplicate grouping.
    """

    if value is None:
        return ""
    text = html.unescape(str(value))
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        " " if unicodedata.category(char).startswith("C") else char for char in text
    )
    return WHITESPACE_RE.sub(" ", text).strip()


def strict_duplicate_key(text: str) -> str:
    return unicodedata.normalize("NFKC", clean_text(text)).casefold()


def template_duplicate_key(
    text: str,
    *,
    mask_urls: bool = True,
    mask_emails: bool = True,
    mask_numbers: bool = True,
) -> str:
    value = strict_duplicate_key(text)
    if mask_urls:
        value = URL_RE.sub(" <url> ", value)
    if mask_emails:
        value = EMAIL_RE.sub(" <email> ", value)
    if mask_numbers:
        value = PHONE_RE.sub(" <number> ", value)
        value = DIGIT_RE.sub("<number>", value)
    value = re.sub(r"[^\w<>]+", " ", value, flags=re.UNICODE)
    return WHITESPACE_RE.sub(" ", value).strip()


def stable_hash(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def text_quality_flags(text: str) -> dict[str, bool]:
    return {
        "has_url": bool(URL_RE.search(text) or "<URL>" in text.upper()),
        "has_email": bool(EMAIL_RE.search(text)),
        "has_phone": bool(PHONE_RE.search(text)),
        "has_replacement_character": "\ufffd" in text,
    }

