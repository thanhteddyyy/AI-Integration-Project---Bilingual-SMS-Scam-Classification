# Bilingual SMS Scam Classification Baseline

Baseline này triển khai Tầng 1 cho bài toán phân loại SMS thành ba lớp:

- `legitimate`: tin nhắn hợp lệ
- `spam`: quảng cáo hoặc tin rác, chưa có dấu hiệu chiếm đoạt rõ
- `scam`: giả mạo, phishing, smishing, dụ lấy OTP hoặc tiền

Phiên bản hiện tại chỉ dùng dữ liệu tiếng Anh. IMC25 được lọc đúng `language = English`; pipeline không dùng cột `translation`. SmishX được giữ làm external test. Tầng 2 chưa được huấn luyện, nhưng `scam_type` đã được chuẩn hoá trong master table để có thể bổ sung sau.

## 1. Dataset đã gắn với file nào

| File | Dataset | Vai trò |
| --- | --- | --- |
| `Dataset_5971.csv` | SMS Phishing Dataset | Train, validation và internal test cho Tầng 1 |
| `dataset.csv` | SmishX | External test cho Tầng 1 |
| `final_dataset_output.csv` | IMC25 Fishing for Smishing | Bổ sung spam/scam cho train, validation, internal test; chuẩn bị `scam_type` cho Tầng 2 |

Audit ban đầu xác nhận:

- SMS Phishing có 5.971 dòng: 4.844 `ham`, 489 biến thể `spam`, 638 biến thể `smishing`.
- SmishX có 1.200 dòng: 622 `legitimate`, 319 `spam`, 259 `smishing`.
- IMC25 có 33.869 dòng, trong đó 22.078 dòng có `language = English`.
- SMS Phishing và SmishX có nhiều mẫu trùng. Vì SmishX là external test, pipeline loại bản tương ứng khỏi development data trước khi chia train/validation/test.

Số dòng cuối cùng có thể thay đổi theo cấu hình fuzzy grouping. Xem `reports/data_quality_report.json` và `data/processed/split_summary.csv` sau khi chạy.

## 2. Nguyên tắc chống leakage

Pipeline áp dụng thứ tự sau:

1. Adapter riêng đọc và kiểm tra schema của từng dataset.
2. `text_clean` chỉ chuẩn hoá Unicode NFC, giải mã HTML entity, bỏ control character và gộp khoảng trắng. URL, số, dấu câu và ký tự đáng ngờ vẫn được giữ cho model.
3. Nhãn gốc được giữ trong `label_original`; nhãn dùng để train nằm ở `label_level_1`.
4. Exact duplicate được phát hiện bằng NFKC, case-folding và khoảng trắng chuẩn hoá.
5. Template duplicate chỉ mask URL, email và số trong khoá dedup. Nội dung đưa vào model không bị mask.
6. Fuzzy duplicate dùng SimHash candidate buckets và xác nhận bằng similarity. Các dòng gần trùng nhận cùng `group_id`.
7. Nhóm có nhãn xung đột bị loại và ghi vào `reports/label_conflicts.csv`.
8. Dòng development trùng nhóm với SmishX bị loại. SmishX không tham gia train hoặc chọn model.
9. Exact duplicate chỉ giữ một dòng đại diện. Near duplicate còn lại được giữ cùng một split để duy trì campaign context mà không rò rỉ qua các split.
10. Train, validation và internal test được stratify theo nhãn ở cấp `group_id`. TF-IDF và vocabulary CharCNN chỉ fit trên train.

## 3. Cấu trúc codebase

```text
configs/
  english.yaml           Cấu hình đầy đủ
  quick.yaml             Cấu hình kiểm tra nhanh
  label_mapping.csv      Mapping nhãn có thể audit
data/raw/                Ba CSV gốc
data/processed/          Master table và modeling table sinh ra khi chạy
reports/                 Audit, conflict, exclusion và bảng so sánh model
artifacts/               Model, metrics, prediction và confusion matrix
src/scam_baseline/
  data/                   Adapter, cleaning, deduplication, group split
  models/                 Naive Bayes, SVM TF-IDF, CharCNN
  audit.py                Audit nguồn dữ liệu
  evaluation.py           Metrics và confusion matrix
  cli.py                  Command-line interface
tests/                    Unit và smoke tests
```

## 4. Cài đặt local

Khuyến nghị Python 3.10 đến 3.12.

### Có cả CharCNN

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[deep]"
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[deep]"
```

Nếu chỉ cần chạy Naive Bayes và SVM:

```bash
pip install -e .
```

Với GPU NVIDIA, cài bản PyTorch phù hợp CUDA theo hướng dẫn chính thức của PyTorch trước, sau đó chạy `pip install -e .`. Không cần tự cài CUDA toolkit nếu môi trường PyTorch/Kaggle đã cung cấp runtime phù hợp.

## 5. Chạy từng bước

Chạy từ thư mục gốc của project.

### Bước 1: audit ba nguồn

```bash
python -m scam_baseline.cli --config configs/english.yaml audit
```

Output chính:

- `reports/source_audit.json`
- `reports/cross_dataset_overlap_audit.csv`

### Bước 2: preprocessing và khoá split

```bash
python -m scam_baseline.cli --config configs/english.yaml prepare
```

Output chính:

- `data/processed/master_manifest.csv`: giữ cả dòng được dùng và dòng bị loại cùng lý do
- `data/processed/modeling_data.csv`: chỉ gồm train, validation, test và external test
- `data/processed/split_summary.csv`
- `reports/data_quality_report.json`
- `reports/exclusion_summary.csv`
- `reports/label_conflicts.csv`
- `reports/label_mapping_used.csv`

Master table có các cột quan trọng:

`sample_id, text_raw, text_clean, language, source_dataset, source_record_id, label_original, label_level_1, scam_type, group_id, split, exclusion_reason`

### Bước 3: chạy Naive Bayes

```bash
python -m scam_baseline.cli --config configs/english.yaml train --models nb
```

B0 dùng word TF-IDF `(1, 2)` và Multinomial Naive Bayes. Đây là baseline nhẹ để xác nhận pipeline và tạo mốc so sánh.

### Bước 4: chạy SVM TF-IDF

```bash
python -m scam_baseline.cli --config configs/english.yaml train --models svm
```

B1 dùng `FeatureUnion` gồm:

- word TF-IDF `(1, 2)`
- character TF-IDF `char_wb (3, 5)`
- LinearSVC với `class_weight=balanced`

Character n-gram giúp nhận mẫu URL, lỗi chính tả, viết tắt và cách viết né bộ lọc.

### Bước 5: chạy CharCNN

```bash
python -m scam_baseline.cli --config configs/english.yaml train --models charcnn
```

B2 là Character CNN viết từ đầu bằng PyTorch:

- vocabulary ký tự chỉ được fit trên train
- embedding ký tự train từ đầu
- nhiều kernel convolution
- global max pooling, dropout và linear classifier
- class-weighted cross entropy
- early stopping theo validation Macro-F1

### Chạy toàn bộ

```bash
python -m scam_baseline.cli --config configs/english.yaml run-all
```

Hoặc kiểm tra nhanh với cấu hình nhẹ:

```bash
python -m scam_baseline.cli --config configs/quick.yaml run-all --models nb svm
```

## 6. Đánh giá và chọn model

Mỗi model tạo metrics cho:

- `validation`: dùng để chọn cấu hình và model
- `test`: internal test, chỉ dùng sau khi chốt cấu hình
- `external_test`: SmishX sau khi loại overlap

Các metrics gồm Accuracy, Macro-F1, Weighted-F1, precision/recall/F1 từng lớp, scam precision, scam recall và confusion matrix.

`reports/model_comparison.csv` tổng hợp các model. `reports/best_model.json` chọn model theo validation Macro-F1; scam recall chỉ dùng làm tie-breaker. Pipeline không chọn model theo test hoặc external test.

## 7. Inference một SMS

Sau khi train:

```bash
python -m scam_baseline.cli --config configs/english.yaml predict \
  --model svm \
  --text "Your bank account is locked. Verify now at http://example.com"
```

Với CharCNN, đổi `--model charcnn`.

## 8. Chạy test

```bash
python -m unittest discover -s tests -v
```

Test CharCNN tự bỏ qua nếu môi trường chưa có PyTorch. Việc đó không ảnh hưởng các test preprocessing, split, Naive Bayes và SVM.

## 9. Chạy trên Kaggle

Xem `notebooks/KAGGLE.md`. Quy trình ngắn:

1. Upload project dưới dạng Kaggle Dataset hoặc notebook input.
2. Bật GPU nếu train CharCNN.
3. Copy ba CSV vào `data/raw/` nếu project được upload không kèm data.
4. Cài package editable bằng `pip install -e . --no-deps` nếu Kaggle đã có pandas, scikit-learn và torch.
5. Chạy `run-all` hoặc train từng model.
6. Download `artifacts/` và `reports/` làm deliverable.

## 10. Thêm dataset tiếng Việt sau này

Không cần sửa code adapter nếu CSV tiếng Việt có một cột text và một cột nhãn. Thêm một phần tử vào `data.extra_datasets` trong YAML:

```yaml
extra_datasets:
  - name: vietnamese_sms
    path: data/raw/vietnamese_sms.csv
    text_column: text
    label_column: label
    language: vi
    label_mapping:
      hợp_lệ: legitimate
      rác: spam
      lừa_đảo: scam
    metadata_columns: []
```

Trước khi dùng, cần audit guideline nhãn tiếng Việt. Không map một nhãn mơ hồ sang `scam` chỉ vì tin nhắn chứa URL. Nếu dataset Việt không có scam type đáng tin cậy, chỉ dùng cho Tầng 1.

## 11. Tầng 2 được chuẩn bị như thế nào

IMC25 đã map:

- `banking` sang `banking_finance`
- `delivery` sang `delivery_logistics`
- `government` sang `government_services`
- `telecom` sang `telecom_account`
- `wrong number` và `hey mum/dad` sang `social_impersonation`
- `others` sang `other_scam`
- `spam` giữ `scam_type = unknown` vì không chạy Tầng 2

Khi triển khai Tầng 2, chỉ lấy `label_level_1 = scam` và `scam_type != unknown`, sau đó audit lại số lượng từng lớp trước khi train.

## 12. Các quyết định đã khoá trong baseline này

- Chỉ English trong IMC25.
- Nhãn Tầng 1 là `legitimate/spam/scam`.
- Phiên bản hiện tại train Tầng 1; Tầng 2 chỉ chuẩn bị dữ liệu.
- SmishX là external test.
- Không dịch toàn bộ corpus.
- Không fit vectorizer hoặc character vocabulary ngoài train.
- Không dùng Accuracy làm tiêu chí chọn model chính.

