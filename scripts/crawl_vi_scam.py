"""Crawl real Vietnamese scam SMS quoted in public news warnings (v2).

Output is a CANDIDATE file for human review, used ONLY as external test data.
`label_suggested` / `scam_type_suggested` follow definition_of_ham_spam_scam.md
heuristically; every row must still be checked by a person (EasyOCR is only a
typing aid - the project's classifier is trained from scratch).

Pipeline per article
  0. discovery  - dated sitemaps of ~13 news sites; URL slug scored into
                  tier 2 (channel word + scam word) and tier 1 (scam word only).
  1. relevance  - the article body must actually talk about text messages.
  2. text       - SMS quoted verbatim, only when introduced by "tin nhắn có nội
                  dung", "nhắn", ... and not a quote of a person / advice list.
  3. ocr        - only screenshot-like images (caption / file name / the
                  paragraph before the image mention a message), read with
                  EasyOCR, status bar / UI text removed, split into chat bubbles.

Every stage is counted in crawl_stats.json so a weak stage is visible.

Runs locally or on Kaggle (GPU recommended for OCR):
    python scripts/crawl_vi_scam.py --months 36 --max-articles 1500 --target 400
    python scripts/crawl_vi_scam.py --no-ocr --max-articles 20 --months 2   # quick test
    python scripts/crawl_vi_scam.py --urls-file my_urls.txt --no-discover    # own URLs

The crawler is resumable: re-running skips articles already processed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
import threading
import time
import unicodedata
import urllib.robotparser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    # line_buffering: progress shows up live under `!python` in Kaggle/Jupyter.
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

USER_AGENT = "Mozilla/5.0 (compatible; VNScamResearchBot/0.2; academic research)"
VN_TZ = timezone(timedelta(hours=7))

# ---------------------------------------------------------------------------
# Sources (checked 2026-11-25: robots.txt allows crawling, no `ai-train=no`).
#   kind "dated"    : sitemap index whose children carry a date in their name
#   kind "category" : fixed list of child sitemaps (no date -> slug filter only)
# Deliberately absent: tinnhiemmang.vn (robots `ai-train=no`), chongluadao.vn
# (JavaScript-only), vnexpress.net (dated sitemaps redirect bots to homepage),
# nld.com.vn (dated sitemaps are empty), plo.vn / laodong.vn / baochinhphu.vn /
# ictvietnam.vn (no usable sitemap).
# Articles from any other site can still be added with --urls-file.
# ---------------------------------------------------------------------------
SOURCES: dict[str, dict] = {
    "thanhnien": {"index": "https://thanhnien.vn/sitemap.xml"},
    "tuoitre": {"index": "https://tuoitre.vn/sitemaps/index.rss"},
    "dantri": {"index": "https://dantri.com.vn/sitemap.xml"},
    "vietnamnet": {"index": "https://vietnamnet.vn/sitemap.xml"},
    "znews": {"index": "https://znews.vn/sitemap/sitemap.xml"},
    "cand": {"index": "https://cand.vn/sitemap.xml"},
    "vietnamplus": {"index": "https://www.vietnamplus.vn/sitemap.xml"},
    "tienphong": {"index": "https://tienphong.vn/sitemaps.xml"},
    "sggp": {"index": "https://www.sggp.org.vn/sitemaps.xml"},
    "vtv": {"index": "https://vtv.vn/sitemap.xml"},
    "genk": {"index": "https://genk.vn/sitemap.xml"},
    "kenh14": {"index": "https://kenh14.vn/sitemap.xml"},
    "vov": {"children": [f"https://vov.vn/sitemap-{c}.xml" for c in
                         ("phap-luat", "cong-nghe", "xa-hoi", "doi-song", "kinh-te")]},
}
# Each CMS names its dated child sitemaps differently -> (regex, order of groups).
CHILD_SITEMAP_DATE_PATTERNS = [
    (re.compile(r"sitemaps-(\d{4})-(\d{1,2})-(\d{1,2})-\d{1,2}\.xml"), "ymd"),  # thanhnien, tuoitre, nld, vtv, genk, kenh14
    (re.compile(r"/article-(\d{4})-(\d{2})-(\d{2})\.xml"), "ymd"),  # dantri (monthly)
    (re.compile(r"sitemap-article-(\d{4})(\d{2})(\d{2})\.xml"), "ymd"),  # znews (daily)
    (re.compile(r"sitemap-article-(\d{1,2})-(\d{4})-\d+\.xml"), "my"),  # vietnamnet (monthly chunks)
    (re.compile(r"/news-(\d{4})-(\d{1,2})\.xml"), "ym"),  # cand, vietnamplus, tienphong, sggp (monthly)
]


def child_sitemap_date(url: str):
    for pattern, order in CHILD_SITEMAP_DATE_PATTERNS:
        match = pattern.search(url)
        if not match:
            continue
        values = [int(v) for v in match.groups()]
        if order == "my":
            year, month, day = values[1], values[0], 1
        elif order == "ym":
            year, month, day = values[0], values[1], 1
        else:
            year, month, day = values
        try:
            return datetime(year, month, day).date()
        except ValueError:
            return None
    return None


# URL slug vocabulary (whole hyphen tokens, so "starlink" does not match "link").
SLUG_CHANNEL = ("tin-nhan", "nhan-tin", "sms", "brandname", "otp", "link", "duong-link", "dau-so",
                "tram-bts", "bts-gia", "sim", "zalo", "ma-qr", "thue-bao")
# Strong words alone are enough for tier 1; weak words ("canh-bao" also covers
# weather warnings) only count together with a channel word (tier 2).
SLUG_SCAM_STRONG = ("lua-dao", "gia-mao", "mao-danh", "gia-danh", "chiem-doat", "thu-doan",
                    "chieu-lua", "lua-tien", "scam", "phishing", "bi-lua")
SLUG_SCAM_WEAK = ("canh-bao", "chieu-tro", "ma-doc", "danh-cap", "sap-bay")

CONTENT_SELECTORS = (
    '[data-role="content"]', ".detail-content", ".singular-content", ".the-article-body",
    ".detail__content", ".article__body", ".article-content", ".content-detail", ".cms-body",
    ".maincontent", "#maincontent", ".fck_detail", ".knc-content", "article", "main",
)

OUTPUT_COLUMNS = [
    "candidate_id", "message", "label_suggested", "scam_type_suggested", "label_reason",
    "channel_suggested", "sms_score", "evidence_type", "source_name", "source_url", "article_title",
    "published_date", "article_tier", "article_relevance", "collected_at", "image_url", "image_path",
    "image_rank", "context_snippet", "ocr_raw",
    "review_label", "review_scam_type", "review_channel", "reject_reason", "review_note",
]
REJECT_REASONS = ["not_message", "journalism", "ocr_garbage", "fragment", "duplicate", "not_vietnamese", "other"]

# ---------------------------------------------------------------------------
# Text heuristics
# ---------------------------------------------------------------------------
URL_PATTERN = (
    r"(?:https?://\S+|www\.\S+|\b[a-z0-9][a-z0-9-]{1,62}(?:\.[a-z0-9-]{2,62})*"
    r"\.(?:vn|com|net|org|info|top|xyz|vip|online|site|link|cc|me|io|shop|club|icu|live|app|"
    r"asia|tech|store|bond|buzz|sbs|cfd|ly|gl)\b(?:/\S*)?)"
)
URL_RE = re.compile(URL_PATTERN, re.IGNORECASE)
URL_SPLIT_RE = re.compile(f"({URL_PATTERN})", re.IGNORECASE)
ODD_URL_RE = re.compile(
    r"(?i)\.(?:top|xyz|vip|online|site|cc|icu|shop|club|live|asia|tech|store|bond|buzz|sbs|cfd)\b|"
    r"bit\.ly|t\.ly|tinyurl|goo\.gl|cutt\.ly|rb\.gy|is\.gd|\.apk\b")
PHONE_RE = re.compile(r"(?<![\w/])(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?![\w/])")
BANK_ACC_RE = re.compile(r"(?i)((?:stk|số tài khoản|so tai khoan|tk)\s*[:.]?\s*)\d[\d\s.\-]{6,20}\d")
MONEY_RE = re.compile(
    r"(?i)\b\d[\d.,]*\s*(?:đồng|dong|vnđ|vnd|đ|d|triệu|trieu|tr|tỷ|ty|nghìn|nghin|k)(?!\w)")
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d(?:[:][0-5]\d)?\b")
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
LONG_NUMBER_RE = re.compile(r"(?<![\w\[])\d{6,}(?![\w\]])")

QUOTE_RE = re.compile(r"[“\"«]([^”\"»]{30,700})[”\"»]")
CONTENT_INTRO_RE = re.compile(r"(?i)(?:với\s+|có\s+)?nội dung(?:\s+như sau)?\s*[:：]\s*(.{30,700})$")
# A quote counts as a message only when the words right before it say so.
INTRO_BEFORE_RE = re.compile(
    r"(?i)(tin nhắn|nhắn tin|\bnhắn\b|\bsms\b|gửi tin|brandname|đầu số|nội dung|như sau|có dạng|"
    r"thông báo\s*(?:rằng|là)?|mạo danh[^.]{0,40}gửi|với lời lẽ|soạn sẵn|"
    r"(?:lý do|kịch bản|lời lẽ|cái cớ|thông điệp|câu)[^.]{0,30}(?:như|kiểu)|[\"”»],\s*(?:hoặc|hay)?)[^.]{0,60}$")
SENTENCE_START_RE = re.compile(r"^\s*(?:[\[(]|\d|[A-ZĐÀ-Ỹ])")
SMS_MENTION_RE = re.compile(
    r"(?i)tin nhắn|nhắn tin|\bsms\b|brandname|đầu số|trạm bts|bts giả|trạm phát sóng giả|gửi tin")

SMS_MARKERS = [
    (URL_RE, 2),
    (re.compile(r"(?i)\bquý khách|quy khach|\bqk\b|\bqúy khách"), 1),
    (re.compile(r"(?i)tài khoản|tai khoan|\btk\b"), 1),
    (re.compile(r"(?i)\botp\b|mã xác (?:thực|nhận|minh)|ma xac (?:thuc|nhan|minh)"), 1),
    (re.compile(r"(?i)truy cập|truy cap|bấm|nhấp|nhấn|click|đăng nhập|dang nhap|cập nhật|cap nhat|"
                r"liên hệ|lien he|soạn|soan|gọi ngay|chuyển khoản|chuyen khoan|chuyển vào|nạp|xác nhận"), 1),
    (re.compile(r"(?i)\btrước\b|\btruoc\b|ngay lập tức|khẩn|khan cap|hết hạn|het han|bị khóa|bi khoa|"
                r"kịp thời|kip thoi|tạm ngưng|tam ngung|bị hạn chế"), 1),
    (re.compile(r"(?i)nộp phạt|nop phat|vi phạm|vi pham|thanh toán|thanh toan|\bphí\b|\bphi\b|"
                r"hoàn tiền|hoan tien|xác minh|xac minh|trúng thưởng|trung thuong|đổi quà|doi qua"), 1),
    (re.compile(r"(?i)bằng chứng|scandal|theo dõi bạn|ảnh nhạy cảm|clip nóng|tống tiền|cho mượn|chuyển cho (?:con|mẹ|anh|em)|"
                r"lệnh bắt|truy nã|kích hoạt|khấu trừ|gia hạn"), 1),
    (re.compile(r"^\s*(?:\[[^\]]{2,20}\]|\([^)]{2,20}\)|[A-Z0-9][A-Za-z0-9 ]{1,14}\s*[:：])"), 1),
    (PHONE_RE, 1),
    (MONEY_RE, 1),
]
JOURNALISM_MARKERS = re.compile(
    r"(?i)\bcho biết\b|\bkhuyến cáo\b|\bngười dân\b|\bđối tượng\b|\bnạn nhân\b|\bthủ đoạn\b|"
    r"\bkẻ gian\b|\blừa đảo\b|\bcơ quan chức năng\b|\btheo đó\b|\bphóng viên\b|\bchia sẻ\b|"
    r"\bchuyên gia\b|\bcảnh giác\b|\bkẻ xấu\b|\bchiêu trò\b|\bđiều đó\b|\brủi ro\b|\bnghĩa là\b")
FIRST_PERSON_RE = re.compile(r"(?i)^\s*(tôi|mình|chúng tôi|lúc đó|khi đó|sau khi|thấy|thực tế)\b")
ADVICE_RE = re.compile(r"(?i)^\s*(\d+\s*(là|\.|\))|thứ (nhất|hai|ba)|không (nên|được)|hãy|cần|nên)\b")

# Tier-2 classes and priority decided 2026-11-27 (docs/NHAT_KY_TANG2.md section 2). Only a SUGGESTION:
# the first matching rule wins, the reviewer always checks.
_BANK_NAMES = (r"vietcombank|\bvcb\b|techcombank|bidv|agribank|vietinbank|mbbank|mb ?bank|vpbank|\bacb\b|sacombank|"
               r"tpbank|napas|hdbank|\bshb\b|\bocb\b|eximbank|seabank|\bmsb\b|\bvib\b|momo|zalopay|vnpay|shopeepay")
_TELECOM = r"thuê bao|thue bao|nhà mạng|nha mang|viettel|vinaphone|mobifone|\bvnpt\b|\bfpt\b|vtvcab|\bsim\b|\b4g\b|\b5g\b|cáp quang|cap quang"
_REWARD = r"tặng|tang\b|thưởng|thuong|quà|qua tang|miễn phí|mien phi|đổi điểm|doi diem|điểm thưởng|diem thuong"
SCAM_TYPE_RULES = [
    ("job_task_scam", r"việc làm|viec lam|cộng tác viên|cong tac vien|\bctv\b|nhiệm vụ|nhiem vu|hoa hồng|hoa hong|làm thêm|lam them|tuyển dụng|tuyen dung|chốt đơn"),
    ("investment", r"đầu tư|dau tu|lợi nhuận|loi nhuan|chứng khoán|chung khoan|tiền ảo|tien ao|\bcoin\b|\bsàn\b|forex"),
    # before banking: "mẹ chuyển giúp con ... STK Techcombank" / "sếp nhờ chuyển ... VietinBank" impersonate a PERSON
    ("social_impersonation", r"người thân|nguoi than|cấp cứu|cap cuu|\bmượn\b|\bmuon\b|chuyển giúp|chuyen giup|\bsếp\b|\bsep nho\b|"
                             r"\bcon\b.*\bmẹ\b|\bmẹ\b.*\bcon\b|hack (?:zalo|facebook)"),
    # 1. a named bank / e-wallet -> banking (also loans / debts that name a bank)
    ("banking_finance", _BANK_NAMES),
    # 2. a named state body or essential service (power, water)
    ("gov_utility_services", r"thuế|thue\b|vneid|căn cước|can cuoc|cccd|bhxh|bảo hiểm xã hội|phạt nguội|phat nguoi|vi phạm giao thông|vi pham giao thong|nộp phạt|nop phat|csgt|công an|cong an|điện lực|dien luc|evn|tòa án|toa an|dịch vụ công|dichvucong|cấp nước|cap nuoc|tiền nước|tien nuoc"),
    # strong loan words before telecom ("[SIM CASH] ... khoản vay" is a lending app); a bare "nợ" ("nợ cước") is checked later
    ("loan_debt", r"khoản vay|khoan vay|\bvay\b|giải ngân|giai ngan|nợ xấu|\bno xau\b|trả góp|tra gop|tín dụng đen"),
    # 3. telecom: reward bait -> prize, otherwise (threats, offers) -> gov_utility_services
    ("prize_lottery", rf"(?=.*(?:{_TELECOM}))(?=.*(?:{_REWARD}))"),
    ("gov_utility_services", _TELECOM),
    ("delivery_logistics", r"giao hàng|giao hang|đơn hàng|don hang|shipper|bưu (?:điện|phẩm|kiện)|buu (?:dien|pham|kien)|vnpost|viet ?nam ?post|ghtk|\bghn\b|j&t|kiện hàng|kien hang"),
    # 4. loans / debt collection through an app or a lending company (no named bank)
    ("loan_debt", r"\bnợ\b|đòi nợ|doi no|thu hồi nợ"),
    ("prize_lottery", r"trúng thưởng|trung thuong|quà tặng|qua tang|tri ân|tri an|giải thưởng|giai thuong|may mắn|may man|đổi quà|doi qua|lượt quay|luot quay|hũ|nổ hũ"),
    ("banking_finance", r"ngân hàng|ngan hang|\bthẻ\b|the tin dung|\botp\b"),
]
SCAM_TYPE_RES = [(name, re.compile(rf"(?i){pattern}")) for name, pattern in SCAM_TYPE_RULES]

# Label hints following definition_of_ham_spam_scam.md + project rules (docs/HANDOFF section 1).
QC_RE = re.compile(r"(?i)[\[(]\s*qc\s*[\])]")
OPT_OUT_RE = re.compile(r"(?i)từ chối|tu choi|\btc\s*(?:gửi|gui)|huỷ qc|hủy qc")
VAS_RE = re.compile(r"(?i)(?:soạn|soan|nhắn|nhan)[^.!]{0,40}?(?:gửi|gui|đến|den)\s*:?\s*\(?\s*(?:[5-9]\d{3}|1900\d+)\b"
                    r"|gọi\s*(?:ngay\s*)?1900\d+[^.]{0,40}(?:nghe|lời nhắn|loi nhan|bài hát|bai hat)")
LURE_RE = re.compile(r"(?i)miễn phí|mien phi|may mắn|may man|chúc mừng|chuc mung|cơ hội (?:trúng|nhận)|co hoi (?:trung|nhan)")
SCAM_CUE_RE = re.compile(
    r"(?i)\botp\b|mật khẩu|mat khau|đăng nhập|dang nhap|xác minh|xac minh|xác thực|xac thuc|bị khóa|bi khoa|"
    r"tạm khóa|hạn chế|phạt|vi phạm|vi pham|chuyển khoản|chuyen khoan|chuyển vào|chuyen vao|cho mượn|"
    r"trúng thưởng|trung thuong|đổi quà|doi qua|hết hạn|het han|giao (?:hàng )?(?:không )?thành công|sai địa chỉ|"
    r"cài đặt|cai dat|\.apk|tuyển|ctv|nhiệm vụ|thám tử|nợ|lệnh bắt|truy nã|cccd|vneid|định danh|cập nhật|cap nhat")
WARNING_RE = re.compile(
    r"(?i)khuyến cáo|cảnh báo người dân|không (?:cung cấp|bấm|nhấn|truy cập|chia sẻ)|tuyệt đối không|"
    r"bão số|áp thấp|mưa lũ|phòng chống thiên tai|pctt")
# Text of warning infographics / posters (not a message): dropped in the OCR stream.
# Matched on accent-stripped text because OCR often gets the diacritics wrong.
INFOGRAPHIC_RE = re.compile(
    r"khuy\w{0,2}n cao|nguyen tac|quy tac|cach xu ly|phong ngua|dau hieu nhan biet|luu y|"
    r"\d\s*khong\b|canh giac|thu doan|nguoi dan|hay\s+(?:kiem tra|lien he)|trinh bao|"
    r"doi mat khau|lien he ngan hang|can lam gi")


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D").lower()
AD_RE = re.compile(r"(?i)khuyến mãi|khuyen mai|ưu đãi|uu dai|giảm giá|giam gia|\bsale\b|mở bán|chiết khấu|bất động sản")

CHANNEL_RES = [
    ("zalo", re.compile(r"(?i)\bzalo\b")),
    ("messenger", re.compile(r"(?i)messenger|facebook|\bfb\b")),
    ("whatsapp", re.compile(r"(?i)whatsapp")),
    ("telegram", re.compile(r"(?i)telegram")),
    ("viber", re.compile(r"(?i)\bviber\b")),
    ("sms", re.compile(r"(?i)tin nhắn|\bsms\b|brandname|đầu số|tin nhan|nhắn tin|trạm bts|imessage")),
]

SCREENSHOT_HINT_RE = re.compile(
    r"(?i)anh-man-hinh|chup-man-hinh|screenshot|screen-shot|tin-nhan|sms|messenger|zalo|"
    r"tin nhắn|ảnh chụp màn hình|chụp màn hình|màn hình|nội dung tin|ảnh chụp|tin nhắn giả|tin nhắn mạo danh")
SKIP_IMAGE_RE = re.compile(r"(?i)logo|icon|avatar|banner|sprite|\.gif(\?|$)|\.svg(\?|$)|/ads?/|qrcode|placeholder|emoji")
# Phone UI / status bar text that OCR picks up around the message bubble.
UI_NOISE_RE = re.compile(
    r"(?i)^(?:\d{1,2}[:.]\d{2}\b.{0,12}|.{0,14}\b(?:hôm nay|hom nay|hôm qua|hom qua|today|yesterday)\b.{0,10}|"
    r"(?:th|thứ)\s*\d.{0,20}(?:thg|tháng).{0,12}|tin nh[aắả]n(?: v[aă]n b[aả]n)?|text message|imessage|sms|"
    r"nhắn tin|gửi|send|type here|nhập tin nhắn|thêm vào danh bạ|chặn số|báo cáo rác|đang hoạt động|"
    r"không phải người liên hệ|công cụ an toàn|tìm hiểu thêm|\d{1,3}\s*%|lte|4g|5g|vo?lte|"
    r"viettel|vinaphone|mobifone|vietnamobile|sim\s*\d|\+?\d[\d\s]{6,}|.{0,3})$")
# OCR often reads "https://" as "https:ll", "https:|I", "https:/l" ...
OCR_URL_FIX_RE = re.compile(r"(?i)\b(https?)\s*[:;]\s*[|Il1/\\]{1,3}\s*")
# Status-bar time / date glued to the start of a bubble: "09.14 Th 4, 18 thg 12 NETFLIX ..."
OCR_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:\d{1,2}[:.]\d{2}\s*)?(?:(?:th|thứ)\s*\w{1,3},?\s*\d{1,2}\s*(?:thg|tháng)\s*\d{1,2}(?:,?\s*\d{4})?\s*)?")


def fix_ocr_text(text: str) -> str:
    text = OCR_URL_FIX_RE.sub(lambda m: m.group(1).lower() + "://", text)
    return OCR_PREFIX_RE.sub("", text).strip()


def nfc(text: str) -> str:
    text = unicodedata.normalize("NFC", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def mask_pii(text: str) -> str:
    """Same placeholders as the Tuấn training set; URLs are never touched (they are features)."""
    masked = []
    for part in URL_SPLIT_RE.split(text):
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


def sms_score(text: str) -> int:
    score = sum(weight for pattern, weight in SMS_MARKERS if pattern.search(text))
    score -= 2 * len(JOURNALISM_MARKERS.findall(text))
    return score


def vietnamese_ratio(text: str) -> float:
    """Share of letters that are Latin (Vietnamese uses Latin + diacritics)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ok = sum(1 for c in letters if c.isascii() or "LATIN" in unicodedata.name(c, ""))
    return ok / len(letters)


def suggest_labels(text: str) -> tuple[str, str, str]:
    """Return (label, scam_type, reason). Order follows the definition's decision tree."""
    scam_type = next((name for name, pattern in SCAM_TYPE_RES if pattern.search(text)), "other_scam")
    odd_link = bool(ODD_URL_RE.search(text))
    if WARNING_RE.search(text) and not odd_link:
        return "legitimate", "", "cảnh báo/thông báo chính thức"
    if odd_link:
        return "scam", scam_type, "bước 1.1: link lạ/rút gọn"
    if SCAM_CUE_RE.search(text):
        return "scam", scam_type, "bước 1: mạo danh/khẩn cấp/đòi tiền-thông tin"
    if VAS_RE.search(text) or (LURE_RE.search(text) and re.search(r"(?i)soạn|soan", text)):
        return "spam", "", "bước 2.2: bẫy cước đầu số"
    if QC_RE.search(text) and OPT_OUT_RE.search(text):
        return "legitimate", "", "1.3: [QC] + cú pháp từ chối"
    if AD_RE.search(text):
        return "spam", "", "2.1: quảng cáo"
    return "scam", scam_type, "mặc định (bài cảnh báo lừa đảo) - cần xem kỹ"


def guess_channel(*texts: str) -> str:
    joined = " ".join(t for t in texts if t)
    for name, pattern in CHANNEL_RES:
        if pattern.search(joined):
            return name
    return "unknown"


def dedup_key(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"\[(?:number|money|time|date|phone|bank_acc)\]", " ", value)
    value = re.sub(r"[^\w]+", " ", value)
    return hashlib.sha1(value.strip().encode("utf-8")).hexdigest()


def shingles(text: str, k: int = 4) -> set[str]:
    value = re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()
    return {value[i:i + k] for i in range(max(1, len(value) - k + 1))}


def near_duplicate(text: str, pool: list[set[str]], threshold: float = 0.8) -> bool:
    a = shingles(text)
    for b in pool:
        inter = len(a & b)
        if inter and inter / len(a | b) >= threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Polite HTTP: one lock + delay PER HOST, so different sites run in parallel
# while each single site still sees at most one request every `delay` seconds.
# ---------------------------------------------------------------------------
class PoliteSession:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.local = threading.local()
        self.host_locks: dict[str, threading.Lock] = {}
        self.host_last: dict[str, float] = {}
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.meta_lock = threading.Lock()

    def _session(self) -> requests.Session:
        if not hasattr(self.local, "session"):
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.8"})
            self.local.session = session
        return self.local.session

    def _host_lock(self, host: str) -> threading.Lock:
        with self.meta_lock:
            return self.host_locks.setdefault(host, threading.Lock())

    def _robots_for(self, url: str):
        host = urlparse(url).netloc
        with self.meta_lock:
            if host in self.robots:
                return self.robots[host]
        parser = urllib.robotparser.RobotFileParser()
        try:
            response = self._session().get(f"https://{host}/robots.txt", timeout=20)
            text = response.text if response.ok else ""
        except requests.RequestException:
            text = ""
        if re.search(r"(?im)^\s*content-signal:.*ai-train\s*=\s*no", text):
            print(f"  [robots] {host} declares ai-train=no -> skipping this domain")
            parser = None
        else:
            parser.parse(text.splitlines())
        with self.meta_lock:
            self.robots[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return parser is not None and parser.can_fetch(USER_AGENT, url)

    def get(self, url: str, *, binary: bool = False, retries: int = 3, max_bytes: int = 8_000_000):
        if not self.allowed(url):
            return None
        host = urlparse(url).netloc
        lock = self._host_lock(host)
        for attempt in range(retries):
            with lock:
                wait = self.delay - (time.time() - self.host_last.get(host, 0.0))
                if wait > 0:
                    time.sleep(wait)
                self.host_last[host] = time.time()
                try:
                    headers = {"Accept": "image/jpeg,image/png,image/webp;q=0.9,*/*;q=0.5"} if binary else None
                    response = self._session().get(url, timeout=30, allow_redirects=True, headers=headers)
                except requests.RequestException as error:
                    print(f"  [warn] {error.__class__.__name__} on {url[:90]}")
                    response = None
            if response is None:
                time.sleep(2 ** attempt * self.delay)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (attempt + 1) * self.delay)
                continue
            # Redirect to a different path (e.g. homepage / 404 page) means "not available".
            if not response.ok or urlparse(response.url).path != urlparse(url).path:
                return None
            if binary:
                if "avif" in response.headers.get("content-type", ""):
                    return None  # OpenCV / older Pillow cannot decode AVIF
                return response.content if len(response.content) <= max_bytes else None
            return response.text
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def slug_tier(url: str) -> int:
    """2 = channel word + scam word, 1 = scam word only, 0 = skip."""
    slug = "-" + urlparse(url).path.lower().strip("/").rsplit(".", 1)[0].rsplit("/", 1)[-1] + "-"

    def has(term: str) -> bool:
        return f"-{term}-" in slug

    strong = any(has(t) for t in SLUG_SCAM_STRONG)
    weak = any(has(t) for t in SLUG_SCAM_WEAK)
    channel = any(has(t) for t in SLUG_CHANNEL)
    if channel and (strong or weak):
        return 2
    return 1 if strong else 0


def discover_source(http: PoliteSession, source: str, months: int) -> list[tuple[str, str, int]]:
    config = SOURCES[source]
    cutoff = datetime.now(VN_TZ).date() - timedelta(days=30 * months)
    children = list(config.get("children", []))
    if "index" in config:
        index_xml = http.get(config["index"])
        if not index_xml:
            print(f"[discover] cannot read sitemap index of {source}")
            return []
        for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", index_xml):
            loc = html.unescape(loc)
            date = child_sitemap_date(loc)
            if date is not None and date >= cutoff.replace(day=1):
                children.append(loc)
    print(f"[discover] {source}: scanning {len(children)} child sitemaps since {cutoff}")
    found: dict[str, int] = {}
    for number, child in enumerate(children, 1):
        xml = http.get(child)
        if not xml:
            continue
        for url in (html.unescape(u) for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)):
            tier = slug_tier(url)
            if tier:
                found[url] = max(tier, found.get(url, 0))
        if number % 20 == 0:
            print(f"  {source}: {number}/{len(children)} sitemaps, {len(found)} articles so far")
    tiers = Counter(found.values())
    print(f"[discover] {source}: {len(found)} articles (tier2={tiers[2]}, tier1={tiers[1]})")
    return [(url, source, tier) for url, tier in found.items()]


def discover_articles(http: PoliteSession, sources: list[str], months: int) -> list[tuple[str, str, int]]:
    results: list[tuple[str, str, int]] = []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        for future in as_completed([pool.submit(discover_source, http, s, months) for s in sources]):
            results.extend(future.result())
    return results


def interleave(queue: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    """Tier 2 first, and round-robin over sources so parallel workers hit different hosts."""
    ordered = []
    for tier in (2, 1, 0):
        by_source: dict[str, list] = {}
        for item in queue:
            if item[2] == tier:
                by_source.setdefault(item[1], []).append(item)
        lists = list(by_source.values())
        while any(lists):
            for items in lists:
                if items:
                    ordered.append(items.pop(0))
    return ordered


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


PARSER = "lxml" if _has_lxml() else "html.parser"


def parse_article(page: str, url: str) -> dict | None:
    soup = BeautifulSoup(page, PARSER)
    for junk in soup(["script", "style", "noscript"]):
        junk.decompose()

    def paragraph_chars(element) -> int:
        return sum(len(p.get_text(strip=True)) for p in element.find_all("p"))

    content = None
    for selector in CONTENT_SELECTORS:
        element = soup.select_one(selector)
        if element is not None and paragraph_chars(element) >= 400:
            content = element
            break
    if content is None:  # fallback: the container holding the most paragraph text
        containers = [p.parent for p in soup.find_all("p") if p.parent is not None]
        if not containers:
            return None
        content = max(set(containers), key=paragraph_chars)
        if paragraph_chars(content) < 400:
            return None
    title_tag = soup.select_one("h1")
    published = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find(
        "meta", attrs={"itemprop": "datePublished"})
    blocks = []
    for tag in content.find_all(["p", "blockquote", "li", "em", "i"]):
        text = nfc(tag.get_text(" ", strip=True))
        if len(text) >= 30:
            blocks.append((tag.name, text))
    images = []
    for rank, img in enumerate(content.find_all("img")):
        src = img.get("data-original") or img.get("data-src") or img.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        # The caption must belong to THIS image: nearest <figure>, else the closest
        # ancestor that contains no other image.
        figure = img.find_parent("figure")
        if figure is None:
            figure = next((p for p in img.parents if len(p.find_all("img")) == 1
                           and p.select_one("figcaption, .PhotoCMS_Caption, .image-caption")), None)
        caption_tag = figure.select_one("figcaption, .PhotoCMS_Caption, .image-caption") if figure else None
        caption = nfc(caption_tag.get_text(" ", strip=True)) if caption_tag else ""
        previous = img.find_previous("p")
        before = nfc(previous.get_text(" ", strip=True))[-250:] if previous else ""
        width = _int(img.get("width")) or _int(img.get("data-width"))
        height = _int(img.get("height")) or _int(img.get("data-height"))
        # CDNs (cand, tienphong, vietnamplus) serve "x.jpg.avif"; the original "x.jpg" exists too.
        src = re.sub(r"(?i)(\.(?:jpe?g|png|webp))\.avif(?=$|\?)", r"\1", src)
        images.append({"url": urljoin(url, src), "alt": nfc(img.get("alt", "")), "caption": caption,
                       "before": before, "rank": rank, "width": width, "height": height})
    published_value = (published.get("content") if published else "") or ""
    if not published_value:  # JSON-LD fallback (dantri, vietnamnet)
        match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
        published_value = match.group(1) if match else ""
    title = nfc(title_tag.get_text(" ", strip=True)) if title_tag else ""
    relevance = len(SMS_MENTION_RE.findall(title)) * 2 + sum(
        len(SMS_MENTION_RE.findall(text)) for _, text in blocks)
    return {"title": title, "published": published_value, "blocks": blocks, "images": images,
            "relevance": relevance}


def _int(value) -> int:
    try:
        return int(str(value).strip().rstrip("px"))
    except (TypeError, ValueError):
        return 0


def looks_like_message(span: str) -> bool:
    if FIRST_PERSON_RE.match(span) and not URL_RE.search(span):
        return False
    if ADVICE_RE.match(span):
        return False
    if JOURNALISM_MARKERS.search(span):
        return False
    return True


def text_candidates(article: dict, stats: Counter, debug: list | None = None) -> list[tuple[str, str]]:
    """(message, context) pairs quoted verbatim AND introduced as a message."""
    results = []
    for tag_name, block in article["blocks"]:
        spans = []
        for match in QUOTE_RE.finditer(block):
            before = block[max(0, match.start() - 140):match.start()]
            if INTRO_BEFORE_RE.search(before):
                spans.append(match.group(1))
            else:
                stats["text_quote_no_intro"] += 1
                if debug is not None:
                    debug.append(("text_quote_no_intro", match.group(1), before))
        intro = CONTENT_INTRO_RE.search(block)
        if intro and SMS_MENTION_RE.search(block[:intro.start() + 1] or block):
            spans.append(intro.group(1))
        if tag_name in ("blockquote", "em", "i") and 30 <= len(block) <= 700:
            spans.append(block)
        for span in spans:
            span = nfc(span).strip(" \"“”'«»")
            stats["text_spans"] += 1
            if not looks_like_message(span):
                stats["text_rejected_journalism"] += 1
                if debug is not None:
                    debug.append(("text_rejected_journalism", span, block[:200]))
                continue
            results.append((span, block[:300]))
    return results


def image_priority(image: dict) -> int:
    name = image["url"].rsplit("/", 1)[-1]
    score = 0
    if SCREENSHOT_HINT_RE.search(name + " " + image["caption"]):
        score += 3
    if SMS_MENTION_RE.search(image["before"]) or re.search(r"(?i)nội dung|như sau|dưới đây|ảnh", image["before"][-80:]):
        score += 2
    if image["height"] and image["width"] and image["height"] > image["width"] * 1.2:
        score += 1
    return score


def select_images(article: dict, limit: int, stats: Counter) -> list[dict]:
    """Rule-based screenshot filter (no pretrained model): skip logos/small images and
    only OCR images whose caption / file name / preceding paragraph points to a message."""
    chosen = []
    for image in article["images"]:
        stats["images_seen"] += 1
        if SKIP_IMAGE_RE.search(image["url"]):
            stats["images_skip_logo"] += 1
            continue
        if (image["width"] and image["width"] < 250) or (image["height"] and image["height"] < 150):
            stats["images_skip_small_attr"] += 1
            continue
        image["priority"] = image_priority(image)
        if image["priority"] < 2:
            stats["images_skip_no_hint"] += 1
            continue
        chosen.append(image)
    chosen.sort(key=lambda i: (-i["priority"], i["rank"]))
    stats["images_selected"] += len(chosen[:limit])
    return chosen[:limit]


def image_size(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return (0, 0)


class OcrEngine:
    def __init__(self) -> None:
        import easyocr  # imported lazily: heavy dependency

        try:
            import torch
            gpu = bool(torch.cuda.is_available())
        except ImportError:
            gpu = False
        print(f"[ocr] EasyOCR loading (gpu={gpu}) ...")
        self.reader = easyocr.Reader(["vi", "en"], gpu=gpu, verbose=False)

    def read_blocks(self, image_bytes: bytes, height: int) -> tuple[list[str], str]:
        """Return (bubbles, raw_text). Lines are grouped into blocks by vertical gap and
        horizontal overlap, so two columns / two bubbles do not get mixed together."""
        source = image_bytes
        try:  # decode with Pillow (handles WebP/CMYK/palette PNGs that cv2.imdecode may reject)
            import numpy as np
            from PIL import Image
            with Image.open(io.BytesIO(image_bytes)) as image:
                source = np.array(image.convert("RGB"))
        except Exception:
            pass
        results = self.reader.readtext(source, detail=1, paragraph=False)
        lines = []
        for box, text, confidence in results:
            text = nfc(text)
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append({"x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                          "text": text, "conf": confidence})
        raw = "\n".join(l["text"] for l in sorted(lines, key=lambda l: (round(l["y0"] / 12), l["x0"])))
        keep = []
        for line in lines:
            if line["conf"] < 0.3 or UI_NOISE_RE.match(line["text"]):
                continue
            if height and line["y1"] < height * 0.07 and len(line["text"]) < 25:  # status bar
                continue
            keep.append(line)
        if not keep:
            return [], raw
        heights = sorted(l["y1"] - l["y0"] for l in keep)
        line_h = heights[len(heights) // 2] or 12

        def joins(block: list[dict], line: dict) -> bool:
            yc = (line["y0"] + line["y1"]) / 2
            # same visual row: EasyOCR often cuts one line into side-by-side pieces
            for other in block:
                if abs((other["y0"] + other["y1"]) / 2 - yc) < 0.5 * line_h:
                    gap = max(line["x0"] - other["x1"], other["x0"] - line["x1"])
                    if gap < 2.5 * line_h:
                        return True
            # next row of the same bubble: small vertical gap + horizontal overlap with the block
            bottom = max(l["y1"] for l in block)
            bx0, bx1 = min(l["x0"] for l in block), max(l["x1"] for l in block)
            overlap = min(bx1, line["x1"]) - max(bx0, line["x0"])
            return -0.3 * line_h <= line["y0"] - bottom < 1.3 * line_h and overlap > 0

        blocks: list[list[dict]] = []
        for line in sorted(keep, key=lambda l: (l["y0"], l["x0"])):
            target = next((b for b in reversed(blocks) if joins(b, line)), None)
            if target is None:
                blocks.append([line])
            else:
                target.append(line)
        bubbles = []
        for block in blocks:
            ordered = sorted(block, key=lambda l: (round(((l["y0"] + l["y1"]) / 2) / line_h), l["x0"]))
            bubbles.append(fix_ocr_text(" ".join(l["text"] for l in ordered)))
        return bubbles, raw


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def default_out_dir() -> Path:
    if Path("/kaggle/working").exists():
        return Path("/kaggle/working/vi_scam_crawl_v2")
    return Path(__file__).resolve().parent.parent / "data" / "raw" / "vi_scam_crawl_v2"


def load_state(out_dir: Path) -> tuple[set[str], set[str], list[set[str]], int]:
    done_file = out_dir / "articles_done.txt"
    done = set(done_file.read_text(encoding="utf-8").split()) if done_file.exists() else set()
    keys: set[str] = set()
    pool: list[set[str]] = []
    count = 0
    candidates = out_dir / "vi_scam_candidates.csv"
    if candidates.exists():
        with candidates.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                keys.add(dedup_key(row["message"]))
                pool.append(shingles(row["message"]))
                count += 1
    return done, keys, pool, count


def load_skip_sources(paths: list[Path]) -> tuple[set[str], set[str], list[set[str]]]:
    """Articles / messages of EARLIER crawl runs (--skip-from), so a new run only collects new data.

    A directory contributes its articles_done.txt and every *.csv with a `message` column (candidates,
    reviewed files); a .txt file is a list of article URLs; a .csv contributes `message` and `source_url`.
    Skipped data is NOT written to the new output."""
    urls: set[str] = set()
    keys: set[str] = set()
    pool: list[set[str]] = []
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += sorted(path.glob("articles_done*.txt")) + sorted(path.glob("*.csv"))
        elif path.exists():
            files.append(path)
        else:
            print(f"[skip-from] WARNING: {path} not found")
    for file in files:
        if file.suffix == ".txt":
            urls.update(file.read_text(encoding="utf-8").split())
            continue
        with file.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "message" not in reader.fieldnames:
                continue
            for row in reader:
                if row.get("source_url"):
                    urls.add(row["source_url"].strip())
                if row.get("message"):
                    keys.add(dedup_key(row["message"]))
                    pool.append(shingles(row["message"]))
    return urls, keys, pool


def append_rows(path: Path, rows: list[dict]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def fetch_article(http: PoliteSession, url: str, args, stats: Counter) -> dict | None:
    """Network part (runs in worker threads): page + selected screenshots."""
    page = http.get(url)
    if not page:
        stats["articles_fetch_failed"] += 1
        return None
    article = parse_article(page, url)
    if not article:
        stats["articles_parse_failed"] += 1
        return None
    if article["relevance"] < args.min_relevance:
        stats["articles_not_about_messages"] += 1
        return article | {"skip": True}
    stats["articles_relevant"] += 1
    article["downloads"] = []
    if args.ocr is not False:
        for image in select_images(article, args.max_images, stats):
            data = http.get(image["url"], binary=True)
            if data:
                article["downloads"].append((image, data))
    return article


def write_review_html(out_dir: Path) -> None:
    """Static page: image next to editable text + label dropdowns, exports CSV."""
    path = out_dir / "vi_scam_candidates.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    page = REVIEW_HTML.replace("__ROWS__", data).replace("__COLUMNS__", json.dumps(OUTPUT_COLUMNS)) \
        .replace("__REASONS__", json.dumps(REJECT_REASONS))
    (out_dir / "review.html").write_text(page, encoding="utf-8")


REVIEW_HTML = r"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Duyệt tin nhắn crawl</title><style>
body{font:14px/1.45 system-ui,sans-serif;margin:0;background:#f6f6f4;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:8px 16px;display:flex;gap:12px;align-items:center;z-index:2}
.card{display:grid;grid-template-columns:340px 1fr;gap:14px;background:#fff;margin:12px 16px;padding:12px;border:1px solid #ddd;border-radius:6px}
.card.done{border-left:6px solid #2a7}.card.no{border-left:6px solid #c44}
img{max-width:330px;max-height:520px;cursor:zoom-in;border:1px solid #eee}
textarea{width:100%;min-height:90px;font:inherit}
.meta{color:#666;font-size:12px;margin:4px 0}.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
select,input{font:inherit}button{font:inherit;padding:4px 10px}
</style></head><body>
<header><b>Duyệt tin nhắn</b><span id="prog"></span>
<label><input type="checkbox" id="hide"> ẩn tin đã duyệt</label>
<button onclick="exportCsv()">Xuất CSV đã duyệt</button>
<span class="meta">Tự lưu trong trình duyệt (localStorage).</span></header>
<div id="list"></div>
<script>
const ROWS=__ROWS__, COLS=__COLUMNS__, REASONS=__REASONS__;
const KEY="vi_scam_review_"+ROWS.length;
const saved=JSON.parse(localStorage.getItem(KEY)||"{}");
ROWS.forEach(r=>Object.assign(r,saved[r.candidate_id]||{}));
const LABELS=["","scam","spam","legitimate","drop"];
const TYPES=["","banking_finance","gov_utility_services","delivery_logistics","job_task_scam","investment","loan_debt","prize_lottery","social_impersonation","other_scam"];
const CH=["","sms","zalo","messenger","whatsapp","telegram","viber","unknown"];
function opt(list,v){return list.map(x=>`<option ${x===v?"selected":""}>${x}</option>`).join("")}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function save(r){saved[r.candidate_id]={message:r.message,review_label:r.review_label,review_scam_type:r.review_scam_type,review_channel:r.review_channel,reject_reason:r.reject_reason,review_note:r.review_note};localStorage.setItem(KEY,JSON.stringify(saved));prog()}
function prog(){const n=ROWS.filter(r=>r.review_label).length;document.getElementById("prog").textContent=`${n}/${ROWS.length} đã duyệt`;
 document.querySelectorAll(".card").forEach((c,i)=>{const r=ROWS[i];c.className="card"+(r.review_label?(r.review_label==="drop"?" no":" done"):"");c.style.display=(document.getElementById("hide").checked&&r.review_label)?"none":""})}
function render(){document.getElementById("list").innerHTML=ROWS.map((r,i)=>`<div class="card">
 <div>${r.image_path?`<a href="${esc(r.image_path)}" target="_blank"><img loading="lazy" src="${esc(r.image_path)}"></a>`:"<i>(trích từ văn bản bài báo)</i>"}
 <div class="meta">${esc(r.evidence_type)} · ${esc(r.source_name)} · điểm ${esc(r.sms_score)}</div>
 <div class="meta"><a href="${esc(r.source_url)}" target="_blank">${esc(r.article_title)}</a></div>
 <div class="meta">Ngữ cảnh: ${esc(r.context_snippet)}</div></div>
 <div><textarea data-i="${i}" data-f="message">${esc(r.message)}</textarea>
 <div class="meta">Gợi ý: <b>${esc(r.label_suggested)}</b> ${esc(r.scam_type_suggested)} — ${esc(r.label_reason)} · kênh: ${esc(r.channel_suggested)}</div>
 <div class="row">Nhãn <select data-i="${i}" data-f="review_label">${opt(LABELS,r.review_label)}</select>
 Loại <select data-i="${i}" data-f="review_scam_type">${opt(TYPES,r.review_scam_type)}</select>
 Kênh <select data-i="${i}" data-f="review_channel">${opt(CH,r.review_channel)}</select>
 Lý do loại <select data-i="${i}" data-f="reject_reason">${opt([""].concat(REASONS),r.reject_reason)}</select>
 <input data-i="${i}" data-f="review_note" placeholder="ghi chú" value="${esc(r.review_note)}">
 <button onclick="quick(${i})">= gợi ý</button></div>
 ${r.ocr_raw?`<details><summary class="meta">OCR gốc</summary><pre>${esc(r.ocr_raw)}</pre></details>`:""}</div></div>`).join("");
 document.querySelectorAll("[data-f]").forEach(el=>el.addEventListener("change",e=>{const r=ROWS[+el.dataset.i];r[el.dataset.f]=el.value;
  if(el.dataset.f==="review_label"&&el.value==="drop"&&!r.reject_reason){r.reject_reason="not_message"}save(r);if(el.dataset.f==="review_label")render()}));prog()}
function quick(i){const r=ROWS[i];r.review_label=r.label_suggested;r.review_scam_type=r.scam_type_suggested;r.review_channel=r.review_channel||r.channel_suggested;save(r);render()}
function exportCsv(){const q=v=>'"'+String(v??"").replace(/"/g,'""')+'"';
 const csv="﻿"+COLS.join(",")+"\n"+ROWS.map(r=>COLS.map(c=>q(r[c])).join(",")).join("\n");
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="vi_scam_candidates_reviewed.csv";a.click()}
document.getElementById("hide").addEventListener("change",prog);render();
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=default_out_dir())
    parser.add_argument("--sources", nargs="+", default=list(SOURCES), choices=list(SOURCES))
    parser.add_argument("--months", type=int, default=36, help="how far back to scan sitemaps")
    parser.add_argument("--max-articles", type=int, default=1500)
    parser.add_argument("--target", type=int, default=0, help="stop once this many candidates are on disk (0 = no limit)")
    parser.add_argument("--min-tier", type=int, default=1, choices=(1, 2), help="2 = only slugs with channel+scam words")
    parser.add_argument("--min-relevance", type=int, default=2, help="mentions of tin nhắn/SMS/brandname... in the article")
    parser.add_argument("--urls-file", type=Path, help="extra article URLs, one per line (any site)")
    parser.add_argument("--no-discover", action="store_true", help="only use --urls-file")
    parser.add_argument("--rediscover", action="store_true", help="ignore the cached articles_queue.csv")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between requests to the SAME site")
    parser.add_argument("--workers", type=int, default=8, help="parallel article downloads (different sites)")
    parser.add_argument("--min-score", type=int, default=2, help="minimum SMS-likeness score")
    parser.add_argument("--ocr", dest="ocr", action="store_true", default=None)
    parser.add_argument("--no-ocr", dest="ocr", action="store_false")
    parser.add_argument("--max-images", type=int, default=4, help="screenshots OCR'd per article")
    parser.add_argument("--debug", action="store_true", help="also write rejected texts to rejected_debug.csv")
    parser.add_argument("--skip-from", nargs="+", type=Path,
                        help="earlier run folders / files (articles_done.txt, candidate or reviewed CSVs): their "
                             "articles and messages are skipped, e.g. data/review/vi_crawl_seen_run1_2")
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    candidates_path = out_dir / "vi_scam_candidates.csv"
    done_path = out_dir / "articles_done.txt"
    queue_path = out_dir / "articles_queue.csv"
    stats_path = out_dir / "crawl_stats.json"
    done, seen_keys, shingle_pool, existing = load_state(out_dir)
    stats: Counter = Counter(json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {})
    print(f"[state] {len(done)} articles already processed, {existing} candidates on disk -> {out_dir}")
    if args.skip_from:
        skip_urls, skip_keys, skip_pool = load_skip_sources(args.skip_from)
        done |= skip_urls
        seen_keys |= skip_keys
        shingle_pool += skip_pool
        print(f"[skip-from] earlier runs: {len(skip_urls)} articles and {len(skip_keys)} messages will be skipped")

    ocr = None
    if args.ocr is not False:
        try:
            ocr = OcrEngine()
        except Exception as error:  # ImportError or model download failure
            if args.ocr:
                raise
            print(f"[ocr] disabled ({error.__class__.__name__}: {error}). Install easyocr to enable.")
            args.ocr = False

    http = PoliteSession(args.delay)

    # 1. Build the article queue (cached so a restart does not rescan sitemaps).
    queue: list[tuple[str, str, int]] = []
    if queue_path.exists() and not args.rediscover:
        with queue_path.open(encoding="utf-8", newline="") as handle:
            queue = [(r["url"], r["source"], int(r.get("tier") or 2)) for r in csv.DictReader(handle)]
        print(f"[queue] loaded {len(queue)} articles from {queue_path.name}")
    elif not args.no_discover:
        started = time.time()
        queue = interleave(discover_articles(http, args.sources, args.months))
        with queue_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["url", "source", "tier"])
            writer.writerows(queue)
        tiers = Counter(t for _, _, t in queue)
        print(f"[queue] discovered {len(queue)} articles (tier2={tiers[2]}, tier1={tiers[1]}) "
              f"in {(time.time() - started) / 60:.1f} min")
    if args.urls_file:
        extra = [line.strip() for line in args.urls_file.read_text(encoding="utf-8").splitlines()]
        queue = [(u, urlparse(u).netloc, 2) for u in extra if u.startswith("http")] + queue

    # 2. Process articles: downloads in parallel (per-site politeness), OCR + writing in this thread.
    todo = [item for item in queue if item[0] not in done and item[2] >= args.min_tier][: args.max_articles]
    print(f"[crawl] {len(todo)} articles to process (max {args.max_articles}, workers {args.workers})")
    total_new = 0
    seen_images: set[str] = set()
    debug: list | None = [] if args.debug else None
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_article, http, url, args, stats): (url, source, tier)
                   for url, source, tier in todo}
        for number, future in enumerate(as_completed(futures), 1):
            url, source, tier = futures[future]
            try:
                article = future.result()
            except Exception as error:  # never let one bad page stop the crawl
                print(f"  [error] {error.__class__.__name__}: {error} on {url[:90]}")
                article = None
            stats["articles_processed"] += 1
            rows: list[dict] = []
            if article and not article.get("skip"):
                now = datetime.now(VN_TZ).isoformat(timespec="seconds")
                base = {
                    "source_name": source, "source_url": url, "article_title": article["title"],
                    "published_date": article["published"][:10], "collected_at": now,
                    "article_tier": tier, "article_relevance": article["relevance"],
                    "review_label": "", "review_scam_type": "", "review_channel": "",
                    "reject_reason": "", "review_note": "",
                }

                def add(message: str, evidence: str, context: str, min_score: int | None = None, **extra) -> bool:
                    message = nfc(message)
                    score = sms_score(message)  # scored before masking (phones/money are signals)
                    # A quote already introduced as a message ("tin nhắn có nội dung ...") needs
                    # less evidence, but must look like a whole sentence, not a fragment.
                    if min_score is None:
                        min_score = args.min_score
                    if evidence == "text":
                        if not SENTENCE_START_RE.match(message):
                            stats["text_fragment"] += 1
                            return False
                        min_score = max(1, args.min_score - 1)
                    if len(message) < 25 or score < min_score:
                        stats[f"{evidence}_low_score"] += 1
                        if debug is not None:
                            debug.append((f"{evidence}_low_score({score})", message, context[:200]))
                        return False
                    if vietnamese_ratio(message) < 0.9:
                        stats[f"{evidence}_not_vietnamese"] += 1
                        return False
                    if evidence == "ocr" and INFOGRAPHIC_RE.search(strip_accents(message)) \
                            and not message.lstrip().startswith("["):
                        stats["ocr_infographic"] += 1
                        if debug is not None:
                            debug.append(("ocr_infographic", message, context[:200]))
                        return False
                    message = mask_pii(message)
                    key = dedup_key(message)
                    if key in seen_keys or near_duplicate(message, shingle_pool):
                        stats[f"{evidence}_duplicate"] += 1
                        return False
                    seen_keys.add(key)
                    shingle_pool.append(shingles(message))
                    label, scam_type, reason = suggest_labels(message)
                    stats[f"{evidence}_kept"] += 1
                    rows.append({
                        **base, **extra, "candidate_id": f"vi_crawl_{key[:12]}", "message": message,
                        "label_suggested": label, "scam_type_suggested": scam_type, "label_reason": reason,
                        "channel_suggested": guess_channel(context, article["title"], message),
                        "sms_score": score, "evidence_type": evidence,
                        "context_snippet": mask_pii(context)[:300],
                    })
                    return True

                for message, context in text_candidates(article, stats, debug):
                    add(message, "text", context, image_url="", image_path="", image_rank="", ocr_raw="")

                for image, data in article.get("downloads", []):
                    digest = hashlib.sha1(data).hexdigest()
                    if digest in seen_images:
                        stats["images_duplicate"] += 1
                        continue
                    seen_images.add(digest)
                    width, height = image_size(data)
                    if width and (min(width, height) < 200):
                        stats["images_skip_small_real"] += 1
                        continue
                    stats["images_ocr"] += 1
                    try:
                        bubbles, raw = ocr.read_blocks(data, height)
                    except Exception as error:
                        print(f"  [ocr] failed on {image['url'][:90]}: {error}")
                        continue
                    before_rows = len(rows)
                    suffix = Path(urlparse(image["url"]).path).suffix.lower() or ".jpg"
                    image_path = out_dir / "images" / f"{digest[:16]}{suffix}"
                    context = " ".join(x for x in (image["caption"], image["before"]) if x)
                    image_extra = {"image_url": image["url"], "image_rank": image["rank"], "ocr_raw": raw,
                                   "image_path": str(image_path.relative_to(out_dir)).replace("\\", "/")}
                    for bubble in bubbles:
                        stats["ocr_bubbles"] += 1
                        add(bubble, "ocr", context, **image_extra)
                    # No single bubble passed: one message was probably split by the layout
                    # (two columns, wide gaps). Retry with all pieces joined, stricter score.
                    if len(rows) == before_rows and 1 < len(bubbles) <= 12:
                        if add(" ".join(bubbles), "ocr", context, min_score=args.min_score + 1, **image_extra):
                            stats["ocr_merged_fallback"] += 1
                    if len(rows) > before_rows:  # keep only images that produced a candidate
                        image_path.write_bytes(data)
                        stats["images_with_candidate"] += 1

            if rows:
                append_rows(candidates_path, rows)
                total_new += len(rows)
            if debug:
                debug_path = out_dir / "rejected_debug.csv"
                new_file = not debug_path.exists()
                with debug_path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    if new_file:
                        writer.writerow(["stage", "text", "context", "source_url"])
                    writer.writerows([(stage, text, ctx, url) for stage, text, ctx in debug])
                debug.clear()
            with done_path.open("a", encoding="utf-8") as handle:
                handle.write(url + "\n")
            stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            if rows or number % 25 == 0:
                rate = number / max(1e-9, (time.time() - started) / 60)
                print(f"[{number}/{len(todo)}] +{len(rows):2d} (total {existing + total_new}) "
                      f"{rate:.0f} art/min | {url[:80]}")
            if args.target and existing + total_new >= args.target:
                print(f"[crawl] target {args.target} reached -> stopping")
                for pending in futures:
                    pending.cancel()
                break

    # 3. Summary + review page.
    write_review_html(out_dir)
    print("\n" + "=" * 70)
    print(f"New candidates this run: {total_new} | total on disk: {existing + total_new}")
    print("Funnel:", json.dumps({k: stats[k] for k in sorted(stats)}, ensure_ascii=False))
    if candidates_path.exists():
        with candidates_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for column in ("source_name", "evidence_type", "label_suggested", "scam_type_suggested", "channel_suggested"):
            print(f"  {column:<20} {dict(Counter(r[column] for r in rows).most_common())}")
    print(f"Output: {candidates_path}\nReview page: {out_dir / 'review.html'} (open it next to the images/ folder)")
    print("NEXT: every row must be reviewed by a person (review.html -> export CSV).")


if __name__ == "__main__":
    main()
