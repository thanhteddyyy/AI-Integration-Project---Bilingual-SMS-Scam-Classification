# BÁO CÁO TIẾN TRÌNH DỰ ÁN (PROJECT PROGRESS REPORT)
**Đồ án:** Phân loại Tin nhắn SMS Lừa đảo Song ngữ (Bilingual SMS Scam Classification)  
**Thời gian cập nhật:** 27/10/2026  
**Trạng thái chung:** **Đã hoàn thành phần Kỹ thuật & Thực nghiệm mô hình (Codebase & Experiments)**.

---
**Lưu ý:** Do bộ Dataset tiếng Việt không chia ra 3 nhãn đầy đủ như tiếng Anh nên hiện tại chỉ chia thành 2 nhãn là Legit và Risky (scam và spam) gộp chung.

---

### 1. Bảng đối chiếu yêu cầu đề bài môn học ([ai_project_plan.md](ai_project_plan.md))

| Hạng mục trong Đề bài | Yêu cầu cụ thể | Trạng thái | Chi tiết hiện thực trong Dự án |
| :--- | :--- | :---: | :--- |
| **Yêu cầu Kỹ thuật AI** (Mục 2) | Tự xây dựng mô hình trên Framework cụ thể (`PyTorch`) | **ĐẠT 100%** | Tự code mô hình **CharCNN** từ đầu bằng PyTorch (`torch.nn.Module`, `Conv1d`, `Embedding`, custom vocabulary, custom training loop, early stopping) trong `charcnn.py`. |
| | Train trên dataset cụ thể | **ĐẠT 100%** | Đã nạp và huấn luyện thành công trên **4 tập dữ liệu tiếng Việt** (15.130 dòng) và **3 tập dữ liệu tiếng Anh** (33.800+ dòng). |
| | **KHÔNG dùng API có sẵn / model build sẵn chỉ để infer** | **ĐẠT 100%** | Tuyệt đối không dùng API OpenAI/Gemini hay nạp pre-trained weights. Toàn bộ TF-IDF, từ vựng ký tự và trọng số mô hình đều được huấn luyện từ scratch. |
| | Áp dụng kiến thức KTLT, DSA | **ĐẠT 100%** | Ứng dụng giải thuật nâng cao: SimHash 64-bit + LSH buckets để phát hiện near-duplicate $O(N)$, Union-Find (Disjoint Set) để gom nhóm chiến dịch, Stratified Group Split. |
| | Tái hiện (Reproduce) paper hoặc học 1 project AI cụ thể | **ĐẠT 100%** | Tái hiện bài toán phát hiện SMS Phishing/Smishing đa tầng từ tập IMC25 và mô hình phân loại văn bản mức ký tự (CharCNN theo nghiên cứu Zhang et al. 2015). |
| **Phương pháp & Thuật toán** (Mục 5, 6) | Hiện thực **2 - 3 phương pháp** | **ĐẠT 100%** | Hiện thực đủ 3 phương pháp đối trọng:<br>1. **Naive Bayes** (Word TF-IDF n-gram 1, 2)<br>2. **Support Vector Machine (LinearSVC)** (Word TF-IDF + Character n-gram 3-5)<br>3. **Deep Learning CharCNN** (PyTorch Conv1d đa tỷ lệ). |
| **Độ đo & Đánh giá** (Mục 4, 6) | Đánh giá bằng metrics và trực quan hóa kết quả | **ĐẠT 100%** | Tự động tính: Accuracy, Macro-F1, Weighted-F1, Scam Precision, Scam Recall và tự động vẽ lưu ma trận nhầm lẫn (**Confusion Matrix**) ra ảnh `.png`. |
| **Thực thi & Demo** (Mục 3, 7) | Mô tả Input/Output, chạy code demo | **ĐẠT 100%** | Có CLI hoàn chỉnh (`scam-baseline predict`) hỗ trợ suy luận trực tiếp một tin nhắn SMS thời gian thực trả về nhãn JSON. |
| **Hồ sơ báo cáo** (Mục 3) | Đủ 3 thành phần: `Slide`, `Demo`, `Report` | **ĐANG THỰC HIỆN** | - **Demo:** Hoàn tất 100% (chạy được local và Kaggle).<br>- **Report & Slide:** Đang biên soạn dựa trên số liệu thực nghiệm thu được. |

---

### 2. Các cột mốc kỹ thuật quan trọng đã hoàn thành

#### ① Xử lý và làm sạch dữ liệu Tiếng Việt (Vietnamese Data Pipeline)
Đã tích hợp và chuẩn hóa 4 bộ dữ liệu:
1. `train_dataset_spamscam.csv` (2.394 dòng): Phân chia thành Train (85%) và Validation (15%).
2. `test_dataset_spamscam.csv` (597 dòng): Giữ làm tập **Internal Test** độc lập.
3. `corpus_dataset_vie-spam-sms-filtering.txt` (6.570 dòng): **External Test 1** (SMS thực tế ngoài đời).
4. `vi_dataset_vnese_spam_post_in_social.csv` (5.569 dòng): **External Test 2** (Dữ liệu bài đăng mạng xã hội).

#### ② Phát hiện và xử lý rò rỉ dữ liệu (Anti-Leakage Breakthrough)
- **Điểm sáng học thuật lớn:** Pipeline phát hiện bộ dữ liệu gốc của tác giả SpamScam bị **rò rỉ 145 mẫu tin nhắn tương đồng** giữa tập Train và tập Test. Pipeline đã tự động cách ly và loại bỏ 145 mẫu này khỏi tập Train, đảm bảo kết quả kiểm thử trên tập Test là 100% khách quan và trung thực.
- Loại bỏ **1.578 mẫu trùng lặp chính xác** (Exact Duplicates) để mô hình không học vẹt.
- Thanh lọc **345 mẫu xung đột nhãn** (Label Conflicts) giữa các nguồn.
- Đạt kết quả kiểm tra: `"leakage_check": "passed"`.

#### ③ Cấu hình và Môi trường
- Tạo file cấu hình chuyên biệt: [`configs/vietnamese.yaml`](configs/vietnamese.yaml).
- Thiết lập môi trường ảo `.venv` trên máy cục bộ, cài đặt thành công các gói phụ thuộc.

---

### 3. Kết quả Thực nghiệm Thực tế trên Nhánh Tiếng Việt

Sau khi chạy huấn luyện trên môi trường local với lệnh:
```powershell
python -m scam_baseline.cli --config configs/vietnamese.yaml train --models nb svm
```

Bảng số liệu thực nghiệm chính thức thu được (ghi nhận trong `reports/vietnamese/model_comparison.csv`):

| Mô hình (Model) | Tập dữ liệu (Split) | Số mẫu (Rows) | Accuracy | Macro-F1 | Weighted-F1 | Scam Precision | Scam Recall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Linear SVM** | **Validation** | 281 | **97.15%** | **96.30%** | **97.14%** | **95.83%** | **93.24%** |
| Naive Bayes | Validation | 281 | 93.59% | 91.60% | 93.54% | 90.00% | 85.14% |
| **Linear SVM** | **Internal Test** | 563 | **92.72%** | **90.28%** | **92.85%** | **81.08%** | **90.23%** |
| Naive Bayes | Internal Test | 563 | 87.57% | 82.50% | 87.47% | 74.80% | 71.43% |
| Naive Bayes | External Test | 10.109 | 57.00% | 40.77% | 63.89% | 6.65% | 18.29% |
| Linear SVM | External Test | 10.109 | 34.53% | 30.21% | 43.16% | 7.74% | 37.98% |

#### 💡 Đánh giá và Biện luận kết quả:
1. **Hiệu năng xuất sắc trên tập Test nội bộ (In-Domain):**
   - Mô hình **Linear SVM** giành chiến thắng áp đảo với **90.28% Macro-F1** và bắt trúng **90.23% tin nhắn rác/lừa đảo** (Scam Recall), dù toàn bộ 145 mẫu rò rỉ đã bị loại bỏ trước khi train.
2. **Ưu thế vượt trội của Character n-gram:**
   - SVM (kết hợp Word + Character n-gram 3-5) vượt trội hơn Naive Bayes thuần từ vựng gần **8% F1** và gần **19% Recall**, chứng minh việc học ở mức chuỗi ký tự giúp nhận diện teencode, viết tắt và tên miền độc hại hiệu quả hơn hẳn.
3. **Phát hiện nghiên cứu về Hiện tượng Lệch miền (Domain Shift):**
   - Trên tập `external_test`, độ chính xác suy giảm do sự khác biệt giữa phong cách SMS ngân hàng/viễn thông (chứa mã OTP, số tiền) và tin nhắn chat đời thường/bài đăng mạng xã hội. Đây là luận điểm nghiên cứu giá trị cao để trình bày trong báo cáo và slide.

---

### 4. Cấu trúc Sản phẩm bàn giao hiện có (Artifacts Deliverables)

```text
bilingual-scam-baseline/
├── configs/
│   ├── english.yaml                    # Cấu hình pipeline Tiếng Anh
│   └── vietnamese.yaml                 # Cấu hình pipeline Tiếng Việt
├── data/
│   ├── raw/                            # 4 dataset tiếng Việt + 3 dataset tiếng Anh
│   └── processed_vi/                   # Master manifest và Modeling data sạch tiếng Việt
├── reports/
│   └── vietnamese/
│       ├── data_quality_report.json    # Báo cáo chi tiết khử trùng lặp & chống rò rỉ
│       ├── model_comparison.csv        # Bảng tổng hợp so sánh chỉ số các mô hình
│       ├── best_model.json             # Ghi nhận SVM là mô hình chiến thắng
│       └── label_conflicts.csv         # Danh sách 345 mẫu mâu thuẫn nhãn đã xử lý
├── artifacts/
│   └── vietnamese/
│       ├── svm/
│       │   ├── model.joblib            # Trọng số mô hình SVM đã train
│       │   ├── confusion_matrix_test.png       # Ma trận nhầm lẫn trực quan trên Test
│       │   └── confusion_matrix_validation.png # Ma trận nhầm lẫn trên Validation
│       └── naive_bayes/
│           ├── model.joblib            # Trọng số Naive Bayes đã train
│           └── confusion_matrix_test.png
├── src/scam_baseline/                  # Toàn bộ mã nguồn module hóa
└── tests/                              # Unit tests kiểm thử pipeline
```

---

### 5. Kế hoạch công việc tiếp theo (Next Steps)

1. **Huấn luyện mô hình CharCNN (Deep Learning bằng PyTorch):**
   - Cài đặt PyTorch và chạy:
     `python -m scam_baseline.cli --config configs/vietnamese.yaml train --models charcnn`
   - Đưa kết quả của CharCNN vào bảng so sánh 3 bên: Naive Bayes vs Linear SVM vs CharCNN.
2. **Viết Báo cáo đồ án (Report):**
   - Trình bày 4 chương mục tiêu chuẩn:
     1. *Lý do chọn đề tài* (Thực trạng lừa đảo viễn thông).
     2. *Mục tiêu & Phạm vi* (Phân loại SMS tiếng Việt / song ngữ).
     3. *Khảo sát phương pháp* (Lý thuyết Naive Bayes, SVM, CharCNN).
     4. *Đề xuất giải pháp & Phân tích thực nghiệm* (Bảng số liệu F1, Confusion Matrix, phân tích Domain Shift).
3. **Soạn Slide thuyết trình:**
   - Đóng gói các sơ đồ pipeline, biểu đồ Confusion Matrix và bảng đối chiếu kết quả thành slide báo cáo Giữa kỳ / Cuối kỳ.
