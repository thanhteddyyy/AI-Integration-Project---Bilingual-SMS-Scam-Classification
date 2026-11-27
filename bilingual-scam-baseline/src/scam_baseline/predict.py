"""C2 – full prediction pipeline for the demo: tier 1 -> language -> tier 2.

    from scam_baseline.predict import ScamDetector
    detector = ScamDetector()                      # loads the 3 models once
    result = detector.predict("Tai khoan cua ban bi khoa, xac thuc tai vcb-xacminh.top")

Models (paths relative to `artifacts_dir`, default <repo>/artifacts):
  tier 1   bilingual/svm/model.joblib     Linear SVM, ham / spam / scam, vi + en
  langid   langid/model.joblib            char n-gram NB, vi / en (scripts/train_langid.py)
  tier 2   tier2_vi/final/model.joblib    Linear SVM, 9 Vietnamese scam types (scripts/train_tier2.py)

Input preparation follows how each model's TRAINING data looked (checked 2026-11-27):
  * tier 1, Vietnamese: Tuan-style masking [NUMBER] [MONEY] ... by default (`mask_vi_tier1=True`). Every
    Vietnamese SCAM in training was masked, so a scam typed with real numbers is otherwise easily missed
    ("Ho so vay 50 trieu da duyet... giai ngan": raw -> ham, masked -> scam). On vie_sms holdout masking keeps
    false alarms at 1.03% but spam recall drops 76% -> 57% (spam -> ham, the less harmful error). The tier-1
    numbers already reported (real crawled scams) were measured on masked text, so masking matches them.
  * tier 1, English: <URL> <PHONE> ... placeholders, like every English training source;
  * tier 2: Tuan-style masking, like all tier-2 training rows (Tuan + crawl).

SVM scores are decision values, NOT probabilities: the larger, the more likely; the margin between the two
best classes says how clear-cut the decision is.

Only sklearn / numpy / joblib (+ pandas through adapters) are needed – no PyTorch.
"""
from __future__ import annotations

import re
from pathlib import Path

import joblib
import numpy as np

from .data.adapters import normalize_en_placeholders
from .data.clean import clean_text
from .data.masking import mask_vi
from .data.scam_types import VI_TIER2_GROUPS

# repo layout: <repo>/src/scam_baseline -> <repo>/artifacts; demo bundle: <bundle>/scam_baseline -> <bundle>/models
_REPO_ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts"
DEFAULT_ARTIFACTS = _REPO_ARTIFACTS if _REPO_ARTIFACTS.exists() else Path(__file__).resolve().parents[1] / "models"
MODEL_PATHS = {
    "tier1": "bilingual/svm/model.joblib",
    "langid": "langid/model.joblib",
    "tier2_vi": "tier2_vi/final/model.joblib",
}

LABEL_VI = {"legitimate": "Tin bình thường (ham)", "spam": "Tin rác / quảng cáo (spam)", "scam": "Tin lừa đảo (scam)"}
SCAM_TYPE_VI = {
    "banking_finance": "Mạo danh ngân hàng / ví điện tử",
    "gov_utility_services": "Mạo danh cơ quan nhà nước / điện, nước, nhà mạng",
    "delivery_logistics": "Mạo danh đơn vị giao hàng",
    "job_task_scam": "Việc làm ảo / làm nhiệm vụ",
    "investment": "Đầu tư / tiền ảo lừa đảo",
    "loan_debt": "Cho vay / đòi nợ lừa đảo",
    "prize_lottery": "Trúng thưởng / quà tặng giả",
    "social_impersonation": "Giả danh người thân / người quen",
    "other_scam": "Lừa đảo khác",
}
GROUP_VI = {
    "3.1_brand_authority_spoofing": "3.1 Giả mạo tổ chức",
    "3.2_financial_task": "3.2 Lừa đảo tài chính & việc làm ảo",
    "3.3_prize_lottery": "3.3 Trúng thưởng & quà giả",
    "extension_person_impersonation": "Mở rộng: giả danh cá nhân",
    "extension_other": "Mở rộng: khác",
}
ADVICE_VI = {
    "banking_finance": "Không bấm link, không cung cấp OTP/mật khẩu. Gọi tổng đài in trên thẻ hoặc mở app ngân hàng chính thức để kiểm tra.",
    "gov_utility_services": "Cơ quan nhà nước, điện lực, nhà mạng không gửi link yêu cầu nộp phạt hay cập nhật thông tin. Tra cứu trên VNeID / cổng dịch vụ công / app chính thức.",
    "delivery_logistics": "Kiểm tra đơn trên app mua sắm hoặc web chính thức của hãng vận chuyển; không trả phí qua link lạ.",
    "job_task_scam": "Việc 'nhẹ lương cao', làm nhiệm vụ phải nạp tiền trước là lừa đảo. Không chuyển tiền để 'kích hoạt' hay 'nhận hoa hồng'.",
    "investment": "Không tham gia sàn, nhóm 'kéo lợi nhuận' không được cấp phép; lợi nhuận cam kết cao là dấu hiệu lừa đảo.",
    "loan_debt": "Không nộp 'phí giải ngân/bảo hiểm khoản vay' trước. Bị đòi nợ đe dọa: lưu bằng chứng và báo công an.",
    "prize_lottery": "Không có giải thưởng nào bắt đóng phí trước. Không bấm link nhận thưởng.",
    "social_impersonation": "Gọi điện (gọi thoại/video) trực tiếp cho người thân để xác minh trước khi chuyển tiền.",
    "other_scam": "Không bấm link lạ, không chuyển tiền hay cung cấp thông tin cá nhân khi chưa xác minh.",
}
# A money-transfer request can be a scam even when the text looks like a real friend's message (hacked account):
# the content alone cannot tell (docs/NHAT_KY_TANG2.md 7.4) -> warn, never change the label.
TRANSFER_REQUEST_RE = re.compile(
    r"(?i)(cho (?:em|anh|chị|chi|tao|tớ|to|mình|minh)?\s*mượn|cho\s+muon|mượn tạm|muon tam|vay tạm|vay tam|"
    r"chuyển (?:giúp|gấp|tạm|ngay|khoản gấp)|chuyen (?:giup|gap|tam|ngay)|ck (?:giúp|gấp|tạm)|"
    r"(?:tk|tài khoản|tai khoan) còn (?:đủ|tiền)|(?:tk|tai khoan) con (?:du|tien))"
)
TRANSFER_WARNING = ("Tin có yêu cầu chuyển/mượn tiền. Kể cả khi giống tin người quen, tài khoản người gửi có thể đã bị chiếm: "
                    "hãy GỌI ĐIỆN xác minh trước khi chuyển.")


def _word_contributions(model, text: str, label: str, top: int) -> list[tuple[str, float]]:
    """Word n-grams of `text` that pushed the SVM towards `label` (char n-grams are used but not listed)."""
    features = model.named_steps["features"]
    classifier = model.named_steps["classifier"]
    word = dict(features.transformer_list)["word_tfidf"]
    names = word.get_feature_names_out()
    row = features.transform([text]).tocsr()
    in_word = row.indices < len(names)
    idx, val = row.indices[in_word], row.data[in_word]
    contrib = val * classifier.coef_[list(classifier.classes_).index(label)][idx]
    order = np.argsort(-contrib)[:top]
    return [(str(names[idx[i]]), round(float(contrib[i]), 4)) for i in order if contrib[i] > 0]


def _scores(model, text: str) -> dict[str, float]:
    values = model.decision_function([text])[0]
    return {str(c): round(float(v), 4) for c, v in zip(model.named_steps["classifier"].classes_, values)}


def _margin(scores: dict[str, float]) -> float:
    top = sorted(scores.values(), reverse=True)
    return round(top[0] - top[1], 4) if len(top) > 1 else 0.0


class ScamDetector:
    def __init__(self, artifacts_dir: str | Path | None = None, top_words: int = 6, mask_vi_tier1: bool = True) -> None:
        base = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS
        missing = [str(base / p) for p in MODEL_PATHS.values() if not (base / p).exists()]
        if missing:
            raise FileNotFoundError("missing model files: " + ", ".join(missing))
        self.tier1 = joblib.load(base / MODEL_PATHS["tier1"])
        self.langid = joblib.load(base / MODEL_PATHS["langid"])
        self.tier2_vi = joblib.load(base / MODEL_PATHS["tier2_vi"])
        self.top_words = top_words
        self.mask_vi_tier1 = mask_vi_tier1

    def predict(self, text: str) -> dict:
        cleaned = clean_text(text)
        result: dict = {"input": text, "warnings": [], "notes": []}
        if not cleaned:
            result.update(label=None, notes=["Tin rỗng."])
            return result

        lang_classes = list(self.langid.classes_)
        p_lang = self.langid.predict_proba([cleaned])[0]
        language = lang_classes[int(np.argmax(p_lang))]
        result["language"] = language
        result["language_confidence"] = round(float(np.max(p_lang)), 4)

        if language == "vi":
            tier1_text = mask_vi(cleaned) if self.mask_vi_tier1 else cleaned
        else:
            tier1_text = normalize_en_placeholders(cleaned)
        scores = _scores(self.tier1, tier1_text)
        label = max(scores, key=scores.get)
        result.update(
            label=label,
            label_vi=LABEL_VI.get(label, label),
            label_scores=scores,
            label_margin=_margin(scores),
            tier1_text=tier1_text,
            tier1_top_words=_word_contributions(self.tier1, tier1_text, label, self.top_words),
            scam_type=None, scam_type_vi=None, scam_group=None, scam_group_vi=None,
            scam_type_scores=None, scam_type_margin=None, tier2_text=None, tier2_top_words=[], advice=None,
        )

        if label == "scam":
            if language == "vi":
                tier2_text = mask_vi(cleaned)
                t2 = _scores(self.tier2_vi, tier2_text)
                scam_type = max(t2, key=t2.get)
                group = VI_TIER2_GROUPS.get(scam_type)
                result.update(
                    scam_type=scam_type,
                    scam_type_vi=SCAM_TYPE_VI.get(scam_type, scam_type),
                    scam_group=group,
                    scam_group_vi=GROUP_VI.get(group, group),
                    scam_type_scores=t2,
                    scam_type_margin=_margin(t2),
                    tier2_text=tier2_text,
                    tier2_top_words=_word_contributions(self.tier2_vi, tier2_text, scam_type, self.top_words),
                    advice=ADVICE_VI.get(scam_type),
                )
            else:
                result["notes"].append("Tầng 2 (loại lừa đảo) hiện chỉ hỗ trợ tiếng Việt.")
        if TRANSFER_REQUEST_RE.search(cleaned):
            result["warnings"].append(TRANSFER_WARNING)
        return result

    def predict_batch(self, texts) -> list[dict]:
        return [self.predict(t) for t in texts]


_DEFAULT: ScamDetector | None = None


def predict_pipeline(text: str) -> dict:
    """Convenience wrapper (loads the models on first call)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ScamDetector()
    return _DEFAULT.predict(text)
