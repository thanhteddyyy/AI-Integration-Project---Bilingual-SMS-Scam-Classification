# Phân tích lỗi (việc 5) – 28/11/2026

Số liệu đầy đủ: `reports/error_analysis/summary.md` (sinh bằng `scripts/error_analysis.py`, chạy lại được) và các file csv
cùng thư mục. Tầng 1 = Linear SVM song ngữ (`artifacts/bilingual/svm`); tầng 2 = Linear SVM 9 loại. Với tầng 2, dùng dự đoán
**ngoài fold** của CV 5 lượt theo khuôn (cùng cách chia với `train_tier2.py`), nên mỗi tin trong train+val được chấm đúng một lần
bởi model chưa thấy khuôn của nó (524 tin thay vì khoảng 85 tin test). Số trong ngoặc vuông là khoảng tin cậy Wilson 95%.

Câu lệnh: `$env:PYTHONPATH="src"; py -3.11 scripts/error_analysis.py` (khoảng 1 phút, không train lại model nào ngoài các model trong từng fold CV).

---

## Tóm tắt (dùng cho báo cáo)

| # | Phát hiện | Con số chính | Hệ quả |
|---|---|---|---|
| 1 | Tầng 1 **không bắt được lừa đảo giọng cá nhân** (mượn tiền, "con cấp cứu", "sếp nhờ") | 0/10 (Tuấn test), 0/10 (crawl); giọng tổ chức: 74,5% và 88,2% | Giới hạn chính; demo cảnh báo bằng luật |
| 2 | Lừa đảo **không có link** (yêu cầu chuyển khoản vào STK, gọi điện) bị bỏ sót nhiều hơn | bấm link 85,7% · chuyển vào STK 66,7% · gọi điện/Zalo 71,0% | Model dựa nhiều vào link; dữ liệu cần thêm loại không link |
| 3 | Lối tắt X4: model **có** học "tên miền lạ = scam", nhưng phân biệt được tên miền lạ với chính thống | thêm link lạ vào tin ham → 29,9% thành scam; link chính thống → 3,2% | Đúng tinh thần X4; rủi ro thấp ngoài đời |
| 4 | Scam có link vẫn được nhận ra **nhờ nội dung**, không chỉ nhờ link | bỏ link → chỉ 11,4% (VI), 3,5% (EN) hết scam | Không phụ thuộc hoàn toàn vào link |
| 5 | SmishX báo nhầm cao do **tin giao dịch thật có "Click `<URL>`"** của dịch vụ Ấn Độ | ham EN có link bị báo scam 65,5%; train chỉ có 2,6% ham có link | Lệch miền, không phải lối tắt token `<URL>` (thêm `<URL>` chỉ đổi 5,4%) |
| 6 | Test EN lạc quan vì **IMC25 test giống train hơn** | độ giống TB 0,52 (IMC25) và 0,36 (SmishX); 15,5% tin IMC25 gần như đã thấy | Dùng SmishX làm con số thực tế |
| 7 | **Margin < 0,3 = model đoán gần như may rủi** ở cả hai tầng | tầng 1: 51,5% đúng (5% tin); tầng 2: 50,4% đúng (26% tin) | Demo hiện "model phân vân" khi margin < 0,3 |
| 8 | Lỗi tầng 2 tập trung ở **ca ranh giới của quy tắc nhãn**, nhất là quy tắc 1 (tên ngân hàng nhận tiền) | 8/12 lỗi tự tin nhất là "Hồ sơ vay… nộp phí vào TK + tên ngân hàng" (nhãn banking, model đoán loan_debt) | **Cần người dùng quyết định** (mục 3.3) |
| 9 | Tầng 1 bỏ sót **spam** của tập Tuấn (đoán thành ham) | 90/138 spam test → ham | Ít nguy hiểm (tầng 1 ưu tiên scam); nêu trong báo cáo |

---

## 1. Tầng 1 – lỗi theo nguồn (T1-a)

- **IMC25** (EN): lỗi chủ yếu là scam ↔ spam (74–85 tin mỗi tập) và scam → ham (66–67). Nhãn IMC25 vốn có tin sai (giới hạn 5 trong
  `TONG_KET_TIEN_DO.md`), nên một phần "lỗi" là nhãn chưa đúng.
- **Tuấn test** (`spamscam_test`): 159 lỗi trên 565 tin, trong đó **90 tin spam bị đoán là ham** và 30 tin scam bị đoán là ham.
  Spam của Tuấn là quảng cáo không có `[QC]` (bất động sản, sim, vay…). Model song ngữ học "tin tiếng Việt bình thường" chủ yếu từ
  `vie_sms` (tin cá nhân), nên kiểu quảng cáo này dễ bị đẩy về ham. Tầng 1 chọn theo F2 của scam nên chấp nhận đánh đổi này.
- **SmishX** (EN thật): 52 tin ham bị báo scam là lỗi lớn nhất (mục 3.2).
- **vie_sms_holdout** (VI thật): 28 tin ham bị báo scam (1,0%), 38 spam → ham.

## 2. Lừa đảo tiếng Việt bị bỏ sót (T1-b)

Gộp 104 tin scam của Tuấn test và 44 tin scam crawl đợt 1–2 (tập đầy đủ, mọi kênh). **48 tin bị bỏ sót, 44 tin bị đoán là ham**,
chỉ 4 tin bị đoán là spam (đều là quảng cáo cờ bạc kiểu "nạp đầu 50 nhận 50", vốn là scam theo quy tắc X4+).

### 2.1 Giọng cá nhân: 0/20
Tin có lời gọi thân mật hoặc yêu cầu mượn/chuyển tiền ("Mẹ ơi con…", "Sếp nhờ chút…", "Tài khoản còn đủ… cho mượn") **không tin nào
được bắt**. Lý do đã ghi ở `NHAT_KY_TANG2.md` mục 7.4: nội dung giống hệt tin của người quen thật, lừa đảo nằm ở **danh tính người gửi**.
Tầng 1 cố ý không học kiểu này để tránh báo nhầm tin thật (từng lên 24%). Demo đã có cảnh báo bằng luật (`TRANSFER_REQUEST_RE`).

Một số tin "giọng doanh nghiệp" cũng bị bỏ sót vì cùng cơ chế: "Bên em là kế toán cty, lỡ chuyển dư… Phiền chuyển lại giúp em",
"mình lỡ tay chuyển nhầm… hoàn lại vào STK". Đây là kịch bản **người lạ** nhờ chuyển tiền, không có link hay tên tổ chức.

### 2.2 Không có link thì khó hơn
Chỉ xét tin giọng tổ chức/thông báo (để tách khỏi mục 2.1):

| Kẻ gian yêu cầu | Số tin | Bắt được |
|---|---|---|
| bấm link | 63 | **85,7%** [75,0–92,3] |
| chuyển tiền vào STK | 24 | **66,7%** [46,7–82,0] |
| gọi điện / nhắn Zalo | 31 | **71,0%** [53,4–83,9] |

Ví dụ bị bỏ sót: "Phương tiện biển số … vi phạm tốc độ, mức phạt … Tra cứu và nộp phạt, liên hệ [NUMBER]", "Bạn là người bảo lãnh khoản
vay … Gọi [NUMBER] ngay", "[Viettel] Thuê bao … sẽ bị khóa 1 chiều … Vui lòng gọi [NUMBER]". Cùng kịch bản nhưng kèm link thì model bắt
được. → Dữ liệu scam tiếng Việt có link chiếm phần lớn, nên link là tín hiệu mạnh nhất. **Hướng cải thiện:** thêm tin scam yêu cầu gọi
điện hoặc chuyển khoản. Không dùng luật "có STK = scam" vì tin thật cũng có STK.

## 3. Lối tắt "link lạ = scam" (X4) (T1-c)

Quy tắc X4 gán **mọi** tin có tên miền lạ (`.xyz .top .vip .cc …`) là scam. Lo ngại: model có học "có link = scam" thay vì đọc nội dung?

### 3.1 Phép thử phản thực tế (chỉ sửa phần link, trên các tin đang đoán đúng)

| Phép thử | Số tin | Đổi kết quả |
|---|---|---|
| VI scam: **bỏ** link | 44 | 11,4% hết scam |
| VI scam: đổi sang tên miền **chính thống** | 44 | 2,3% hết scam |
| VI ham: **thêm link lạ** | 2.835 | **29,9%** thành scam |
| VI ham: thêm link **chính thống** | 2.835 | 3,2% thành scam |
| VI ham có link: đổi sang tên miền **lạ** | 128 | 19,5% thành scam |
| VI spam: thêm link lạ (theo X4 thì đổi là **đúng**) | 93 | 16,1% thành scam |
| EN scam: bỏ `<URL>` | 926 | 3,5% hết scam |
| EN ham: thêm `<URL>` | 1.153 | 5,4% thành scam |

**Kết luận:**
- Model **có** học tín hiệu tên miền: cùng một tin ham, thêm `csgt-gov.xyz` làm 30% thành scam, thêm `csgt.vn` chỉ 3%. Model đọc
  **tên miền**, không chỉ "có link". Đây đúng là điều X4 mong muốn. Ngoài đời, tin người quen kèm link `.xyz` cũng đáng nghi.
- Model **không phụ thuộc hoàn toàn** vào link: bỏ link khỏi tin scam, gần 89% (VI) và 96% (EN) vẫn bị báo scam nhờ nội dung
  ("tài khoản bị khóa", "xác minh", "nộp phạt"…).
- Đổi tên miền lạ thành chính thống gần như không cứu được tin scam (2,3%). Vậy model không bị lừa chỉ vì kẻ gian dùng tên miền giống thật.
- Tiếng Anh: model chỉ thấy token `<URL>`, không thấy tên miền (giới hạn của dữ liệu EN), và token này ảnh hưởng ít.

### 3.2 SmishX báo nhầm: lệch miền, không phải lối tắt
Tin ham tiếng Anh **có link** bị báo scam 65,5% (38/58 tin SmishX), so với 2,5% ở tin ham không link. Nhưng thêm `<URL>` vào tin ham chỉ
đổi 5,4%, nên nguyên nhân là **nội dung** đi kèm link. Các tin bị báo nhầm là tin giao dịch thật của dịch vụ Ấn Độ: Jio ("data quota …
click `<URL>`"), Kotak Bank ("If not you, REPORT FRAUD on `<URL>`"), BPCL, Tata Play, Amazon ("Track at `<URL>`"). Trong train, chỉ
**81/3.096 tin ham tiếng Anh (2,6%) có link**, so với 1.665/4.000 tin scam (42%). Model gần như chưa thấy tin thật kiểu "bấm link để quản lý
dịch vụ". → **Giới hạn:** dữ liệu ham tiếng Anh thiếu tin giao dịch có link. Hướng cải thiện: bổ sung tin giao dịch thật có link.

## 4. Vì sao test tiếng Anh tốt hơn SmishX (T1-d)

Đo độ giống của mỗi tin scam với tin scam tiếng Anh giống nhất trong train (cosine TF-IDF cụm ký tự 3–5):

| Nguồn | Độ giống TB | Gần như đã thấy (≥ 0,8) | Recall khi giống < 0,5 | 0,5–0,8 | ≥ 0,8 |
|---|---|---|---|---|---|
| IMC25 | 0,52 | 15,5% | 88,1 | 98,2 | 100 |
| SmishX | 0,36 | 3,1% | 83,9 | 85,7 | 100 |

- IMC25 test **giống train hơn hẳn** (cùng nguồn, nhiều mẫu), và recall tăng rõ khi tin giống train. Đây là lý do test EN cao.
- Với tin **ít giống train** (< 0,5), hai nguồn chênh nhau ít (88 so với 84). Phần lớn khoảng cách đến từ việc IMC25 có nhiều tin
  "gần như đã thấy". Khoảng cách về báo nhầm thì đến từ mục 3.2.
- → Giữ quyết định cũ: **báo cáo SmishX làm con số tiếng Anh thực tế**.

## 5. Margin có dùng được để báo "model phân vân" không (T1-e, T2)

| Margin | Tầng 1: % tin / đúng | Tầng 2: % tin / đúng |
|---|---|---|
| < 0,3 | 5,1% / **51,5%** | 25,8% / **50,4%** |
| 0,3–0,6 | 5,2% / 66,6% | 22,9% / 81,7% |
| 0,6–1 | 7,8% / 77,8% | 21,9% / 96,5% |
| ≥ 1 | 82,0% / 96,8% | 29,4% / 92,2% |

→ Ngưỡng 0,3 đã ghi trong `demo/README.md` **được xác nhận bằng số liệu**: dưới ngưỡng này cả hai tầng chỉ đúng khoảng một nửa.
Tầng 2 phân vân ở khoảng 1/4 số tin, nên demo nên hiện **2 loại có điểm cao nhất** khi margin < 0,3, thay vì chỉ 1 loại.

## 6. Tầng 2 – nhầm lẫn giữa các loại (T2-a)

Ngoài fold: 524 tin, sai 105 (độ chính xác 80,0%). Các cặp nhầm nhiều nhất:

| Thật → đoán | Số tin | Nguyên nhân chính |
|---|---|---|
| gov_utility → prize_lottery | 10 | "Để nhận tiền **hoàn thuế**, chuyển trước phí…": từ "nhận / tiền / hoàn" kéo về trúng thưởng; "sim số đẹp Mobifone" (nhãn theo quy tắc 3) |
| other_scam → gov_utility | 10 | `other_scam` là lớp tạp; vài tin có thể **sai nhãn**: "Yêu cầu công dân… vụ án kinh tế… `bocongan.apk-chinhphu.cc`" là mạo danh Bộ Công an, đáng lẽ là gov_utility theo quy tắc 2 |
| banking → loan_debt | 9 | "Hồ sơ vay … đã duyệt, nộp phí bảo hiểm vào TK … **Vietcombank**": nhãn banking theo quy tắc 1, nội dung là vay |
| gov_utility → banking | 6 | "OTP… xác thực tại evn.io.vn", "Thuê bao… bị khóa 2 chiều": từ "OTP / xác thực / tài khoản / bị khóa" thuộc về banking |
| other_scam ↔ investment | 11 | Tin "hợp đồng", "đổi Pi lấy bất động sản", "đất nền" |
| banking → social | 5 | Nhóm "chuyển nhầm tiền, hoàn lại vào STK + ngân hàng" (câu hỏi mở ở `NHAT_KY_TANG2.md` mục 5) |

### 6.1 Quy tắc 1 gây phần lớn lỗi "tự tin"
- Tin **chỉ nêu ngân hàng nhận tiền** ("vào STK [NUMBER] ACB"): đúng 69,5%, so với 81,3% ở tin còn lại. Nhóm này chiếm 11% số tin nhưng
  17% số lỗi.
- **12 lỗi mà model rất tự tin (margin ≥ 1)**: 8 tin là khuôn "Hồ sơ vay/Khoản vay … nộp phí bảo hiểm vào TK + tên ngân hàng". Model
  tự tin đó là `loan_debt` (cũng là kịch bản "vay vốn giải ngân nhanh" mà định nghĩa xếp vào 3.2). Nhãn hiện tại là `banking_finance`
  vì quy tắc 1 tính cả tên ngân hàng của **tài khoản nhận tiền**.
- Kết hợp với thí nghiệm A3 (che tên ngân hàng nhận tiền không đổi điểm), kết luận là: tên ngân hàng nhận tiền **không** phải dấu hiệu
  mạo danh ngân hàng, cả về ý nghĩa lẫn với model.

### 6.2 Đề xuất (chờ người dùng quyết)
**Sửa quy tắc 1: chỉ tính ngân hàng/ví bị MẠO DANH (người gửi, ví dụ "[Vietcombank] Tài khoản của quý khách…"), không tính ngân hàng
của tài khoản nhận tiền.** Khi đó:
- Khuôn "Hồ sơ vay … nộp phí vào TK + ngân hàng" → `loan_debt`.
- Khuôn "chuyển nhầm tiền, hoàn lại vào STK + ngân hàng" → `other_scam` (người lạ, không mạo danh ai), trả lời luôn câu hỏi mở ở
  `NHAT_KY_TANG2.md` mục 5.
- Các khuôn đã gán theo kịch bản dù có STK + ngân hàng (ví dụ "phí kích hoạt hoa hồng … vào [NUMBER] (BIDV)" = `job_task_scam`,
  "thiếu cước … vào STK (ACB)" = `delivery_logistics`) giữ nguyên. Sửa quy tắc 1 làm nhãn **nhất quán** với các khuôn này.
- Chỉ đổi cột `scam_type`, nên tầng 1 không cần train lại. Tầng 2 phải chạy lại `train_tier2.py`.

Danh sách để rà: `reports/error_analysis/t2_confident_errors_review.csv` (12 tin) và `t2_oof_errors.csv` (105 tin, có cột `why_words`,
tức các từ đẩy về lớp sai).

### 6.3 Có dấu / không dấu
Tin không dấu đúng 84,8%, tin có dấu đúng 78,3%. Không có dấu hiệu tầng 2 yếu với tin không dấu. Lỗi kiểu "de, ho, vi" (từ không dấu
đa nghĩa) có xuất hiện nhưng ít.

## 7. Tầng 2 trên tin thật đợt 3 (T2-b)

Đợt 3 sau khi duyệt chỉ còn **9 tin** (7 khuôn mới, 2 khuôn đã có trong train); cách duyệt ở `data/review/vi_crawl_run3_reviewed.csv`.
Chạy lại `train_tier2.py` ngày 28/11: CV không đổi (SVM 79,5 ± 4,6 > NB 70,2 > CharCNN 61,3), vẫn chọn SVM.

| Tin (rút gọn) | Nhãn | Tầng 1 | Tầng 2 (SVM) |
|---|---|---|---|
| CSGT "Thông báo vi phạm giao thông… Điều 19…" | gov_utility | scam | ✅ gov_utility |
| CSGT "Phương tiện… csgt.bocongan.web.id" (khuôn đã biết) | gov_utility | scam | ✅ gov_utility |
| "Hóa đơn tiền điện… cúp điện trong 2 giờ" | gov_utility | ❌ **ham** | ✅ gov_utility |
| "Cục Thuế thông báo nợ thuế… cấm xuất cảnh" | gov_utility | scam | ✅ gov_utility |
| Techcombank "12.500 điểm thưởng" (khuôn đã biết) | banking | scam | ✅ banking |
| "Western Union TB: (MB BANK)… nhận tiền tại biolink…" | banking | scam | ✅ banking |
| "Giao dịch nạp tiền điện tử Ibanking… Mã OTP" | banking | scam | ❌ prize_lottery |
| Messenger "MoMo Pro" – bong bóng gói lợi nhuận | banking (quy tắc 1) | ❌ **ham** | investment |
| Messenger "MoMo Pro" – thông báo GÓI QUỸ LỢI NHUẬN | banking (quy tắc 1) | scam | investment |

- **Tầng 2: 6/9** (khuôn mới 4/7). **Cả chuỗi: 5/9.** Mẫu quá nhỏ để kết luận (khoảng tin cậy rộng); chỉ dùng để minh họa.
- 2 tin MoMo bị tính sai chỉ vì **quy tắc 1** (có tên ví → banking). Mô hình đoán `investment`, đúng với kịch bản "nạp vốn gói lợi nhuận".
  Đây là cùng vấn đề với mục 6.2. Nếu sửa quy tắc 1 thì tầng 2 đạt 8/9.
- Tầng 1 bỏ sót đúng 2 kiểu đã thấy ở mục 2: tin **không có link** (tiền điện) và tin chat giọng thân mật ("…anh nhé").

**Tầng 1 trên đợt 3** (`scripts/score_vi_crawl_full.py --input data/raw/vi_crawl_tier2_external.csv --out-dir reports/vi_crawl_run3`,
không train lại):

| Mô hình tầng 1 (song ngữ) | Tất cả (9) | Khuôn mới (7) | SMS (7) | Chat (2) |
|---|---|---|---|---|
| **SVM** (đã chọn) | **7/9** | **5/7** | 6/7 | 1/2 |
| Naive Bayes | 2/9 | 1/7 | 2/7 | 0/2 |
| CharCNN | 2/9 | **0/7** | 2/7 | 0/2 |

→ Kết quả lặp lại đúng xu hướng của đợt 1–2 (SVM 19/22 so với CharCNN 12/22 trên tin SMS khuôn mới): CharCNN chỉ bắt được tin cùng
khuôn đã thấy, **không bắt được tin khuôn mới nào**. Đây là thêm một bằng chứng cho lựa chọn SVM ở tầng 1.

**Gộp tin thật cả 3 đợt cho SVM song ngữ** (tập đầy đủ, mọi kênh): đợt 1–2 là 30/44, đợt 3 là 7/9, **tổng 37/53 (70%)**. Riêng SMS:
đợt 1–2 là 29/32, đợt 3 là 6/7, tổng **35/39 (90%)**. Chat (Zalo/Messenger): **2/14**.

## 8. Việc nên làm tiếp (theo thứ tự lợi ích)

1. **Người dùng quyết mục 6.2** (sửa quy tắc 1). Nếu đồng ý, agent áp nhãn và chạy lại tầng 2.
2. **Demo:** margin < 0,3 thì hiện "model phân vân" và 2 loại cao nhất ở tầng 2 (thành viên làm giao diện, dữ liệu đã có trong
   `scam_type_scores`).
3. **Báo cáo:** dùng bảng tóm tắt đầu tài liệu. Phát hiện 1, 2, 5 vào phần giới hạn; phát hiện 3, 4 vào phần đánh giá (chứng minh không
   có lối tắt nguy hiểm); phát hiện 7 vào phần demo.
4. Dữ liệu (nếu còn thời gian crawl): tin scam **không link** (yêu cầu gọi điện/chuyển khoản), tin giao dịch thật có link.
