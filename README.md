# Phát hiện tin nhắn lừa đảo song ngữ Việt–Anh (Bilingual SMS Scam Classification)

Đồ án tổng hợp hướng Trí tuệ nhân tạo – HK261. **Trạng thái: 28/11/2026 – đã chốt pipeline và mô hình của cả hai tầng.**

Nhập một tin nhắn tiếng Việt hoặc tiếng Anh, hệ thống trả lời:
1. Tin **bình thường** (`legitimate`), **rác / quảng cáo** (`spam`) hay **lừa đảo** (`scam`);
2. nếu là lừa đảo **tiếng Việt**: thuộc **loại lừa đảo nào** (9 loại), kèm lời khuyên;
3. các từ khiến mô hình nghi ngờ, mức độ chắc chắn, và cảnh báo khi tin yêu cầu chuyển / mượn tiền.

Toàn bộ mô hình được **train từ đầu** trên dữ liệu của đồ án (không dùng API, không dùng model train sẵn, không dùng dữ liệu do LLM sinh).

---

## 1. Pipeline đã chốt

```text
Tin nhắn
   │  làm sạch (Unicode NFC, HTML, khoảng trắng)
   │  che số kiểu tập Tuấn với tin tiếng Việt: số tiền, SĐT, STK → [MONEY] [NUMBER] …  (giữ nguyên đường link)
   ▼
Nhận diện ngôn ngữ  ── Naive Bayes trên cụm 1–3 ký tự (vi / en, kể cả tiếng Việt không dấu)
   ▼
TẦNG 1 ── Linear SVM song ngữ: legitimate / spam / scam ──► legitimate, spam: dừng
   │ scam
   ├── tiếng Anh: dừng (chưa có tầng 2 tiếng Anh)
   ▼ tiếng Việt
TẦNG 2 ── Linear SVM tiếng Việt: 1 trong 9 loại lừa đảo → nhóm theo định nghĩa → lời khuyên
   ▼
Kết quả: nhãn, loại lừa đảo, từ đặc trưng, margin (độ chắc chắn), cảnh báo bằng luật
```

| Thành phần | Mô hình chốt | Quy tắc chọn (cố định trước khi xem kết quả) |
|---|---|---|
| Tầng 1 (ham / spam / scam) | **Linear SVM song ngữ** | F2 lớp scam cao nhất trên validation (bỏ sót lừa đảo nguy hiểm hơn báo nhầm) |
| Tầng 2 (9 loại lừa đảo, tiếng Việt) | **Linear SVM** | macro-F1 trung bình CV 5 lượt chia theo khuôn (mọi loại quan trọng như nhau) |
| Nhận diện ngôn ngữ | Naive Bayes cụm ký tự 1–3 | – |
| Cảnh báo chuyển / mượn tiền | Luật (regex), **không đổi nhãn** | Lừa đảo giọng người quen không phân biệt được chỉ từ chữ |

Cả hai tầng đều so sánh 3 mô hình: **Naive Bayes**, **Linear SVM** và **CharCNN** (mạng tích chập mức ký tự tự cài bằng PyTorch,
theo Zhang và cộng sự 2015). SVM được chọn ở cả hai tầng; CharCNN gần ngang trên tập test nhưng kém rõ trên tin thật.

---

## 2. Trạng thái (28/11/2026)

| Phần | Trạng thái |
|---|---|
| Dữ liệu: gán nhãn lại, chia theo khuôn, chống rò rỉ, tin thật crawl 3 đợt | ✅ Đã chốt |
| Tầng 1: NB / SVM / CharCNN × 3 thiết lập (Việt, Anh, song ngữ) | ✅ Chốt SVM song ngữ |
| Tầng 2: NB / SVM / CharCNN, 9 loại lừa đảo tiếng Việt | ✅ Chốt SVM |
| Nhận diện ngôn ngữ + `predict_pipeline` (ghép cả hệ thống) | ✅ |
| Phân tích lỗi | ✅ `docs/PHAN_TICH_LOI.md` |
| Notebook Colab chạy lại cả 2 tầng | ✅ Bản chính thức = lần chạy Colab 28/11 (SVM/NB trùng 100% với bản trên máy) |
| Gói demo cho giao diện (`demo_bundle.zip`) | ✅ Lõi dự đoán xong |
| Giao diện demo (Gradio) | ⬜ Đang làm |
| Báo cáo + slide | ⬜ Đang làm (sườn: `docs/SUON_BAO_CAO.md`) |
| Tầng 2 tiếng Anh | ✖ Ngoài phạm vi (hướng phát triển) |

---

## 3. Kết quả chính (bản chính thức: Colab 28/11)

**Tầng 1 – SVM song ngữ**

| Đo gì | Kết quả |
|---|---|
| Validation / test: F2 lớp scam | 93,6 / 91,9 |
| Tin lừa đảo **SMS tiếng Việt thật** (crawl báo chí, 3 đợt) | **35/39 (90%)** |
| Tin lừa đảo **Zalo / Messenger** thật | 2/14 – điểm yếu chính |
| Báo nhầm tin tiếng Việt thật (`vie_sms`, 2.870 tin) | 1,0% |
| SmishX (tiếng Anh thật): bắt được / báo nhầm | 84,7% / 9,9% |

| Song ngữ (val F2 scam) | Naive Bayes | **SVM** | CharCNN |
|---|---|---|---|
| Tiếng Việt / Tiếng Anh / Song ngữ | 79,6 / 91,8 / 92,3 | **92,1 / 93,8 / 93,6** | 84,8 / 92,6 / 92,9 |

**Tầng 2 – 9 loại lừa đảo tiếng Việt**

| Model | CV macro-F1 (chọn) | Test macro-F1 | Tin thật đợt 3 | Cả chuỗi tầng 1 → 2 |
|---|---|---|---|---|
| Naive Bayes | 70,2 ± 4,5 | 72,5 | 6/9 | 5/9 |
| **SVM** | **79,5 ± 4,6** | **76,1** | 6/9 | 5/9 |
| CharCNN | 61,9 ± 8,1 | 58,2 | 5/9 | 4/9 |

Chi tiết: `reports/tier1/tier1_selection.md`, `reports/tier2_vi/summary.md`, `reports/error_analysis/summary.md`.

**Giới hạn chính:** lừa đảo giọng cá nhân / qua chat gần như không bắt được (nội dung giống tin người quen thật);
tin lừa đảo không có link khó bắt hơn; scam tiếng Việt để train chỉ từ một nguồn; tin thật tiếng Việt còn ít (khoảng tin cậy rộng).

---

## 4. Dữ liệu

### 4.1 Nguồn và vai trò

| Nguồn | File (`data/raw/`) | Ngôn ngữ | Vai trò |
|---|---|---|---|
| Tập **SpamScam** của Tuấn | `train_dataset_spamscam_v3.csv`, `test_dataset_spamscam_v3.csv` | Việt | **Tập chính tiếng Việt**: ham / spam / scam + loại lừa đảo; nguồn duy nhất của tầng 2 |
| **vie-spam-sms** (2015) | `vie_sms_corpus_dev_v3.csv`, `vie_sms_corpus_holdout_v3.csv` | Việt | Tin thật: phần dev vào train (chữa lối tắt "có dấu = scam"), phần holdout làm external |
| **IMC25** (Fishing for Smishing) | `final_dataset_output.csv` | Anh | **Tập chính tiếng Anh** (chủ yếu tin lừa đảo) |
| **SMS Phishing Dataset** | `Dataset_5971.csv` | Anh | Bổ sung tin bình thường (IMC25 chỉ có khoảng 200 tin bình thường) |
| **SmishX** | `dataset.csv` | Anh | **Chỉ chấm** (external), không train |
| **Crawl báo chí** (3 đợt, người duyệt 100%) | `vi_crawl_*.csv` | Việt | Đợt 1–2: chấm tầng 1 + thêm vào train tầng 2; đợt 3: external của tầng 2 |

Mỗi quyết định gán nhãn được lưu trong `data/review/` (file duyệt, danh sách đổi nhãn, tin bị loại). Chuẩn gán nhãn:
`definition_of_ham_spam_scam.md`.

### 4.2 Các bước xử lý chính
- **Gán nhãn lại:** rà tay toàn bộ nhãn tiếng Việt (bản v3); rà 711 tin tiếng Anh nghi sai, 524 tin đổi nhãn hoặc loại.
- **Chống rò rỉ:** gộp tin trùng / gần trùng (SimHash + Union-Find), chia train/val/test **theo khuôn tin** (Jaccard cụm 3 từ ≥ 0,5).
  Trước khi sửa, 80% tin scam test có "anh em" trong train.
- **Chống lối tắt:** thêm tin cá nhân thật → báo nhầm tin thật giảm 24% → 0,1%.
- **Cân bằng:** giữ toàn bộ dữ liệu thật + `class_weight=balanced`; augment có kiểm soát chỉ cho train tiếng Việt.
- **Che thông tin:** số tiền / SĐT / tên → `[MONEY]`, `[NUMBER]`, `[NAME]`…; giữ đường link (tên miền là dấu hiệu). Lý do và căn cứ:
  `docs/TU_LIEU_CHE_THONG_TIN.md`.

### 4.3 Quy mô dữ liệu đã chốt

| Thiết lập | Train | Validation | Test | External |
|---|---|---|---|---|
| Tiếng Việt (`data/processed_vi_balanced/`) | 4.899 | 712 | 565 | 2.896 |
| Tiếng Anh (`data/processed_en_balanced/`) | 8.120 | 3.175 | 2.829 | 1.023 |
| **Song ngữ – tầng 1** (`data/processed_bilingual/`) | **13.018** | 3.886 | 3.394 | 3.917 |
| **Tầng 2** (`data/processed_tier2_vi/`) | 438 | 86 | 84 | 9 |

9 loại lừa đảo tầng 2: `banking_finance`, `gov_utility_services`, `delivery_logistics` (giả mạo tổ chức) · `job_task_scam`,
`investment`, `loan_debt` (tài chính & việc làm ảo) · `prize_lottery` (trúng thưởng) · `social_impersonation`, `other_scam` (mở rộng).

---

## 5. Cấu trúc thư mục

```text
configs/                    Cấu hình YAML: bilingual / vietnamese_balanced / english_balanced (tầng 1), tier2_vietnamese (tầng 2)
data/raw/                   Dữ liệu gốc + tin crawl đã duyệt
data/review/                Mọi quyết định gán nhãn (file duyệt, overrides)
data/processed_*/           Dữ liệu đã xử lý, đã chia tập – dùng để train
src/scam_baseline/
  data/                     Adapter từng nguồn, làm sạch, che thông tin, gộp trùng (SimHash, Union-Find), chia theo khuôn
  models/                   Naive Bayes, Linear SVM (TF-IDF từ + ký tự), CharCNN (PyTorch)
  tier2.py                  Dữ liệu + đánh giá tầng 2
  langid.py                 Nhận diện ngôn ngữ
  predict.py                ScamDetector / predict_pipeline – ghép cả hệ thống
  evaluation.py, cli.py     Độ đo (F2, macro-F1, MCC, Wilson CI…), dòng lệnh
scripts/                    Train tầng 2, nhận diện ngôn ngữ, so sánh / chọn mô hình, chấm tin thật, phân tích lỗi, đóng gói
notebooks/                  colab_tier1_tier2.ipynb (chạy lại cả 2 tầng), notebook crawl
demo/README.md              Giao diện dữ liệu trả về cho người làm demo
docs/                       Nhật ký, phân tích lỗi, tư liệu báo cáo
tests/                      39 test (pytest)
artifacts/, reports/        Model và báo cáo sinh ra khi chạy (không vào git, trừ vài file tổng hợp)
```

---

## 6. Cài đặt

Python **3.11** (khuyến nghị). Trên Windows dùng `py -3.11`.

```powershell
py -3.11 -m pip install -e ".[deep]"        # có PyTorch cho CharCNN; bỏ [deep] nếu chỉ cần NB / SVM
py -3.11 -m pip install scikit-learn==1.9.1 # model lưu bằng joblib chỉ nạp được với đúng phiên bản đã train
$env:PYTHONPATH = "src"                     # PowerShell; Linux/macOS: export PYTHONPATH=src
```

---

## 7. Cách dùng

### 7.1 Thử hệ thống với một tin nhắn (cần model trong `artifacts/`)

```powershell
py -3.11 scripts/try_pipeline.py --text "Vietcombank thong bao: tai khoan bi tam khoa, xac minh tai vcb-xacminh.top"
py -3.11 scripts/try_pipeline.py            # chế độ hỏi đáp
```

```python
from scam_baseline.predict import predict_pipeline
r = predict_pipeline("Ho so vay 50 trieu da duyet, vui long nop phi bao hiem 2 trieu de giai ngan")
print(r["label"], r["scam_type"], r["label_margin"], r["advice"], r["warnings"])
```

Các khóa của kết quả: `demo/README.md`. Margin < 0,3 nghĩa là mô hình phân vân (khi đó chỉ đúng khoảng 50%).

### 7.2 Chạy lại toàn bộ trên Google Colab (cách khuyến nghị)

```powershell
py -3.11 scripts/make_colab_notebook.py   # sinh notebooks/colab_tier1_tier2.ipynb
py -3.11 scripts/package_for_colab.py     # tạo bilingual-scam-colab.zip ở thư mục gốc (code + dữ liệu đã xử lý)
```
Trên Colab: `File → Upload notebook` → `Runtime → T4 GPU` → kéo thả zip vào thanh Files → `Run all` (20–35 phút).
Kết quả tải về `colab_results.zip` (model + báo cáo cả 2 tầng).

### 7.3 Chạy trên máy

```powershell
# Tầng 1: 3 mô hình × 3 thiết lập, rồi chọn mô hình
py -3.11 -m scam_baseline.cli --config configs/bilingual.yaml train --models nb svm charcnn
py -3.11 -m scam_baseline.cli --config configs/vietnamese_balanced.yaml train --models nb svm charcnn
py -3.11 -m scam_baseline.cli --config configs/english_balanced.yaml train --models nb svm charcnn
py -3.11 scripts/compare_tier1.py                      # → reports/tier1/tier1_selection.md

# Tầng 1 trên tin lừa đảo tiếng Việt thật (không train lại)
py -3.11 scripts/score_vi_crawl_full.py                # đợt 1–2 → reports/vi_crawl_full/
py -3.11 scripts/score_vi_crawl_full.py --input data/raw/vi_crawl_tier2_external.csv --out-dir reports/vi_crawl_run3

# Tầng 2 (cần model tầng 1 song ngữ để chấm cả chuỗi); khoảng 10 phút trên CPU
py -3.11 scripts/train_tier2.py                        # → reports/tier2_vi/summary.md, artifacts/tier2_vi/final/

# Nhận diện ngôn ngữ, phân tích lỗi
py -3.11 scripts/train_langid.py
py -3.11 scripts/error_analysis.py                     # → reports/error_analysis/summary.md
```

### 7.4 Gói demo cho giao diện

```powershell
py -3.11 scripts/package_demo.py   # → demo_bundle/ + demo_bundle.zip (3 model + code dự đoán, không cần PyTorch)
```

### 7.5 Test

```powershell
py -3.11 -m pytest -q              # 39 test
```

### 7.6 Tạo lại dữ liệu đã xử lý từ dữ liệu gốc (nâng cao)
Dữ liệu trong `data/processed_*/` đã có sẵn trong repo. Muốn tạo lại từ `data/raw/` + `data/review/`, chạy theo thứ tự:
áp nhãn v3 (`apply_vi_labels_v3.py`) → dựng tập crawl (`build_vi_crawl_external.py`) → `prepare` từng thiết lập →
`balance_datasets.py` → `merge_bilingual.py`. Thứ tự và lưu ý (file chỉ-đọc cần xóa trước) ở `docs/NHAT_KY_TANG2.md` mục 6 và
`docs/HANDOFF_xu_ly_du_lieu_tieng_viet.md`.

---

## 8. Tài liệu

| File | Nội dung |
|---|---|
| `docs/TONG_KET_TIEN_DO.md` | Tiến độ chung, kết quả, việc còn lại |
| `docs/NHAT_KY_THAY_DOI_DU_LIEU.md` | Mọi thay đổi dữ liệu và lý do |
| `docs/NHAT_KY_TANG2.md` | Tầng 2: danh sách lớp, quyết định, tư liệu báo cáo (mục 7) |
| `docs/PHAN_TICH_LOI.md` | Phân tích lỗi cả 2 tầng, bảng tóm tắt cho báo cáo |
| `docs/TU_LIEU_CHE_THONG_TIN.md` | Vì sao che `[MONEY]`, `[NAME]`; căn cứ; câu trả lời khi bảo vệ |
| `docs/GIAI_THICH_TANG2_VA_META_FEATURES.md` | Lý do từng lớp tầng 2; meta-features (không dùng) |
| `docs/rerank_experiment.md` | Thí nghiệm ghép SVM + CharCNN ở tầng 1 (không hơn SVM đơn) |
| `docs/HANDOFF_xu_ly_du_lieu_tieng_viet.md` | Chi tiết kỹ thuật xử lý dữ liệu tiếng Việt |
| `docs/huong_dan_crawl_vi_scam.md` | Hướng dẫn crawl tin lừa đảo từ báo chí |
| `docs/SUON_BAO_CAO.md` | Sườn báo cáo đồ án |
| `definition_of_ham_spam_scam.md` | Định nghĩa ham / spam / scam và các loại lừa đảo |
| `demo/README.md` | Giao diện dữ liệu cho người làm demo |
