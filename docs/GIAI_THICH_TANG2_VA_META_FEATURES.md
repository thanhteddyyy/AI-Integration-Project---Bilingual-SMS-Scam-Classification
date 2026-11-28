# Ghi chú thảo luận 26/11/2026: lớp tầng 2 tiếng Việt và meta-features của SVM

Trạng thái: **27/11 đã chốt 9 lớp và đã áp vào dữ liệu (mục 2.6)**. Mục 2.4–2.5 là đề xuất cũ (8 lớp), giữ lại để đối chiếu.
Xem thêm [`TONG_KET_TIEN_DO.md`](TONG_KET_TIEN_DO.md) mục 3.

---

## 1. Phân công

- **Việc 4 (Demo Gradio)** và **việc 8 (Báo cáo, slide)** giao cho thành viên khác trong nhóm. Hai việc này nằm cuối chuỗi,
  không làm chậm tầng 2, bộ nhận diện ngôn ngữ hay phân tích lỗi.
- Lưu ý khi bàn giao:
  - Demo phụ thuộc tầng 2 và bộ nhận diện ngôn ngữ (cả hai chưa có code). Bạn làm demo nên dựng giao diện với **tầng 1 trước**
    (dựa vào `scripts/try_tier1.py`). Hai bên thống nhất trước một hàm chung, ví dụ
    `predict_pipeline(text) -> {label, scam_type, top_words}`, để sau này cắm tầng 2 vào mà không phải sửa giao diện.
  - `artifacts/` không có trong git → phải gửi tay `artifacts/bilingual/svm/model.joblib` (khoảng 7,5 MB).
  - `.venv` của dự án đang hỏng → dùng Python 3.11 với `PYTHONPATH=src`.
  - Báo cáo: viết được ngay chương dữ liệu và chương tầng 1. Chương tầng 2 và chương phân tích lỗi phải chờ.

---

## 2. Lớp `scam_type` cho tầng 2 tiếng Việt

### 2.1 Mong muốn của người dùng
**Giữ riêng `social_impersonation`** (người thân hoặc sếp nhờ chuyển tiền, "con cấp cứu"). Tuy ít tin nhưng đây là loại lừa đảo
khá phổ biến ngoài đời. Gộp hai lớp nhỏ còn lại.

### 2.2 Số tin thực tế trong pipeline (sau khi lọc tin cùng khuôn)
Con số 20 tin trong log là **trước** khi lọc. Số tin tiếng Việt thuộc lớp `social_impersonation` còn lại thật sự:

| Tập | Số tin | Ghi chú |
|---|---|---|
| Train | **1** | "Ba ơi, con đang dùng máy của bạn…", cộng 2 bản augment của chính tin này |
| Validation | **0** | |
| Test | 6 | Thuộc 4 khuôn: con cấp cứu, con bị tạm giữ ở đồn, sếp nhờ chuyển tiền, con rớt điện thoại |
| Crawl thật (tập đầy đủ) | 5 | |

Hệ quả:
- Model chỉ có 1 khuôn để học, nên gần như không thể nhận ra lớp này.
- Validation có 0 tin, nên không đo được lớp này khi chọn model.

**Vì sao train chỉ còn 1 tin:** do bước "cách B". Bước đó giữ nguyên test của Tuấn và bỏ khỏi train mọi tin cùng khuôn với test.
Lớp này có ít khuôn, phần lớn lại nằm trong test, nên train gần như bị xóa sạch.

Toàn bộ tin scam tiếng Việt trong pipeline theo từng tập, chưa tính bản augment
(nguồn: `data/processed_vi_balanced/modeling_data.csv`):

| scam_type | train | validation | test | external (crawl sạch) | tổng |
|---|---|---|---|---|---|
| banking_finance | 64 | 6 | 41 | 5 | 116 |
| prize_lottery | 57 | 14 | 22 | 0 | 93 |
| government_services | 45 | 9 | 17 | 6 | 77 |
| other_scam | 61 | 11 | 0 | 5 | 77 |
| investment | 41 | 6 | 1 | 0 | 48 |
| job_task_scam | 31 | 5 | 11 | 0 | 47 |
| delivery_logistics | 13 | 2 | 5 | 6 | 26 |
| telecom_account | 4 | 3 | 1 | 0 | 8 |
| social_impersonation | 1 | 0 | 6 | 0 | 7 |
| **Tổng** | 317 | 56 | 104 | 22 | 499 |

### 2.3 Đề xuất: tầng 2 có cách chia train/val/test riêng
- Tầng 1 phải giữ nguyên test của Tuấn để so sánh với bài gốc. Tầng 2 là bài toán mới, không có bài gốc để so,
  nên không bị ràng buộc đó.
- Tầng 2 lấy lại **toàn bộ 641 tin scam của Tuấn**, kể cả các tin đã bị bỏ ở "cách B". Sau đó chia **theo khuôn (họ mẫu)** và
  đảm bảo mỗi lớp đều có mặt ở cả train, val và test.
- Ước tính lớp `social_impersonation` có khoảng 5 khuôn: khoảng 3 vào train, 1 vào val, 1 vào test. Vẫn ít, nhưng model đã học được.
- **Đánh giá cả chuỗi tầng 1 → tầng 2** làm trên **tập crawl thật** (44 tin scam đã có nhãn loại, trong đó 5 tin
  `social_impersonation`). Cách này tránh xung đột giữa hai cách chia, lại là phép đo sát thực tế nhất.
- Cần nêu trong báo cáo: tin `social_impersonation` có giọng cá nhân, đúng loại tầng 1 hay đoán nhầm thành ham. Ngoài đời,
  những tin này ít khi đi được tới tầng 2.
- Nếu nhóm tìm thêm được tin thật thuộc loại này (báo chí, ảnh chụp tin nhắn Zalo), lớp này sẽ tốt lên rõ rệt.
  **Không dùng dữ liệu do LLM sinh.**

### 2.4 Danh sách lớp đề xuất: 8 lớp

| # | Lớp | Nội dung |
|---|---|---|
| 1 | `banking_finance` | Mạo danh ngân hàng hoặc ví điện tử (khóa tài khoản, sinh trắc học, đổi điểm); vay tiền, đòi nợ không mạo danh cơ quan nhà nước |
| 2 | `prize_lottery` | Trúng thưởng, quà giả; cờ bạc kèm tên miền cờ bạc hoặc tên miền ngẫu nhiên |
| 3 | `government_services` | Mạo danh công an, thuế, Cục Viễn thông, điện lực, cấp nước |
| 4 | `job_task_scam` | Tuyển CTV "việc nhẹ lương cao", làm nhiệm vụ, chốt đơn |
| 5 | `investment` | Đầu tư, forex, tiền ảo, khóa học làm giàu, dropship |
| 6 | `delivery_logistics` | Mạo danh bên giao hàng |
| 7 | **`social_impersonation`** | Người thân hoặc sếp nhờ chuyển tiền (**giữ riêng**, theo ý người dùng) |
| 8 | `other_scam` | `other_scam` cũ + `telecom_account` (tài khoản Telegram/Zalo, hẹn hò, timeshare, tin làm rối, thám tử, nhà mạng) |

Phương án khác: gộp `telecom_account` vào `government_services` thay vì `other_scam`. Cả hai cùng kiểu
"mạo danh đơn vị dịch vụ", nên gộp như vậy có lẽ hợp lý hơn về nghĩa. Danh sách vẫn là 8 lớp.

### 2.5 Cần chốt
1. Dùng **8 lớp** như bảng trên? `telecom_account` gộp vào **`other_scam`** hay vào **`government_services`**?
2. Đồng ý cho **tầng 2 chia dữ liệu riêng** (lấy lại tin bị bỏ ở "cách B", chia theo khuôn, mỗi lớp có ở cả 3 tập), và đánh giá
   cả chuỗi trên tập crawl thật?

### 2.6 ĐÃ CHỐT 27/11: 9 lớp, bám theo `definition_of_ham_spam_scam.md` mục 3

Định nghĩa chia scam thành 4 nhóm: **3.1** giả mạo tổ chức (ngân hàng, cơ quan nhà nước kể cả điện lực, giao vận),
**3.2** lừa đảo tài chính & việc làm ảo (CTV, "vay vốn giải ngân nhanh", đầu tư), **3.3** trúng thưởng, **3.4** mã độc (`.apk`).
Mỗi lớp tầng 2 thuộc đúng một nhóm, nên báo cáo được kết quả ở cả hai mức (9 lớp và nhóm của định nghĩa).
Code: `src/scam_baseline/data/scam_types.py` (`VI_TIER2_GROUPS`, `VI_SCAM_TYPE_MERGE`).

| Nhóm định nghĩa | Lớp | Nội dung | Tổng 641 tin Tuấn | So với cũ |
|---|---|---|---|---|
| 3.1 | `banking_finance` | Mạo danh ngân hàng hoặc ví (khóa TK, sinh trắc, giao dịch lạ, thẻ tín dụng, đổi điểm); tin vay/nợ **có nêu tên ngân hàng cụ thể** | 159 | Thu hẹp (bỏ tin vay/nợ qua app) |
| 3.1 | `gov_utility_services` | Cơ quan nhà nước + dịch vụ thiết yếu (điện, nước, **viễn thông**) | 95 | Gộp `telecom_account` (9) |
| 3.1 | `delivery_logistics` | Mạo danh bên giao hàng | 28 | Giữ |
| 3.2 | `job_task_scam` | CTV, làm nhiệm vụ, chốt đơn | 65 | Giữ |
| 3.2 | `investment` | Đầu tư, forex, tiền ảo, khóa học làm giàu | 55 | Giữ |
| 3.2 | **`loan_debt`** | Mời vay, phí giải ngân, đòi nợ qua **app/công ty vay**, không nêu tên ngân hàng cụ thể, không mạo danh cơ quan nhà nước cụ thể | 36 | **Mới** (34 từ banking, 2 từ government) |
| 3.3 | `prize_lottery` | Trúng thưởng, quà giả, cờ bạc | 109 | Giữ |
| Mở rộng | `social_impersonation` | Mạo danh người thân, sếp nhờ chuyển tiền | 20 | **Giữ riêng** |
| Mở rộng | `other_scam` | Tài khoản Telegram/Zalo, hẹn hò, timeshare, thương hiệu nhỏ, tin làm rối | 74 | Giữ |

**Lý do từng quyết định (dùng khi giảng viên hỏi):**
- **Không dùng thẳng 4 nhóm của định nghĩa:** nhóm 3.1 sẽ chiếm khoảng nửa dữ liệu, trộn ngân hàng, công an, giao hàng. Ba kiểu này có cách
  phòng tránh khác nhau. Chia nhỏ hơn nhưng mỗi lớp vẫn thuộc đúng một nhóm, và có báo cáo ở mức nhóm.
- **Giữ riêng `social_impersonation`:** phổ biến, thiệt hại lớn. Cơ chế khác: mạo danh **cá nhân**, trong khi 3.1 chỉ nói về **tổ chức**.
  Vẫn là tấn công kỹ thuật xã hội đúng định nghĩa lõi của scam (Goel & Jain 2018). Ít dữ liệu → tầng 2 chia tập theo khuôn để lớp có ở cả
  train/val/test, báo cáo F1 riêng của lớp kèm khoảng tin cậy.
- **Gộp `telecom_account` → `gov_utility_services`:** chỉ 9 tin. Định nghĩa xếp điện lực (dịch vụ thiết yếu) cùng cơ quan nhà nước, nhà mạng
  cùng loại. Kịch bản giống nhau: "khóa SIM, cắt mạng do nợ cước hoặc chưa chuẩn hóa thông tin" giống "cắt điện do nợ tiền điện".
- **Tách `loan_debt`:** định nghĩa xếp "vay vốn giải ngân nhanh" vào 3.2, không phải 3.1. App vay và đòi nợ kiểu khủng bố rất phổ biến
  ở Việt Nam. **Quy tắc (người dùng chốt 27/11):** tin vay/nợ **có nêu tên một ngân hàng cụ thể** (MSB, Techcombank, cả "nộp phí vào
  STK … Vietcombank") → `banking_finance`; vay/đòi tiền qua app hoặc công ty vay (F88, SIM CASH, Cash24, "TINVAY"…) → `loan_debt`;
  đòi nợ mạo danh **cơ quan nhà nước cụ thể** (Công an, UBND, CIC) → `gov_utility_services`.
- **Giữ `delivery_logistics` dù ít (28):** định nghĩa nêu đích danh "đơn vị giao vận", từ ngữ đặc trưng nên dễ học.
- **Không có lớp mã độc (3.4):** đây là **cách tấn công**, không phải kịch bản (một tin vừa mạo danh thuế vừa bảo tải app). Dữ liệu chỉ
  khoảng 4 tin. Nêu trong giới hạn; có thể thêm cờ "có link `.apk`" bằng luật.
- **Giữ `other_scam`:** định nghĩa không bao hết thực tế, cần chỗ cho phần còn lại thay vì ép vào lớp sai.

**Đã áp vào dữ liệu (27/11):**
- 26 nhóm tin (36 dòng) → `loan_debt` (ban đầu 34 nhóm; 8 nhóm "nộp phí vào STK <tên ngân hàng>" trả về `banking_finance` theo quy tắc trên) trong `data/review/vi_scam_type_overrides.csv` (ghi chú "Rà scam_type 27/11"); 1 tin crawl
  (`vi_crawl_810603087569`) trong `vi_crawl_run2_reviewed.csv`. Ứng viên lọc bằng từ khóa vay/nợ/giải ngân (78 nhóm), agent đọc từng tin.
- `government_services` đổi tên thành `gov_utility_services` (cho thấy lớp gồm cả dịch vụ thiết yếu), `telecom_account` gộp vào; cả hai làm tự động trong `apply_vi_labels_v3.py` và `build_vi_crawl_external.py`; cả hai báo lỗi nếu có lớp ngoài danh sách.
- Chạy lại apply → crawl → prepare → balance (VI) → merge → meta. Kiểm tra: mọi cột khác `scam_type` **giống hệt** bản cũ
  (sao lưu `data/_before_scamtype9_2026-11-27/`) → **không cần train lại tầng 1**. 29/29 test đạt.
- Nhân tiện, `modeling_data_with_meta.csv` cũ thiếu 20 tin crawl lần 2 (dựng trước crawl 2), nay đã khớp `modeling_data.csv` (24.215 dòng).
- Còn lại: tầng 2 chia dữ liệu riêng (mục 2.3) – làm khi viết code tầng 2.

---

## 3. Meta-features của SVM là gì?

### 3.1 Giải thích kỹ thuật
Hiện SVM chỉ nhìn **từ và cụm ký tự** (TF-IDF). Meta-features là **5 con số thống kê** tính trên văn bản gốc (`text_raw`),
ghép thêm vào vector TF-IDF. Code nằm ở `scripts/build_meta_features_dataset.py`.

| Đặc trưng | Ý nghĩa | Vì sao có thể giúp |
|---|---|---|
| `msg_length` | Độ dài tin | Tin lừa đảo thường dài hơn tin cá nhân |
| `url_count` | Số link hoặc IP | Lừa đảo hay kèm link |
| `digit_count` | Số chữ số | Số tiền, số điện thoại, mã |
| `special_char_ratio` | Tỉ lệ ký tự đặc biệt (`$ % ! ? # @ / :`…) | Tin lừa đảo hay giật gân, nhiều ký hiệu |
| `urgent_word_count` | Số từ khẩn cấp hoặc thao túng tâm lý ("khóa tài khoản", "trúng thưởng", "xác thực", tên ngân hàng…, có cả bản có dấu và không dấu) | Dấu hiệu tạo áp lực đặc trưng của lừa đảo |

- Năm số này được chuẩn hóa bằng `StandardScaler`. Scaler **chỉ học trên tập train** nên không bị rò rỉ dữ liệu.
- **Trạng thái:** dữ liệu meta-features đã tính xong, nhưng **SVM chưa dùng tới**. Việc 7 là ghép chúng vào SVM, lưu scaler cùng
  model, rồi so sánh có và không có meta-features (thí nghiệm ablation).
- **Vì sao chỉ là việc tùy chọn:**
  - Phần lớn thông tin này SVM đã thấy qua TF-IDF. Danh sách từ khẩn cấp gần như trùng với những từ SVM đã học,
    nên có thể không cải thiện bao nhiêu.
  - `url_count` và tên ngân hàng có thể làm lối tắt "có link là scam" mạnh thêm. Đây là rủi ro cần kiểm tra trong
    phân tích lỗi (quy tắc X4).
  - Kết quả nào cũng đáng đưa vào báo cáo, kể cả khi không tăng.

### 3.2 Giải thích dễ hiểu (như cho trẻ con)
Tưởng tượng em là chú chó canh cửa, nhiệm vụ là đoán xem lá thư nào là của **kẻ lừa đảo**.

**Hiện giờ, SVM đọc chữ trong thư.** Nó nhớ rằng thư nào có chữ "trúng thưởng", "khóa tài khoản", "chuyển tiền gấp" thì đáng ngờ.

**Meta-features là nhìn hình dáng lá thư, không cần đọc chữ.** Giống như nhìn phong bì rồi đếm:
1. 📏 **Thư dài hay ngắn?** Kẻ lừa đảo hay viết dài để dụ dỗ.
2. 🔗 **Có mấy đường link?** Kẻ lừa đảo hay bảo "bấm vào đây".
3. 🔢 **Có nhiều con số không?** Số tiền, số tài khoản, số điện thoại.
4. ❗ **Có nhiều dấu "!!!", "$", "%" không?** Kẻ lừa đảo hay la hét cho người đọc sợ.
5. ⏰ **Có mấy từ hối thúc?** Ví dụ "khẩn", "ngay", "khóa", "xác thực".

Ghép **đọc chữ** với **5 con số đếm được** này, chú chó có thêm manh mối để đoán. Đó là toàn bộ ý tưởng.

**Sao nó lại là việc "tùy chọn"?**
- Chú chó vốn đã đọc chữ rất giỏi. Các từ hối thúc ở mục 5 thì SVM đã thấy rồi, nên manh mối mới có thể không giúp thêm bao nhiêu.
- Chú chó có thể học thói xấu "cứ thấy link là sủa". Nhưng thư thật từ ngân hàng cũng có link.

→ Phải **thử cả hai cách**, có và không có 5 con số này, rồi xem cách nào đoán đúng hơn.
