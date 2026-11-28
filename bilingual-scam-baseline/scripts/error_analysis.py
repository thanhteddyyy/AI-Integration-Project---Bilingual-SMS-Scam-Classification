"""Error analysis of the chosen models: tier 1 (bilingual Linear SVM) and tier 2 (Vietnamese scam_type SVM).

Questions (docs/TONG_KET_TIEN_DO.md, task 5):
  T1-a  Where does tier 1 fail? error type x source (validation / test / external).
  T1-b  Missed Vietnamese scams: which scam_type, and is the "personal voice" (borrow money, family, boss) the cause?
  T1-c  Shortcut "strange link = scam" (labelling rule X4)? Observational (with / without link) + counterfactual:
          VI  : replace the domain of every link (strange <-> official), add a strange / official link to ham,
                remove the link from scams;
          EN  : the model only sees the token <URL> -> add / remove it.
  T1-d  Why is the English test (IMC25) so much better than SmishX? Recall vs. similarity to the nearest train scam.
  T1-e  Is the SVM margin a usable "uncertain" signal for the demo? Accuracy by margin bin.
  T2-a  Tier 2: out-of-fold (5-fold grouped CV, same folds as train_tier2.py) confusion pairs, with the words that
        pushed the wrong class; accuracy by margin bin.

No model is retrained except the CV fold models of tier 2 (same as train_tier2.py). Inputs are the saved
predictions / models in artifacts/.

Usage (from bilingual-scam-baseline/, Python 3.11):
  $env:PYTHONPATH="src"; py -3.11 scripts/error_analysis.py
Outputs: reports/error_analysis/ (summary.md + csv)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import confusion_matrix
from sklearn.metrics.pairwise import linear_kernel
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.config import load_config  # noqa: E402
from scam_baseline.data.masking import URL_RE  # noqa: E402
from scam_baseline.evaluation import wilson_interval  # noqa: E402
from scam_baseline.models.classical import build_svm  # noqa: E402
from scam_baseline.predict import TRANSFER_REQUEST_RE, _word_contributions  # noqa: E402
from scam_baseline.tier2 import PAYEE_BANK_RE, build_tier2_frame  # noqa: E402

OUT = ROOT / "reports" / "error_analysis"
T1_DIR = ROOT / "artifacts" / "bilingual" / "svm"
SPLITS = ("validation", "test", "external_test")
VI_SOURCES = {"spamscam_train", "spamscam_test", "vie_sms_dev", "vie_sms_holdout", "vi_crawl"}

# strange = TLDs of rule X4 / seen in the crawl; official = real domains of the impersonated brands
STRANGE_DOMAINS = ["vcb-xacminh.top", "csgt-gov.xyz", "nhanqua24h.vip", "evn-hoadon.cc", "vietcombank-vn.online"]
OFFICIAL_DOMAINS = ["vietcombank.com.vn", "csgt.vn", "shopee.vn", "evn.com.vn", "dichvucong.gov.vn"]

PERSONAL_RE = re.compile(
    r"(?i)(^|\b)(bố ơi|bo oi|mẹ ơi|me oi|ba ơi|ba oi|con đang|con dang|sếp|sep nho|anh ơi|chị ơi|em ơi|"
    r"cho (?:em|anh|chị|mình|tớ)?\s*mượn|mượn tạm|vay tạm|bình chọn|binh chon|like giúp|nhờ (?:em|anh|chị|mình)?)"
)
TRANSFER_TO_ACCOUNT_RE = re.compile(r"(?i)(\bstk\b|số tài khoản|so tai khoan|\btk\b|chuyển[^.]{0,40}?vào|chuyen[^.]{0,40}?vao|"
                                    r"chuyển (?:lại|giúp|gấp|tạm)|chuyen (?:lai|giup|gap|tam)|nộp phí|nop phi|thanh toán vào)")
CALL_RE = re.compile(r"(?i)(gọi|goi|liên hệ|lien he|zalo|\bLH\b|nhắn|soạn|soan|hotline|tổng đài|tong dai)")
VI_DIACRITIC_RE = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


def call_to_action(text: str) -> str:
    """What the scammer asks the victim to do (first match wins)."""
    text = str(text)
    if URL_RE.search(text) or "<URL>" in text:
        return "bấm link"
    if TRANSFER_TO_ACCOUNT_RE.search(text):
        return "chuyển tiền vào STK"
    if CALL_RE.search(text):
        return "gọi điện / nhắn Zalo"
    return "không có yêu cầu rõ"


def pct(x: float | None) -> str:
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.1f}"


def ci(k: int, n: int) -> str:
    if n == 0:
        return "–"
    lo, hi = wilson_interval(k, n)
    return f"{pct(k / n)} [{pct(lo)}–{pct(hi)}]"


def md_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines)


def short(text: str, n: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(text)).replace("|", "/")
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------------------------------------------------------
# tier 1
# ---------------------------------------------------------------------------------------------------------------
def load_t1_predictions() -> pd.DataFrame:
    meta = pd.read_csv(ROOT / "data" / "processed_bilingual" / "modeling_data.csv",
                       usecols=["sample_id", "scam_type", "has_url"])
    frames = [pd.read_csv(T1_DIR / f"predictions_{s}.csv") for s in SPLITS]
    df = pd.concat(frames, ignore_index=True).merge(meta, on="sample_id", how="left")
    df["lang"] = np.where(df.source_dataset.isin(VI_SOURCES), "vi", "en")
    return df


def margin_of(model, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    scores = model.decision_function(texts)
    classes = np.array(model.named_steps["classifier"].classes_)
    order = np.sort(scores, axis=1)
    return classes[scores.argmax(1)], order[:, -1] - order[:, -2]


def t1_error_types(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (split, src), g in df.groupby(["split", "source_dataset"]):
        err = g[~g.is_correct.astype(bool)]
        row = {"split": split, "source": src, "rows": len(g), "errors": len(err)}
        for t, p in [("scam", "legitimate"), ("scam", "spam"), ("legitimate", "scam"), ("spam", "scam"),
                     ("spam", "legitimate"), ("legitimate", "spam")]:
            row[f"{t[:4]}→{p[:4]}"] = int(((err.label_level_1 == t) & (err.prediction == p)).sum())
        rows.append(row)
    order = {s: i for i, s in enumerate(SPLITS)}
    return pd.DataFrame(rows).sort_values(["split", "source"], key=lambda c: c.map(order) if c.name == "split" else c)


def t1_missed_vi(df: pd.DataFrame, crawl_full: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recall of VI scams by scam_type and by personal voice (Tuan test + full crawl set)."""
    tuan = df[(df.source_dataset == "spamscam_test") & (df.label_level_1 == "scam")].copy()
    tuan["set"] = "Tuấn test"
    tuan["text"] = tuan.text_clean
    crawl = crawl_full[crawl_full.label_3class == "scam"].copy()
    crawl["set"] = "crawl đợt 1–2 (đầy đủ)"
    crawl["text"] = crawl.message
    crawl["prediction"] = crawl["bilingual/svm"]
    crawl["scam_type"] = crawl.scam_type
    both = pd.concat([tuan[["set", "text", "scam_type", "prediction"]], crawl[["set", "text", "scam_type", "prediction"]]],
                     ignore_index=True)
    both["caught"] = both.prediction.eq("scam")
    both["personal"] = both.text.map(lambda t: bool(PERSONAL_RE.search(t) or TRANSFER_REQUEST_RE.search(t)))
    both["action"] = both.text.map(call_to_action)
    by_type = (both.groupby(["set", "scam_type"]).agg(rows=("caught", "size"), caught=("caught", "sum")).reset_index())
    by_type["recall"] = [ci(int(c), int(n)) for c, n in zip(by_type.caught, by_type.rows)]
    by_voice = both.groupby(["set", "personal"]).agg(rows=("caught", "size"), caught=("caught", "sum")).reset_index()
    by_voice["recall"] = [ci(int(c), int(n)) for c, n in zip(by_voice.caught, by_voice.rows)]
    by_voice["personal"] = by_voice.personal.map({True: "giọng cá nhân", False: "giọng tổ chức/thông báo"})
    # call-to-action, organisation voice only (personal voice is 0 anyway and would mix the two effects)
    org = both[~both.personal]
    by_action = org.groupby("action").agg(rows=("caught", "size"), caught=("caught", "sum")).reset_index()
    by_action["recall"] = [ci(int(c), int(n)) for c, n in zip(by_action.caught, by_action.rows)]
    missed = both[~both.caught].copy()
    return by_type, by_voice, by_action, missed


def t1_en_legit_link(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """English legitimate messages WITH a link that tier 1 calls scam: which source, which messages."""
    g = df[df.split.isin(["test", "external_test"]) & (df.lang == "en") & (df.label_level_1 == "legitimate")
           & df.text_clean.str.contains("<URL>", regex=False)]
    by_src = g.groupby("source_dataset").agg(rows=("prediction", "size"),
                                             scam=("prediction", lambda p: int((p == "scam").sum()))).reset_index()
    by_src["bị đoán scam"] = [ci(int(k), int(n)) for k, n in zip(by_src.scam, by_src.rows)]
    return by_src, g[g.prediction == "scam"]


def t1_link_observational(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["link"] = df.text_clean.map(lambda t: bool(URL_RE.search(t)) or "<URL>" in t)
    rows = []
    for (lang, label), g in df[df.split.isin(["test", "external_test"])].groupby(["lang", "label_level_1"]):
        for has, h in g.groupby("link"):
            k = int((h.prediction == "scam").sum())
            rows.append({"ngôn ngữ": lang, "nhãn thật": label, "có link": "có" if has else "không",
                         "số tin": len(h), "bị đoán scam": ci(k, len(h))})
    return pd.DataFrame(rows)


def _swap_domains(text: str, domains: list[str], i: int) -> str:
    return URL_RE.sub(lambda m: f"https://{domains[i % len(domains)]}", text)


def t1_counterfactual(model, df: pd.DataFrame) -> pd.DataFrame:
    """Flip rates when only the link changes. Base = rows predicted correctly (so a change is due to the edit)."""
    base = df[df.split.isin(["test", "external_test"]) & df.is_correct.astype(bool)].copy()
    rows = []

    def run(name, frame, edit, target):
        if frame.empty:
            return
        edited = [edit(t, i) for i, t in enumerate(frame.text_clean)]
        pred = model.predict(edited)
        k = int((pred == target).sum()) if target != "not_scam" else int((pred != "scam").sum())
        rows.append({"phép thử": name, "số tin": len(frame), "kết quả đổi": ci(k, len(frame))})

    vi, en = base[base.lang == "vi"], base[base.lang == "en"]
    vi_scam_link = vi[(vi.label_level_1 == "scam") & vi.text_clean.str.contains(URL_RE)]
    vi_ham = vi[vi.label_level_1 == "legitimate"]
    vi_ham_nolink = vi_ham[~vi_ham.text_clean.str.contains(URL_RE)]
    vi_spam_nolink = vi[(vi.label_level_1 == "spam") & ~vi.text_clean.str.contains(URL_RE)]
    vi_ham_link = vi_ham[vi_ham.text_clean.str.contains(URL_RE)]
    run("VI scam có link: bỏ link → hết scam", vi_scam_link, lambda t, i: URL_RE.sub(" ", t), "not_scam")
    run("VI scam có link: đổi sang tên miền CHÍNH THỐNG → hết scam", vi_scam_link,
        lambda t, i: _swap_domains(t, OFFICIAL_DOMAINS, i), "not_scam")
    run("VI ham không link: thêm link LẠ → thành scam", vi_ham_nolink,
        lambda t, i: f"{t} https://{STRANGE_DOMAINS[i % 5]}", "scam")
    run("VI ham không link: thêm link CHÍNH THỐNG → thành scam", vi_ham_nolink,
        lambda t, i: f"{t} https://{OFFICIAL_DOMAINS[i % 5]}", "scam")
    run("VI ham có link: đổi sang tên miền LẠ → thành scam", vi_ham_link,
        lambda t, i: _swap_domains(t, STRANGE_DOMAINS, i), "scam")
    run("VI spam không link: thêm link LẠ → thành scam (đúng theo X4)", vi_spam_nolink,
        lambda t, i: f"{t} https://{STRANGE_DOMAINS[i % 5]}", "scam")
    en_scam_link = en[(en.label_level_1 == "scam") & en.text_clean.str.contains("<URL>", regex=False)]
    en_ham_nolink = en[(en.label_level_1 == "legitimate") & ~en.text_clean.str.contains("<URL>", regex=False)]
    run("EN scam có <URL>: bỏ <URL> → hết scam", en_scam_link, lambda t, i: t.replace("<URL>", " "), "not_scam")
    run("EN ham không link: thêm <URL> → thành scam", en_ham_nolink, lambda t, i: f"{t} <URL>", "scam")
    return pd.DataFrame(rows)


def t1_en_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """IMC25 test vs SmishX: max cosine (char 3-5 TF-IDF) of each scam to the EN train scams, recall by bin."""
    data = pd.read_csv(ROOT / "data" / "processed_bilingual" / "modeling_data.csv",
                       usecols=["text_clean", "label_level_1", "split", "source_dataset", "is_augmented"])
    train = data[(data.split == "train") & (data.label_level_1 == "scam") & ~data.source_dataset.isin(VI_SOURCES)]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True).fit(train.text_clean)
    tr = vec.transform(train.text_clean)
    rows = []
    for src in ["imc25", "sms_phishing", "smishx"]:
        g = df[(df.source_dataset == src) & (df.label_level_1 == "scam")]
        sim = linear_kernel(vec.transform(g.text_clean), tr).max(axis=1)
        caught = g.prediction.eq("scam").to_numpy()
        row = {"nguồn": src, "số scam": len(g), "độ giống TB": f"{sim.mean():.2f}",
               "≥ 0,8 (gần như đã thấy)": pct((sim >= 0.8).mean())}
        for lo, hi in [(0, 0.5), (0.5, 0.8), (0.8, 1.01)]:
            m = (sim >= lo) & (sim < hi)
            row[f"recall khi giống {lo:g}–{min(hi, 1):g}"] = ci(int(caught[m].sum()), int(m.sum()))
        rows.append(row)
    return pd.DataFrame(rows)


def margin_bins(truth, pred, margin, edges=(0, 0.3, 0.6, 1.0, np.inf)) -> pd.DataFrame:
    truth, pred, margin = np.asarray(truth), np.asarray(pred), np.asarray(margin)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (margin >= lo) & (margin < hi)
        k = int((truth[m] == pred[m]).sum())
        rows.append({"chênh lệch (margin)": f"{lo:g}–{hi:g}" if np.isfinite(hi) else f"≥ {lo:g}",
                     "số tin": int(m.sum()), "tỉ lệ tin": pct(m.mean()), "độ chính xác": ci(k, int(m.sum()))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------
# tier 2
# ---------------------------------------------------------------------------------------------------------------
def t2_oof(config: dict) -> pd.DataFrame:
    frame, _ = build_tier2_frame(config)
    dev = frame[frame.split.isin(["train", "validation"])].reset_index(drop=True)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=int(config["seed"]))
    out = []
    for fold, (tr, va) in enumerate(cv.split(dev.text_clean, dev.label_level_1, dev.group_id)):
        model = build_svm(config).fit(dev.loc[tr, "text_clean"], dev.loc[tr, "label_level_1"])
        part = dev.loc[va, ["sample_id", "text_clean", "label_level_1", "group_id"]].copy()
        pred, margin = margin_of(model, part.text_clean.tolist())
        part["prediction"], part["margin"], part["fold"] = pred, margin, fold
        part["why_words"] = [", ".join(w for w, _ in _word_contributions(model, t, p, 5)) if p != y else ""
                             for t, p, y in zip(part.text_clean, pred, part.label_level_1)]
        out.append(part)
    return pd.concat(out, ignore_index=True)


def t2_slices(oof: pd.DataFrame) -> pd.DataFrame:
    """Accuracy by writing style (diacritics) and by 'bank name only as payee' (labelling rule 1 boundary)."""
    oof = oof.copy()
    oof["ok"] = oof.label_level_1 == oof.prediction
    oof["dấu"] = np.where(oof.text_clean.map(lambda t: bool(VI_DIACRITIC_RE.search(t))), "có dấu", "không dấu")
    oof["payee"] = np.where(oof.text_clean.map(lambda t: bool(PAYEE_BANK_RE.search(t))),
                            "chỉ nêu ngân hàng NHẬN tiền", "không")
    rows = []
    for col, name in (("dấu", "cách viết"), ("payee", "tên ngân hàng nhận tiền (ca ranh giới quy tắc 1)")):
        for val, g in oof.groupby(col):
            rows.append({"lát cắt": name, "nhóm": val, "số tin": len(g), "độ chính xác": ci(int(g.ok.sum()), len(g)),
                         "% trong tổng lỗi": pct((~g.ok).sum() / max(1, (~oof.ok).sum()))})
    return pd.DataFrame(rows)


def t2_confusion(oof: pd.DataFrame, classes: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    cm = pd.DataFrame(confusion_matrix(oof.label_level_1, oof.prediction, labels=classes), index=classes, columns=classes)
    err = oof[oof.label_level_1 != oof.prediction]
    pairs = (err.groupby(["label_level_1", "prediction"]).size().rename("số tin").reset_index()
             .sort_values("số tin", ascending=False))
    pairs["% lỗi"] = (100 * pairs["số tin"] / len(err)).round(1)
    return cm, pairs


# ---------------------------------------------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t1 = joblib.load(T1_DIR / "model.joblib")
    df = load_t1_predictions()
    crawl_full = pd.read_csv(ROOT / "reports" / "vi_crawl_full" / "predictions.csv")

    types = t1_error_types(df)
    by_type, by_voice, by_action, missed = t1_missed_vi(df, crawl_full)
    en_link_src, en_link_fp = t1_en_legit_link(df)
    obs = t1_link_observational(df)
    cf = t1_counterfactual(t1, df)
    en_sim = t1_en_similarity(df)
    test_ext = df[df.split.isin(["test", "external_test"])]
    _, m1 = margin_of(t1, test_ext.text_clean.tolist())
    t1_margin = margin_bins(test_ext.label_level_1, test_ext.prediction, m1)

    config = load_config(ROOT / "configs" / "tier2_vietnamese.yaml")
    classes = config["data"]["class_order"]
    oof = t2_oof(config)
    cm, pairs = t2_confusion(oof, classes)
    t2_margin = margin_bins(oof.label_level_1, oof.prediction, oof.margin)
    slices = t2_slices(oof)
    # confident mistakes (margin >= 1) are the usual place to find label errors -> list for re-review
    confident = oof[(oof.label_level_1 != oof.prediction) & (oof.margin >= 1)].sort_values("margin", ascending=False)

    # tier-2 external (crawl run 3) predictions written by train_tier2.py, if present
    crawl_pred_path = ROOT / "reports" / "tier2_vi" / "crawl_predictions.csv"
    crawl_pred = pd.read_csv(crawl_pred_path) if crawl_pred_path.exists() else None

    # csv -------------------------------------------------------------------------------------------------------
    types.to_csv(OUT / "t1_error_types.csv", index=False)
    by_type.to_csv(OUT / "t1_vi_scam_recall_by_type.csv", index=False)
    by_voice.to_csv(OUT / "t1_vi_scam_recall_by_voice.csv", index=False)
    missed.to_csv(OUT / "t1_vi_missed_scams.csv", index=False, encoding="utf-8-sig")
    obs.to_csv(OUT / "t1_link_observational.csv", index=False)
    cf.to_csv(OUT / "t1_link_counterfactual.csv", index=False)
    en_sim.to_csv(OUT / "t1_en_similarity.csv", index=False)
    t1_margin.to_csv(OUT / "t1_margin.csv", index=False)
    err_rows = df[~df.is_correct.astype(bool)][["split", "source_dataset", "label_level_1", "prediction", "text_clean"]]
    err_rows.to_csv(OUT / "t1_all_errors.csv", index=False, encoding="utf-8-sig")
    cm.to_csv(OUT / "t2_oof_confusion.csv")
    pairs.to_csv(OUT / "t2_oof_confused_pairs.csv", index=False)
    oof[oof.label_level_1 != oof.prediction].to_csv(OUT / "t2_oof_errors.csv", index=False, encoding="utf-8-sig")
    t2_margin.to_csv(OUT / "t2_margin.csv", index=False)
    by_action.to_csv(OUT / "t1_vi_scam_recall_by_action.csv", index=False)
    en_link_fp.to_csv(OUT / "t1_en_legit_link_false_scam.csv", index=False, encoding="utf-8-sig")
    slices.to_csv(OUT / "t2_slices.csv", index=False)
    confident.to_csv(OUT / "t2_confident_errors_review.csv", index=False, encoding="utf-8-sig")

    # summary.md (numbers only; interpretation lives in docs/PHAN_TICH_LOI.md) ------------------------------------
    L = ["# Phân tích lỗi – số liệu (sinh tự động bởi `scripts/error_analysis.py`)", "",
         "Tầng 1 = `artifacts/bilingual/svm`, tầng 2 = SVM, dự đoán ngoài fold của CV 5 lượt theo khuôn (cùng cách chia với "
         "`train_tier2.py`). Khoảng trong ngoặc vuông là khoảng tin cậy Wilson 95%.", "",
         "## T1-a. Loại lỗi theo nguồn", "", md_table(types), "",
         "## T1-b. Lừa đảo tiếng Việt bị bỏ sót", "", "### Theo giọng văn", "", md_table(by_voice), "",
         "### Theo hành động kẻ gian yêu cầu (chỉ tin giọng tổ chức/thông báo)", "", md_table(by_action), "",
         "### Theo loại lừa đảo", "", md_table(by_type), "",
         "### Tin bị bỏ sót (tất cả bị đoán là gì)", "",
         md_table(missed.prediction.value_counts().rename_axis("dự đoán").reset_index(name="số tin")), "",
         md_table(missed.assign(text=missed.text.map(short))[["set", "scam_type", "personal", "prediction", "text"]].head(40)), "",
         "## T1-c. Lối tắt \"link lạ = scam\" (X4)", "", "### Quan sát (test + external)", "", md_table(obs), "",
         "### Phản thực tế: chỉ đổi phần link (trên các tin model đang đoán đúng)", "", md_table(cf), "",
         f"Tên miền lạ dùng thử: {', '.join(STRANGE_DOMAINS)}. Tên miền chính thống: {', '.join(OFFICIAL_DOMAINS)}.", "",
         "### Tin tiếng Anh thật (ham) có link bị đoán scam", "", md_table(en_link_src), "",
         "\n".join(f"- {short(t, 160)}" for t in en_link_fp.text_clean.head(12)), "",
         "## T1-d. Vì sao test tiếng Anh tốt hơn SmishX", "",
         "Độ giống = cosine TF-IDF cụm ký tự 3–5 giữa mỗi tin scam và tin scam tiếng Anh **giống nhất** trong train.", "",
         md_table(en_sim), "",
         "## T1-e. Chênh lệch điểm SVM (margin) và độ chính xác – tầng 1 (test + external)", "", md_table(t1_margin), "",
         "## T2-a. Tầng 2 – các cặp lớp bị nhầm (ngoài fold, train+val)", "",
         f"Tổng {len(oof)} tin, sai {int((oof.label_level_1 != oof.prediction).sum())}.", "",
         md_table(pairs.head(12)), "", "### Ma trận nhầm lẫn (hàng = thật, cột = dự đoán)", "",
         md_table(cm.reset_index().rename(columns={"index": "thật \\ đoán"})), "",
         "### Ví dụ lỗi và các từ đẩy về lớp sai", ""]
    ex = oof[oof.label_level_1 != oof.prediction].copy()
    top_pairs = list(zip(pairs.label_level_1, pairs.prediction))[:6]
    for t, p in top_pairs:
        L.append(f"**{t} → {p}**")
        L.append("")
        for _, r in ex[(ex.label_level_1 == t) & (ex.prediction == p)].head(4).iterrows():
            L.append(f"- {short(r.text_clean, 160)}  ← *{r.why_words}*")
        L.append("")
    L += ["### Margin và độ chính xác – tầng 2", "", md_table(t2_margin), "",
          "### Lát cắt", "", md_table(slices), "",
          f"### Lỗi mà model rất tự tin (margin ≥ 1): {len(confident)} tin – ứng viên nhãn sai, cần rà lại", "",
          md_table(confident.assign(text=confident.text_clean.map(lambda t: short(t, 130)),
                                    margin=confident.margin.round(2))
                   [["label_level_1", "prediction", "margin", "text"]].head(20)), ""]
    if crawl_pred is not None:
        L += ["## T2-b. Tầng 2 trên tin thật đợt 3 (external)", "",
              md_table(crawl_pred.assign(**{c: crawl_pred[c].map(short) for c in crawl_pred.columns
                                            if crawl_pred[c].dtype == object and crawl_pred[c].str.len().max() > 60})), ""]
    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote", OUT / "summary.md")


if __name__ == "__main__":
    main()
