"""Generate notebooks/colab_tier1_tier2.ipynb: train + evaluate BOTH tiers on Google Colab (Colab only).

Steps in the notebook: GPU check -> upload bilingual-scam-colab.zip -> install (scikit-learn pinned to the local
version so the models load in the demo) -> data check -> tier 1 (NB / SVM / CharCNN x 3 setups, select) ->
tier 1 on real Vietnamese scams (crawl runs 1-2 and run 3) -> tier 2 (9 scam types, grouped CV, external = run 3,
chain tier 1 -> tier 2) -> language id + whole pipeline on sample messages -> error analysis -> results zip.

Usage (from the repository root):
  py -3.11 scripts/make_colab_notebook.py      # writes notebooks/colab_tier1_tier2.ipynb
  py -3.11 scripts/package_for_colab.py        # writes bilingual-scam-colab.zip at the repo root (upload this to Colab)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "colab_tier1_tier2.ipynb"

SKLEARN_VERSION = "1.9.1"  # = local + demo_bundle/requirements.txt; joblib models only load with the same version
EXPECTED = {  # rows per split of the frozen data (data check cell)
    "tier1": {"vietnamese_balanced": 4899, "english_balanced": 8120, "bilingual": 13018},
    "files": {
        "data/raw/train_dataset_spamscam_v3.csv": 2195,
        "data/raw/test_dataset_spamscam_v3.csv": 597,
        "data/review/vi_tuan_train_removed_family_overlap.csv": 199,
        "data/raw/vi_crawl_tier2_train.csv": 48,
        "data/raw/vi_crawl_tier2_external.csv": 9,
        "data/raw/vi_crawl_external_full.csv": 48,
    },
    "tier2": {"train": 438, "validation": 86, "test": 84},
}

cells: list[tuple[str, str]] = []


def md(text: str) -> None:
    cells.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    cells.append(("code", text.strip("\n")))


md("""
# Phát hiện tin nhắn lừa đảo song ngữ – chạy lại **cả 2 tầng** trên Google Colab

| Tầng | Việc | Mô hình | Quy tắc chọn |
|---|---|---|---|
| **1** | ham / spam / scam (Việt + Anh) | Naive Bayes, Linear SVM, CharCNN (PyTorch) × 3 thiết lập | F2 lớp scam trên validation |
| **2** | 9 loại lừa đảo (chỉ tiếng Việt) | Naive Bayes, Linear SVM, CharCNN | macro-F1 trung bình CV 5 lượt theo khuôn |

Đã chốt: **SVM cho cả 2 tầng**. Notebook train lại cả 3 mô hình để có bảng so sánh cho báo cáo.

**Tin thật dùng để chấm (không dùng để train tầng 1):**
- crawl đợt 1–2 (48 tin, 44 scam): chấm tầng 1. Đợt 1–2 cũng được thêm vào **train** tầng 2.
- crawl **đợt 3** (9 tin scam, `data/raw/vi_crawl_tier2_external.csv`): **external test** của tầng 2 và của cả chuỗi tầng 1 → tầng 2.

**Chuẩn bị:** `Runtime → Change runtime type → T4 GPU`, rồi `Runtime → Run all`. Ô bước 2 sẽ hỏi upload
`bilingual-scam-colab.zip`. Thời gian khoảng **20–35 phút** với GPU (tầng 1 chiếm phần lớn).

**Kết thúc:** tải về `colab_results.zip` (model + báo cáo của cả 2 tầng).
""")

md("## Bước 1 – Kiểm tra GPU")
code("""
import torch
print("PyTorch:", torch.__version__)
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
else:
    print("CẢNH BÁO: đang chạy CPU – CharCNN sẽ rất chậm. Bật GPU (Runtime → Change runtime type) rồi chạy lại từ đầu.")
""")

md("## Bước 2 – Tải mã nguồn + dữ liệu (`bilingual-scam-colab.zip`)")
md("""
Cách nhanh: kéo thả `bilingual-scam-colab.zip` vào thanh **📁 Files** bên trái **trước khi** chạy (không giải nén).
Nếu chưa làm, ô dưới sẽ hiện nút **Choose Files** để chọn file zip.
""")
code("""
import glob, os, zipfile
from google.colab import files

ZIP_NAME = "bilingual-scam-colab.zip"
WORK = "/content"
PROJECT = f"{WORK}/bilingual-scam-baseline"

if not os.path.exists(PROJECT):
    local = f"{WORK}/{ZIP_NAME}"
    if not os.path.exists(local):  # chưa kéo thả vào thanh Files -> hỏi upload
        print("Chọn file", ZIP_NAME)
        local = f"{WORK}/" + next(iter(files.upload()))
    zipfile.ZipFile(local).extractall(WORK)

os.chdir(PROJECT)
print("Thư mục làm việc:", os.getcwd())
""")

md(f"""
## Bước 3 – Cài thư viện
`scikit-learn` được ghim đúng bản **{SKLEARN_VERSION}** (giống máy local và gói demo): model SVM / Naive Bayes lưu bằng joblib
chỉ nạp được với đúng phiên bản đã train.
""")
code(f"""
!pip install -q -e .
import subprocess, sys
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scikit-learn=={SKLEARN_VERSION}"], capture_output=True, text=True)
print("Ghim scikit-learn {SKLEARN_VERSION}:", "OK" if r.returncode == 0 else "KHÔNG ĐƯỢC – model sẽ chỉ dùng được trên Colab\\n" + r.stderr[-400:])

# Kernel đang chạy không thấy gói vừa cài kiểu editable -> thêm src/ cho notebook và cho các lệnh !python
SRC = os.path.join(PROJECT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
os.environ["PYTHONPATH"] = SRC + os.pathsep + os.environ.get("PYTHONPATH", "")
import sklearn, scam_baseline
print("scikit-learn", sklearn.__version__, "| scam_baseline OK")
""")

md("""
## Bước 4 – Kiểm tra dữ liệu đúng bản đã chốt
Mọi dòng phải ghi **khớp**. Nếu có dòng **KHÁC** → file zip cũ, hãy đóng gói lại trên máy (`scripts/package_for_colab.py`).
""")
code(f"""
import pandas as pd
EXPECTED_T1 = {EXPECTED["tier1"]!r}
EXPECTED_FILES = {EXPECTED["files"]!r}
SETUPS = {{"vietnamese_balanced": "data/processed_vi_balanced",
          "english_balanced": "data/processed_en_balanced",
          "bilingual": "data/processed_bilingual"}}
ok = True
print("Tầng 1 (số tin train):")
for setup, path in SETUPS.items():
    counts = pd.read_csv(f"{{path}}/modeling_data.csv", usecols=["split"], low_memory=False).split.value_counts()
    good = counts.get("train") == EXPECTED_T1[setup]
    ok &= good
    print(f"  {{setup:20s}} train={{counts.get('train')}} val={{counts.get('validation')}} test={{counts.get('test')}} "
          f"external={{counts.get('external_test')}}  {{'khớp' if good else 'KHÁC (mong đợi %d)' % EXPECTED_T1[setup]}}")
print("Tầng 2 + tin thật (số dòng):")
for path, n in EXPECTED_FILES.items():
    rows = len(pd.read_csv(path, encoding="utf-8-sig")) if os.path.exists(path) else None
    ok &= rows == n
    print(f"  {{path:55s}} {{rows}}  {{'khớp' if rows == n else 'KHÁC (mong đợi %d)' % n}}")
assert ok, "Dữ liệu không khớp bản đã chốt – đóng gói lại zip"
display(pd.read_csv("data/raw/vi_crawl_tier2_external.csv", encoding="utf-8-sig")[["crawl_id", "channel", "scam_type", "message"]])
""")

md("""
# TẦNG 1 – ham / spam / scam

## Bước 5 – Train 3 mô hình × 3 thiết lập
NB và SVM chạy vài giây. CharCNN: tối đa 30 epoch, 5 epoch khởi động, dừng sớm theo F2 lớp scam trên validation.
Muốn chạy nhanh (chỉ mô hình đã chốt): đổi `TIER1_SETUPS = ["bilingual"]` – khi đó bảng chọn mô hình ở bước 7 chỉ có thiết lập song ngữ.
""")
code("""
import time
TIER1_SETUPS = ["vietnamese_balanced", "english_balanced", "bilingual"]
for setup in TIER1_SETUPS:
    start = time.time()
    print(f"\\n===== {setup} =====")
    !python -m scam_baseline.cli --config configs/{setup}.yaml train --models nb svm charcnn
    print(f"--> {setup}: {(time.time() - start) / 60:.1f} phút")
assert os.path.exists("artifacts/bilingual/svm/model.joblib"), "Thiếu model tầng 1 song ngữ – tầng 2 cần nó để chấm cả chuỗi"
""")

md("## Bước 6 – Đường học của CharCNN tầng 1")
code("""
import json
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, len(TIER1_SETUPS), figsize=(5 * len(TIER1_SETUPS), 3.6), squeeze=False)
for ax, setup in zip(axes[0], TIER1_SETUPS):
    hist = json.load(open(f"artifacts/{setup}/charcnn/training_history.json"))
    meta = json.load(open(f"artifacts/{setup}/charcnn/training_metadata.json"))
    ep = [h["epoch"] for h in hist]
    ax.plot(ep, [h.get("validation_scam_f2") for h in hist], marker="o", label="val F2 scam")
    ax.plot(ep, [h["validation_macro_f1"] for h in hist], marker=".", label="val macro-F1")
    ax.axvspan(0.5, meta.get("min_epochs", 1) - 0.5, color="#eee", label="khởi động")
    ax.axvline(meta["best_epoch"], color="gray", linestyle="--", label=f"chọn epoch {meta['best_epoch']}")
    ax.set_title(setup); ax.set_xlabel("epoch"); ax.legend(fontsize=8)
plt.tight_layout(); plt.show()
""")

md("""
## Bước 7 – Tầng 1 trên tin lừa đảo tiếng Việt thật + chọn mô hình
- **Đợt 1–2** (tập đầy đủ: cả tin cùng khuôn với tập Tuấn và tin Zalo/Messenger) → `reports/vi_crawl_full/`
- **Đợt 3** (9 tin) → `reports/vi_crawl_run3/`

Số là **tỉ lệ bắt được** (recall lớp scam). Bảng chọn mô hình dùng validation; tin thật chỉ để báo cáo.
""")
code("""
!python scripts/score_vi_crawl_full.py > /dev/null
!python scripts/score_vi_crawl_full.py --input data/raw/vi_crawl_tier2_external.csv --out-dir reports/vi_crawl_run3 > /dev/null
for name, path in [("Đợt 1–2", "reports/vi_crawl_full/summary.csv"), ("Đợt 3", "reports/vi_crawl_run3/summary.csv")]:
    s = pd.read_csv(path)
    s = s[s.subset.isin(["all", "sms_new_family", "sms_known_family", "chat"])]
    print(name)
    display(s.pivot(index="model", columns="subset", values="scam_recall").round(3))

!python scripts/compare_tier1.py > /dev/null
from IPython.display import Markdown, display
display(Markdown(open("reports/tier1/tier1_selection.md", encoding="utf-8").read()))
""")

md(f"""
# TẦNG 2 – loại lừa đảo (tiếng Việt, 9 loại)

## Bước 8 – Train + chọn mô hình tầng 2
`scripts/train_tier2.py` làm tất cả:
1. Dữ liệu: mọi tin scam của tập Tuấn (565 tin khác nhau) chia 70/15/15 **theo khuôn**, cộng tin crawl đợt 1–2 vào train.
2. Train NB, SVM, CharCNN; **chọn bằng CV 5 lượt theo khuôn** trên train+validation (CharCNN chạy lại 5 lần → phần lâu nhất).
3. Chấm validation / test, **external = crawl đợt 3**, và **cả chuỗi**: tầng 1 (SVM song ngữ vừa train) phải báo scam thì tầng 2 mới được tính đúng.
4. Train lại mô hình được chọn trên toàn bộ dữ liệu → `artifacts/tier2_vi/final/model.joblib` (mô hình dùng trong demo).

Kiểm tra cách chia: train / validation / test phải là **{EXPECTED["tier2"]["train"]} / {EXPECTED["tier2"]["validation"]} / {EXPECTED["tier2"]["test"]}**.
""")
code(f"""
start = time.time()
!python scripts/train_tier2.py
print(f"--> tầng 2: {{(time.time() - start) / 60:.1f}} phút")
split = pd.read_csv("data/processed_tier2_vi/tier2_data.csv").split.value_counts().to_dict()
print("Chia tầng 2:", split, "khớp" if split == {EXPECTED["tier2"]!r} else "KHÁC bản local {EXPECTED["tier2"]}")
""")

md("## Bước 9 – Kết quả tầng 2")
code("""
display(Markdown(open("reports/tier2_vi/summary.md", encoding="utf-8").read()))
""")
md("### Từng tin thật của đợt 3: tầng 1 có báo scam không, tầng 2 đoán loại gì")
code("""
cp = pd.read_csv("reports/tier2_vi/crawl_predictions.csv")
cp["chuỗi đúng (SVM)"] = cp.tier1_prediction.eq("scam") & cp.svm_prediction.eq(cp.label_level_1)
cols = ["subset", "label_level_1", "tier1_prediction", "naive_bayes_prediction", "svm_prediction", "charcnn_prediction",
        "chuỗi đúng (SVM)", "text_clean"]
pd.set_option("display.max_colwidth", 90)
display(cp[[c for c in cols if c in cp.columns]])
""")

md("""
# CẢ HỆ THỐNG

## Bước 10 – Nhận diện ngôn ngữ + chạy thử cả chuỗi
Bộ nhận diện ngôn ngữ (vi / en) quyết định tin nào được đưa sang tầng 2. Sau đó gọi `predict_pipeline` – đúng hàm mà demo dùng.
""")
code("""
!python scripts/train_langid.py > /dev/null
from scam_baseline.predict import predict_pipeline
SAMPLES = [
    "Vietcombank thong bao: tai khoan cua quy khach bi tam khoa. Xac minh tai vcb-xacminh.top",
    "CSGT thong bao: phuong tien cua ban vi pham giao thong, nop phat tai dichvucong-gov.xyz",
    "Ho so vay 50 trieu da duyet, vui long nop phi bao hiem 2 trieu de giai ngan",
    "Your account has been locked. Verify your identity now: http://secure-check.top",
    "Chiều nay 5h họp nhóm đồ án ở thư viện nhé",
    "[QC] Viettel tang ban uu dai goi ST90K. Tu choi QC soan TC gui 199",
    "Có đủ 500k không, cho mượn tạm có việc. Sáng mai gửi lại được không?",
]
rows = []
for text in SAMPLES:
    r = predict_pipeline(text)
    rows.append({"tin": text[:70], "ngôn ngữ": r["language"], "tầng 1": r["label"], "margin": r["label_margin"],
                 "loại scam": r["scam_type"], "cảnh báo": "có" if r["warnings"] else ""})
display(pd.DataFrame(rows))
""")

md("""
## Bước 11 – Phân tích lỗi (số liệu cho báo cáo)
Kết quả: `reports/error_analysis/summary.md`. Phần diễn giải nằm ở `docs/PHAN_TICH_LOI.md` (trên máy).
""")
code("""
!python scripts/error_analysis.py
print(open("reports/error_analysis/summary.md", encoding="utf-8").read()[:3000], "\\n…")
""")

md("## Bước 12 – Đóng gói kết quả để tải về")
code("""
OUT = f"{WORK}/colab_results.zip"
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for top in ["artifacts", "reports"]:
        for path in glob.glob(f"{top}/**/*", recursive=True):
            if os.path.isfile(path) and "_cv_charcnn" not in path:  # bỏ model tạm của từng lượt CV
                z.write(path)
    z.write("data/processed_tier2_vi/tier2_data.csv")
print(OUT, f"{os.path.getsize(OUT) / 1e6:.1f} MB | scikit-learn {sklearn.__version__}")
print("Nếu trình duyệt không tự tải: thanh 📁 Files → chuột phải colab_results.zip → Download")
files.download(OUT)
""")


def to_source(text: str) -> list[str]:
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


nb = {
    "cells": [
        ({"cell_type": "markdown", "metadata": {}, "source": to_source(src)} if kind == "markdown" else
         {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_source(src)})
        for kind, src in cells
    ],
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", OUT, f"({len(cells)} cells)")
