# Tư liệu báo cáo – Che thông tin trong tin nhắn (`[MONEY]`, `[NAME]`, `[NUMBER]`…)

Soạn 28/11/2026 để dùng cho mục **"Tiền xử lý dữ liệu"** của báo cáo. Gồm: đồ án đã che những gì, vì sao che (3 lý do, mỗi lý do
có căn cứ), số liệu nhóm tự đo, và danh sách tài liệu tham khảo.

> ⚠️ Các nghiên cứu bên dưới được tra qua tóm tắt và kết quả tìm kiếm, **chưa đọc toàn văn**. Trước khi trích dẫn, mở link để lấy đúng
> tên tác giả, năm và nội dung (đặc biệt bài Georgetown ở mục 3.3).

---

## 1. Đồ án đã che những gì

| Ký hiệu | Thay cho | Ví dụ |
|---|---|---|
| `[MONEY]` | Số tiền | "nộp phí [MONEY] để giải ngân" |
| `[NUMBER]` | Số điện thoại, số tài khoản, mã số dài | "chuyển vào STK [NUMBER] Vietcombank" |
| `[DATE]`, `[TIME]` | Ngày, giờ | "trước [TIME] hôm nay" |
| `[NAME]` | Tên người, tên tài khoản cá nhân | "Anh/Chị [NAME] không tự giác thanh toán" |
| `<URL>`, `<PHONE>`, `<EMAIL>`, `<NUMBER>`, `<DATE_TIME>` | (dữ liệu tiếng Anh) link, số điện thoại, email, số, ngày giờ | "Verify at `<URL>`" |

- **Đường link tiếng Việt được giữ nguyên**, không che, vì tên miền là dấu hiệu quan trọng (`vcb-xacminh.top` khác `vietcombank.com.vn`).
  Phân tích lỗi cho thấy mô hình phân biệt được tên miền lạ và tên miền chính thống (`docs/PHAN_TICH_LOI.md` mục 3).
- **Tập Tuấn (dữ liệu gốc) đã che sẵn:** `[MONEY]` hơn 3.000 lần, `[NUMBER]` hơn 2.400 lần, `[NAME]` 141 lần. Một số tên vẫn còn sót (ví dụ "chủ TK HÙNG").
- **Tin crawl:** crawler tự che `[MONEY]`, `[NUMBER]`, `[DATE]`, `[TIME]` bằng cùng quy tắc với tập Tuấn (hàm `mask_pii`). Crawler **không** tự che tên,
  và bỏ sót số tiền viết hoa ("ĐỒNG"), nên phải che tay khi duyệt.
- **Lúc dùng thật (demo):** tin tiếng Việt người dùng nhập được che số bằng hàm `mask_vi` (bản sao đúng của `mask_pii`, có test kiểm tra hai hàm
  cho cùng kết quả) trước khi đưa vào mô hình, để khớp với dữ liệu train.

---

## 2. Che và không che – so sánh

| | **Che** | **Không che** |
|---|---|---|
| Khớp với dữ liệu train | ✅ Mô hình đã học token `[MONEY]` từ hàng nghìn tin | ❌ "3.888.000 ĐỒNG" là chuỗi chưa từng gặp, không giúp được gì |
| Độ chính xác (nhóm tự đo, mục 4) | ✅ Tin vay tiền che số → báo **scam** | ❌ Cùng tin để số thật → đoán **ham** |
| Học vẹt | ✅ Không bám vào một con số / cái tên cụ thể | ❌ Có thể học "3.888.000" như dấu hiệu; kẻ gian đổi số là hết tác dụng |
| Quyền riêng tư | ✅ Không phát tán tên, tài khoản của người thật | ❌ Lộ thông tin cá nhân của nạn nhân trong bài báo |
| Mất thông tin | ⚠️ Mất độ lớn số tiền (500 nghìn hay 50 triệu) – gần như không ảnh hưởng bài toán | ✅ Giữ đủ |

**Kết luận:** nên che. Lý do chính là **đồng bộ với dữ liệu train**; quyền riêng tư là lợi ích phụ nhưng quan trọng khi nộp dataset.

---

## 3. Căn cứ từ các nghiên cứu

### 3.1 Lý do 1 – Quyền riêng tư
**Lison, Pilán, Sánchez, Batet, Øvrelid (2021). "Anonymisation Models for Text Data: State of the art, Challenges and Future Directions".
ACL-IJCNLP 2021, tr. 4188–4203. DOI 10.18653/v1/2021.acl-long.323.**
- Bài tổng quan về ẩn danh hóa văn bản tự động: muốn chia sẻ văn bản chứa thông tin về người thật thì phải ẩn danh trước.
- Nêu thách thức là cân bằng giữa **rủi ro lộ thông tin** và **mức độ hữu ích của dữ liệu**.
- **Áp dụng:** tin crawl từ báo có tên và tài khoản của nạn nhân thật → che trước khi đưa vào dataset nộp kèm báo cáo.

### 3.2 Lý do 2 – Chống học lối tắt, đồng bộ giữa các nguồn
**Geirhos, Jacobsen, Michaelis, Zemel, Brendel, Bethge, Wichmann (2020). "Shortcut learning in deep neural networks".
Nature Machine Intelligence 2(11), 665–673. DOI 10.1038/s42256-020-00257-z.**
- Mô hình hay học một **dấu hiệu dễ nhưng không đúng ý** (lối tắt). Nó chạy tốt trên dữ liệu quen thuộc nhưng hỏng khi gặp dữ liệu khác.
- **Áp dụng – hai lối tắt nhóm đã phát hiện trong đồ án:**
  1. **"Có dấu = scam":** khi chỉ train trên tập Tuấn, mô hình báo nhầm **24%** tin nhắn thật. Thêm tin cá nhân thật (`vie_sms`) → còn 0,1%.
  2. **"Ít chữ số = scam":** đặc trưng "số chữ số" thực ra đo **cách che của từng nguồn**: tin Tuấn che số (scam trung bình 1,7 chữ số),
     `vie_sms` để số thật (spam trung bình 25,0 chữ số). Dùng nguyên đặc trưng này, mô hình sẽ học nguồn dữ liệu chứ không học lừa đảo.
- → Che **đồng bộ** giữa các nguồn là cách chặn loại lối tắt này.

### 3.3 Lý do 3 – Che là cách xử lý thông dụng khi lọc tin rác SMS
- Bài lọc spam SMS của **Đại học Georgetown** trên bộ dữ liệu của Cormack và cộng sự: **thay mọi con số bằng ký hiệu chung** để xử lý số
  một cách nhất quán. ⚠️ Cần mở PDF để lấy đúng tên tác giả và năm.
- **"On Detecting Messaging Abuse in Short Text Messages using Linguistic and Behavioral patterns"** (arXiv 1408.3934): tin rác thường dùng link
  hoặc số điện thoại làm lời kêu gọi hành động; bài thử chuẩn hóa văn bản khi tách từ.
- **"Machine Learning Driven Smishing Detection Framework for Mobile Security"** (arXiv 2412.09641): chuẩn hóa giúp giảm độ đa dạng của
  ngôn ngữ SMS (viết tắt, tiếng lóng).
- Trong chính dữ liệu đồ án dùng: tập Tuấn đã che sẵn `[MONEY]`, `[NUMBER]`, `[NAME]`; tài liệu của SmishX che một phần link bằng "xxx".

### 3.4 Che có làm giảm độ chính xác không – thường là không đáng kể
Văn bản y tế bắt buộc phải ẩn danh, nên lĩnh vực này có nhiều nghiên cứu đo ảnh hưởng:
- **Vakili & Dalianis (BioNLP 2022), "Utility Preservation of Clinical Text After De-Identification":** ẩn danh hóa không làm giảm độ hữu ích
  của dữ liệu cho các bài toán NLP.
- **Baumgartner và cộng sự (2022), "Impact Analysis of De-Identification in Clinical Notes Classification"** (PubMed 35592981):
  mô hình phân loại **đơn giản** gần như không bị ảnh hưởng; mô hình nhạy hơn thì giảm một ít.
- **Nghiên cứu ghi chú khoa cấp cứu (PMC6779034):** độ chính xác khoảng 95% trên cả bản gốc lẫn bản đã ẩn danh.
- **Áp dụng:** đồ án dùng Linear SVM, một mô hình đơn giản → đúng với trường hợp ít bị ảnh hưởng.

---

## 4. Số liệu nhóm tự đo (bằng chứng mạnh nhất)

Đo trên đúng dữ liệu và đúng bài toán của đồ án (`docs/NHAT_KY_TANG2.md` mục 8.2, tầng 1 = Linear SVM song ngữ).

**Cùng một tin, che và không che:**

| Tin nhập | Không che số | Che số |
|---|---|---|
| "Ho so vay 50 trieu da duyet, vui long nop phi bao hiem 2 trieu de giai ngan" | **ham** ❌ | **scam** ✅ |

Lý do: mọi tin scam tiếng Việt lúc train đều đã che số, nên mô hình chỉ nhận ra kịch bản khi tin được viết theo cùng cách.

**Trên tin thật `vie_sms` (holdout):**

| | Không che | Che |
|---|---|---|
| Tin bình thường bị báo scam | 1,03% | 1,03% |
| Spam được nhận ra | 76,2% | 57,5% |

- Che số **không làm tăng báo nhầm**.
- Cái giá: spam bị đoán thành ham nhiều hơn. Nhóm vẫn chọn che vì tầng 1 **ưu tiên không bỏ sót scam**; spam bị đoán là ham ít nguy hiểm hơn.
- Đây là một **đánh đổi có đo đạc**, nên trình bày đúng như vậy trong báo cáo.

---

## 5. Gợi ý đoạn văn cho báo cáo

> **Che thông tin.** Số tiền, số điện thoại, số tài khoản, ngày giờ và tên người được thay bằng ký hiệu chung (`[MONEY]`, `[NUMBER]`,
> `[DATE]`, `[TIME]`, `[NAME]`), giống cách tập dữ liệu gốc của Tuấn đã làm; riêng đường link được giữ nguyên vì tên miền là dấu hiệu
> lừa đảo quan trọng. Việc che nhằm ba mục đích. (1) Bảo vệ thông tin cá nhân của người thật trong dữ liệu thu thập từ báo chí
> (Lison et al., 2021). (2) Đồng bộ cách viết giữa các nguồn dữ liệu để mô hình không học lối tắt theo nguồn (Geirhos et al., 2020);
> nhóm đã gặp hai lối tắt như vậy: "có dấu = scam" và "ít chữ số = scam". (3) Giúp mô hình nhận ra kịch bản thay vì nhớ con số cụ thể.
> Các nghiên cứu về ẩn danh văn bản y tế cho thấy việc che gần như không làm giảm độ chính xác của mô hình phân loại đơn giản
> (Vakili & Dalianis, 2022; Baumgartner et al., 2022). Đo trên dữ liệu của đồ án, che số không làm tăng tỉ lệ báo nhầm (1,03% ở cả hai
> trường hợp) và giúp mô hình nhận ra tin lừa đảo viết với số thật; đổi lại, tỉ lệ nhận ra spam giảm từ 76,2% xuống 57,5%, một đánh đổi
> nhóm chấp nhận vì ưu tiên không bỏ sót tin lừa đảo.

---

## 6. Che không đồng đều giữa các nguồn – đã kiểm tra gì

Dữ liệu gộp nhiều nguồn, mỗi tác giả xử lý khác nhau nên **không phải chỗ nào cũng được che**. Nguyên tắc nhóm dùng:
**không cần che 100%, nhưng việc che không được lệch theo nhãn**, nếu không mô hình sẽ học "có ký hiệu che = scam".

Tỉ lệ tin có ký hiệu che trong dữ liệu tầng 1 (`data/processed_bilingual/modeling_data.csv`):

| Nguồn | Nhãn | `[NAME]` | `[MONEY]` | `[NUMBER]` |
|---|---|---|---|---|
| Tuấn (train) | ham / spam / scam | 7,2% / 1,6% / 3,0% | 74,6% / 33,5% / 28,8% | 56,6% / 28,6% / 15,0% |
| Tuấn (test) | ham / spam / scam | 2,5% / 1,4% / 7,7% | 45,8% / 84,1% / 58,7% | 66,3% / 86,2% / 69,2% |
| `vie_sms` (dev + holdout) | ham / spam | 0% / 0% | 0% / 0% | 0% / 0% |

- **`[NAME]`:** tỉ lệ thấp, có ở cả 3 nhãn → không thành lối tắt. Tên người là từ hiếm, phần lớn bị TF-IDF bỏ qua (`min_df=2`).
  Che tên chủ yếu vì quyền riêng tư (bắt buộc với tin crawl về người thật).
- **`[MONEY]`, `[NUMBER]` trong tập Tuấn:** che ở cả 3 nhãn, tin ham còn được che nhiều hơn tin scam → token `[MONEY]` không có nghĩa là scam.
- **Giữa hai nguồn thì lệch:** tập Tuấn che số, `vie_sms` (công bố năm 2015) để số thật. Mọi tin scam tiếng Việt đều từ tập Tuấn,
  `vie_sms` không có tin scam → mô hình có xu hướng học **"có số thật → không phải scam"**. Đã đo được (mục 4): tin vay tiền để số thật → ham.
- **Cách xử lý hiện tại:** khi dùng thật (demo), mọi tin tiếng Việt được **che số trước khi đưa vào mô hình** (`mask_vi`) → đầu vào luôn
  giống dữ liệu train. Cái giá đã đo: báo nhầm không đổi (1,03%), nhận ra spam giảm 76,2% → 57,5%.
- **Cách sửa triệt để (hướng cải tiến):** che số luôn các tin `vie_sms` trong dữ liệu train bằng cùng quy tắc, rồi train lại tầng 1.
  _Trạng thái: chưa làm (28/11). Nếu làm, cập nhật số liệu trước/sau vào đây._

---

## 7. Câu trả lời khi bảo vệ

Nguyên tắc: **thẳng thắn, rồi chứng minh bằng số liệu**, theo trình tự *phát hiện → đo → xử lý → còn lại gì*. Không nói "dữ liệu đã
được che toàn bộ" khi thực tế chưa phải vậy; bị hỏi vặn thì mất điểm hơn là thừa nhận ngay từ đầu.

**Câu hỏi: "Sao dữ liệu chỗ che chỗ không?"** (khoảng 1 phút)

> Dạ, dữ liệu của nhóm gộp từ nhiều nguồn, mỗi tác giả có cách xử lý riêng: tập của Tuấn đã che sẵn số tiền, số điện thoại, tên người;
> tập `vie_sms` (công bố năm 2015) thì để nguyên. Nhóm không che lại toàn bộ, nhưng đã kiểm tra một nguyên tắc: **việc che không được
> lệch theo nhãn**, nếu không mô hình sẽ học "có ký hiệu che thì là lừa đảo".
>
> - Với **tên người**, tỉ lệ che thấp và có ở cả ba nhãn, nên không ảnh hưởng.
> - Với **số tiền và số điện thoại**, nhóm phát hiện một lệch giữa hai nguồn: mọi tin lừa đảo tiếng Việt đều đến từ tập đã che, nên
>   mô hình có xu hướng coi "tin có số thật" là tin bình thường. Nhóm đã đo được: cùng một tin vay tiền, để số thật thì bị đoán là bình
>   thường, che số thì được báo lừa đảo.
>
> Vì vậy khi dùng thật, hệ thống **che số mọi tin tiếng Việt trước khi đưa vào mô hình**, để đầu vào luôn giống dữ liệu train. Nhóm cũng
> đo cái giá: tỉ lệ báo nhầm không tăng (1,03%), nhưng tỉ lệ nhận ra tin rác giảm từ 76% xuống 58%. Nhóm chấp nhận đánh đổi này vì
> ưu tiên không bỏ sót tin lừa đảo.

**Hỏi tiếp: "Sao không che lại toàn bộ cho đồng bộ?"**
> Dạ, đó là hướng cải tiến nhóm đã xác định: che luôn tập `vie_sms` theo cùng quy tắc rồi train lại tầng 1. Nhóm ưu tiên hoàn thành hệ
> thống và đo được vấn đề trước. *(Nếu đã làm: "Kết quả sau khi sửa là …". Nếu chưa: "Phần này nhóm ghi vào hướng phát triển.")*

**Hỏi tiếp: "Làm sao biết việc che không làm sai kết quả?"**
> Nhóm kiểm tra theo hai cách: đếm tỉ lệ có ký hiệu che theo từng nhãn và từng nguồn (mục 6), và thử cùng một tin ở hai dạng che /
> không che rồi so dự đoán (mục 4). Các nghiên cứu về ẩn danh văn bản y tế cũng cho thấy che gần như không làm giảm độ chính xác của
> mô hình đơn giản như SVM (Vakili & Dalianis, 2022; Baumgartner et al., 2022).

**Hỏi tiếp: "Có lối tắt nào khác không?"**
> Dạ có, nhóm phát hiện thêm hai: "có dấu là lừa đảo", làm mô hình báo nhầm 24% tin thật, đã sửa bằng cách thêm tin nhắn cá nhân thật
> vào train; và đặc trưng "số chữ số" thực ra đo cách che của từng nguồn, nên nhóm quyết định không dùng.

**Luôn kèm con số:** 1,03%; 76% → 58%; ví dụ tin vay tiền; 24% → 0,1%.

---

## 8. Tài liệu tham khảo (link)

- Lison et al. 2021 – ACL Anthology: https://www.aclanthology.org/2021.acl-long.323
- Geirhos et al. 2020 – Nature Machine Intelligence: https://link.springer.com/article/10.1038/s42256-020-00257-z · arXiv: https://arxiv.org/abs/2004.07780
- SMS Spam Detection – Georgetown (PDF): https://ir.cs.georgetown.edu/downloads/pp052-SMS-SpamDetection-camera-ready.pdf
- On Detecting Messaging Abuse in Short Text Messages (arXiv 1408.3934): https://ar5iv.arxiv.org/html/1408.3934
- Machine Learning Driven Smishing Detection Framework (arXiv 2412.09641): https://arxiv.org/html/2412.09641v1
- Baumgartner et al. 2022 – PubMed: https://www.pubmed.gov/35592981/
- De-identification in emergency department notes – PMC6779034: https://pmc.ncbi.nlm.nih.gov/articles/PMC6779034
- Vakili & Dalianis – Utility Preservation of Clinical Text After De-Identification (PDF):
  https://www.digitalfutures.kth.se/wp-content/uploads/2024/12/Utility-Preservation-of-Clinical-Text-After-De-Identification.pdf
