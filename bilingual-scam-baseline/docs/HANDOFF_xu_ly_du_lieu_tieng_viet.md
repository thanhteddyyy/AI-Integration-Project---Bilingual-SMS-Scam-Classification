# HANDOFF – Xử lý dữ liệu tiếng Việt (cập nhật 2026-11-25 tối)

> File này dành cho agent/người tiếp tục công việc. Đọc hết trước khi sửa dữ liệu.
> Nhánh git: `bilingual-meta-features`. Đã commit tới phần crawl v2; **các thay đổi từ "áp nhãn v3" trở đi CHƯA commit**.
> **Đọc mục 2.9 (nhật ký 25/11) trước** – tóm tắt toàn bộ việc đã làm và trạng thái hiện tại.
> Chạy pipeline: `C:\Users\USER\AppData\Local\Programs\Python\Python311\python.exe` + `PYTHONPATH=src` (`.venv` của repo hỏng).

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
| X4+ | (25/11) **Cờ bạc** + tên miền cờ bạc/số ngẫu nhiên/nhái, **kể cả `.com/.net`** (`8qbet16.com`, `m.[NUMBER].com`, `Bidvux.com`) | **scam** `prize_lottery` |
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

### 2.9 Nhật ký 25/11/2026 (chiều–tối) – TÓM TẮT TOÀN BỘ VIỆC ĐÃ SỬA
**Điều tra (không sửa dữ liệu):**
- Rà lại các dataset tiếng Việt công khai: không có bộ SMS lừa đảo thật nào mới (chỉ trùng Tuấn / Pham & Le-Hong, VNPhish = LLM sinh,
  VNSED = email đã tiền xử lý, không công khai). → external scam thật chỉ có thể từ crawl / tự thu thập.
- Phân tích tập Tuấn: 2.991 dòng nhưng chỉ ~1.835 họ mẫu; test = đợt thu cuối (lệch phân phối); **80% scam test có họ mẫu trong train**.
- Crawl lần 1: chỉ **4 tin SMS độc lập** dùng được → `data/review/vi_crawl_run1_clean.csv` (chép tay từ ảnh). Tin báo hay đăng đã nằm sẵn trong Tuấn.
**Sửa dữ liệu & code (chi tiết ở 3.4a–3.4e):**
1. Áp nhãn v3 (`scripts/apply_vi_labels_v3.py`) → `data/raw/*_v3.csv`; Tuấn v3 = 2.065 ham / 285 spam / 641 scam.
   Quy tắc mới X4+ (cờ bạc + tên miền cờ bạc/ngẫu nhiên kể cả .com = scam), tin "thám tử" = `other_scam`; 12 tin "spam" là OTP/"Ok" → ham.
2. **Cách B:** giữ test của Tuấn, bỏ 199 dòng train cùng họ mẫu với test.
3. `vie_sms_corpus` chia đôi theo họ mẫu: **dev** (vào train/val) / **holdout** (external khóa). Chọn cấu hình **e2** (thêm dev) vì
   không có tin cá nhân thì model báo nhầm 24% tin thật là scam ("có dấu = scam"); có dev → 0,1%.
4. Pipeline chia theo **họ mẫu** (`family_id`, `deduplication.family_jaccard: 0.5`) cho cả VI và EN.
5. EN: thống nhất placeholder giữa IMC25 / sms_phishing / SmishX; script đề xuất sửa nhãn EN (chưa áp, chờ duyệt).
6. `balance_datasets.py` v2: giữ toàn bộ dữ liệu thật, EN scam cap 4.000, augment VI có kiểm soát; NB `fit_prior: false`.
7. Đánh giá: thêm F2 scam, MCC, FPR, Wilson CI, kết quả theo nguồn; chọn best model theo val F2 scam.
8. Adapter crawl `scripts/build_vi_crawl_external.py` (lọc trùng với toàn bộ Tuấn) + dataset `vi_crawl` trong config.
9. Chạy lại toàn bộ pipeline + train NB/SVM 4 cấu hình (kết quả 3.4e). Kết quả cũ sao lưu ở `reports|artifacts/_before_v3_2026-11-25/`.
10. Test: 26 test pass (`tests/test_balance.py`, `test_evaluation.py` mới; thêm test adapter/split).
**Việc của người dùng:** chạy crawl v2 (Kaggle) → lưu file duyệt thành `data/review/vi_crawl_run2_reviewed.csv`; duyệt
`data/review/en_label_review_candidates.csv`; chốt `scam_type` khó (GĐ2); hỏi giảng viên về EasyOCR / dữ liệu LLM.
**Khi có crawl:** `build_vi_crawl_external.py` → prepare `vietnamese_3class` → balance → merge → meta → chấm lại model (không cần train lại).

---

## 3. CẦN XỬ LÝ TIẾP (theo thứ tự ưu tiên)

### 3.0 LỘ TRÌNH HOÀN THIỆN DATASET (thứ tự đã thống nhất 24/11)
| Bước | Việc | Phụ thuộc | Mục chi tiết |
|---|---|---|---|
| 1 | **Cải thiện crawl** → thu nhiều scam thật hơn, đạt ≥100–200 tin | – | 3.2 – script v2 xong, **người dùng đang chạy Kaggle** |
| 2 | Duyệt dữ liệu crawl theo `definition.md` (người dùng + agent) | 1 | 3.2 – ⏳ chờ kết quả |
| 3 | Script **áp nhãn** từ các file review vào `data/raw` + test | – | ✅ 3.4a |
| 4 | Sửa `balance_datasets.py` (B1) | – | ✅ 3.4b |
| 5 | Adapter crawl → `external_test` | 2 | ✅ script sẵn (3.4b), chạy lại khi có crawl |
| 6 | Chạy lại pipeline (prepare → balance → merge → meta-features) + test toàn vẹn | 3, 4, 5 | ✅ 25/11 (chạy lại khi có crawl) |
| 7 | Rà `scam_type` cho Giai đoạn 2 (≈640 tin scam VI) | 6 | ✅ 3.4g |
| 8 | F2/MCC ✅, train NB/SVM ✅, **CharCNN ⬜ (Kaggle)**, Giai đoạn 2 ⬜, demo ⬜ | 6 (7 cho GĐ2) | 3.5 |
| 9 | (mới) Rà nhãn EN theo định nghĩa rồi áp | – | ✅ 3.4f |

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

### 3.3 B1 – Sửa `scripts/balance_datasets.py` (ĐÃ LÀM 25/11, xem 3.4b – phần dưới chỉ là mô tả lỗi cũ)
Lỗi đã xác minh:
1. Từ đồng nghĩa tiếng Việt chỉ viết không dấu, 61% tin scam có dấu → **182/319 dòng augment là bản sao y hệt**. VI scam train: 500 dòng nhưng chỉ 310 text khác nhau, 164 group.
2. Chỉ sửa `text_clean`, **không sửa `text_raw`** → meta-features (tính từ `text_raw`) của dòng augment sai.
3. EN augment **không gán `sample_id` mới** → **920 `sample_id` trùng**.
4. **Bỏ phí dữ liệu thật**: VI legit 1.231→500, EN legit 3.007→2.000, EN scam 10.315→2.000, trong khi config đã bật `class_weight: balanced`.
Cách sửa đã thống nhất: giữ toàn bộ dữ liệu thật + class_weight (+ sample weight theo ngôn ngữ), EN scam cap ~4.000 phân tầng theo `scam_type`; augment VI có: bỏ dấu, đồng nghĩa có/không dấu, đổi thực thể, teencode; loại bản trùng; tối đa 2 bản/tin gốc; cập nhật `text_raw`, `sample_id` mới, cột `is_augmented`, `aug_parent_id`, giữ `group_id` gốc; cờ config `use_augmentation`, `use_vnphish`.

### 3.4a ĐÃ LÀM 25/11 – Áp nhãn v3 + cách B (lọc họ mẫu)
- Script `scripts/apply_vi_labels_v3.py` (chạy lại được, `--check` để xem trước) → `data/raw/train_dataset_spamscam_v3.csv`,
  `test_dataset_spamscam_v3.csv`, `vie_sms_corpus_v3.csv`; log `data/review/vi_tuan_train_removed_family_overlap.csv`,
  số liệu `data/review/vi_labels_v3_summary.json`. File gốc và `*_reannotated.csv` (nhãn cũ) giữ nguyên.
- **Cách B:** giữ nguyên test của Tuấn (597: 329 ham/145 spam/123 scam); bỏ khỏi train 199 dòng cùng họ mẫu với test
  (128 scam/53 ham/18 spam; họ mẫu = Jaccard 3-gram từ ≥ 0,5 sau khi bỏ dấu/số/URL/placeholder). Train còn 2.195 (1.683 ham/122 spam/390 scam).
- **Quy tắc bổ sung chốt 25/11 (X4 mở rộng):** quảng cáo **cờ bạc + link tên miền cờ bạc/số ngẫu nhiên/nhái** (kể cả `.com/.net`,
  vd `8qbet16.com`, `m.[NUMBER].com`, `Bidvux.com`) = link lạ → **scam** `prize_lottery`. Đã áp cho 30 tin Tuấn
  (COM_072, COM_067, COM_1212, COM_1228 + 26 tin quét thêm). Tập Tuấn v3: 2.065 ham / 285 spam / 641 scam.
- Còn 2 dòng `label_conflict` (cặp `[Amazon_Drop]`: link `.top` = scam, link `.com` = spam) – đúng theo X4, pipeline tự loại.
- `vie_sms_corpus`: nhãn review lan sang các dòng trùng mẫu mà pipeline cũ đã loại (322 dòng); 12 dòng "spam" rõ là ham
  (OTP, "Ok"…) → `data/review/vi_external_spam_conflict_overrides.csv`. Kết quả 6.123 legit / 381 spam / 66 drop.
- `adapters.load_custom_dataset` thêm `scam_type_column` (test mới trong `tests/test_adapters.py`); 3 config VI trỏ sang file v3.
- `prepare` `vietnamese_3class.yaml` chạy OK bằng `Python311` (`PYTHONPATH=src`), leakage check passed, 11/11 test OK.
  Sau dedup (ham/spam/scam): train 1.192/102/318, val 210/18/55, test 323/138/104, external 5.532 legit/323 spam/0 scam.
- ⚠️ `vie_sms_corpus` giờ đọc từ CSV v3 → `sample_id` mới khác `sample_id` trong các file review cũ (review cũ vẫn áp đúng vì script tính theo file .txt gốc).
- Chưa làm: B1 `balance_datasets.py` (đừng chạy balance/merge trước khi sửa), chạy lại bilingual.

### 3.4b ĐÃ LÀM 25/11 (tối) – A2, A1 (B1), A3, B1-crawl, A4
- **A2 – chỉ số:** `evaluation.py` thêm `scam_f2` (beta=2), `mcc`, `scam_f1`, `scam_fpr` (tỉ lệ báo nhầm), Wilson CI 95%
  (`scam_recall_ci95`, `scam_fpr_ci95`), `by_source`. `reporting.py` chọn best model theo **`scam_f2`** (tie-breaker `macro_f1`,
  đổi được bằng `evaluation.selection_metric`), ghi thêm `model_comparison_by_source.csv`. CharCNN vẫn early-stop theo macro_f1.
- **A1 – `scripts/balance_datasets.py` viết lại (v2):** giữ toàn bộ dữ liệu thật; EN scam cap 4.000 phân tầng `scam_type`, EN không augment;
  VI augment chỉ scam/spam trong train (bỏ dấu, đồng nghĩa có/không dấu, đổi thực thể, teencode; ≤2 bản/tin; loại bản trùng với MỌI split
  theo template key; `text_raw`+`text_clean` cùng đổi; `sample_id` mới; cột `is_augmented/aug_parent_id/aug_ops`; giữ `group_id` cha).
  Bỏ mẹo thêm tiền tố `[QC]` cũ (đổi nhãn theo X3). `--no-vi-augment` để chạy ablation. Test: `tests/test_balance.py`.
  NB thêm `fit_prior` (đặt `false` ở 3 config VI/bilingual) thay cho việc cắt mẫu.
- **A3 – đã chạy lại:** prepare VI → balance → merge → meta (đã xóa và tạo lại `master_dataset_base.csv`). Train song ngữ:
  EN 3.007/1.080/4.000, VI 1.192/182/817 (318 scam thật + 499 augment; 102 spam thật + 80 augment).
- **B1-crawl – `scripts/build_vi_crawl_external.py`:** đọc `data/review/vi_crawl_run*_clean.csv` / `*_reviewed.csv`, chỉ kênh SMS,
  che PII bằng `mask_pii` của crawler, khử trùng nội bộ, **loại tin cùng họ mẫu với toàn bộ Tuấn** → `data/raw/vi_crawl_external.csv`
  (dataset `vi_crawl`, đã khai báo external trong `vietnamese_3class.yaml`); log `data/review/vi_crawl_external_excluded.csv`.
  Hiện 4 tin (run 1). **Kết quả crawl v2: lưu file duyệt thành `data/review/vi_crawl_run2_reviewed.csv` rồi chạy lại script + pipeline.**
- **A4 – NB/SVM** (kết quả cũ sao lưu ở `reports|artifacts/_before_v3_2026-11-25/`). Test VI (cách B, không rò rỉ), lớp scam:
  | Cấu hình | Model | Precision | Recall | F2 | MCC | FPR test |
  |---|---|---|---|---|---|---|
  | VI chỉ thật (`vietnamese_3class`) | SVM | 0,81 | 0,74 | 0,75 | 0,57 | 0,04 |
  | VI + augment (`vietnamese_balanced`) | SVM | 0,69 | 0,76 | 0,75 | 0,49 | 0,08 |
  | VI + augment | NB | 0,72 | 0,87 | 0,83 | 0,49 | 0,08 |
  | Song ngữ (`bilingual`), phần VI | SVM | 0,78 | 0,71 | 0,72 | 0,46 | 0,05 |
  Validation (cùng phân phối train) cao hơn nhiều (F2 ≈ 0,90) → khoảng cách val/test là do lệch đợt thu (mục 2 phân tích Tuấn).
- ⚠️ **PHÁT HIỆN LỚN – lối tắt "có dấu = scam":** trên `vie_sms_corpus` (ham/spam thật, không có scam), SVM chỉ-VI **báo nhầm
  scam 24,7%** (NB 54,6%; augment 51,6%); song ngữ 9,9%. 79% tin bị báo nhầm là **tin cá nhân có dấu** ("A đang ở nhà ko?",
  "Bố tự ăn nhé"). Nguyên nhân: ham của Tuấn gần như chỉ là tin nhà mạng/OTP không dấu, scam 71% có dấu, train không có tin cá nhân.
  Hướng xử lý (chưa làm, cần người dùng chọn): (a) TF-IDF `strip_accents` (bỏ dấu khi trích đặc trưng); (b) đưa một phần ham cá nhân
  của `vie_sms_corpus` vào train (chia theo group, phần còn lại vẫn là external); (c) augment bỏ dấu cho ham.

### 3.4c ĐÃ LÀM 25/11 – Chia đôi vie_sms_corpus + thí nghiệm sửa lối tắt "có dấu = scam"
- `apply_vi_labels_v3.py` chia `vie_sms_corpus` 50/50 theo **họ mẫu**, phân tầng nhãn, tất định: `vie_sms_corpus_dev_v3.csv`
  (3.058 ham/191 spam – được phép vào train/val) và `vie_sms_corpus_holdout_v3.csv` (3.065/190 – **external khóa, không tinh chỉnh trên nó**).
  `vietnamese_3class.yaml`: external = `[vie_sms_holdout, vi_crawl]`.
- `classical.py`: `models.*.strip_accents` (`vietnamese` = bỏ dấu kể cả đ). `config.py`: tìm project root đúng cho config trong thư mục con.
- 4 config `configs/experiments/vi_e{0..3}_*.yaml` (chỉ dữ liệu thật VI, không augment). Kết quả SVM (NB kém hơn ở mọi cấu hình):
  | Thí nghiệm | val F2 (Tuấn, 55 scam) | test P / R / F2 / MCC | FPR holdout (2.872 tin) |
  |---|---|---|---|
  | e0 gốc | 0,901 | 0,83 / 0,73 / 0,75 / 0,57 | **24,3%** |
  | e1 bỏ dấu | 0,916 | 0,82 / 0,72 / 0,74 / 0,56 | 20,4% |
  | e2 + vie_sms_dev | 0,911 | 0,85 / 0,70 / 0,73 / 0,58 | **0,1%** (2 tin) |
  | e3 + vie_sms_dev + bỏ dấu | 0,922 | 0,81 / 0,63 / 0,66 / 0,58 | 0,1% (3 tin) |
  → Nguyên nhân chính là **train thiếu tin cá nhân**, không phải bản thân dấu. Chênh lệch val giữa e1/e2/e3 < 1 tin scam (1/55 = 0,018) → coi như hoà.
  **ĐÃ CHỐT (người dùng 25/11): e2** – `vietnamese_3class.yaml` và `vietnamese.yaml` đã thêm `vie_sms_dev`. Quy tắc chọn ghi trong báo cáo:
  "val hoà (< 1 tin) → chọn cấu hình đơn giản hơn (giữ dấu)".

### 3.4d Kiểm tra dữ liệu tiếng Anh (25/11) – sửa 1, 2 ĐÃ LÀM; 3 chờ người dùng duyệt
1. **Lối tắt placeholder:** `imc25` có token kiểu `<PHONE_NUMBER>`, `<DATE_TIME>` ở ~80% tin; `sms_phishing`, `smishx` 0% →
   model học "có `<...>` = không phải ham". EN test 76% là imc25 → điểm test EN bị thổi phồng (SVM song ngữ: test scam recall 0,94 vs SmishX 0,71).
2. **Nguồn trùng nhãn:** toàn bộ ham EN từ `sms_phishing`; imc25 chỉ có scam/spam.
3. **Rò rỉ họ mẫu:** 501/2.237 scam test EN (22%), 452 scam val có họ mẫu trong train (pipeline chỉ gom ngưỡng 0,95).
4. **Nhãn chưa theo `definition.md` (Q8):** spam EN chứa "WINNER/prize/claim" (≈330 tin, chủ yếu imc25) – theo định nghĩa là scam 3.3;
   `sms_phishing` "scam" có quảng cáo ("half price Orange line rental").
Đề xuất: (i) thống nhất placeholder cho mọi nguồn EN; (ii) áp cách B cho EN test; (iii) rà nhãn EN theo định nghĩa (ít nhất bằng quy tắc).
- **(i) ĐÃ LÀM:** `adapters.normalize_en_placeholders` (bật bằng `data.normalize_en_placeholders: true` trong `english.yaml`):
  tag Presidio của IMC25 → bộ chung `<URL> <PHONE> <EMAIL> <DATE_TIME> <NUMBER>`; tag NER (`<NAMED_ENTITY>`, `<LOCATION>`…) bị bỏ;
  cùng regex che URL/email/giờ/ngày/số điện thoại/số dài cho MỌI nguồn EN (sửa cả `text_raw` → meta-features đúng). Test trong `tests/test_adapters.py`.
  Lưu ý: EN mất thông tin tên miền (VI vẫn giữ URL).
- **(ii) ĐÃ LÀM, tổng quát hơn cách B:** pipeline có `deduplication.family_jaccard: 0.5` → cột `family_id` (họ mẫu, `src/scam_baseline/data/family.py`);
  `split.py` chia train/val/test và loại chồng lấn test/external **theo họ mẫu** (mâu thuẫn nhãn vẫn tính theo `group_id`);
  `assert_no_group_leakage` kiểm cả `family_id`. Bật cho `english.yaml`, `vietnamese_3class.yaml`, `vietnamese.yaml`.
  EN: loại 961 dòng dev cùng họ mẫu với SmishX (684 `sms_phishing` – SmishX trùng nguồn UCI – và 277 `imc25`).
- **(iii) CHƯA ÁP:** `scripts/flag_en_label_review.py` → `data/review/en_label_review_candidates.csv` (603 tin / 560 nhóm):
  R1 spam→scam giải thưởng giả (215), R2 spam→scam đòi xác minh + link (7), R3 scam→spam quảng cáo (381 – quy tắc lỏng, cần duyệt kỹ).
  Người dùng điền `review_label`; cần viết bước áp (chưa có).

### 3.4e Kết quả sau khi sửa (25/11 tối) – NB/SVM, đã chạy lại toàn bộ pipeline
Lớp scam; VI test = test của Tuấn (565 dòng); "FPR holdout" = tỉ lệ tin thật bị báo scam trên `vie_sms_holdout` (2.872 tin).
| Cấu hình | Model | Test P / R / F2 / MCC | FPR holdout | External khác |
|---|---|---|---|---|
| VI thật + vie_dev (`vietnamese_3class`) | SVM | 0,84 / 0,65 / 0,68 / 0,47 | 0,1% | crawl 3/4 |
| VI + augment (`vietnamese_balanced`) | SVM ★ | 0,82 / 0,70 / 0,72 / 0,50 | 0,1% | crawl 4/4 |
| VI + augment | NB | 0,79 / 0,68 / 0,70 / 0,56 | 1,4% | crawl 3/4 |
| EN (`english_balanced`) | SVM ★ | 0,97 / 0,92 / 0,93 / 0,83 | – | SmishX R 0,70, FPR 11,6% |
| Song ngữ – phần VI | SVM ★ | 0,81 / 0,67 / 0,70 / 0,48 | 1,0% | crawl 3/4 |
| Song ngữ – phần EN | SVM | 0,97 / 0,92 / 0,93 / 0,82 | – | SmishX R 0,71 |
★ = best model theo val F2. Ghi chú:
- VI: augment giúp SVM (+0,04 F2) khi train đã có tin cá nhân. Validation VI có 712 dòng (gồm vie_dev).
- EN: test vẫn cao hơn SmishX nhiều (R 0,92 vs 0,70) dù đã sửa placeholder + họ mẫu → còn lệch nguồn: test EN 97% scam là IMC25
  (R 0,93), scam `sms_phishing` chỉ R 0,77. Báo cáo phải dùng SmishX làm con số "ngoài đời" cho EN.
- **NB song ngữ sụp ở phần VI** (recall 0,20): từ vựng EN áp đảo. Dùng SVM cho song ngữ; nếu cần NB thì train riêng từng ngôn ngữ.
- crawl chỉ 4 tin → chưa kết luận được gì (Wilson CI ~ [0,30; 0,95] với 3/4).

### 3.4f ĐÃ LÀM 25/11 (đêm) – Rà nhãn tiếng Anh theo `definition.md` (Q8)
- Ứng viên: R1–R3 (`scripts/flag_en_label_review.py`) + R4 (tin "scam" có dấu hiệu giao dịch: OTP, giao hàng, gia hạn, nạp tiền) = 711 tin.
  Agent đọc theo họ mẫu, quyết từng họ; kết quả + lý do: `data/review/en_label_review_v1.csv` (cột `decision`, `review_label`, `review_note`).
- Người dùng chốt 25/11: (a) **quảng cáo thương hiệu thật gửi khách hàng + cú pháp từ chối = HAM (1.3)** – áp cho cả tiếng Anh;
  (b) tin không chắc thật/giả (link bị che) → **drop**.
- Đổi nhãn: 151 spam→scam (giải thưởng giả 3.3, việc làm giả), 141 scam→spam (quảng cáo/premium/chính trị), 201 →ham
  (OTP/giao hàng/gia hạn chính chủ – IMC25 gắn nhầm scam), 31 drop. File áp: `data/review/en_label_overrides.csv` (theo `source_record_id`).
- Pipeline: `data.label_overrides` (`src/scam_baseline/data/overrides.py`) – kiểm tra text khớp lúc review, **lan nhãn sang mọi bản trùng y hệt**
  (548 dòng đổi, 36 dòng bỏ); scam mới có `scam_type` (`prize_lottery`, `job_task_scam`, `other_scam`). Test: `tests/test_overrides.py`.
- Kết quả SVM EN sau sửa: test P/R/F2 = 0,96/0,92/0,93; **SmishX R 0,84 (trước 0,70)**, FPR 9,7% (nhãn SmishX cũng được sửa → không so trực tiếp).
- Còn lại: R1–R4 chỉ là bộ lọc theo quy tắc → có thể còn tin sai nhãn khác trong IMC25 (ghi vào giới hạn).

### 3.4g ĐÃ LÀM 25/11 (đêm) – Rà `scam_type` tiếng Việt (GĐ2)
- Quy tắc gợi ý theo từ khóa → 238 tin lệch với nhãn hiện tại → agent đọc 174 họ mẫu, chốt theo nguyên tắc
  **"đơn vị bị mạo danh trước, chủ đề mồi sau"**: đổi điểm ngân hàng/ví → `banking_finance`; Cục Viễn thông, điện lực, cấp nước → `government_services`;
  nhà mạng/internet/truyền hình cáp → `telecom_account`; vay/đòi nợ không mạo danh cơ quan → `banking_finance`; tài khoản Telegram/Zalo/Google,
  hẹn hò, resort/timeshare, tin làm rối → `other_scam`; người thân/sếp nhờ chuyển tiền → `social_impersonation`.
- 89 tin / 104 dòng đổi: `data/review/vi_scam_type_overrides.csv` (áp trong `apply_vi_labels_v3.py`).
  Phân bố mới (641 scam Tuấn): banking 193, prize 109, gov 88, other 74 (trước 109), job 65, investment 55, delivery 28, social 20 (trước 2), telecom 9.
- ⚠️ GĐ2 tiếng Việt: `social_impersonation` chỉ 3 tin trong train (đa số rơi vào test), `telecom_account` 11 → quá ít để học; cân nhắc gộp lớp nhỏ
  hoặc dùng crawl để bổ sung. Chỉ `scam_type` đổi → **không cần train lại tầng 1**.

**Người dùng chốt (25/11 đêm):** nhãn EN (3.4f) và quy tắc `scam_type` (3.4g) OK; **gộp lớp `scam_type` nhỏ** khi làm GĐ2;
**không dùng VNPhish**; OCR (EasyOCR) dùng trong khâu thu thập – trình bày với giảng viên nếu được hỏi.
Nhật ký thay đổi để báo cáo: [`NHAT_KY_THAY_DOI_DU_LIEU.md`](NHAT_KY_THAY_DOI_DU_LIEU.md).

### 3.4 Áp nhãn mới vào pipeline – ĐÃ XONG toàn bộ (3.4a–3.4g); khi có crawl chỉ cần chạy lại bước 2–4
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

## 5. Danh sách file
**Đã commit (24–25/11):** crawler v2, notebook Kaggle, hướng dẫn crawl, `definition_of_ham_spam_scam.md`, review v3 ban đầu, bỏ `social_spam_post`.

**Chưa commit (25/11 chiều–tối):**
- Script mới: `scripts/apply_vi_labels_v3.py`, `scripts/build_vi_crawl_external.py`, `scripts/flag_en_label_review.py`; viết lại `scripts/balance_datasets.py`.
- Code: `src/scam_baseline/data/family.py` (mới), `adapters.py`, `dedup.py`, `split.py`, `pipeline.py`, `config.py`, `evaluation.py`, `reporting.py`, `models/classical.py`.
- Test: `tests/test_balance.py`, `tests/test_evaluation.py` (mới), `tests/test_adapters.py`, `tests/test_split.py`.
- Config: `english.yaml`, `english_balanced.yaml`, `bilingual.yaml`, `vietnamese*.yaml`, `configs/experiments/` (4 thí nghiệm e0–e3).
- Dữ liệu: `data/raw/*_v3.csv`, `vie_sms_corpus_{dev,holdout}_v3.csv`, `vi_crawl_external.csv`; `data/review/` (override xung đột,
  log loại train, tóm tắt v3, ứng viên sửa nhãn EN, log crawl bị loại, sửa nhãn cờ bạc trong 2 file review Tuấn); `data/processed_*` sinh lại.
- Không nên commit: `crawl_data_scam/`, `*.zip`, `data/processed_vi_exp_*` (dữ liệu thí nghiệm, sinh lại được).
