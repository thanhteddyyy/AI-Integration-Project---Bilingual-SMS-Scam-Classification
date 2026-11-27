"""Build notebooks/crawl_vi_scam_kaggle.ipynb from scripts/crawl_vi_scam.py.

Run after every change to the crawler, so the notebook's %%writefile cell
always contains the current script:
    python scripts/make_crawl_notebook.py
"""
import base64
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
script = (ROOT / "scripts" / "crawl_vi_scam.py").read_text(encoding="utf-8")
OUT = "/kaggle/working/vi_scam_crawl_run3"
# articles + messages of crawl runs 1-2 (data/review/vi_crawl_seen_run1_2): a Kaggle dataset is used when
# attached, otherwise the copy EMBEDDED below is unpacked (no upload needed; 2026-11-27 run failed without it)
SEEN_GLOB = "/kaggle/input/**/seen_messages.csv"
SEEN_LOCAL = "/kaggle/working/vi_crawl_seen_run1_2"
_buf = io.BytesIO()
with tarfile.open(fileobj=_buf, mode="w:gz") as _tar:
    for _f in sorted((ROOT / "data" / "review" / "vi_crawl_seen_run1_2").iterdir()):
        _tar.add(_f, arcname=_f.name)
_b64 = base64.b64encode(_buf.getvalue()).decode("ascii")
SEEN_BLOB = "\n".join(_b64[i:i + 120] for i in range(0, len(_b64), 120))


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(True)}


cells = [
    md(f"""
# Crawl tin nhắn lừa đảo tiếng Việt – đợt 3 (External test của tầng 2)

Notebook chạy `crawl_vi_scam.py` trên Kaggle. Hướng dẫn: `docs/huong_dan_crawl_vi_scam.md`.

**Trước khi chạy**, thanh bên phải → *Settings*:
- **Internet → On** (cần xác minh số điện thoại cho tài khoản Kaggle)
- **Accelerator → GPU T4** (EasyOCR chạy trên GPU; 1 GPU là đủ)

Mục tiêu: **~200–400 ứng viên MỚI** → sau khi người duyệt còn ≥100 tin dùng được.

**Đợt 3 phải bỏ qua dữ liệu đợt 1–2** (đợt 1–2 đã nằm trong train tầng 2). Danh sách bài và tin của đợt 1–2
đã được **nhúng sẵn trong notebook** (ô 4a) → không cần tải gì lên Kaggle. (Nếu có gắn Dataset `vi_crawl_seen_run1_2`
thì ô 4a dùng Dataset đó.)
EasyOCR chỉ là công cụ gõ hộ: **mọi tin đều phải được người kiểm tra và sửa**.

Kết quả trong `{OUT}/`:
- `vi_scam_candidates.csv` – ứng viên
- `review.html` + `images/` – trang duyệt (mở trên máy sau khi tải zip về)
- `crawl_stats.json` – số lượng ở từng khâu (bài → ảnh → bong bóng → ứng viên)
"""),
    md("## 1. Cài thư viện"),
    code("""
!pip install -q easyocr
import torch; print("GPU:", torch.cuda.is_available(), torch.cuda.device_count())
"""),
    md("## 2. Ghi script ra file\nNội dung giống hệt `scripts/crawl_vi_scam.py` (sinh bằng `scripts/make_crawl_notebook.py`)."),
    code("%%writefile crawl_vi_scam.py\n" + script),
    md("## 3. Chạy thử (1 tháng, 15 bài)\nKiểm tra mạng và OCR. Nếu một báo báo `cannot read sitemap index` thì bỏ báo đó khỏi `--sources`."),
    code("!python crawl_vi_scam.py --months 1 --max-articles 15 --out-dir /kaggle/working/test_run"),
    md(f"""
## 4. Chạy đầy đủ
- Dừng khi đủ `--target` ứng viên hoặc hết `--max-articles` bài.
- Bị ngắt thì chạy lại ô này: script tự bỏ qua bài đã xử lý.
- Muốn quét lại sitemap (đổi `--months`/nguồn): thêm `--rediscover`.
- Muốn chỉ lấy bài chắc chắn nói về tin nhắn: thêm `--min-tier 2`.
"""),
    md("""
## 4a. Dữ liệu đợt 1–2 cần bỏ qua (bắt buộc, tự động)
Dùng Dataset nếu có gắn, nếu không thì giải nén bản nhúng sẵn. Phải in ra khoảng 2.500 bài và 240 tin.
"""),
    code(f'''
import base64, glob, io, os, tarfile
SEEN_BLOB = """
{SEEN_BLOB}
"""
hits = glob.glob("{SEEN_GLOB}", recursive=True)
if hits:
    SEEN = os.path.dirname(hits[0]); print("dùng Dataset đã gắn:", SEEN)
else:
    SEEN = "{SEEN_LOCAL}"
    os.makedirs(SEEN, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode("".join(SEEN_BLOB.split()))), mode="r:gz") as tar:
        tar.extractall(SEEN, filter="data")
    print("dùng bản nhúng sẵn ->", SEEN)
n_urls = sum(len(open(os.path.join(SEEN, f), encoding="utf-8").read().split()) for f in os.listdir(SEEN) if f.endswith(".txt"))
n_msgs = sum(1 for _ in open(os.path.join(SEEN, "seen_messages.csv"), encoding="utf-8-sig")) - 1
print(os.listdir(SEEN), "| bài:", n_urls, "| dòng tin (gồm cả xuống dòng trong tin):", n_msgs)
assert n_urls > 2000, "thiếu danh sách bài đợt 1–2 – đừng chạy tiếp, sẽ crawl trùng"
'''),
    code(f"!python crawl_vi_scam.py --months 36 --max-articles 2500 --target 400 --max-images 4 --skip-from $SEEN --out-dir {OUT}"),
    md("## 5. Xem nhanh kết quả"),
    code(f"""
import json, pandas as pd
print(json.dumps(json.load(open("{OUT}/crawl_stats.json")), indent=1, ensure_ascii=False))
df = pd.read_csv("{OUT}/vi_scam_candidates.csv")
print(len(df), "candidates")
for col in ["source_name", "evidence_type", "label_suggested", "scam_type_suggested", "channel_suggested"]:
    print(col, df[col].value_counts().to_dict())
pd.set_option("display.max_colwidth", 200)
df.sort_values("sms_score", ascending=False)[["sms_score", "evidence_type", "label_suggested", "message"]].head(30)
"""),
    md("## 6. Nén kết quả để tải về\nTải `vi_scam_crawl_run3.zip` ở tab **Output** → giải nén → mở `review.html` (cùng thư mục với `images/`) → duyệt → **Xuất CSV**."),
    code("!cd /kaggle/working && zip -rq vi_scam_crawl_run3.zip vi_scam_crawl_run3 && ls -lh vi_scam_crawl_run3.zip"),
]
nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu", "isInternetEnabled": True}},
      "nbformat": 4, "nbformat_minor": 5}
out = ROOT / "notebooks" / "crawl_vi_scam_kaggle.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", out)
