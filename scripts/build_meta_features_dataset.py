from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    class StandardScaler:  # type: ignore[no-redef]
        """Exact drop-in StandardScaler (zero mean, unit variance, ddof=0)."""

        def __init__(self) -> None:
            self.mean_: np.ndarray | None = None
            self.scale_: np.ndarray | None = None

        def fit(self, X: pd.DataFrame | np.ndarray) -> "StandardScaler":
            arr = np.asarray(X, dtype=np.float64)
            self.mean_ = np.mean(arr, axis=0)
            scale = np.std(arr, axis=0, ddof=0)
            self.scale_ = np.where(scale == 0.0, 1.0, scale)
            return self

        def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
            if self.mean_ is None or self.scale_ is None:
                raise RuntimeError("StandardScaler is not fitted yet.")
            arr = np.asarray(X, dtype=np.float64)
            return (arr - self.mean_) / self.scale_

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


META_FEATURE_COLS = [
    "msg_length",
    "url_count",
    "digit_count",
    "special_char_ratio",
    "urgent_word_count",
]

# Regex patterns for feature extraction on text_raw
URL_IP_RE = re.compile(
    r"(?i)(?:https?://\S+|www\.\S+|\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|org|net|io|co|ly|me|uk|vn|info|biz|top|vip|xyz|club|online|site|link|vc|in)\b(?:/\S*)?|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|<URL>|<IP_ADDRESS>)"
)

DIGIT_RE = re.compile(r"\d")

SPECIAL_CHAR_RE = re.compile(r"[$£€₫%!&?*#@/:<>]")

URGENT_KEYWORDS_RE = re.compile(
    r"(?i)\b(?:"
    # English psychological manipulation / scam keywords
    r"otp|bank|banking|urgent|urgently|verify|verification|account|click|suspend|suspended|"
    r"lock|locked|compromised|unauthorized|unauthorised|confirm|immediately|alert|security|"
    r"update|delivery|package|parcel|warehouse|usps|ups|fedex|dhl|irs|hmrc|tax|refund|"
    r"claim|prize|winner|won|free|cash|bonus|voucher|urgent|"
    # Vietnamese psychological manipulation / scam keywords (with and without diacritics)
    r"tài\s*khoản|tai\s*khoan|khóa|khoa|tạm\s*ngưng|tam\s*ngung|vĩnh\s*viễn|vinh\s*vien|"
    r"trúng\s*thưởng|trung\s*thuong|khẩn|khan|xác\s*thực|xac\s*thuc|xác\s*minh|xac\s*minh|"
    r"ngân\s*hàng|ngan\s*hang|cấp\s*cứu|cap\s*cuu|chuyển\s*nhầm|chuyen\s*nham|"
    r"hoàn\s*thuế|hoan\s*thue|sinh\s*trắc\s*học|sinh\s*trac\s*hoc|đăng\s*nhập|dang\s*nhap|"
    r"vietcombank|techcombank|vpbank|bidv|mbbank|mb\s*bank|acb|sacombank|vietinbank|tpbank|agribank"
    r")\b"
)


def extract_raw_meta_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the 5 statistical meta-features directly from text_raw."""
    texts = df["text_raw"].fillna("").astype(str)

    msg_length = texts.str.len().astype(np.float64)
    url_count = texts.map(lambda t: len(URL_IP_RE.findall(t))).astype(np.float64)
    digit_count = texts.map(lambda t: len(DIGIT_RE.findall(t))).astype(np.float64)
    special_count = texts.map(lambda t: len(SPECIAL_CHAR_RE.findall(t))).astype(np.float64)
    special_char_ratio = np.where(msg_length > 0, special_count / msg_length, 0.0)
    urgent_word_count = texts.map(lambda t: len(URGENT_KEYWORDS_RE.findall(t))).astype(np.float64)

    return pd.DataFrame(
        {
            "msg_length": msg_length,
            "url_count": url_count,
            "digit_count": digit_count,
            "special_char_ratio": special_char_ratio,
            "urgent_word_count": urgent_word_count,
        },
        index=df.index,
    )


def build_base_and_meta_datasets(project_root: Path) -> None:
    out_dir = project_root / "data" / "processed_bilingual"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_manifest = out_dir / "master_manifest.csv"
    base_path = out_dir / "master_dataset_base.csv"
    meta_path = out_dir / "modeling_data_with_meta.csv"

    print("=" * 72)
    print("STEP 1: LOCK & SAVE BASE MASTER DATASET (master_dataset_base.csv)")
    print("=" * 72)
    df_base = pd.read_csv(source_manifest, low_memory=False)

    # If base_path already exists and is read-only, temporarily make writable only if missing
    if not base_path.exists():
        df_base.to_csv(base_path, index=False, encoding="utf-8")
        # Set Read-Only permission flag on master_dataset_base.csv
        os.chmod(base_path, stat.S_IREAD)
        print(f"Saved and locked READ-ONLY base dataset: {base_path}")
    else:
        print(f"Base dataset already exists and is locked READ-ONLY: {base_path}")

    # Reload strictly from the locked master_dataset_base.csv to guarantee fidelity
    df_locked = pd.read_csv(base_path, low_memory=False)
    print(f"Base dataset shape: {df_locked.shape[0]:,} rows x {df_locked.shape[1]} columns")
    print("Sources present:", df_locked["source_dataset"].value_counts().to_dict())
    print("Classes present:", df_locked["label_level_1"].value_counts().to_dict())

    print("\n" + "=" * 72)
    print("STEP 2: FEATURE ENGINEERING ON IN-MEMORY COPY (FROM text_raw)")
    print("=" * 72)
    df_copy = df_locked.copy(deep=True)
    raw_features = extract_raw_meta_features(df_copy)

    print("Raw Meta-Features Summary (Before Scaling):")
    print(raw_features.describe().T[["mean", "std", "min", "50%", "max"]].to_string())

    # Calculate correlation with scam label (is_scam = 1 if label_level_1 == 'scam' else 0)
    is_scam = (df_copy["label_level_1"] == "scam").astype(int)
    corr_df = raw_features.copy()
    corr_df["is_scam"] = is_scam

    print("\n" + "=" * 72)
    print("STEP 3: ANTI-LEAKAGE NORMALIZATION (FIT ON TRAIN ONLY)")
    print("=" * 72)
    train_mask = df_copy["split"] == "train"
    non_train_mask = ~train_mask

    scaler = StandardScaler()
    # Fit strictly on train split only
    scaler.fit(raw_features.loc[train_mask, META_FEATURE_COLS])
    print(f"Fitted StandardScaler strictly on {int(train_mask.sum()):,} TRAIN rows.")
    for col, mean_val, scale_val in zip(META_FEATURE_COLS, scaler.mean_, scaler.scale_):
        print(f"  - {col:<20}: train_mean = {mean_val:8.4f} | train_std = {scale_val:8.4f}")

    # Transform train and non-train splits using the train-fitted scaler
    scaled_values = pd.DataFrame(
        index=df_copy.index, columns=META_FEATURE_COLS, dtype=np.float64
    )
    scaled_values.loc[train_mask, META_FEATURE_COLS] = scaler.transform(
        raw_features.loc[train_mask, META_FEATURE_COLS]
    )
    scaled_values.loc[non_train_mask, META_FEATURE_COLS] = scaler.transform(
        raw_features.loc[non_train_mask, META_FEATURE_COLS]
    )

    print("\n" + "=" * 72)
    print("STEP 4: REPACKAGE DERIVED DATASET (modeling_data_with_meta.csv)")
    print("=" * 72)
    for col in META_FEATURE_COLS:
        df_copy[col] = scaled_values[col]

    # Verify text_clean was 100% untouched
    assert (df_copy["text_clean"].fillna("") == df_locked["text_clean"].fillna("")).all(), (
        "CRITICAL ERROR: text_clean was modified!"
    )
    print("Verified: text_clean is 100% identical to master_dataset_base.csv.")

    df_copy.to_csv(meta_path, index=False, encoding="utf-8")
    print(f"Saved derived dataset with meta-features to: {meta_path}")

    print("\n" + "=" * 72)
    print("STEP 5: AUDIT COMPARISON & CORRELATION REPORT")
    print("=" * 72)
    df_verify_base = pd.read_csv(base_path, low_memory=False)
    df_verify_meta = pd.read_csv(meta_path, low_memory=False)

    print(f"1. File master_dataset_base.csv     : {df_verify_base.shape[0]:,} rows x {df_verify_base.shape[1]} columns")
    print(f"2. File modeling_data_with_meta.csv : {df_verify_meta.shape[0]:,} rows x {df_verify_meta.shape[1]} columns")
    print(f"   Added columns ({len(META_FEATURE_COLS)}): {META_FEATURE_COLS}")

    # Correlation on the new file between the 5 meta-features and binary scam target
    df_verify_meta["is_scam"] = (df_verify_meta["label_level_1"] == "scam").astype(int)
    df_verify_meta["is_spam"] = (df_verify_meta["label_level_1"] == "spam").astype(int)
    df_verify_meta["is_legitimate"] = (df_verify_meta["label_level_1"] == "legitimate").astype(int)

    target_cols = META_FEATURE_COLS + ["is_scam", "is_spam", "is_legitimate"]
    pearson_corr = df_verify_meta[target_cols].corr(method="pearson")
    spearman_corr = df_verify_meta[target_cols].rank().corr(method="pearson")

    corr_summary = pd.DataFrame({
        "Pearson_r (vs scam)": pearson_corr["is_scam"].loc[META_FEATURE_COLS],
        "Spearman_rho (vs scam)": spearman_corr["is_scam"].loc[META_FEATURE_COLS],
        "Pearson_r (vs spam)": pearson_corr["is_spam"].loc[META_FEATURE_COLS],
        "Pearson_r (vs legitimate)": pearson_corr["is_legitimate"].loc[META_FEATURE_COLS],
    })
    print("\n=== Correlation Table of 5 Meta-Features with Labels (Full Dataset) ===")
    print(corr_summary.round(4).to_string())

    # Group means by class (unscaled raw features for interpretability + scaled features)
    raw_with_label = raw_features.copy()
    raw_with_label["label_level_1"] = df_verify_meta["label_level_1"]
    print("\n=== Mean Value of Raw Meta-Features by Class ===")
    print(raw_with_label.groupby("label_level_1")[META_FEATURE_COLS].mean().round(4).to_string())

    print("\n=== Mean Value of Standardized (Z-score) Meta-Features by Class ===")
    print(df_verify_meta.groupby("label_level_1")[META_FEATURE_COLS].mean().round(4).to_string())


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    build_base_and_meta_datasets(root)
