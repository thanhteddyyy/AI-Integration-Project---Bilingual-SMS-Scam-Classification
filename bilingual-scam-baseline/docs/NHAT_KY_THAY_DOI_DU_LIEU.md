# Nhật ký thay đổi dữ liệu & pipeline (24–25/11/2026)

Tài liệu tóm tắt **đã sửa gì, vì sao, kết quả ra sao**, dùng để theo dõi tiến độ và báo cáo. Chi tiết kỹ thuật đầy đủ
(lệnh chạy, tên cột, số liệu từng bước) nằm ở [`HANDOFF_xu_ly_du_lieu_tieng_viet.md`](HANDOFF_xu_ly_du_lieu_tieng_viet.md).

Chuẩn gán nhãn duy nhất: [`definition_of_ham_spam_scam.md`](../definition_of_ham_spam_scam.md) (ham → spam → scam theo cây
quyết định, có trích dẫn ITU-T X.1240, Almeida 2011, GSMA, NĐ 91/2020) + các quy tắc bổ sung ghi ở mục 1 của handoff.

---

## 1. Tóm tắt một trang

| # | Vấn đề phát hiện | Cách xử lý | Kết quả |
|---|---|---|---|
| 1 | Nhãn tiếng Việt do máy gán bằng từ khóa, sai nhiều | Rà tay toàn bộ theo `definition.md` (nhãn v3) | Tập Tuấn: 2.065 ham / 285 spam / **641 scam** (trước: 272 scam) |
| 2 | `social_spam_post` là bản dịch máy của UCI (tiếng Anh) → rò rỉ chéo ngôn ngữ | Bỏ khỏi dữ liệu | – |
| 3 | **80% tin scam trong test của Tuấn có bản "cùng khuôn" trong train** | Giữ test của Tuấn, bỏ 199 tin train cùng khuôn ("cách B"); pipeline chia theo **họ mẫu** | Rò rỉ = 0 |
| 4 | Model học lối tắt **"có dấu = scam"**: báo nhầm 24% tin cá nhân thật là scam | Chia đôi `vie_sms_corpus`: một nửa vào train (tin cá nhân), nửa kia khóa làm external | Báo nhầm còn **0,1–1%** |
| 5 | Script cân bằng dữ liệu cũ: vứt bỏ dữ liệu thật, augment ra bản sao y hệt, trùng `sample_id` | Viết lại: giữ toàn bộ dữ liệu thật + `class_weight`; augment có kiểm soát | 0 bản trùng, `sample_id` duy nhất |
| 6 | Tiếng Anh: IMC25 có token `<PHONE_NUMBER>`… còn nguồn khác không → model học "có token = scam" | Thống nhất placeholder cho mọi nguồn tiếng Anh | Hết lối tắt theo nguồn |
| 7 | Nhãn tiếng Anh không theo định nghĩa (giải thưởng giả gắn spam; mã OTP, giao hàng gắn scam) | Rà 711 tin theo `definition.md` | 524 tin đổi nhãn / bỏ; recall SmishX 0,70 → 0,84 |
| 8 | `scam_type` tiếng Việt gán bằng từ khóa, sai (vd "con cấp cứu" = ngân hàng) | Rà lại theo nguyên tắc "đơn vị bị mạo danh trước" | 89 tin đổi loại; `other_scam` 109 → 74 |
| 9 | Chưa có chỉ số phù hợp bài toán lừa đảo | Thêm F2 (ưu tiên recall), MCC, tỉ lệ báo nhầm, khoảng tin cậy Wilson, kết quả theo nguồn | Chọn model theo F2 lớp scam |
| 10 | External tiếng Việt **không có scam thật** | Crawl báo chí (script v2) + adapter lọc trùng với tập Tuấn | Lần 1: chỉ 4 tin dùng được → **đang chờ crawl lần 2** |

---

## 2. Chi tiết theo hạng mục

### 2.1 Nhãn tiếng Việt (v3)
- **Vấn đề:** tập Tuấn gốc chỉ có 0/1; 798 tin nhãn 1 được máy tách scam/spam bằng từ khóa → sai nhiều. `vie_sms_corpus` (2015) gắn
  "spam" cả quảng cáo hợp lệ của nhà mạng.
- **Đã làm:** rà tay theo `definition.md` + quy tắc bổ sung (X1–X4+, Câu A/B, Q2–Q7). Ví dụ quy tắc: tuyển CTV "việc nhẹ lương cao" = scam;
  `[QC]` + cú pháp từ chối = ham; link tên miền lạ = scam; cờ bạc + tên miền cờ bạc/ngẫu nhiên (kể cả `.com`) = scam.
- **Kết quả:** tập Tuấn 2.065 ham / 285 spam / 641 scam; `vie_sms_corpus` 6.123 ham / 381 spam / 0 scam (66 tin bị loại).
- **File:** `data/review/vi_tuan_label*_review*.csv`, `vi_external_*`, `scripts/apply_vi_labels_v3.py` → `data/raw/*_v3.csv`.

### 2.2 Rò rỉ train/test và chia theo họ mẫu
- **Vấn đề:** tập Tuấn chứa nhiều tin sinh theo mẫu (đổi tên ngân hàng/link/số tiền). 80% scam test có "anh em" trong train
  → điểm test bị thổi phồng. Tiếng Anh cũng có 22% scam test cùng khuôn với train.
- **Định nghĩa họ mẫu:** hai tin cùng họ nếu độ giống Jaccard trên cụm 3 từ ≥ 0,5 (sau khi bỏ dấu, số, link, placeholder).
- **Đã làm:** (i) "cách B" – giữ nguyên test của Tuấn để so sánh với bài gốc, bỏ 199 tin train cùng khuôn (128 scam, 53 ham, 18 spam);
  (ii) pipeline chia train/val/test và loại chồng lấn với test/external **theo họ mẫu** cho cả hai ngôn ngữ.
- **File:** `src/scam_baseline/data/family.py`, `split.py`, `dedup.py`; tham số `deduplication.family_jaccard: 0.5`.

### 2.3 Lối tắt "có dấu = scam"
- **Vấn đề:** ham của Tuấn gần như chỉ là tin nhà mạng/OTP không dấu, còn 71% scam có dấu, và train không có tin cá nhân.
  Trên tin thật của `vie_sms_corpus`, SVM báo nhầm **24,3%** là scam (79% số tin bị báo nhầm là tin cá nhân có dấu).
- **Thí nghiệm (4 cấu hình, chọn theo validation):** bỏ dấu khi trích đặc trưng chỉ giảm còn 20%; thêm tin cá nhân vào train giảm còn **0,1%**.
  → Nguyên nhân thật là **train thiếu tin cá nhân**. Chọn cấu hình e2 (chênh lệch validation < 1 tin → chọn cấu hình đơn giản hơn).
- **Đã làm:** `vie_sms_corpus` chia 50/50 theo họ mẫu: nửa *dev* vào train/val, nửa *holdout* khóa làm external (không tinh chỉnh trên nó).
- **File:** `configs/experiments/vi_e*.yaml`, `data/raw/vie_sms_corpus_{dev,holdout}_v3.csv`.

### 2.4 Cân bằng dữ liệu (`scripts/balance_datasets.py`)
- **Vấn đề cũ:** cắt ham thật 1.231 → 500 (VI), scam 10.315 → 2.000 (EN); 182/319 tin augment là bản sao y hệt; chỉ sửa `text_clean`
  (meta-features sai); 920 `sample_id` trùng; thêm tiền tố `[QC]` làm đổi nhãn theo quy tắc X3.
- **Đã làm:** giữ toàn bộ dữ liệu thật + `class_weight: balanced` (NB: `fit_prior: false`); EN scam giới hạn 4.000, phân tầng theo `scam_type`;
  augment VI chỉ cho scam/spam trong train (bỏ dấu, đồng nghĩa, đổi thực thể, teencode; ≤ 2 bản/tin; loại bản trùng với mọi split).

### 2.5 Tiếng Anh: placeholder và nhãn
- **Placeholder:** token Presidio của IMC25 và số/link thô của `sms_phishing`, SmishX được quy về chung `<URL> <PHONE> <EMAIL> <DATE_TIME> <NUMBER>`;
  token tên riêng bị bỏ. (Đánh đổi: tiếng Anh mất thông tin tên miền.)
- **Nhãn:** lọc 711 tin nghi sai theo 4 quy tắc, đọc theo họ mẫu, quyết từng họ (lý do ghi trong file).
  151 spam → scam (giải thưởng giả, việc làm giả); 141 scam → spam (quảng cáo, đầu số tính phí cao, tin chính trị);
  201 → ham (OTP, giao hàng, gia hạn gói – IMC25 gắn nhầm scam); 31 bỏ (link bị che, không xác định được).
  Nhãn mới được áp cho mọi bản trùng y hệt (548 dòng đổi, 36 dòng bỏ).
- **Quyết định của người dùng:** quảng cáo của thương hiệu thật gửi khách hàng có cú pháp từ chối = **ham** (mục 1.3), áp cho cả tiếng Anh.
- **File:** `data/review/en_label_review_v1.csv` (quyết định + lý do), `en_label_overrides.csv`, `src/scam_baseline/data/overrides.py`.

### 2.6 `scam_type` tiếng Việt (Giai đoạn 2)
- **Nguyên tắc:** xếp theo **đơn vị bị mạo danh** trước, chủ đề mồi sau. Đổi điểm ngân hàng/ví → `banking_finance`; Cục Viễn thông, điện lực,
  cấp nước → `government_services`; nhà mạng/internet → `telecom_account`; người thân/sếp nhờ chuyển tiền → `social_impersonation`;
  tài khoản Telegram/Zalo, hẹn hò, tin làm rối → `other_scam`.
- **Kết quả:** 89 tin đổi loại. Phân bố 641 scam: banking 193, prize 109, gov 88, other 74, job 65, investment 55, delivery 28, social 20, telecom 9.
- **Quyết định của người dùng:** lớp quá nhỏ (social, telecom) được **gộp** khi làm Giai đoạn 2.

### 2.7 Đánh giá
- Thêm: **F2 lớp scam** (recall quan trọng gấp đôi precision – bỏ sót lừa đảo nguy hiểm hơn báo nhầm), **MCC**, **tỉ lệ báo nhầm (FPR)**,
  **khoảng tin cậy Wilson 95%** (cần cho tập external nhỏ), kết quả **theo từng nguồn**.
- Chọn model tốt nhất theo F2 lớp scam trên **validation**; test và external chỉ để báo cáo.

### 2.8 Dữ liệu scam thật cho external tiếng Việt
- Đã rà: không có bộ SMS lừa đảo tiếng Việt thật công khai nào khác (các bộ tìm được trùng tập Tuấn / Pham & Le-Hong, hoặc do LLM sinh như VNPhish).
- **Không dùng VNPhish** (dữ liệu do LLM viết, nguồn gốc từ trang có `ai-train=no`) – quyết định của người dùng.
- Crawl báo chí: script v2 dùng **OCR (EasyOCR) để đọc ảnh chụp tin nhắn**, người kiểm tra lại 100%. Lần 1: 119 bài → 4 tin SMS độc lập dùng được
  (nhiều tin báo đăng đã có sẵn trong tập Tuấn). Adapter `scripts/build_vi_crawl_external.py` lọc trùng với **toàn bộ** tập Tuấn.
- **Crawl lần 2 (26/11):** 200 ứng viên; AI (Claude) lọc + gắn nhãn sơ bộ sau khi đọc ảnh gốc (48 giữ, 152 loại có lý do),
  người dùng xác nhận 100% tin giữ (`review_prelabeled.html` → `data/review/vi_crawl_run2_reviewed.csv`).
  Một ảnh minh họa do AI vẽ đã bị loại. Adapter thêm bước **gộp theo họ mẫu ngay trong tập crawl** (báo đăng lại một khuôn nhiều lần).
- **Quyết định: báo cáo 2 tập external scam (26/11).**
  (i) **Tập sạch** `vi_crawl` (trong pipeline): chỉ SMS, bỏ tin cùng họ mẫu với Tuấn → đo khả năng bắt **lừa đảo mới** – con số chính.
  (ii) **Tập đầy đủ** `data/raw/vi_crawl_external_full.csv`: mọi kênh, **giữ** tin cùng họ mẫu với Tuấn (cột `tuan_family`) →
  đo lừa đảo **đang lưu hành thật**; chênh lệch (i)/(ii) cho thấy model dựa vào nhớ khuôn đến đâu. Tập này **không** đưa vào
  pipeline (pipeline sẽ tự loại tin train/test của Tuấn cùng họ → đổi dữ liệu train); chấm bằng `scripts/score_vi_crawl_full.py`
  (→ `reports/vi_crawl_full/`), tách khuôn mới/đã biết × SMS/chat, kèm Wilson CI.

---

## 3. Kết quả hiện tại (SVM, lớp scam)

| Cấu hình | Test: Precision / Recall / F2 | Báo nhầm trên tin thật ngoài | Nguồn ngoài |
|---|---|---|---|
| Tiếng Việt (+ augment) | 0,82 / 0,70 / 0,72 | 0,1% (`vie_sms` holdout) | crawl: 4/4 (quá ít để kết luận) |
| Tiếng Anh | 0,96 / 0,92 / 0,93 | – | SmishX: recall 0,84, báo nhầm 9,7% |
| Song ngữ – phần VI | 0,82 / 0,67 / 0,70 | 1,0% | crawl: 4/4 |
| Song ngữ – phần EN | 0,96 / 0,92 / 0,93 | – | SmishX: recall 0,85 |

Kết quả cũ (trước khi sửa) được sao lưu ở `reports/` và `artifacts/_before_v3_2026-11-25/`.

### 3.1 External scam tiếng Việt thật sau crawl lần 2 (26/11/2026)
Chấm lại bằng model đã train (`scripts/rescore_external.py`): train/val/test cả 3 bộ dữ liệu được kiểm tra **giống hệt từng mẫu** trước/sau
(sao lưu `data/_before_crawl2_2026-11-26/`, `artifacts/_before_crawl2_2026-11-26/`). Recall lớp scam, Wilson 95%:

| Model | **Tập sạch** (SMS, khuôn mới, n=22) | SMS khuôn đã có trong Tuấn (n=10) | Zalo/Messenger (n=12) | Báo nhầm `vie_sms` holdout |
|---|---|---|---|---|
| SVM tiếng Việt (+augment) | **0,86** (0,67–0,95) | 1,00 (0,72–1,00) | 0,08 (0,01–0,35) | 0,1% |
| SVM tiếng Việt 3 lớp | 0,82 (0,61–0,93) | 1,00 | 0,08 | 0,07% |
| SVM song ngữ – phần VI | 0,86 (0,67–0,95) | 1,00 | 0,08 | 1,0% |
| NB tiếng Việt (+augment) | 0,59 (0,39–0,77) | 1,00 | 0,00 | 1,4% |
| NB song ngữ – phần VI | 0,14 (0,05–0,33) | 0,70 | 0,00 | 2,3% |

Không tin hợp lệ nào của crawl bị báo nhầm (chỉ 2–4 tin, không kết luận được). Nhận xét:
- SVM bắt khuôn đã biết 100%, khuôn mới 86% → có dựa vào nhớ khuôn nhưng tụt ít.
- **Mọi tin bị bỏ sót đều bị đoán `legitimate`** (không phải spam): tin giọng cá nhân/hội thoại (mượn tiền, bình chọn, thám tử tư, "HUIT chúc mừng")
  → mặt trái của việc thêm tin cá nhân vào train (mục 2.3). Model gần như **mù với lừa đảo qua Zalo/Messenger** (1/12) – giới hạn cần nêu, hướng phát triển.
- Chi tiết: `reports/vi_crawl_full/{summary,predictions}.csv`, `artifacts/*/metrics_external_test.json` (mục `by_source.vi_crawl`).

## 4. Giới hạn cần nêu trong báo cáo
1. Scam tiếng Việt chỉ đến từ **một nguồn** (tập Tuấn, ~640 tin), nhiều tin sinh theo mẫu.
2. External scam tiếng Việt thật còn nhỏ: 22 tin SMS khuôn mới (+10 khuôn đã biết, +12 Zalo/Messenger) → khoảng tin cậy rộng;
   `vie_sms_corpus` là tin năm 2015. Nhãn crawl lần 2 do AI gắn sơ bộ, người dùng xác nhận.
3. Test tiếng Anh vẫn lạc quan hơn thực tế vì 97% scam test là IMC25 → dùng **SmishX** làm con số thực tế cho tiếng Anh.
4. Rà nhãn tiếng Anh dựa trên bộ lọc theo quy tắc → IMC25 có thể còn tin sai nhãn khác.
5. NB không hợp với mô hình song ngữ (phần VI recall 0,19) → dùng SVM.
6. Quy tắc X4 ("link lạ = scam") có thể khiến model học lối tắt theo tên miền → cần phân tích lỗi.

## 5. Trạng thái đồ án và việc còn lại (cập nhật 25/11/2026)

### Đã hoàn thành
- **Dữ liệu:** nhãn VI + EN rà theo `definition.md`; sửa rò rỉ họ mẫu, lối tắt "có dấu = scam", lối tắt placeholder EN;
  rà `scam_type` VI; pipeline chạy lại được toàn bộ, 29 test.
- **Giai đoạn 1 (ham/spam/scam):** NB + SVM cho VI, EN, song ngữ (kết quả mục 3); chỉ số F2, MCC, FPR, Wilson CI.
- **Tài liệu:** nhật ký này + handoff (`HANDOFF_xu_ly_du_lieu_tieng_viet.md`).

### Cần hoàn thành
| # | Việc | Ai | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| 1 | **Scam VI thật cho external** (≥ 100 tin): crawl v2 → duyệt → lưu `data/review/vi_crawl_run2_reviewed.csv` → `build_vi_crawl_external.py` → prepare/balance/merge/meta → chấm lại model (không cần train lại) | Người dùng crawl + duyệt; agent chạy pipeline | – | ✅ 26/11: 22 tin sạch (SMS) + tập đầy đủ 44 scam – dưới mục tiêu 100, xem 3.1 |
| 2 | **Giai đoạn 2 – phân loại `scam_type`**: gộp lớp nhỏ (`social_impersonation`, `telecom_account`), train NB/SVM, đánh giá | Agent | – | ⬜ chưa có code |
| 3 | **Demo Gradio + `predict_pipeline`**: nhập tin → ham/spam/scam → loại scam → giải thích | Agent viết, người dùng chạy thử | 2 | ⬜ chưa có code |
| 4 | **Train CharCNN** (model thứ 3 để so sánh) | Người dùng chạy Colab/Kaggle, agent chuẩn bị notebook | – (GPU) | ✅ 26/11 (Kaggle lần 2, `results_2.zip`): CharCNN train đủ (khởi động 5 epoch); **SVM thắng cả 3 thiết lập** → tầng 1 = Linear SVM. Thí nghiệm kết hợp SVM+CharCNN: [`rerank_experiment.md`](rerank_experiment.md) – không hơn SVM đơn ở song ngữ. Trước đó: notebook `notebooks/tier1_compare_colab.ipynb` + `bilingual-scam-colab.zip` sẵn sàng; CharCNN dừng sớm theo F2 scam (trước: macro-F1); sửa lỗi `lr`→`learning_rate` trong config VI/EN; chọn tầng 1 bằng `scripts/compare_tier1.py` |
| 5 | **Phân tích lỗi**: model sai ở đâu, có học lối tắt "link lạ = scam" (X4) không, vì sao test EN cao hơn SmishX | Agent | nên sau 1 | ⬜ |
| 6 | **Đưa meta-features vào SVM** (lưu scaler cùng model), so sánh có/không | Agent | – | ⬜ (dữ liệu meta đã có) |
| 7 | **Viết báo cáo + slide** (chương dữ liệu dựa trên nhật ký này) | Người dùng | 1–6 | ⬜ |
| 8 | Trình bày với giảng viên nếu được hỏi: dùng EasyOCR trong thu thập; không dùng dữ liệu LLM (VNPhish) | Người dùng | – | khi cần |

**Thứ tự đề xuất:** làm 2 → 3 trong lúc chờ crawl (người dùng chạy 4 trên Colab, bắt đầu viết chương dữ liệu) →
khi crawl xong làm 1 → 5, 6 → hoàn thiện 7.
