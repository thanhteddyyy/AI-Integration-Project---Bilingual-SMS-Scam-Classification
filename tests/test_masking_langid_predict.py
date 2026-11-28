import sys
import types
from pathlib import Path

import pytest

from scam_baseline.data.masking import mask_vi
from scam_baseline.langid import langid_preprocess_one

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [
    "Me oi chuyen giup con 5 trieu vao STK 0123456789 Vietcombank truoc 17h30 ngay 30/11",
    "Goi 0912 345 678 de nhan 500k, han chot 12/12/2026 luc 9h15. Link: https://vcb-xacminh.top/a?id=123456",
    "Ma OTP 482913 het han sau 5 phut",
    "Tài khoản còn đủ 2.000.000đ không, cho mượn tạm",
]


def _crawler_mask():
    for name, attrs in (("requests", {"Session": object}), ("bs4", {"BeautifulSoup": object})):
        if name not in sys.modules:
            try:
                __import__(name)
            except ModuleNotFoundError:
                stub = types.ModuleType(name)
                for key, value in attrs.items():
                    setattr(stub, key, value)
                sys.modules[name] = stub
    sys.path.insert(0, str(ROOT / "scripts"))
    from crawl_vi_scam import mask_pii
    return mask_pii


def test_mask_vi_matches_the_crawler_and_tuan_style():
    mask_pii = _crawler_mask()
    for text in SAMPLES:
        assert mask_vi(text) == mask_pii(text)
    assert "[NUMBER]" in mask_vi(SAMPLES[0]) and "https://vcb-xacminh.top/a?id=123456" in mask_vi(SAMPLES[1])
    assert mask_vi(mask_vi(SAMPLES[1])) == mask_vi(SAMPLES[1])  # idempotent


def test_langid_preprocess_removes_source_specific_tokens():
    assert langid_preprocess_one("Goi [NUMBER] tai https://abc.top hoac <URL> 0912345678") == "goi tai hoac"


MODELS = ROOT / "artifacts"


@pytest.mark.skipif(not (MODELS / "tier2_vi" / "final" / "model.joblib").exists(), reason="models not trained")
def test_pipeline_contract_and_routing():
    from scam_baseline.predict import ScamDetector
    d = ScamDetector()
    vi = d.predict("Vietcombank thong bao: tai khoan cua quy khach bi tam khoa. Xac thuc ngay tai vcb-xacminh.top")
    assert vi["language"] == "vi" and vi["label"] == "scam" and vi["scam_type"] == "banking_finance"
    assert vi["scam_group"] == "3.1_brand_authority_spoofing" and vi["advice"]
    en = d.predict("Your account has been locked. Verify now at secure-bank-login.com")
    assert en["language"] == "en" and en["scam_type"] is None and en["notes"]
    borrow = d.predict("Co du 500k khong, cho muon tam co viec. Sang mai gui lai duoc khong?")
    assert borrow["warnings"]
    assert d.predict("   ")["label"] is None
