# Nhật ký tầng 2 tiếng Việt (phân loại `scam_type`) – thảo luận 27/11/2026

Ghi lại các quyết định, lý do, kết quả và lưu ý từ buổi thảo luận 27/11, để nhóm tra lại và dùng khi bảo vệ.
Tài liệu liên quan: [`GIAI_THICH_TANG2_VA_META_FEATURES.md`](GIAI_THICH_TANG2_VA_META_FEATURES.md) mục 2.6 (lý do từng lớp),
[`TONG_KET_TIEN_DO.md`](TONG_KET_TIEN_DO.md) (tiến độ chung), [`definition_of_ham_spam_scam.md`](../definition_of_ham_spam_scam.md).

**Trạng thái:** tầng 2 đã có code, đã chọn model (**SVM**), A1–A4 đã làm (mục 5). Chờ đợt crawl 3 (mục 5b) và 1 câu hỏi nhãn (mục 5).
**Chưa commit gì.**

---

## 1. Tầng 2 làm gì

- Nhận tin mà tầng 1 đã báo **scam** và trả lời "lừa đảo **kiểu gì**", chọn 1 trong 9 loại. Tầng 2 không kiểm tra lại tin có phải scam không.
- Mục đích: đưa ra lời khuyên cụ thể (gọi tổng đài ngân hàng, tra VNeID, không nộp "phí giải ngân", gọi xác minh người thân…)
  và thống kê loại lừa đảo phổ biến.
- Chỉ có tiếng Việt. Tin tiếng Anh dừng ở tầng 1 cho tới khi làm tầng 2 tiếng Anh, nên cần thêm bộ nhận diện ngôn ngữ.

## 2. Danh sách lớp (đã chốt và đã áp vào dữ liệu)

| Nhóm định nghĩa | Lớp | Số tin (641 tin Tuấn) | Ghi chú |
|---|---|---|---|
| 3.1 Giả mạo tổ chức | `banking_finance` | 158 | Gồm cả tin vay/nợ **có nêu tên ngân hàng cụ thể** |
| 3.1 | `gov_utility_services` | 95 | Đổi tên từ `government_services`; gộp `telecom_account` (9 tin) |
| 3.1 | `delivery_logistics` | 28 | |
| 3.2 Tài chính & việc làm ảo | `job_task_scam` | 65 | |
| 3.2 | `investment` | 55 | |
| 3.2 | **`loan_debt`** (mới) | 36 | Mời vay, phí giải ngân, đòi nợ qua app/công ty vay |
| 3.3 Trúng thưởng | `prize_lottery` | 111 | |
| Mở rộng | `social_impersonation` | 20 | **Giữ riêng** dù ít tin (phổ biến ngoài đời) |
| Mở rộng | `other_scam` | 73 | |

**Thứ tự ưu tiên khi gán `scam_type`** (để giải thích các ca ranh giới):
1. Có **tên ngân hàng hoặc ví cụ thể** → `banking_finance`, kể cả đổi điểm thưởng ngân hàng hay "nộp phí vào STK … Vietcombank".
2. Mạo danh **cơ quan nhà nước cụ thể** (Công an, CSGT, Thuế, BHXH, UBND, Viện kiểm sát, CIC) → `gov_utility_services`, kể cả khi nội dung là đòi nợ.
3. Mạo danh **nhà mạng, điện, nước**: đe dọa (khóa SIM, cắt dịch vụ, nợ cước) → `gov_utility_services`; **mồi thưởng/quà** → `prize_lottery`
   *(đã áp 27/11, mục 5 – A1)*.
4. Vay/đòi nợ qua app hoặc công ty vay, kể cả khi chỉ nhắc chữ "ngân hàng" chung chung hay "nợ xấu NHNN" → `loan_debt`.
5. Còn lại xét theo kịch bản; không khớp lớp nào → `other_scam`.

**Không có lớp mã độc (3.4):** mã độc là *cách tấn công* (tải `.apk`), không phải *kịch bản*, và dữ liệu chỉ có khoảng 4 tin.

**Thay đổi nhãn đã áp (27/11):**
- 26 nhóm tin (36 dòng) → `loan_debt`; 8 nhóm "nộp phí vào STK + tên ngân hàng" trả về `banking_finance` theo quy tắc 1.
- COM_1477 ("Mã OTP… xác thực tại evn.io.vn"): `banking_finance` → `gov_utility_services`. Tin không có tên ngân hàng, tên miền mạo danh EVN,
  và khớp với tin crawl cùng khuôn mà người dùng đã duyệt.
- 1 tin crawl ("Khoản vay… tự động giải ngân") → `loan_debt`.
- Mọi thay đổi chỉ chạm cột `scam_type`. Dữ liệu tầng 1 được kiểm tra giống hệt bản cũ → **không cần train lại tầng 1**.

## 3. Dữ liệu và cách chia của tầng 2

- **Tầng 2 chia riêng**, khác tầng 1. Tầng 1 phải giữ test của Tuấn để so với bài gốc; tầng 2 là bài toán mới nên không bị ràng buộc này.
- Lấy toàn bộ 641 tin scam của Tuấn, gồm cả các tin bị bỏ ở "cách B" của tầng 1. Bỏ tin trùng y hệt còn **565 tin, 409 khuôn**.
  Chia **70/15/15 theo khuôn**, lớp nào cũng có ở cả 3 tập.
- **Tin crawl đợt 1–2 được đưa vào train** (41 tin, mọi kênh). Chỉ giữ tin lừa đảo chính, nên tin Zalo/Messenger được coi như SMS
  và **bỏ tiêu chí chia theo kênh**.
  - 3 tin không đưa vào vì cùng khuôn với tin trong val/test (Vietcombank khóa TK, CSGT phạt nguội, Netflix).
  - Val/test chỉ có tin của Tuấn và giữ nguyên.
  - Bản đóng băng: `data/raw/vi_crawl_tier2_train.csv`.
- **External test của tầng 2 = đợt crawl 3** (người dùng sẽ crawl), dựng ra `data/raw/vi_crawl_tier2_external.csv`.
  Trước khi có đợt 3 thì **chưa có** số liệu tin thật và chuỗi tầng 1 → tầng 2.
- **Tầng 1 giữ nguyên, không thêm tin crawl.** Lý do: tin "Có đủ 500k không, cho mượn tạm…" từ tài khoản bị hack và tin của bạn bè thật
  **giống hệt nhau về chữ**. Lừa đảo nằm ở danh tính người gửi, model chỉ đọc chữ thì không phân biệt được. Ép tầng 1 học "mượn tiền = scam"
  sẽ gây báo nhầm tin thật, giống lỗi 24% trước đây. → Ghi là **giới hạn** trong báo cáo; demo có thể thêm cảnh báo bằng luật.

## 4. Chọn model và kết quả

**Quy tắc chọn (chốt 27/11): CV macro-F1 trung bình cao nhất.** 5 lượt `StratifiedGroupKFold` theo khuôn trên train+val; chênh nhau ít hơn
1 độ lệch thì coi như ngang và chọn model đơn giản hơn. Phần báo cáo trung bình qua 10 cách chia đã bỏ (vẫn còn tùy chọn `--split-seeds`).

| Model | CV macro-F1 (5 lượt) | Từng lượt |
|---|---|---|
| **SVM** ✅ | **81,8 ± 1,4** | 80,3 · 81,6 · 82,3 · 84,2 · 80,8 |
| Naive Bayes | 73,0 ± 5,4 | 69,3 · 82,4 · 66,4 · 72,4 · 74,3 |
| CharCNN | 64,0 ± 3,4 | 61,5 · 67,7 · 66,5 · 58,8 · 65,5 |

→ **Tầng 2 = Linear SVM** (cùng siêu tham số với tầng 1, không chỉnh riêng). CharCNN chỉ để so sánh: val 1 lần trông ngang SVM (82,7),
nhưng CV chỉ 64; thêm 41 tin là dao động mạnh.

**Vì sao không chọn theo val 1 lần:** val và test mỗi tập chỉ khoảng 85 tin chia cho 9 lớp. SVM có val 85,4 nhưng test 62,9; chia lại 10 cách
thì test dao động 64–84. Tác hại: chọn nhầm model vì may rủi, báo sai con số thật, chỉnh tham số theo nhiễu, CharCNN chọn epoch theo nhiễu.

**Vì sao CV (82) cao hơn test (63–71):** 92% tin trong val/test là khuôn chỉ có 1 tin (cách chia đẩy khuôn lớn vào train), còn các lượt CV
có cả khuôn lớn, dễ đoán hơn. CV dùng để **so sánh model**; test đo độ chính xác trên **khuôn lạ**.

**Kiểm tra CV (theo checklist của người dùng) – không có lỗi cấu trúc:**
- `StratifiedGroupKFold`, không khuôn nào lọt sang cả hai phía; tỉ lệ lớp đều giữa các fold. Riêng `social_impersonation` lệch (3–7 tin)
  vì có khuôn lớn không cắt được.
- TF-IDF được tạo mới và fit **chỉ trên phần học** của mỗi fold: 0 cụm từ chỉ có ở phần thi lọt vào từ vựng.
- CharCNN: dừng sớm theo 15% khuôn tách từ **phần học**, không dùng phần thi; mỗi fold đặt lại seed, học lại bộ ký tự, tạo model mới,
  checkpoint riêng.
- **NB dao động (66–82) là do bản chất model.** Fold tệ nhất: `loan_debt` 4 tin sai cả 4 (mất khoảng 6 điểm), nhầm qua lại ngân hàng và
  điện/nước/nhà mạng. Tỉ lệ từ lạ (OOV) ở hai fold như nhau (15,1% và 14,4%). Cùng fold đó SVM vẫn 82,3.
  NB chỉ dùng đặc trưng từ; SVM có thêm cụm ký tự 3–5 nên bắt được biến thể viết sai ("Vjettel", "M0BlF0NE", "Techcom6ank").

**Các phát hiện khác:**
- `social_impersonation` trên test 0/3, ở cả 3 model. Train chỉ có kiểu "con nhắn bố/mẹ"; test là "Sếp nhờ chút… chuyển vào STK VietinBank"
  → model bám vào lối tắt "STK + tên ngân hàng = banking". Đây là **thiếu đa dạng dữ liệu**, không hẳn là overfit.
  Ghép thêm CharCNN không giúp: CNN cũng sai đúng 3 tin đó, và trên tin thật CNN không đúng thêm tin nào mà SVM sai.
- Nhiều lỗi rơi vào ca ranh giới nhãn nhà mạng (Viettel tặng data, Mobifone sim số đẹp bị đoán thành trúng thưởng) → quy tắc 3 ở mục 2.
- Lần chạy đầu (khi train chưa có tin crawl): trên tin crawl, tầng 2 đúng 68% tin SMS khuôn mới, 33% tin chat; cả chuỗi 50%.
  Nút thắt là **tầng 1** (bắt được 68% tin scam crawl, tin chat gần như 0). Lưu ở `reports/tier2_vi_run1_no_crawl_train/`.

## 5. A1–A4 (đã làm 27/11)

**A1 – quy tắc nhà mạng (đã áp):** TE_048 "VNPT điểm thưởng" và COM_1563 "Viettel tặng data 4G" → `prize_lottery`; COM_1582
"VNPT-Invoice" → `gov_utility_services`. FPT "giảm 50%", Mobifone "sim số đẹp" giữ `gov_utility_services`; Viettel Post giữ
`delivery_logistics` (mạo danh bên giao hàng). Phân bố mới: prize 111, gov_utility 95, other 73.

**A2 – giấu từng khuôn social** (`scripts/tier2_experiments.py` → `reports/tier2_vi/experiments.md`): 10 khuôn social, mỗi lần bỏ 1 khuôn
khỏi train rồi dự đoán khuôn đó. SVM nhận ra **8/10 khuôn, 19/23 tin**. Hai khuôn sai:
- "Ba ơi, con đang dùng máy của bạn… tài khoản Facebook bị khóa" (1 tin) → `other_scam`;
- **"Sếp nhờ chút… chuyển cho đối tác vào STK… lát anh hoàn lại"** (3 tin) → `banking_finance`.
  Phân tích trọng số: các từ đẩy về banking là **"anh", "em", "hoàn lại", "lát"**, không phải tên ngân hàng. Chúng đến từ 12 tin
  `banking_finance` kiểu **"mình lỡ chuyển nhầm… hoàn lại vào STK [NUMBER] BIDV"**, vốn mang nhãn banking chỉ vì có tên ngân hàng nhận tiền.
- Lưu ý: 5 khuôn crawl "cho mượn tiền" giống nhau về chủ đề (Jaccard < 0,5 nên tách khuôn), nên A2 hơi lạc quan với nhóm này.
→ Con số 0/3 trên test trước đây là do **đúng một khuôn khó**; khả năng nhận ra khuôn social mới thực tế khoảng 80%.

**A3 – che tên ngân hàng nhận tiền** (`mask_payee_bank`, ký hiệu `[PAYEE_BANK]`; lần chạy đầu dùng `[BANK]` bị tách thành từ "bank"
trùng "MB Bank" nên đã sửa): 62 tin bị che. CV 79,5 ± 4,6 → 79,8 ± 4,3; test 76,1 → 76,1; A2 19/23 → 19/23; social CV F1 +1,9;
banking +1,4. → **Không có tác dụng rõ** (nằm trong mức nhiễu) và **mâu thuẫn với quy tắc nhãn** "có tên ngân hàng → banking"
(che tên đi thì mất đúng dấu hiệu mà nhãn dựa vào). **Đề xuất: không dùng.**

**Câu hỏi mở cho người dùng:** nhóm 12 tin "chuyển nhầm tiền, hoàn lại vào STK + tên ngân hàng" có nên giữ `banking_finance` không? Kẻ gian
giả làm **người lạ**, không mạo danh ngân hàng; tên ngân hàng chỉ là nơi nhận tiền. Chính nhóm này kéo tin "sếp nhờ" về banking.

**Kết quả sau A1 (chạy lại 27/11, bản hiện hành):** CV macro-F1 **SVM 79,5 ± 4,6** > NB 70,2 ± 4,5 > CharCNN 61,3 ± 7,1 → vẫn SVM.
Test (seed 42) SVM 76,1 (trước 62,9). Đổi nhãn 3 tin làm thay đổi cách chia theo khuôn của từng lớp, nên val/test đổi theo;
điều này lại cho thấy **một lần chia rất dao động**. Thứ hạng giữa các model thì không đổi.

**A4 – model cuối:** `train_tier2.py` train lại model được chọn trên **toàn bộ** dữ liệu tầng 2 → `artifacts/tier2_vi/final/model.joblib`
(+ `training_metadata.json`; tắt bằng `--no-final`). Con số báo cáo vẫn là CV/test ở trên; model cuối không còn dữ liệu giữ lại.

Hướng dài hạn cho social: crawl thêm kiểu "sếp nhờ", "người quen mượn tiền" (đợt 3). Không dùng dữ liệu do LLM sinh.

## 5b. Đợt crawl 3 (người dùng chạy)

- Notebook `notebooks/crawl_vi_scam_kaggle.ipynb` đã sinh lại cho đợt 3 (`/kaggle/working/vi_scam_crawl_run3`).
- Danh sách đợt 1–2 (`data/review/vi_crawl_seen_run1_2/`) đã **nhúng sẵn trong notebook** (ô 4a), không cần tải lên Kaggle. Crawler có tùy chọn mới
  `--skip-from`, nhờ đó bỏ qua **2.502 bài** và **239 tin** của đợt 1–2. Không có bước này thì đợt 3 lấy lại các bài cũ, vốn đã nằm trong
  train tầng 2. Đợt 2 dừng ở mức tối đa 2.500 bài nên hàng đợi vẫn còn bài mới.
- Gợi ý `scam_type` của crawler và danh sách lớp trong `review.html` đã cập nhật theo 9 lớp và thứ tự ưu tiên ở mục 2 (có `loan_debt`).
- Duyệt xong: lưu `data/review/vi_crawl_run3_reviewed.csv`, dựng `data/raw/vi_crawl_tier2_external.csv` (lệnh ở mục 6), chạy lại `train_tier2.py`.

## 6. Lưu ý kỹ thuật (dễ quên)

- **Chạy tầng 2:** `$env:PYTHONPATH="src"; py -3.11 scripts/train_tier2.py`. Đủ 3 model mất khoảng 10 phút (5 lượt CV CharCNN trên CPU);
  `--models nb svm` thì khoảng 1 phút. Báo cáo: `reports/tier2_vi/summary.md`.
- **File cấu hình và code:** `configs/tier2_vietnamese.yaml`, `src/scam_baseline/tier2.py`, `src/scam_baseline/data/scam_types.py`
  (danh sách lớp, nhóm định nghĩa, ánh xạ tên cũ → mới), `tests/test_tier2.py`.
- **Tên lớp:** file duyệt nhãn gốc giữ tên cũ (`government_services`, `telecom_account`). Tên mới được ánh xạ khi dựng dữ liệu, trong
  `VI_SCAM_TYPE_MERGE`. Tiếng Anh vẫn để tên cũ.
- **Sửa `scam_type`:** sửa `data/review/vi_scam_type_overrides.csv` (Tuấn) hoặc cột `review_scam_type` của file crawl đã duyệt, rồi chạy lại:
  `apply_vi_labels_v3.py` → `build_vi_crawl_external.py` → prepare `vietnamese_3class` → `balance_datasets.py --lang vi` → `merge_bilingual.py`
  → `build_meta_features_dataset.py`. Trước khi chạy: bỏ thuộc tính chỉ-đọc và xóa `data/processed_bilingual/master_dataset_base.csv`;
  chạy xong đặt lại chỉ-đọc.
- **Kiểm tra tự động:** script báo lỗi nếu có lớp ngoài danh sách 9 lớp, hoặc tin crawl cùng khuôn với tin Tuấn nhưng khác nhãn.
- **Đợt crawl 3:** dựng bằng
  `build_vi_crawl_external.py --inputs data/review/vi_crawl_run3_reviewed.csv --out <tạm> --full-out data/raw/vi_crawl_tier2_external.csv`.
  Chạy **không** có `--inputs` thì cả 3 đợt bị gộp vào tập crawl của **tầng 1** (không sao với tầng 1, vì tầng 1 không train trên crawl).
- **Sao lưu:** `data/_before_scamtype9_2026-11-27/` (trước khi đổi 9 lớp), `reports/tier2_vi_run1_no_crawl_train/` (kết quả trước khi thêm crawl).
- Đã sửa thêm: `modeling_data_with_meta.csv` cũ thiếu 20 tin crawl đợt 2, nay khớp `modeling_data.csv`; ảnh ma trận nhầm lẫn
  9 lớp xoay nhãn cho dễ đọc.
- Script kiểm tra CV hiện chỉ nằm trong thư mục tạm của phiên, chưa đưa vào repo.

## 7. Tư liệu viết báo cáo (tổng hợp thảo luận 27/11)

Viết sẵn theo kiểu "luận điểm + số liệu + câu trả lời khi bị hỏi", dùng thẳng cho chương tầng 2, đánh giá và giới hạn.

### 7.1 Kiến trúc và lựa chọn model
- Hệ thống 2 tầng: **tầng 1** (ham/spam/scam, Linear SVM song ngữ) → nhận diện ngôn ngữ → **tầng 2** (9 loại scam, Linear SVM tiếng Việt).
  **Cả hai tầng đều chọn Linear SVM** (TF-IDF từ 1–2 + cụm ký tự 3–5, `class_weight=balanced`).
- Tầng 1 chọn theo **F2 lớp scam trên validation** (bỏ sót lừa đảo nguy hiểm hơn báo nhầm). Tầng 2 chọn theo **CV macro-F1** (mọi loại scam
  quan trọng như nhau, kể cả lớp ít tin).
- Bảng tầng 2 (CV 5 lượt, sau A1): SVM **79,5 ± 4,6**, NB 70,2 ± 4,5, CharCNN 61,3 ± 7,1.
- *Nếu hỏi "sao không dùng deep learning?"*: đã thử CharCNN ở cả hai tầng. Tầng 1: CharCNN tốt trên test của Tuấn nhưng kém trên tin thật
  (12/22 so với 19/22 của SVM, báo nhầm 3,6% so với 1,0%). Tầng 2: CharCNN thấp nhất và dao động mạnh nhất. Với vài trăm tin, model tuyến
  tính trên TF-IDF ổn định hơn; cụm ký tự giúp SVM bắt được biến thể cố tình viết sai ("Vjettel", "M0BlF0NE", "Techcom6ank").
- *Nếu hỏi "sao không ghép SVM với CharCNN?"*: ở tầng 1 đã thử rerank, không hơn SVM đơn. Ở tầng 2, hai model sai ở cùng các tin
  (ví dụ cả hai cùng sai 3/3 tin "sếp nhờ"), và trên tin thật CNN không đúng thêm tin nào mà SVM sai → ghép không có lợi.

### 7.2 Phương pháp đánh giá (điểm mạnh nên nhấn mạnh)
- **Chia theo khuôn (họ mẫu)**, không chia ngẫu nhiên: tập Tuấn nhiều tin sinh từ cùng mẫu. Trước khi sửa, 80% scam test có "anh em"
  trong train → điểm bị thổi phồng.
- **Một lần chia rất nhiễu với dữ liệu nhỏ:** val/test của tầng 2 chỉ khoảng 85 tin cho 9 lớp. Cùng SVM: val 85,4 nhưng test 62,9;
  chia lại 10 cách thì test dao động 64–84; chỉ đổi nhãn 3 tin là test nhảy 62,9 → 76,1. → Dùng **CV theo khuôn** để chọn model.
- **CV đã được kiểm tra cấu trúc** (`StratifiedGroupKFold`; TF-IDF fit trong từng fold, 0 cụm từ của phần thi lọt vào từ vựng; CharCNN
  dừng sớm bằng tập tách từ phần học, khởi tạo lại mỗi fold). NB dao động 66–82 giữa các fold là do bản chất model (lớp `loan_debt`
  4 tin sai cả 4 ở fold tệ nhất; tỉ lệ từ lạ ở hai fold như nhau), không phải lỗi chia.
- **Báo cáo theo từng lớp kèm khoảng tin cậy Wilson** (lớp 3–4 tin có khoảng tin cậy rất rộng), và báo cáo thêm ở **mức nhóm của định nghĩa**
  (3.1 / 3.2 / 3.3 / mở rộng).
- **Tin thật (crawl báo chí) tách khỏi dữ liệu train:** đợt 1–2 dùng train tầng 2; đợt 3 (bỏ qua mọi bài và tin của đợt 1–2) là
  external test, kèm đánh giá **cả chuỗi tầng 1 → tầng 2** (tầng 1 để lọt thì tính là sai).

### 7.3 Danh sách lớp – câu trả lời khi bị hỏi
Xem mục 2 (thứ tự ưu tiên) và [`GIAI_THICH_TANG2_VA_META_FEATURES.md`](GIAI_THICH_TANG2_VA_META_FEATURES.md) mục 2.6. Tóm tắt:
- Mỗi lớp thuộc đúng một nhóm của `definition_of_ham_spam_scam.md` (3.1 giả mạo tổ chức, 3.2 tài chính/việc làm ảo, 3.3 trúng thưởng).
- `social_impersonation` giữ riêng dù ít tin: phổ biến ngoài đời, mạo danh **cá nhân** (định nghĩa 3.1 chỉ nói tổ chức).
- `loan_debt` tách khỏi ngân hàng vì định nghĩa xếp "vay vốn giải ngân nhanh" vào 3.2.
- `gov_utility_services` gồm cơ quan nhà nước **và** dịch vụ thiết yếu (điện, nước, viễn thông), vì định nghĩa 3.1 xếp "Điện lực" cùng
  Công an, Thuế. Nhà mạng mồi thưởng/quà thì là trúng thưởng.
- Không có lớp mã độc (3.4): đó là cách tấn công, không phải kịch bản; dữ liệu khoảng 4 tin.

### 7.4 Phát hiện đáng đưa vào báo cáo
- **Lớp social:** test 0/3 là do một khuôn khó ("Sếp nhờ chuyển cho đối tác"). Đánh giá giấu từng khuôn: SVM nhận ra **8/10 khuôn,
  19/23 tin** chưa từng thấy. Khuôn "sếp" bị kéo về banking bởi các từ "anh/em/hoàn lại/lát", do nhóm tin "chuyển nhầm tiền, hoàn lại vào
  STK + tên ngân hàng" đang mang nhãn banking.
- **Che tên ngân hàng nhận tiền không giúp** (CV 79,5 → 79,8, trong mức nhiễu) → lối tắt không nằm ở tên ngân hàng.
- **Tin "mượn tiền" không thể nhận ra chỉ từ chữ:** tin từ tài khoản bị hack và tin của bạn thật giống hệt nhau; lừa đảo nằm ở danh tính
  người gửi. Nên tầng 1 không train thêm loại này (tránh báo nhầm tin thật, từng lên tới 24%); demo thêm cảnh báo bằng luật "hãy gọi
  xác minh".
- **Meta-features (nếu không làm):** dữ liệu đã tính sẵn nhưng khi kiểm tra thì đặc trưng **số chữ số đo cách che số của từng nguồn**,
  không đo lừa đảo: tin Tuấn che số thành `[NUMBER]` (scam trung bình 1,7 chữ số), `vie_sms` để số thật (spam trung bình 25,0). Dùng
  nguyên sẽ thành lối tắt "ít chữ số = scam". Các đặc trưng còn lại phần lớn đã có trong TF-IDF ("khóa tài khoản", "xác thực"…);
  `url_count` có nguy cơ làm mạnh lối tắt "có link = scam". → Đây là một phát hiện về kiểm soát lối tắt, nên ghi vào báo cáo.
- **Xung đột nhãn giữa hai nguồn được phát hiện tự động:** tin "Mã OTP… evn.io.vn" Tuấn gán banking, tin crawl cùng khuôn gán
  điện/nước → đã sửa theo quy tắc, và script nay tự báo lỗi khi gặp trường hợp này.

### 7.5 Giới hạn (bổ sung cho mục 4 của `TONG_KET_TIEN_DO.md`)
1. Tầng 2 chỉ có tiếng Việt; tin tiếng Anh dừng ở tầng 1.
2. Lớp nhỏ (`social_impersonation` 20 tin, `delivery_logistics` 28, `loan_debt` 36) → F1 từng lớp dao động mạnh.
3. Lừa đảo giọng cá nhân/chat: tầng 1 gần như không bắt được; một phần không thể giải bằng nội dung tin.
4. Val/test tầng 2 thiên về khuôn hiếm (92% là khuôn chỉ 1 tin) → con số test là "trên khuôn lạ", thấp hơn CV.
5. Nhãn `scam_type` có ca ranh giới (nhà mạng, "chuyển nhầm tiền") – đã ghi quy tắc ưu tiên để nhất quán.

### 7.6 Đợt crawl 3 – ghi lại quy trình (cho phần thu thập dữ liệu)
- Crawler thêm `--skip-from` để bỏ qua bài và tin của các đợt trước; danh sách đợt 1–2 (2.502 bài, 239 tin) nhúng sẵn trong notebook.
  Lần chạy đầu trên Kaggle dừng ở ô kiểm tra vì chưa có danh sách này → đã sửa bằng cách nhúng.
- Gợi ý `scam_type` của crawler và giao diện duyệt đã theo 9 lớp mới. Mọi tin vẫn do người duyệt 100%; EasyOCR chỉ là công cụ gõ hộ;
  không dùng dữ liệu do LLM sinh.

## 8. C1 – nhận diện ngôn ngữ và C2 – `predict_pipeline` (đã làm 27/11)

### 8.1 C1 – bộ nhận diện ngôn ngữ vi / en

**Vai trò:** quyết định tin nào được đưa sang tầng 2 (tầng 2 chỉ có tiếng Việt). Tầng 1 là model song ngữ nên không cần bước này.

**Cách làm**
- Model: Naive Bayes đa thức trên TF-IDF cụm ký tự 1–3 (`char_wb`, `min_df=2`, `alpha=0.1`). Chọn NB vì nhanh, nhẹ (1,1 MB),
  là cách làm kinh điển cho nhận diện ngôn ngữ, và không phụ thuộc model bên ngoài.
- Dữ liệu: `data/processed_bilingual/modeling_data.csv`, nhãn `language` lấy theo nguồn (Tuấn, vie_sms → vi; IMC25, sms_phishing,
  SmishX → en). Train trên tập train của tầng 1 (10.430 tin), không chỉnh tham số theo test.
- **Tiền xử lý bỏ những thứ khác nhau theo nguồn, không theo ngôn ngữ:** ký hiệu che (`[NUMBER]`, `<PHONE>`…), link, email, chữ số.
  Nếu giữ lại, model sẽ học "có `[NUMBER]` = tiếng Việt, có `<PHONE>` = tiếng Anh" (cùng loại lối tắt với "có dấu = scam" trước đây).
  3 tin không còn chữ nào sau bước này bị bỏ.
- **Tiếng Việt không dấu:** mỗi tin tiếng Việt trong train được thêm một bản bỏ dấu (4.897 tin) → tổng 15.327 tin train.

**Kết quả** (`reports/langid/summary.md`, `artifacts/langid/metrics.json`)

| Tập | Số tin | Accuracy | Recall vi | Recall en | Tiếng Việt bỏ dấu | Tin ngắn ≤ 30 ký tự |
|---|---|---|---|---|---|---|
| validation | 3.886 | 99,64 | 98,31 | 99,94 | 97,89 | 97,56 |
| test | 3.394 | 99,50 | 97,70 | 99,86 | 97,52 | 96,74 |
| external | 3.915 | 95,73 | 94,68 | 98,73 | 94,06 | 94,07 |

- 10/10 câu thử viết tay đúng (có tin không dấu, tin chứa tên thương hiệu tiếng Anh như "Vietcombank: Ma OTP…", tin rất ngắn "ok e").
- External thấp hơn chủ yếu do **nhãn theo nguồn chưa chính xác**: trong 154 "lỗi" ở `vie_sms_holdout`, khoảng 82 tin là tiếng Anh thật
  (mã xác minh Google/Facebook, "Okay babe"…) và 15 tin gần như không có chữ. Lỗi thật khoảng 60/2.870 (~2%): tin viết tắt
  ("So du TK VCB… Ref POS"), đáp án bài tập ("1c 2d 3a").
- Hệ quả nếu đoán sai: tin scam tiếng Việt bị coi là tiếng Anh vẫn được tầng 1 báo scam, chỉ **không có loại lừa đảo**.

### 8.2 C2 – `predict_pipeline` (ghép cả hệ thống cho demo)

**Luồng xử lý**
```
tin gốc → clean_text → nhận diện ngôn ngữ
        → tầng 1 (SVM song ngữ): legitimate / spam / scam
        → nếu scam và tiếng Việt → tầng 2 (SVM 9 loại) → nhóm theo định nghĩa → lời khuyên
        → cảnh báo bằng luật (yêu cầu chuyển/mượn tiền) – không đổi nhãn
```
- Kết quả là một `dict` có bộ khóa cố định (bảng đầy đủ trong `demo/README.md`): `label`, `label_vi`, `label_scores`, `label_margin`,
  `tier1_top_words`, `scam_type`, `scam_type_vi`, `scam_group(_vi)`, `scam_type_scores`, `scam_type_margin`, `tier2_top_words`,
  `advice`, `warnings`, `notes`, `language`, `language_confidence`, `tier1_text`, `tier2_text`.
- **Giải thích kết quả:** "từ khiến model nghi ngờ" = các cụm từ trong tin có đóng góp dương lớn nhất (giá trị TF-IDF × trọng số SVM của lớp
  được chọn); chỉ liệt kê cụm từ (dễ đọc), cụm ký tự vẫn được dùng để quyết định.
- **Điểm SVM không phải xác suất** → hiển thị chênh lệch giữa hai lớp cao nhất (`label_margin`); nhỏ hơn khoảng 0,3 = model phân vân.
- Tốc độ: nạp 3 model khoảng 10 giây, sau đó khoảng 0,15 giây/tin trên CPU; không cần PyTorch.

**Quyết định che số trước khi đưa vào model (đo bằng số liệu)**

| Trên `vie_sms` holdout (tin thật) | Không che | Che kiểu Tuấn |
|---|---|---|
| Tin ham bị báo scam | 1,03% | 1,03% |
| Spam được nhận ra | 76,2% | 57,5% (spam bị đoán thành ham) |

- Tin scam gõ với số thật: "Ho so vay 50 trieu da duyet, vui long nop phi bao hiem 2 trieu de giai ngan" → không che: **ham**; che: **scam**.
  Lý do: mọi tin scam tiếng Việt lúc train đều đã che số.
- → **Chọn che số cho tin tiếng Việt ở cả hai tầng** (mặc định, `ScamDetector(mask_vi_tier1=False)` để tắt). Tầng 1 ưu tiên không bỏ sót
  scam; spam bị đoán thành ham là lỗi ít nguy hiểm hơn; và con số tầng 1 đã báo cáo (tin crawl) được đo trên tin đã che số.
- Tin tiếng Anh: quy về `<URL> <PHONE> <EMAIL> <DATE_TIME> <NUMBER>` như dữ liệu train tiếng Anh.
- Hàm che số tiếng Việt (`mask_vi`) là bản sao đúng của `mask_pii` trong crawler (crawler phải là 1 file độc lập để chạy trên Kaggle);
  test kiểm tra hai hàm cho kết quả giống nhau.

**Cảnh báo bằng luật:** tin có dạng "cho mượn", "chuyển giúp/gấp/tạm", "TK còn đủ tiền không"… → *"Tin có yêu cầu chuyển/mượn tiền… hãy
GỌI ĐIỆN xác minh trước khi chuyển."* Không đổi nhãn, vì nội dung tin không phân biệt được tin người quen thật với tài khoản bị chiếm (mục 7.4).

**Chạy thử** (`scripts/try_pipeline.py`)

| Tin | Tầng 1 | Tầng 2 | Ghi chú |
|---|---|---|---|
| "Vietcombank thong bao: tai khoan… bi tam khoa… vcb-xacminh.top" | scam | banking_finance | |
| "CSGT thong bao: … nop phat tai dichvucong-gov.xyz" | scam | gov_utility_services | |
| "Ho so vay 50 trieu da duyet… de giai ngan" | scam (sau khi che số) | loan_debt | |
| "Your account has been locked. Verify…" | scam | – | tầng 2 chỉ tiếng Việt |
| "Chiều nay 5h họp nhóm đồ án ở thư viện nhé" | ham | – | |
| "[QC] Viettel… Tu choi QC soan TC gui 199" | ham | – | quảng cáo hợp chuẩn |
| "Có đủ 500k không, cho mượn tạm…" | ham | – | có cảnh báo chuyển tiền |
| "Sếp nhờ chút… chuyển tạm 20 triệu cho đối tác…" | ham | – | có cảnh báo chuyển tiền |
| "Mẹ ơi con đang cấp cứu… chuyển giúp con 5 triệu vào STK… Vietcombank" | **ham** | – | có cảnh báo; xem giới hạn |

**Giới hạn thấy rõ:** tin giọng cá nhân ("con cấp cứu", "sếp nhờ") bị tầng 1 đoán là ham nên không tới được tầng 2. Riêng khuôn
"con cấp cứu" nằm trong test của Tuấn nên tầng 1 chưa từng học (cách B); tầng 2 lại nhận ra được khuôn này. Có thể cân nhắc cho demo: khi có
cảnh báo chuyển tiền mà tầng 1 nói ham thì vẫn hiện gợi ý "nếu là lừa đảo, có thể thuộc loại…" (chưa làm, chờ người dùng quyết).

### 8.3 Gói demo cho thành viên làm giao diện
- `py -3.11 scripts/package_demo.py` → `demo_bundle/` và `demo_bundle.zip` (4,6 MB; **không vào git**): 3 model (`models/`), package
  `scam_baseline/`, `try_pipeline.py`, `requirements.txt` ghim phiên bản (scikit-learn 1.9.1, numpy 2.4.6, scipy 1.17.1, joblib 1.6.0,
  pandas 2.3.3, gradio), `README.md` (= `demo/README.md`: cài đặt, cách gọi, bảng khóa kết quả, đoạn Gradio mẫu, lưu ý trình bày),
  `MODEL_INFO.md` (số liệu chính từng model).
- Đã kiểm tra: giải nén ở thư mục khác, chạy bằng `python -I` (không dùng code của repo) → chạy đúng.
- Phải dùng **đúng phiên bản scikit-learn** khi chạy gói, vì model được lưu bằng joblib.

### 8.4 File mới / sửa trong C1–C2
| File | Vai trò |
|---|---|
| `src/scam_baseline/langid.py` | Tiền xử lý + model nhận diện ngôn ngữ |
| `scripts/train_langid.py` | Train, đánh giá, báo cáo → `artifacts/langid/`, `reports/langid/summary.md` |
| `src/scam_baseline/data/masking.py` | `mask_vi` (che số kiểu Tuấn), `PLACEHOLDER_RE`, `URL_RE` dùng chung |
| `src/scam_baseline/predict.py` | `ScamDetector`, `predict_pipeline(text)`; nhãn/loại/lời khuyên tiếng Việt |
| `scripts/try_pipeline.py` | Thử trong terminal (`--text`, `--json`, chế độ hỏi đáp) |
| `scripts/package_demo.py`, `demo/README.md` | Đóng gói demo + tài liệu giao diện |
| `tests/test_masking_langid_predict.py` | `mask_vi` khớp crawler; tiền xử lý langid; hợp đồng đầu ra + định tuyến của pipeline |
| `.gitignore` | Bỏ qua `demo_bundle/`, `demo_bundle.zip` |

Lệnh: `$env:PYTHONPATH="src"; py -3.11 scripts/train_langid.py` · `py -3.11 scripts/try_pipeline.py` · `py -3.11 scripts/package_demo.py`
· test: `py -3.11 -m pytest -q` (**39/39 đạt**).
