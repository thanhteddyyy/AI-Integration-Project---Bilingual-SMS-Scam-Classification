"""Language identification vi / en for routing a scam message to the tier-2 model of its language.

Character n-gram Naive Bayes (classic, fast, no external model). Two things keep it honest:
  * `langid_preprocess` removes what differs by DATA SOURCE, not by language: placeholders ([NUMBER],
    <URL> ...), URLs, e-mails and digits. Otherwise "[NUMBER] = Vietnamese, <PHONE> = English" would be learned.
  * Vietnamese without diacritics: every Vietnamese training text is added a second time with the
    diacritics removed (`strip_vietnamese_accents`), so "Tai khoan cua ban bi khoa" is still Vietnamese.
"""
from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from .data.masking import PLACEHOLDER_RE, URL_RE

LANGUAGES = ("en", "vi")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_DIGIT_RE = re.compile(r"\d+")
_SPACE_RE = re.compile(r"\s+")


def langid_preprocess_one(text: str) -> str:
    text = PLACEHOLDER_RE.sub(" ", str(text))
    text = URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = _DIGIT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip().lower()


def langid_preprocess(texts) -> list[str]:
    return [langid_preprocess_one(t) for t in texts]


def build_langid_model(alpha: float = 0.1) -> Pipeline:
    return Pipeline([
        ("prep", FunctionTransformer(langid_preprocess, validate=False)),
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3), min_df=2, sublinear_tf=True,
                                  max_features=50000, dtype=np.float32)),
        ("nb", MultinomialNB(alpha=alpha)),
    ])
