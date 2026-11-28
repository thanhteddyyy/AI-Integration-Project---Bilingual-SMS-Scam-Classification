# BÁO CÁO KIỂM TOÁN KỸ THUẬT DỮ LIỆU (DATA ENGINEERING AUDIT REPORT)
**Dự án:** Bilingual Scam SMS Baseline  
**Hệ thống mục tiêu:** Pipeline tiền xử lý, khử trùng lặp, chia tập dữ liệu và gộp song ngữ (IMC25, SMS Phishing, SmishX, và Tập dữ liệu Tiếng Việt)  
**Thời gian kiểm toán:** 2026-10-31  
**Vai trò:** Data Engineering Auditor  

---

## MỤC LỤC
1. [Tổng quan Phạm vi & Đối tượng Kiểm toán](#1-tổng-quan-phạm-vi--đối-tượng-kiểm-toán)
2. [Đánh giá Chi tiết 5 Tiêu chuẩn Kỹ thuật](#2-đánh-giá-chi-tiết-5-tiêu-chuẩn-kỹ-thuật)
   * [Tiêu chuẩn 1: Ánh xạ cấu trúc (Schema & Label Harmonization)](#tiêu-chuẩn-1-ánh-xạ-cấu-trúc-schema--label-harmonization)
   * [Tiêu chuẩn 2: Tiền xử lý bảo tồn đặc trưng (Feature-Preserving Normalization)](#tiêu-chuẩn-2-tiền-xử-lý-bảo-tồn-đặc-trưng-feature-preserving-normalization)
   * [Tiêu chuẩn 3: Khử trùng lặp mờ chéo tập dữ liệu (Cross-dataset Fuzzy Deduplication)](#tiêu-chuẩn-3-khử-trùng-lặp-mờ-chéo-tập-dữ-liệu-cross-dataset-fuzzy-deduplication)
   * [Tiêu chuẩn 4: Phát hiện và Xử lý xung đột nhãn (Label Conflict Resolution)](#tiêu-chuẩn-4-phát-hiện-và-xử-lý-xung-đột-nhãn-label-conflict-resolution)
   * [Tiêu chuẩn 5: Phân chia tập dữ liệu chống rò rỉ (Anti-leakage Stratified Split)](#tiêu-chuẩn-5-phân-chia-tập-dữ-liệu-chống-rò-rỉ-anti-leakage-stratified-split)
3. [Phát hiện Kiểm toán Quan trọng (Critical Audit Findings)](#3-phát-hiện-kiểm-toán-quan-trọng-critical-audit-findings)
   * [Phát hiện 1: Rò rỉ dữ liệu giữa Train và External Test (246 cụm VI)](#phát-hiện-1-rò-rỉ-dữ-liệu-giữa-train-và-external-test-246-cụm-vi)
   * [Phát hiện 2: Xung đột và rò rỉ xuyên ngôn ngữ EN-VI (6 cụm Bilingual)](#phát-hiện-2-xung-đột-và-rò-rỉ-xuyên-ngôn-ngữ-en-vi-6-cụm-bilingual)
4. [Kế hoạch Khắc phục Đề xuất (Remediation Plan)](#4-kế-hoạch-khắc-phục-đề-xuất-remediation-plan)
5. [Bảng Tổng kết Đánh giá Tuân thủ](#5-bảng-tổng-kết-đánh-giá-tuân-thủ)

---

## 1. TỔNG QUAN PHẠM VI & ĐỐI TƯỢNG KIỂM TOÁN

Quá trình kiểm toán thẩm tra 3 tầng bảng dữ liệu Master trong hệ thống:
1. **English Master Manifest (`data/processed/master_manifest.csv` — 29,249 dòng):**
   * Tích hợp 3 nguồn: `imc25` (22,078 dòng), `sms_phishing` (5,971 dòng), `smishx` (1,200 dòng).
   * Bao gồm cả 7,593 dòng bị loại (`excluded`) do trùng lặp, xung đột nhãn, hoặc chồng lấn test.
2. **Vietnamese 3-Class Master Manifest (`data/processed_vi_3class/master_manifest.csv` — 15,130 dòng):**
   * Tích hợp 4 nguồn: `vie_sms_corpus` (6,570 dòng), `social_spam_post` (5,569 dòng), `spamscam_train` (2,394 dòng), `spamscam_test` (597 dòng).
   * Bao gồm 2,537 dòng bị loại (`excluded`).
3. **Bilingual Master Manifest (`data/processed_bilingual/master_manifest.csv` — 25,691 dòng):**
   * Bảng gộp song ngữ phục vụ huấn luyện mô hình đa ngôn ngữ, sinh ra từ kịch bản cân bằng (`scripts/balance_datasets.py`) và hợp nhất (`scripts/merge_bilingual.py`).

---

## 2. ĐÁNH GIÁ CHI TIẾT 5 TIÊU CHUẨN KỸ THUẬT

### Tiêu chuẩn 1: Ánh xạ cấu trúc (Schema & Label Harmonization)

#### 1. Kiểm tra 9 cột chuẩn
* **Kết quả:** **ĐẠT (PASS)**.
* Tất cả các bảng Master đều chứa đủ 9 cột bắt buộc: `text_raw`, `text_clean`, `source_dataset`, `language`, `label_original`, `label_level_1`, `scam_type`, `group_id`, `split` (nằm trong cấu trúc mở rộng 21 cột định nghĩa tại `MASTER_COLUMNS` trong `src/scam_baseline/data/pipeline.py`).

#### 2. Bảo toàn nhãn gốc (`label_original`) và kiểm tra số lượng Class (`label_level_1`)
* **Kết quả:** **ĐẠT (PASS)**.
* Hàm `_base_frame` tại `src/scam_baseline/data/adapters.py` lưu nguyên trạng nhãn gốc vào `output["label_original"] = raw[label_column].astype("string")`.
* Quá trình ánh xạ sang `label_level_1` tạo cột độc lập, không ghi đè nhãn gốc.
* Trên các tập modeling hợp lệ (và toàn bộ bảng Bilingual Master), `label_level_1` **chỉ có đúng 3 class**: `legitimate`, `scam`, `spam`.

#### Truy vấn Pandas đối chiếu:
```python
import pandas as pd

df_bi = pd.read_csv("data/processed_bilingual/master_manifest.csv", low_memory=False)

# 1. Kiểm tra phân bố label_level_1
print("=== Bilingual Master: label_level_1.value_counts() ===")
print(df_bi["label_level_1"].value_counts(dropna=False))

# 2. Đối chiếu chéo label_original và label_level_1 để chứng minh không ghi đè
print("\n=== Cross-tab label_original vs label_level_1 ===")
print(pd.crosstab(df_bi["label_original"], df_bi["label_level_1"]))
```

#### Kết quả trích xuất:
```text
=== Bilingual Master: label_level_1.value_counts() ===
label_level_1
legitimate    13855
scam           7228
spam           4608
Name: count, dtype: int64

=== Cross-tab label_original vs label_level_1 ===
label_level_1   legitimate  scam  spam
label_original                        
Smishing                 0   214     0
Spam                     0     0    28
banking                  0  2825     0
delivery                 0   520     0
government               0   564     0
ham                  12113     0     0
hey mum/dad              0    30     0
legitimate            1742     0     0
others                   0  1580     0
scam                     0   591     0
smishing                 0   214     0
spam                     0     0  4580
telecom                  0   597     0
wrong number             0    93     0
```

---

### Tiêu chuẩn 2: Tiền xử lý bảo tồn đặc trưng (Feature-Preserving Normalization)

#### 1. Chuẩn hóa Unicode NFC trong hàm `clean_text`
* **Kết quả:** **ĐẠT (PASS)**.
* Hàm `clean_text` (`src/scam_baseline/data/clean.py`) thực thi:
  1. `html.unescape(str(value))` giải mã thực thể web.
  2. `unicodedata.normalize("NFC", text)` ghép các dấu thanh tổ hợp thành ký tự dựng sẵn chuẩn tiếng Việt, loại bỏ triệt để lỗi font.
  3. Loại bỏ ký tự điều khiển (`category.startswith("C")`) và gộp khoảng trắng thừa.
  4. **Giữ nguyên 100% URL, số điện thoại, dấu câu, chữ số** trong `text_clean` đưa vào mô hình.

#### 2. Truy vấn chứng minh KHÔNG xóa URL và Số điện thoại:
```python
import pandas as pd

df = pd.read_csv("data/processed_bilingual/master_manifest.csv", low_memory=False)
cond_url = df["text_clean"].str.contains(r"(?:https?://|www\.)\S+", regex=True, na=False)
cond_phone = df["text_clean"].str.contains(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", regex=True, na=False)

sample = pd.concat([
    df[(df["language"] == "en") & (cond_url | cond_phone)].head(3),
    df[(df["language"] == "vi") & (cond_url | cond_phone)].head(2)
])
print(sample[["source_dataset", "language", "label_level_1", "has_url", "has_phone", "text_clean"]].to_string())
```

#### Kết quả 5 dòng minh chứng:
| Index | `source_dataset` | `language` | `label_level_1` | `has_url` | `has_phone` | `text_clean` (Bảo tồn URL và Số điện thoại) |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| **3** | `sms_phishing` | `en` | `spam` | `False` | `True` | `Double Mins & Double Txt & 1/2 price Linerental on Latest Orange Bluetooth mobiles. Call MobileUpd8 for the very latest offers. 08000839402 or call2optout/LF56` |
| **53** | `sms_phishing` | `en` | `spam` | `True` | `False` | `Over 3,0,000 songs on the www, music. nokia.com. Download 5 free tracks from the Nokia Music Store. Download now at http://music.nokia.co.in/myn5free` |
| **61** | `sms_phishing` | `en` | `spam` | `False` | `True` | `January Male Sale! Hot Gay chat now cheaper, call 08709222922. National rate from 1.5p/min cheap to 7.8p/min peak! To stop texts call 08712460324 (10p/min)` |
| **13254** | `spamscam_train` | `vi` | `scam` | `True` | `False` | `[Sh0pee_CTV] Tuyển nhân viên xử lý dữ liệu đơn hàng ảo tại nhà, thu nhập [MONEY] - [MONEY]/ngày lương trả theo giờ qua ATM. Liên hệ nhận j0b: http://shopee.tuyendung-ctv.top` |
| **13256** | `spamscam_train` | `vi` | `legitimate` | `True` | `False` | `Doi thanh cong [POINT] tieu dung Viettel++ thanh 60 MB Data de Quy khach trai nghiem dich vu. Han su dung truoc [DATE]. Tong diem tieu dung con lai trong tai khoan Viettel++ cua Quy khach la 10.[POINT]. De kiem tra lich su doi diem va lua chon uu dai hap dan khac, vui long truy cap https://myvt.page.link/vtplus. Tran trong.` |

---

### Tiêu chuẩn 3: Khử trùng lặp mờ chéo tập dữ liệu (Cross-dataset Fuzzy Deduplication)

#### 1. Thuật toán băm và gom cụm đã sử dụng
* **Phương pháp:** Gom cụm 3 tầng kết hợp cấu trúc `UnionFind` (Disjoint-Set) tại `src/scam_baseline/data/dedup.py`:
  1. **Strict Key:** Chuẩn hóa `NFKC` + `casefold()`.
  2. **Template Key:** Che URL (`<url>`), email (`<email>`), số điện thoại/số tiền (`<number>`) để nhận diện mẫu lừa đảo thay link/số OTP.
  3. **Fuzzy SimHash 64-bit + LSH:**
     * Băm văn bản thành các 4-character shingles qua hàm `hashlib.blake2b` (digest 64-bit).
     * Chia fingerprint thành 4 bands $\times$ 16-bit LSH để quét ứng viên nhanh.
     * So khớp ứng viên qua `difflib.SequenceMatcher` với ngưỡng `threshold >= 0.96` (EN) và `0.95` (VI).
  4. Gán mã đại diện cụm `group_id = "grp_" + min(SHA-256[:20])`.

#### 2. Thống kê cụm chéo nguồn (Cross-dataset) & Ví dụ thực tế:
* **English Master:** **596 cụm `group_id`** trải dài trên $\ge 2$ nguồn dữ liệu khác nhau.
* **Vietnamese Master:** **66 cụm `group_id`** trải dài trên $\ge 2$ nguồn dữ liệu khác nhau.

#### Ví dụ Cụm chéo giữa `smishx` và `imc25` (`grp_008d56b704d92932911a`):
```text
- smishx:1145 (smishx, split = external_test, label = scam):
  "The USPS package has arrived at the warehouse and cannot be delivered due to incomplete address information. Please confirm your address in the link. https://uspspgcm.com (Please reply to 1, then exit the SMS, open the SMS activation link again, or copy the link to Safari browser and open it) The US Postal team wishes you a wonderful day!"

- imc25:185 (imc25, split = excluded [overlap_with_external_test], label = scam):
  "The USPS package has arrived at the warehouse and cannot be delivered due to incomplete address information. Please confirm your address in the link. <URL> (Please reply to 1, then exit the SMS, open the SMS activation link again, or copy the link to Safari browser and open it) The <LOCATION> Postal team wishes you a wonderful day!"
```

---

### Tiêu chuẩn 4: Phát hiện và Xử lý xung đột nhãn (Label Conflict Resolution)

#### 1. Quét xung đột nhãn trên cột `group_id`
* **English Master:** Phát hiện **111 cụm xung đột** (326 dòng).
* **Vietnamese Master:** Phát hiện **88 cụm xung đột** (393 dòng).

#### 2. Phương pháp xử lý: LOẠI BỎ TRIỆT ĐỂ (Exclusion Policy)
* Hệ thống **KHÔNG áp dụng bỏ phiếu đa số (Majority Voting)** vì ranh giới giữa `spam` và `scam` rất nhạy cảm. Giữ lại nhãn mâu thuẫn bằng bỏ phiếu sẽ làm sai lệch mô hình và điểm benchmark.
* Toàn bộ các dòng thuộc cụm xung đột đều bị chuyển sang `split = "excluded"` với lý do `exclusion_reason = "label_conflict_in_duplicate_group"`.

#### Ví dụ Xung đột nhãn điển hình:
1. **Tiếng Anh (`grp_0fd2b4bddb294d498937` - `sms_phishing` vs `smishx`):**
   * `sms_phishing:3099` gán nhãn **`spam`** cho tin trúng thưởng `£350` (`www.txttowin.co.uk`).
   * `smishx:617` gán nhãn **`scam`** cho cùng mẫu tin trúng thưởng `£250` (`www.txttowin.co.uk`).
   * → Pipeline loại cả 2 dòng sang `excluded`.
2. **Tiếng Việt (`grp_0aaea7e2af01738b5849` - Cờ bạc 8qbet):**
   * `spamscam_train:1058` gán nhầm là **`legitimate`** (`...Tai https://dx3389.8qbet16.com`).
   * `spamscam_train:1820` gán nhãn là **`spam`** (`...Tai https://dx1115.868qbet.com`).
   * → Pipeline phát hiện xung đột template và loại cả 2 dòng sang `excluded`.

---

### Tiêu chuẩn 5: Phân chia tập dữ liệu chống rò rỉ (Anti-leakage Stratified Split)

#### 1. Kiểm tra tính tách ly của tập SmishX
* **Kết quả:** **ĐẠT TUYỆT ĐỐI (PASS)**.
* Trong 1,200 dòng của `smishx`, **1,081 dòng** nằm độc lập tại `external_test`, 119 dòng bị loại (`excluded`) do trùng lặp hoặc xung đột. **0 dòng lọt vào `train`, `validation`, hay `test`**.
* Đồng thời, 670 dòng của `imc25` và `sms_phishing` có nội dung tương đồng với `smishx` đều bị cách ly khỏi tập phát triển (`exclusion_reason = "overlap_with_external_test"`).

#### 2. Phương pháp phân chia tập Train / Validation
* Phân chia theo **cụm `group_id` phân tầng (Stratified Group Split)** thông qua hàm `_stratified_group_partition`.
* Tuyệt đối không cắt ngẫu nhiên theo dòng đơn lẻ.
* Hàm `assert_no_group_leakage` bảo đảm không có cụm nào xuất hiện ở nhiều hơn 1 split.

---

## 3. PHÁT HIỆN KIỂM TOÁN QUAN TRỌNG (CRITICAL AUDIT FINDINGS)

Dù pipeline gốc đạt chuẩn 100%, kiểm toán đã phát hiện **2 lỗi nghiêm trọng tại tầng kịch bản cân bằng dữ liệu và hợp nhất song ngữ**:

### Phát hiện 1: Rò rỉ dữ liệu giữa Train và External Test (246 cụm VI)
* **Tệp vi phạm:** `scripts/balance_datasets.py` (dòng 110–118 và 158).
* **Bản chất lỗi:** 
  Khi bù số lượng mẫu `spam` tiếng Việt trong tập Train lên 500 mẫu, kịch bản đã "mượn" 256 mẫu `spam` từ `external_test` (`vie_sms_corpus` và `social_spam_post`) đưa vào `train`, **nhưng không xóa các dòng này khỏi `external_test`** trước khi gộp lại.
* **Hậu quả:** 
  **246 cụm `group_id`** (gồm 256 mẫu tin nhắn rác) xuất hiện song song ở cả `train` và `external_test`.
* **Minh chứng dữ liệu (`grp_00fcd28f21163e8a6253`):**
  * Bản ghi `vie_sms_corpus:5820` nằm trong `train` (dưới tên nguồn `vie_sms_corpus_balanced_train`).
  * Bản ghi `vie_sms_corpus:5820` và biến thể `vie_sms_corpus:5752` tiếp tục nằm nguyên trong `external_test`.
  * Mô hình được kiểm tra trên chính dữ liệu nó đã học, làm điểm kiểm thử ngoài bị sai lệch (data leakage).

### Phát hiện 2: Xung đột và rò rỉ xuyên ngôn ngữ EN-VI (6 cụm Bilingual)
* **Tệp vi phạm:** `scripts/merge_bilingual.py`.
* **Bản chất lỗi:** 
  Do tập `social_spam_post` (Tiếng Việt) có nguồn gốc dịch từ kho SMS tiếng Anh, một số câu ngắn và emoticon không được dịch mà giữ nguyên tiếng Anh. Khi gộp hai tập ngôn ngữ lại:
  * **5 cụm** bị rò rỉ giữa `validation`/`test` (EN) và `external_test` (VI), ví dụ: `:)`, `:-) :-)`, `Wot u up 2 u weirdo?`.
  * **1 cụm (`grp_9f86d081884c7d659a2f`)** gây xung đột nhãn trực tiếp: Tin nhắn `"test"` được `imc25` (EN, `validation`) gán nhãn là **`scam`**, nhưng `vie_sms_corpus` (VI, `external_test`) gán nhãn là **`legitimate`**.

---

## 4. KẾ HOẠCH KHẮC PHỤC ĐỀ XUẤT (REMEDIATION PLAN)

### Bước 1: Khắc phục triệt để `scripts/balance_datasets.py`
1. **Loại bỏ hoàn toàn logic mượn mẫu từ `external_test`**. Tập `external_test` phải được giữ nguyên trạng độc lập 100%.
2. Bù đắp 256 mẫu `spam` tiếng Việt bằng kỹ thuật **Tăng cường dữ liệu nội bộ (In-split Data Augmentation)**:
   * Sinh mẫu mới từ chính 244 mẫu `spam` gốc của tập `train` thông qua hàm `augment_vietnamese_spam` (thêm/hoán đổi tiền tố quảng cáo `(QC)`, `(TB)`, từ đồng nghĩa khuyến mãi).
3. Đặt hàm chặn `assert_no_group_leakage` trước khi lưu `data/processed_vi_balanced/modeling_data.csv`.

### Bước 2: Khắc phục `scripts/merge_bilingual.py`
1. Bổ sung bước kiểm tra trùng lặp chéo sau khi gộp hai bảng (`en` + `vi`):
   * Tự động loại bỏ (`excluded`) cụm bị xung đột nhãn xuyên ngôn ngữ (`"test"`).
   * Tự động lọc bỏ các mẫu emoticon vô nghĩa trùng lặp xuyên split (`:)`).
2. Tái tạo hai file đầu ra sạch: `data/processed_bilingual/modeling_data.csv` và `data/processed_bilingual/master_manifest.csv`.

---

## 5. BẢNG TỔNG KẾT ĐÁNH GIÁ TUÂN THỦ

| Tiêu chuẩn Kiểm toán | Pipeline Gốc (`en` & `vi_3class`) | Bản Cân Bằng Cũ (`bilingual`) | Sau khi Thực hiện Remediation |
| :--- | :---: | :---: | :---: |
| **1. Ánh xạ cấu trúc (Schema & Label)** | **PASS** | **PASS** | **PASS** |
| **2. Bảo tồn đặc trưng (NFC, URL, Phone)** | **PASS** | **PASS** | **PASS** |
| **3. Khử trùng lặp mờ (SimHash LSH)** | **PASS** | **PASS** | **PASS** |
| **4. Xử lý xung đột nhãn (Exclude)** | **PASS** | **FAIL (1 cụm EN-VI)** | **PASS (100% Excluded)** |
| **5. Phân chia chống rò rỉ (Group Split)** | **PASS (0 rò rỉ)** | **FAIL (252 cụm rò rỉ)** | **PASS (0 rò rỉ)** |
| **Độ tin cậy khoa học của Benchmark** | **Chuẩn** | **Bị nghi vấn rò rỉ** | **Đạt chuẩn đồ án tốt nghiệp** |

