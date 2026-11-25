# HANDOFF – Xử lý dữ liệu tiếng Việt (cập nhật 2026-11-24)

> File này dành cho agent/người tiếp tục công việc. Đọc hết trước khi sửa dữ liệu.
> Nhánh git: `bilingual-meta-features`. **Chưa commit** các thay đổi trong phiên này.

---

## 0. Bối cảnh ngắn

Đồ án phân loại SMS song ngữ Việt–Anh, 3 lớp `legitimate / spam / scam`, 3 giai đoạn
(Tầng 1 phân loại → Tầng 2 `scam_type` → demo Gradio). Phiên này tập trung **làm sạch
nhãn dữ liệu tiếng Việt**, vì phát hiện tiếng Việt thiếu scam thật và nhãn sai nhiều.

**Nguyên tắc làm việc người dùng yêu cầu:** câu nào hợp lý theo quy tắc thì tự gán,
**không chắc thì hỏi lại người dùng**, không đoán.

---

## 1. Quy tắc gán nhãn đã chốt (annotation guideline) – CẬP NHẬT 24/11 tối

**Chuẩn gốc: [`definition_of_ham_spam_scam.md`](../definition_of_ham_spam_scam.md)** (ITU-T X.1240, Almeida 2011,
Delany 2012/GSMA, Goel & Jain 2018, Rahman 2022, NĐ 91/2020). Áp cây quyết định theo thứ tự
**Bước 1 SCAM → Bước 2 SPAM → Bước 3 HAM**. Bộ quy tắc cũ (2 câu hỏi "nói dối / mất tiền") **đã bỏ**.

Quy tắc bổ sung người dùng đã chốt (những chỗ định nghĩa chưa phủ hoặc tự mâu thuẫn):
| # | Trường hợp | Nhãn |
|---|---|---|
| X1 | Tuyển CTV / việc nhẹ lương cao tại nhà | **scam** `job_task_scam` (3.2) |
| X2 | Dụ nhắn/gọi đầu số GTGT (8x/6x/7x/9xxx, 1900) kiểu lô đề, tử vi, "nghe lời nhắn" – không có link, không báo trúng giải | **spam** (2.2) |
| X3 | `[QC]`/brandname + cú pháp từ chối | **ham** (1.3) – trừ khi rơi vào Câu B (dụ đăng ký bằng lời mời gọi) |
| X4 | Link **tên miền lạ** (`.xyz .top .vip .cc .online .tech`, `x.de`…) | **scam** (bước 1.1), kể cả quảng cáo cờ bạc/BĐS/spa kèm link lạ |
| Câu A | Link **rút gọn** (bit.ly, tinyurl, goo.gl, qrco.de) | chỉ là tín hiệu: **scam** khi kèm mạo danh/khẩn cấp/trúng thưởng/đăng nhập; thương hiệu thật → không đổi nhãn |
| Câu B | Đăng ký qua **tổng đài nhà mạng 3 số / \*USSD#** (191, 900, 888, 109, 123…) | **ham** |
| Câu B | Dụ **soạn tin đăng ký** bằng lời mời gọi ("miễn phí", "may mắn", "chúc mừng", "cơ hội trúng"…) hoặc tới đầu số 4 chữ số | **spam** (2.2), kể cả có `[QC]` |
| Câu B | Số bị che `[NUMBER]`, lời lẽ trung tính | **ham** |
| Q2 | Khuyến mãi/thông báo chính chủ nhà mạng gắn `[TB]` (không `[QC]`), kể cả "Tin giáo dục" Viettel Study | **ham** |
| Q3 | Tin bị làm rối ký tự kèm link | **scam** `other_scam` |
| Q6 | Mạo danh công an xin thông tin | **scam** `government_services` |
| Q7 | Quay thưởng của CTKM nhà mạng có thật | không phải scam (3.3 chỉ áp cho chương trình **không có thật**) |
| Nợ | Bịa đặt người nhận **đang nợ / đang gặp nguy hiểm** (đòi nợ khủng bố, đe dọa pháp lý) | **scam** `banking_finance` (mạo danh cơ quan → `government_services`) |
| – | Tin xác nhận ("đã đăng ký/đã hủy thành công", "đã nhận mã dự thưởng") | **ham** (1.2) |

- **drop:** không phải tiếng Việt (H'Mông, tiếng Anh), mảnh câu, chỉ có số điện thoại/email.
- `scam_type` map: cờ bạc/nhận thưởng → `prize_lottery`; hẹn hò/tình dục, tin làm rối, quảng cáo link lạ → `other_scam`;
  vay/đòi nợ → `banking_finance`; khóa học làm giàu/forex/dropship → `investment`; mạo danh cơ quan → `government_services`.
- Tiếng Anh (`Dataset_5971`) **chưa** rà theo định nghĩa này (Q8 – để sau, ghi vào giới hạn).

---

## 2. Đã xử lý xong

### 2.1 Loại nguồn `social_spam_post` (quyết định của người dùng)
- Là **bản dịch máy UCI SMS Spam Collection** (5.569 dòng ≈ 5.574 UCI; 4.823 ham ≈ 4.827; 746 spam ≈ 747). Không phải tiếng Việt thật.
- UCI cũng nằm trong `sms_phishing` tiếng Anh (train) → **rò rỉ chéo ngôn ngữ**: 61/115 tin dịch có dãy số trùng với EN train.
- Đã xóa khỏi `configs/vietnamese_3class.yaml`, `vietnamese_balanced.yaml`, `vietnamese.yaml` (đã kiểm tra load OK). File raw vẫn giữ ở `data/raw/`.

### 2.2 A1 – Rà nhãn phía **spam** của external test (`vie_sms_corpus`)
- Script: `scripts/flag_vi_external_scam.py` (chấm điểm, gom theo `group_id`).
  **CẢNH BÁO:** chạy lại script này sẽ **ghi đè** `data/review/vi_external_spam_review.csv`.
- File kết quả chính thức: **`data/review/vi_external_spam_review_v3.csv`** (650 nhóm, theo `definition.md`, không còn HỎI).
  Nhãn cuối ở cột `review_label`; áp cho mọi dòng trong `group_member_ids`.
  Kết quả v3: **legitimate 329 nhóm/500 dòng, spam 297/312, drop 24, scam 0**.
  (v2 cũ: scam 23 / legit 65 / spam 538. 23 scam → spam theo X2/X7; 264 spam → ham theo X3/Câu B/Q2.)
- ⚠️ **External test tiếng Việt hiện có 0 scam** → bắt buộc có dữ liệu crawl (mục 3.2).
- `vi_external_spam_review.csv` (bản sửa tay nhầm cột) và `_v2.csv` chỉ để lịch sử. Dùng **v3**.

### 2.3 Rà phía **legitimate (ham)** của external test
- 5.047 dòng ham (4.823 nhóm): lọc tự động + đọc 160 nhóm đáng ngờ + mẫu ngẫu nhiên 40/40 đúng → **gần như sạch**.
- Chỉ 3 dòng đổi thành `drop`: `data/review/vi_external_legit_overrides.csv`.
- Đã quét lại theo `definition.md` (24/11 tối): các tin trúng bộ lọc đều là thông báo dịch vụ/hotline → giữ ham.
  Riêng "Các cuộc gọi nhỡ… (QC) … soạn NC gửi…" (2 nhóm / 11 dòng) → **spam** (người dùng chốt), đã thêm vào `vi_external_legit_overrides.csv`.
- Người dùng chốt thêm: "Đã quá hạn thanh toán… bỏ qua nếu đã thanh toán" = ham; "Tin giáo dục" Viettel Study = ham; quảng cáo BĐS/spa/gia sư kèm link lạ = scam.
- **Không che PII** (quyết định người dùng): ham chứa số tài khoản, họ tên, cả 1 tin có mật khẩu Homebanking. Người dùng sẽ **không trích** các tin này trong báo cáo.

### 2.4 Crawl tin scam thật (công cụ)
- `scripts/crawl_vi_scam.py` + `notebooks/crawl_vi_scam_kaggle.ipynb` + `docs/huong_dan_crawl_vi_scam.md`.
- Nguồn: thanhnien, tuoitre, dantri, vietnamnet, znews (sitemap). Loại: tinnhiemmang (`ai-train=no`), chongluadao (JS), vnexpress (sitemap redirect), nld (sitemap rỗng).
- Có luồng OCR (EasyOCR) vì báo chủ yếu đăng **ảnh chụp** tin nhắn.
- Notebook được sinh từ script bằng **`scripts/make_crawl_notebook.py`** – chạy lại mỗi khi sửa script.

### 2.5 A2 – Rà nhãn scam/spam của tập Tuấn (train/val/test tiếng Việt)
- Nguồn vấn đề: tập Tuấn gốc chỉ có nhãn 0/1. 798 tin nhãn `1` được **máy** tách scam/spam bằng từ khóa (`scripts/reannotate_vietnamese.py`) → sai nhiều.
- File kết quả chính thức: **`data/review/vi_tuan_label1_review_v3.csv`** (711 tin = 798 dòng; cột `message_ids` để áp ngược). Không còn HỎI.
  Kết quả v3: **scam 525 tin/601 dòng, spam 178/189, legitimate 8/8** (legitimate = sửa nhãn gốc 1→0).
- Lịch sử: `vi_tuan_label1_review.csv` (bản gốc A2, có sửa tay của người dùng) → `_v2.csv` (63 HỎI đã chốt theo định nghĩa ngắn)
  → `_v3.csv` (áp `definition.md` + quy tắc mục 1; ghi chú `v3 (definition.md): …` trong `review_note`).

### 2.6 Q1 – Rà phía **ham (nhãn 0)** của tập Tuấn (mới, 24/11 tối)
- 2.193 dòng / 1.919 text. File: **`data/review/vi_tuan_label0_review.csv`** – chỉ chứa các tin **đổi nhãn** (132 tin / 135 dòng).
- **10 → scam**: cờ bạc + link lạ (5), mạo danh ngân hàng tên miền nhái `vletcombank.com`/`techcombank.shop` (2), bịa nợ (3).
- **122 → spam**: bẫy cước "MIỄN PHÍ 100% 3G/4G… soạn X gửi [NUMBER] ([MONEY])… sau KM [MONEY]/ngày" (Câu B).
- Giữ ham có chủ đích: OTP, quyên góp MTTQ, cảnh báo Bộ Công an, vay `[QC]`+TC của Viettel Money/FE Credit, `[TB]` nhà mạng qua 191/\*091#,
  tin xác nhận đăng ký, "Đã quá hạn thanh toán… bỏ qua nếu đã thanh toán" (nhắc cước bình thường).
- Script/regex dùng để rà nằm ở scratchpad (`sig.py`, `rules.py`, `apply_l1_v3.py`, `ext_v3.py`) – **không ở repo**.

---

### 2.7 Nhật ký phiên 24/11 (tối) – tóm tắt
1. Người dùng viết `definition_of_ham_spam_scam.md` (3 tầng, có trích dẫn) → chọn làm **chuẩn duy nhất**.
2. Rà xung đột X1–X7 giữa nhãn cũ / nhãn chốt sáng / định nghĩa → người dùng chốt toàn bộ theo định nghĩa + quy tắc bổ sung (mục 1).
3. Áp lại cho 3 nguồn: Tuấn nhãn 1 (v3), Tuấn nhãn 0 (Q1, file mới), external (v3) + override ham "cuộc gọi nhỡ (QC)" → spam.
4. Kết luận đánh giá: external VI còn **0 scam**; mục tiêu crawl **≥100, nên 150–200** scam sau khử trùng.
5. Chưa áp vào `data/raw` / pipeline; chưa commit.

### 2.8 Nhật ký 25/11/2026
1. **Chốt 4 điểm còn mở của gán nhãn:** "Đã quá hạn thanh toán… bỏ qua nếu đã thanh toán" = ham; "cuộc gọi nhỡ kèm (QC)… soạn NC gửi" = spam
   (thêm 2 nhóm/11 dòng vào `vi_external_legit_overrides.csv`); "Tin giáo dục" Viettel Study = ham; quảng cáo BĐS/spa/gia sư kèm link lạ = scam.
2. **Lộ trình hoàn thiện dataset** (mục 3.0) được thống nhất: cải thiện crawl trước, áp nhãn + sửa B1 song song, rồi chạy lại pipeline.
3. **Duyệt kết quả crawl lần 1** (người dùng duyệt 37 ứng viên): 119 bài → 22 dùng được; 212/265 ảnh là ảnh minh họa; nút thắt là số bài tìm được.
4. **Quyết định công cụ:** EasyOCR làm bản nháp + người sửa 100%; không dùng CLIP/VLM (lo ngại yêu cầu đồ án "không dùng model
   build sẵn để infer"). Tin Zalo/Messenger giữ lại, ghi cột kênh.
5. **Tìm dataset tiếng Việt khác:** không có bộ SMS lừa đảo thật nào mới. Tran et al. (2.991) = tập Tuấn; Pham & Le-Hong (6.599) = `vie_sms_corpus`;
   VNPhish/Zenodo PhishVN = AI sinh; PhishVN (53k URL, CC BY 4.0) chỉ là URL – có thể dùng đối chiếu link. Đề xuất thêm: Google Form tự thu thập.
6. **Viết lại `scripts/crawl_vi_scam.py` (v2)** + `scripts/make_crawl_notebook.py` + sinh lại notebook + viết lại `docs/huong_dan_crawl_vi_scam.md`
   (chi tiết + số liệu kiểm thử ở mục 3.2). Chưa chạy bản đầy đủ – người dùng chạy trên Kaggle.

---

## 3. CẦN XỬ LÝ TIẾP (theo thứ tự ưu tiên)

### 3.0 LỘ TRÌNH HOÀN THIỆN DATASET (thứ tự đã thống nhất 24/11)
| Bước | Việc | Phụ thuộc | Mục chi tiết |
|---|---|---|---|
| 1 | **Cải thiện crawl** → thu nhiều scam thật hơn, đạt ≥100–200 tin | – | 3.2 |
| 2 | Duyệt dữ liệu crawl theo `definition.md` (người dùng + agent) | 1 | 3.2 |
| 3 | Script **áp nhãn** từ các file review vào `data/raw` + test | – (làm song song với 1) | 3.4 bước 1 |
| 4 | Sửa `balance_datasets.py` (B1) | – | 3.3 |
| 5 | Adapter crawl → `external_test`, che placeholder giống tập Tuấn, SimHash lọc trùng với train | 2 | 3.2 |
| 6 | Chạy lại pipeline (prepare → balance → merge → meta-features) + test toàn vẹn | 3, 4, 5 | 3.4 bước 2–4 |
| 7 | Rà `scam_type` cho Giai đoạn 2 (≈400 tin scam cũ gán bằng từ khóa; `other_scam` 109 tin) | 6 | 3.1 ghi chú |
| 8 | F2/MCC, train lại NB/SVM/CharCNN, Giai đoạn 2, demo | 6 (7 cho GĐ2) | 3.5 |

### 3.1 ~~Chờ trả lời A2~~ – ĐÃ XONG (63 HỎI chốt ở v2, áp lại theo `definition.md` ở v3)

Ghi chú: `review_scam_type` của các tin **vốn đã scam** đang lấy từ phân loại tự động, có chỗ sai (vd "con cấp cứu" đang `banking_finance`). Rà lại khi làm **Giai đoạn 2**.
Hệ quả X4 cần ghi vào báo cáo: gần như mọi spam có link lạ thành scam → model có thể học lối tắt "link lạ = scam"; kiểm tra bằng phân tích lỗi.

### 3.2 External test – crawl (người dùng đang tự xử lý, CHƯA làm)
- Người dùng đã chạy crawl và kiểm tra: **chỉ ~20% ứng viên dùng được**. Người dùng sẽ tự quyết cách xử lý; **không đụng vào file crawl** khi chưa được yêu cầu.
- Sau v3, external test tiếng Việt có **0 scam** → crawl là nguồn scam duy nhất. Phương án: tăng `--months`, thêm `--urls-file` thủ công, hoặc tự thu thập.
- Mục tiêu đã bàn: **tối thiểu 100, nên 150–200 tin scam sau khử trùng** (đếm theo kịch bản, ≥5–6 `scam_type`, mỗi loại ~15–20).
  <100 tin → gọi là "đánh giá sơ bộ", báo kèm khoảng tin cậy Wilson.
- **Kết quả lần crawl đầu (người dùng đã duyệt `crawl_data_scam/vi_scam_crawl/vi_scam_candidates.csv`, note `no` = loại):**
  119 bài → 265 ảnh → **37 ứng viên → 22 dùng được** (≈0,18 tin/bài). Text: 18 ứng viên, 11 bị loại (trích lời phỏng vấn,
  lời khuyên, câu dẫn của nhà báo). OCR: 19 ứng viên/265 ảnh, 4 bị loại; **212/265 ảnh là ảnh ngang (phần lớn ảnh minh họa báo)**.
  Trong 22 tin "dùng được" còn lẫn: #36 bão số 5 (ham), #23 [QC] VIB (OCR trộn 2 cột), #24 "Chợ Ninh Hiệp kính chào", #25/#27/#31
  (câu mô tả/danh sách link, không phải tin nhắn), #2/#16 chat Zalo/Facebook/WhatsApp (không phải SMS).
- Mục tiêu lần 2 (người dùng): **200 ứng viên → ≥100 tin dùng được**, chạy trên **Kaggle T4 ×2**.
- **Quyết định 25/11:** dùng **EasyOCR làm bản nháp + người sửa 100%**; **không** dùng CLIP/VLM (yêu cầu đồ án
  cấm dùng model build sẵn để infer – người dùng sẽ trình bày với giảng viên). Lọc ảnh bằng quy tắc viết tay.
  Tin qua Zalo/Messenger vẫn giữ, ghi cột kênh; external test chỉ dùng `sms`.
  22 tin lần 1: #36 → ham; #23, #24, #25, #27, #31 → loại.
  **Rà lại 25/11 (chép tay từ ảnh, so trùng với toàn bộ tập Tuấn):** đã lưu `data/review/vi_crawl_run1_clean.csv` (11 dòng, cột
  `use_for_external`, `overlap_tuan_sim`, `message_raw`). Chỉ **4 tin SMS độc lập** dùng được (`yes`), 2 `maybe` (cùng khuôn
  với Tuấn / kênh không chắc SMS), 5 `no` (CSGT, Netflix, vòng quay đã có trong Tuấn; 2 tin Zalo).
  ⚠️ Tin báo chí hay đăng **đã nằm sẵn trong tập Tuấn** → khi duyệt crawl v2 phải lọc trùng với **toàn bộ** tập Tuấn.
- **ĐÃ SỬA script → v2 (25/11)** – chi tiết trong `docs/huong_dan_crawl_vi_scam.md`:
  13 nguồn (thêm cand, vietnamplus, tienphong, sggp, vtv, genk, kenh14, vov), 36 tháng, slug tier 2/1, tải song song
  (khóa + delay theo từng host), lọc bài theo số lần nhắc "tin nhắn/SMS…", câu trích phải có câu dẫn,
  lọc ảnh bằng chú thích/tên file/đoạn trước ảnh, sửa link `.jpg.avif` → `.jpg` (ảnh AVIF làm OCR lỗi),
  OCR tách bong bóng + bỏ thanh trạng thái + bỏ infographic, che placeholder giống tập Tuấn, nhãn gợi ý theo
  `definition.md`, cột `channel`/`reject_reason`, `crawl_stats.json`, `review.html` (duyệt + xuất CSV), `--debug`.
  `scripts/make_crawl_notebook.py` (đã đưa vào repo) sinh lại notebook Kaggle.
- **Kiểm thử local 25/11:** 119 bài cũ (không OCR): ứng viên văn bản 18 (11 rác) → 13 (1 rác).
  19 ảnh cũ: 4/5 ảnh bị người dùng loại nay không ra gì; đa số ảnh OK ra đúng 1 bong bóng sạch.
  40 bài tier 2 mới (2 tháng, có OCR): 10 ứng viên (8 OCR + 2 text), ~0,25 ứng viên/bài.
  Ước lượng 36 tháng tier 2 ≈ 2.000+ bài → đủ cho `--target 400`.
- **Điểm yếu đã thấy trong `scripts/crawl_vi_scam.py` (đọc code 24/11, chưa sửa):**
  1. Lọc URL quá chặt: slug phải có **cả** từ kênh (`tin-nhan`, `sms`, `link`…) **và** từ lừa đảo → bỏ sót bài có slug kiểu `canh-bao-thu-doan-gia-danh-cong-an`.
  2. Chỉ 5 báo; chưa có nguồn chuyên cảnh báo (báo Công an, trang cảnh báo của ngân hàng/nhà mạng, Cục ATTT…) – mỗi nguồn phải kiểm robots/`ai-train` trước.
  3. Mặc định `--max-articles 300`; delay 1,5 s **toàn cục** (không chạy song song giữa các domain) → chậm.
  4. OCR: tối đa 6 ảnh/bài, EasyOCR không tiền xử lý ảnh (phóng to, cắt bong bóng chat) → nhiều rác.
  5. `suggest_labels` dùng **quy tắc cũ** (chưa theo `definition.md`).
  6. Che PII ra `[PHONE]/[MONEY]/[BANK_ACC]` – **khác** placeholder tập Tuấn (`[NUMBER]/[MONEY]/[NAME]/[TIME]/[DATE]`) → model có thể học placeholder.
  7. Chưa ghi **lý do loại** khi người dùng duyệt → không biết 80% bị loại vì đâu (văn báo chí? OCR rác? trùng? không phải SMS?).
  8. `make_nb.py` (sinh notebook Kaggle) chỉ nằm ở scratchpad → dễ mất; nên đưa vào repo.
- Khi có file đã kiểm tra: viết adapter, khai báo `external_test`, **SimHash lọc trùng với toàn bộ train** (kể cả augment);
  **che `[MONEY]/[NUMBER]/[NAME]`** giống tập Tuấn; báo cáo **tách** recall scam (crawl) và FPR trên ham/spam `vie_sms_corpus` (lệch thời đại 2015 vs 2024+, có dấu vs không dấu).

### 3.3 B1 – Sửa `scripts/balance_datasets.py` (chưa làm)
Lỗi đã xác minh:
1. Từ đồng nghĩa tiếng Việt chỉ viết không dấu, 61% tin scam có dấu → **182/319 dòng augment là bản sao y hệt**. VI scam train: 500 dòng nhưng chỉ 310 text khác nhau, 164 group.
2. Chỉ sửa `text_clean`, **không sửa `text_raw`** → meta-features (tính từ `text_raw`) của dòng augment sai.
3. EN augment **không gán `sample_id` mới** → **920 `sample_id` trùng**.
4. **Bỏ phí dữ liệu thật**: VI legit 1.231→500, EN legit 3.007→2.000, EN scam 10.315→2.000, trong khi config đã bật `class_weight: balanced`.
Cách sửa đã thống nhất: giữ toàn bộ dữ liệu thật + class_weight (+ sample weight theo ngôn ngữ), EN scam cap ~4.000 phân tầng theo `scam_type`; augment VI có: bỏ dấu, đồng nghĩa có/không dấu, đổi thực thể, teencode; loại bản trùng; tối đa 2 bản/tin gốc; cập nhật `text_raw`, `sample_id` mới, cột `is_augmented`, `aug_parent_id`, giữ `group_id` gốc; cờ config `use_augmentation`, `use_vnphish`.

### 3.4 Áp nhãn mới vào pipeline (chưa làm – làm 1 lần sau A2 + crawl)
1. Viết bước áp nhãn: `vi_tuan_label1_review_v3.csv` + `vi_tuan_label0_review.csv` → cập nhật `data/raw/*_spamscam_reannotated.csv`
   (theo `message_ids`; `legitimate` ↔ `label` 0, `spam/scam` ↔ 1; cập nhật cả `label_3class`, `category`/`scam_type`);
   `vi_external_spam_review_v3.csv` + `vi_external_legit_overrides.csv` → override nhãn `vie_sms_corpus` (theo `sample_id` trong `group_member_ids`); bỏ dòng `drop`.
2. Xóa `data/processed_bilingual/master_dataset_base.csv` (đang **read-only**, script bỏ qua nếu tồn tại).
3. Chạy: prepare `configs/vietnamese_3class.yaml` → `balance_datasets.py` → `merge_bilingual.py` → `build_meta_features_dataset.py`.
4. Test: không trùng text trong train, `sample_id` duy nhất, augment chỉ trong train, 0 rò rỉ group.

### 3.5 Sau đó (Action Items gốc)
- Thêm **F2 (beta=2, lớp scam)** và **MCC** vào `src/scam_baseline/evaluation.py` + `reporting.py`; chọn best model theo F2 scam.
- Train lại NB / SVM / CharCNN (CharCNN chưa có `model.pt` nào). So sánh: chỉ thật / + augment / + VNPhish.
- Tích hợp meta-features vào Pipeline SVM (scaler lưu cùng model).
- Giai đoạn 2 (`scam_type`, có thể dùng VNPhish đã lọc judge – dữ liệu LLM, CC BY-NC) và `predict_pipeline` + Gradio: **chưa có code**.

---

## 4. Ghi chú quan trọng / đính chính
- Đính chính trước đây: model SVM bilingual **không** cũ (train 7.500 = khớp). Số scam VI thật trước A2 là **272** (181/31/60), không phải 591.
- `vie_sms_corpus` là SMS 2015 (Pham & Le-Hong); scam kiểu cũ (1900, lô đề). Tập Tuấn có nhiều **biến thể sinh theo mẫu** (đổi tên ngân hàng/tên người) → ghi vào giới hạn báo cáo.
- Dataset HF `trannguyenthaituan/vietnamese_sms_dataset` = **chính tập Tuấn đã có** (chỉ khác CRLF/LF) → không bổ sung gì.
- Tool phụ đã cài tạm ở scratchpad (`pylib`, `pylib_ocr`), máy chưa có `yaml`, `bs4` trong Python hệ thống; `.venv` của repo hỏng (thiếu interpreter gốc).
- File `data/review/vi_external_spam_review.csv` từng bị khóa khi mở trong Excel → ghi ra file mới thay vì ghi đè.

## 5. Danh sách file tạo/sửa trong phiên (chưa commit)
- Mới: `scripts/crawl_vi_scam.py`, `scripts/flag_vi_external_scam.py`, `notebooks/crawl_vi_scam_kaggle.ipynb`, `docs/huong_dan_crawl_vi_scam.md`, `docs/HANDOFF_xu_ly_du_lieu_tieng_viet.md`, `data/review/*`, `definition_of_ham_spam_scam.md` (người dùng viết).
- Sửa: `configs/vietnamese_3class.yaml`, `configs/vietnamese_balanced.yaml`, `configs/vietnamese.yaml` (bỏ `social_spam_post`).
