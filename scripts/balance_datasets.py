"""Build the training sets used by the bilingual model (v2, 2026-11-25).

Replaces the old 500/500/500 (VI) and 2000/2000/2000 (EN) balancing, which threw away real data
(VI legit 1,231 -> 500, EN scam 10,315 -> 2,000), produced exact-copy augmentations, edited only
``text_clean`` (so meta-features from ``text_raw`` were wrong) and reused ``sample_id``s.

Policy (handoff section 3.3):
  * Keep every real train row; class imbalance is handled by ``class_weight: balanced`` in the models.
  * English: only the scam class is capped (default 4,000), stratified by ``scam_type``.
  * Vietnamese: optional augmentation of the minority classes (spam, scam), train split ONLY:
    remove diacritics, synonym swap (with and without diacritics), entity swap (bank / courier /
    telco / e-commerce names), teencode. At most ``--vi-max-aug-per-row`` variants per real message;
    a variant is kept only if its text is new (not equal to any row in ANY split, nor to another
    variant, compared on the pipeline's template key). Augmented rows get a fresh ``sample_id``,
    ``is_augmented=True``, ``aug_parent_id``, ``aug_ops``; ``text_raw`` and ``text_clean`` are both
    rewritten; ``group_id`` is the parent's so group-level leakage checks still hold.
  * validation / test / external_test are never touched.

Usage:
  python scripts/balance_datasets.py                 # VI with augmentation + EN
  python scripts/balance_datasets.py --no-vi-augment # VI real data only (for the ablation)
  python scripts/balance_datasets.py --lang vi
"""
from __future__ import annotations

import argparse
import random
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.data.clean import clean_text, stable_hash, template_duplicate_key  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RANDOM_SEED = 42
ACTIVE_SPLITS = ["train", "validation", "test", "external_test"]

# ---------------------------------------------------------------------------
# Vietnamese augmentation resources
# ---------------------------------------------------------------------------
ENTITY_GROUPS = {
    "bank": ["Vietcombank", "Techcombank", "ACB", "BIDV", "MBBank", "Sacombank", "VPBank",
             "VietinBank", "TPBank", "Agribank", "VIB", "SHB", "HDBank", "OCB", "SeABank"],
    "courier": ["GHTK", "GHN", "J&T Express", "Viettel Post", "VNPost", "Ninja Van", "Best Express"],
    "telco": ["Viettel", "Vinaphone", "MobiFone"],
    "shop": ["Shopee", "Lazada", "Tiki", "TikTok Shop"],
}

# (pattern, replacements); accented and unaccented spellings are listed separately because
# about 60% of the Vietnamese scam messages carry diacritics.
SYNONYMS = [
    (r"tài khoản", ["TK", "tài khoản của bạn"]),
    (r"tai khoan", ["TK", "tai khoan cua ban"]),
    (r"vui lòng", ["hãy", "quý khách vui lòng", "đề nghị"]),
    (r"vui long", ["hay", "quy khach vui long", "de nghi"]),
    (r"xác thực", ["xác minh", "cập nhật"]),
    (r"xac thuc", ["xac minh", "cap nhat"]),
    (r"đăng nhập", ["truy cập", "login"]),
    (r"dang nhap", ["truy cap", "login"]),
    (r"thông báo", ["TB", "cảnh báo"]),
    (r"thong bao", ["TB", "canh bao"]),
    (r"quý khách", ["QK", "bạn"]),
    (r"quy khach", ["QK", "ban"]),
    (r"miễn phí", ["free", "0đ", "hoàn toàn miễn phí"]),
    (r"mien phi", ["free", "0d", "hoan toan mien phi"]),
    (r"khuyến mãi", ["KM", "ưu đãi"]),
    (r"khuyen mai", ["KM", "uu dai"]),
    (r"liên hệ", ["LH", "gọi ngay"]),
    (r"lien he", ["LH", "goi ngay"]),
    (r"chúc mừng", ["xin chúc mừng", "chúc mừng bạn"]),
    (r"chuc mung", ["xin chuc mung", "chuc mung ban"]),
    (r"trúng thưởng", ["trúng giải", "nhận thưởng"]),
    (r"trung thuong", ["trung giai", "nhan thuong"]),
    (r"nhận ngay", ["nhận liền", "lĩnh ngay"]),
    (r"nhan ngay", ["nhan lien", "linh ngay"]),
    (r"truy cập", ["vào", "bấm vào"]),
    (r"truy cap", ["vao", "bam vao"]),
    (r"hết hạn", ["sắp hết hạn", "quá hạn"]),
    (r"het han", ["sap het han", "qua han"]),
]

TEENCODE = [
    (r"không", ["ko", "k", "hok"]),
    (r"khong", ["ko", "k"]),
    (r"được", ["đc", "dc"]),
    (r"duoc", ["dc"]),
    (r"anh/chị", ["a/c"]),
    (r"anh/chi", ["a/c"]),
    (r"rồi", ["r"]),
    (r"với", ["vs"]),
    (r"gì", ["j"]),
    (r"nhé", ["nha", "nhá"]),
    (r"tài khoản", ["tk"]),
    (r"tai khoan", ["tk"]),
]


def _word_re(pattern: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){pattern}(?!\w)", re.IGNORECASE)


SYNONYM_RES = [(_word_re(p), r) for p, r in SYNONYMS]
TEENCODE_RES = [(_word_re(p), r) for p, r in TEENCODE]
ENTITY_RES = {
    group: [(name, _word_re(re.escape(name))) for name in names] for group, names in ENTITY_GROUPS.items()
}


def has_diacritics(text: str) -> bool:
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", text)) or "đ" in text.lower()


def op_strip_diacritics(text: str, rng: random.Random) -> str | None:
    if not has_diacritics(text):
        return None
    out = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", out.replace("đ", "d").replace("Đ", "D"))


def _swap_from(table, text: str, rng: random.Random, max_swaps: int) -> str | None:
    candidates = [(rx, reps) for rx, reps in table if rx.search(text)]
    if not candidates:
        return None
    rng.shuffle(candidates)
    out = text
    for rx, reps in candidates[:max_swaps]:
        out = rx.sub(rng.choice(reps), out, count=1)
    return out if out != text else None


def op_synonym(text: str, rng: random.Random) -> str | None:
    return _swap_from(SYNONYM_RES, text, rng, max_swaps=2)


def op_teencode(text: str, rng: random.Random) -> str | None:
    return _swap_from(TEENCODE_RES, text, rng, max_swaps=3)


def op_entity(text: str, rng: random.Random) -> str | None:
    found = [(group, name, rx) for group, items in ENTITY_RES.items() for name, rx in items if rx.search(text)]
    if not found:
        return None
    group, name, rx = rng.choice(found)
    target = rng.choice([n for n in ENTITY_GROUPS[group] if n.lower() != name.lower()])
    return rx.sub(target, text)


AUG_OPS = {
    "strip_diacritics": op_strip_diacritics,
    "synonym": op_synonym,
    "entity": op_entity,
    "teencode": op_teencode,
}


def make_variant(text: str, rng: random.Random) -> tuple[str, list[str]] | None:
    """Apply 1-2 random applicable operations. Returns (new_text, ops) or None."""
    names = list(AUG_OPS)
    rng.shuffle(names)
    wanted = rng.choice([1, 2])
    out, applied = text, []
    for name in names:
        result = AUG_OPS[name](out, rng)
        if result is not None:
            out, applied = result, applied + [name]
            if len(applied) >= wanted:
                break
    return (out, applied) if applied and out != text else None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def add_aug_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column, default in [("is_augmented", False), ("aug_parent_id", ""), ("aug_ops", "")]:
        if column not in frame.columns:
            frame[column] = default
    return frame


def assert_integrity(df: pd.DataFrame, name: str) -> None:
    active = df[df["split"].isin(ACTIVE_SPLITS)]
    leaks = (active.groupby("group_id")["split"].nunique() > 1).sum()
    conflicts = (active.groupby("group_id")["label_level_1"].nunique() > 1).sum()
    dup_ids = int(df["sample_id"].duplicated().sum())
    aug_outside_train = int((df["is_augmented"].astype(str).eq("True") & ~df["split"].eq("train")).sum())
    train_text_dups = int(df.loc[df["split"].eq("train"), "text_clean"].duplicated().sum())
    problems = {
        "leaking_groups": int(leaks),
        "label_conflict_groups": int(conflicts),
        "duplicate_sample_ids": dup_ids,
        "augmented_rows_outside_train": aug_outside_train,
    }
    if any(problems.values()):
        raise AssertionError(f"[{name}] integrity check failed: {problems}")
    print(f"[{name}] integrity OK: 0 leaking groups, 0 label conflicts, unique sample_id, "
          f"augmentation only in train (identical train texts: {train_text_dups}).")


def save(df: pd.DataFrame, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "modeling_data.csv", index=False, encoding="utf-8")
    summary = df.groupby(["split", "label_level_1", "is_augmented"]).size().rename("rows").reset_index()
    summary.to_csv(out_dir / "split_summary.csv", index=False)
    print(f"[{name}] saved {len(df):,} rows -> {out_dir / 'modeling_data.csv'}")
    print(summary.to_string(index=False))


# ---------------------------------------------------------------------------
# Vietnamese
# ---------------------------------------------------------------------------
def augment_vietnamese(train: pd.DataFrame, all_rows: pd.DataFrame, labels: list[str],
                       max_per_row: int, rng: random.Random) -> pd.DataFrame:
    seen = set(all_rows["text_raw"].fillna("").map(template_duplicate_key))
    cap = int((train["label_level_1"] == "legitimate").sum())  # never let a minority class exceed ham
    new_rows = []
    for label in labels:
        pool = train[train["label_level_1"] == label]
        budget = max(0, cap - len(pool))
        made = 0
        for _, parent in pool.sample(frac=1.0, random_state=RANDOM_SEED).iterrows():
            if made >= budget:
                break
            kept = 0
            for _attempt in range(max_per_row * 4):
                if kept >= max_per_row or made >= budget:
                    break
                variant = make_variant(str(parent["text_raw"]), rng)
                if variant is None:
                    continue
                text, ops = variant
                key = template_duplicate_key(text)
                if key in seen:
                    continue
                seen.add(key)
                row = parent.copy()
                row["text_raw"] = text
                row["text_clean"] = clean_text(text)
                row["sample_id"] = "sample_aug_" + stable_hash(f"{parent['sample_id']}|{kept}|{text}")
                row["source_record_id"] = f"{parent['source_record_id']}#aug{kept}"
                row["is_augmented"] = True
                row["aug_parent_id"] = parent["sample_id"]
                row["aug_ops"] = "+".join(ops)
                new_rows.append(row)
                kept += 1
                made += 1
        print(f"  {label}: {len(pool)} real + {made} augmented (cap {budget})")
    return pd.DataFrame(new_rows)


def balance_vietnamese(project_root: Path, augment: bool, max_per_row: int) -> None:
    print("\n" + "=" * 60 + "\nVIETNAMESE TRAINING SET\n" + "=" * 60)
    src = project_root / "data" / "processed_vi_3class" / "modeling_data.csv"
    df = add_aug_columns(pd.read_csv(src, dtype=str, keep_default_na=False))
    df["is_augmented"] = False
    print(f"Loaded {len(df):,} rows from {src}")
    train = df[df["split"] == "train"]
    print("Real train:", train["label_level_1"].value_counts().to_dict())
    parts = [df]
    if augment:
        rng = random.Random(RANDOM_SEED)
        aug = augment_vietnamese(train, df, ["scam", "spam"], max_per_row, rng)
        if not aug.empty:
            parts.append(aug)
            print("Augmentation ops used:", aug["aug_ops"].value_counts().to_dict())
    out = pd.concat(parts, ignore_index=True)
    out = out[out["split"].isin(ACTIVE_SPLITS)].reset_index(drop=True)
    assert_integrity(out, "Vietnamese")
    save(out, project_root / "data" / "processed_vi_balanced", "Vietnamese")


# ---------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------
def balance_english(project_root: Path, scam_cap: int) -> None:
    print("\n" + "=" * 60 + "\nENGLISH TRAINING SET\n" + "=" * 60)
    src = project_root / "data" / "processed" / "modeling_data.csv"
    df = add_aug_columns(pd.read_csv(src, dtype=str, keep_default_na=False))
    df["is_augmented"] = False
    print(f"Loaded {len(df):,} rows from {src}")
    train = df[df["split"] == "train"]
    print("Real train:", train["label_level_1"].value_counts().to_dict())
    scam = train[train["label_level_1"] == "scam"]
    drop_index = pd.Index([])
    if len(scam) > scam_cap:
        # proportional allocation per scam_type (largest remainder), at least 1 per type
        counts = scam["scam_type"].value_counts()
        raw = counts / counts.sum() * scam_cap
        alloc = np.floor(raw).astype(int).clip(lower=1)
        for t in (raw - np.floor(raw)).sort_values(ascending=False).index:
            if alloc.sum() >= scam_cap:
                break
            alloc[t] += 1
        kept = pd.concat([
            scam[scam["scam_type"] == t].sample(n=min(int(n), int(counts[t])), random_state=RANDOM_SEED)
            for t, n in alloc.items()
        ])
        drop_index = scam.index.difference(kept.index)
        print(f"Scam capped {len(scam):,} -> {len(kept):,} (stratified by scam_type):",
              kept["scam_type"].value_counts().to_dict())
    out = df.drop(index=drop_index)
    out = out[out["split"].isin(ACTIVE_SPLITS)].reset_index(drop=True)
    assert_integrity(out, "English")
    save(out, project_root / "data" / "processed_en_balanced", "English")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=["vi", "en", "both"], default="both")
    parser.add_argument("--no-vi-augment", action="store_true", help="Vietnamese real data only")
    parser.add_argument("--vi-max-aug-per-row", type=int, default=2)
    parser.add_argument("--en-scam-cap", type=int, default=4000)
    args = parser.parse_args()
    if args.lang in ("vi", "both"):
        balance_vietnamese(ROOT, augment=not args.no_vi_augment, max_per_row=args.vi_max_aug_per_row)
    if args.lang in ("en", "both"):
        balance_english(ROOT, scam_cap=args.en_scam_cap)


if __name__ == "__main__":
    main()
