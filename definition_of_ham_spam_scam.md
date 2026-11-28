# HỆ THỐNG PHÂN TẦNG KHÁI NIỆM VÀ QUY TẮC PHÂN LOẠI TIN NHẮN (HAM – SPAM – SCAM)

Tài liệu này cung cấp khung phân loại đa tầng (Hierarchical Taxonomy) dành cho bài toán phân loại tin nhắn 3 lớp (**Ham**, **Spam**, **Scam**), được tổng hợp từ các tiêu chuẩn viễn thông quốc tế, văn bản pháp lý Việt Nam và các bài báo khoa học chuyên ngành. Cấu trúc tài liệu được tối ưu hóa để làm **Cơ sở tri thức (Knowledge Base)** cho AI Agent thực hiện suy luận và gắn nhãn dữ liệu.

---

## 1. CƠ SỞ THAM CHIẾU HỌC THUẬT & QUY CHUẨN

Hệ thống phân tầng được xây dựng trên nền tảng các tài liệu sau:
1. **ITU-T Recommendation X.1240, X.1242 & Supplement 29:** Định nghĩa ranh giới kỹ thuật giữa *SMS Spam* (tin nhắn rác hàng loạt) và *Smishing / SMS Phishing* (tấn công lừa đảo qua tin nhắn).
2. **Almeida et al. (2011)** – *"Contributions to the Study of SMS Spam Filtering"*: Thiết lập định nghĩa chuẩn cho *Ham* và *SMS Spam* dựa trên tính chất đồng thuận (*opt-in*) và mục đích thương mại.
3. **Delany, Buckley, & Greene (2012)** – *"SMS spam filtering: Methods and data"* (dựa trên khung phân loại của Hiệp hội Di động Toàn cầu **GSMA**): Phân tách rõ nhóm *Premium Rate Fraud* (lừa đảo cước viễn thông/dịch vụ giá trị gia tăng) khỏi nhóm tấn công đánh cắp tài chính.
4. **Goel & Jain (2018)** – *"Smishing-Classifier: A Novel Framework for Detection of Smishing Attack"*: Xác định *Smishing* là tấn công kỹ thuật xã hội (*Social Engineering*) dựa trên mạo danh và thao túng tâm lý.
5. **Rahman et al. (2022)** – *"Users Really Do Respond To Smishing"*: Hệ thống hóa 3 cơ chế điều hướng hành vi của tin nhắn lừa đảo: **CLICK**, **REPLY**, và **CALL**.
6. **Nghị định 91/2020/NĐ-CP & Thông tư 22/2021/TT-BTTTT (Việt Nam):** Quy định tiêu chuẩn nhận diện tin nhắn quảng cáo hợp pháp (`[QC]` kèm cú pháp từ chối) và tin nhắn rác tại Việt Nam.

---

## 2. CÂY PHÂN TẦNG KHÁI NIỆM (HIERARCHICAL TAXONOMY)

### TẦNG 1: HAM (Tin nhắn hợp lệ / Legitimate Messages)
**Định nghĩa cốt lõi:** Là các thông điệp có nguồn gốc xác thực, nội dung minh bạch, phục vụ giao tiếp cá nhân hoặc thông báo dịch vụ mà người dùng đã chủ động đăng ký/đồng thuận (*Opt-in*) trước đó, không chứa yếu tố lừa dối hay gây hại.

* **1.1. Giao tiếp cá nhân (Person-to-Person – P2P):**
  * *Đặc điểm:* Tin nhắn trao đổi thông thường giữa người thân, bạn bè, đồng nghiệp, đối tác.
  * *Dấu hiệu:* Ngôn ngữ tự nhiên, ngữ cảnh cá nhân hóa, số điện thoại di động thông thường (10 số), không chứa lời kêu gọi hành động (CTA) mang tính thương mại hàng loạt hay đường dẫn lạ.
* **1.2. Thông báo hệ thống & Giao dịch xác thực (Legitimate A2P / Transactional):**
  * *Đặc điểm:* Tin nhắn tự động gửi từ tổ chức uy tín (Ngân hàng, Ví điện tử, Nhà mạng, Sàn TMĐT, Cơ quan hành chính) để thông báo trạng thái giao dịch mà người dùng vừa thực hiện.
  * *Dấu hiệu:* Gửi từ định danh chính thức (*Brandname* đã đăng ký như `Vietcombank`, `VIETTEL`, `Shopee`), nội dung thuần túy thông báo (mã OTP, biến động số dư, trạng thái đơn hàng, cước phí), **tuyệt đối không** kèm đường link yêu cầu đăng nhập lại để hủy giao dịch hoặc xác minh tài khoản.
* **1.3. Tin nhắn quảng cáo hợp chuẩn (Opt-in Promotional Messages):**
  * *Đặc điểm:* Tin nhắn tiếp thị từ doanh nghiệp/nhà mạng gửi tới khách hàng đã đồng ý nhận tin, tuân thủ đầy đủ quy định pháp luật (Nghị định 91/2020/NĐ-CP).
  * *Dấu hiệu:* Bắt đầu bằng nhãn `[QC]` hoặc `(QC)`, gửi từ Brandname/đầu số hợp lệ và **bắt buộc có hướng dẫn từ chối nhận tin** ở cuối (ví dụ: `Tu choi QC, soan TC gui xxxx`).

---

### TẦNG 2: SPAM (Tin nhắn rác / Unsolicited Bulk Messaging)
**Định nghĩa cốt lõi:** Là các thông điệp không mong muốn được phát tán tự động với số lượng lớn nhằm mục đích quảng cáo thương mại, tiếp thị dịch vụ hoặc thu lợi từ cước phí viễn thông (VAS), **không** nhằm mục đích xâm nhập tài khoản ngân hàng, đánh cắp mật khẩu/OTP hay cài mã độc lên thiết bị người nhận.

* **2.1. Quảng cáo thương mại không mong muốn (Unsolicited Commercial Spam):**
  * *Đặc điểm:* Mời chào mua hàng, sử dụng dịch vụ (bất động sản, sim số đẹp, bảo hiểm, cho vay tín chấp, thẩm mỹ, khóa học) gửi từ các SIM rác (số di động 10 số) mà người nhận chưa từng đăng ký.
  * *Dấu hiệu:* Thiếu nhãn `[QC]`, không có cú pháp từ chối, chứa số điện thoại liên hệ trực tiếp hoặc lời mời chào giảm giá/ưu đãi thương mại.
* **2.2. Tin nhắn bẫy cước viễn thông & Dịch vụ giá trị gia tăng (Premium Rate / VAS Traps):**
  * *Cơ sở học thuật:* Phân loại theo nhóm *Premium Rate Fraud* của GSMA / Delany et al. (2012).
  * *Đặc điểm:* Sử dụng thủ thuật câu dẫn nhẹ (núp bóng thông báo hệ thống hoặc khơi gợi tò mò) để dụ người dùng tự nguyện nhắn tin tới các đầu số dịch vụ giá trị gia tăng (`8xxx`, `6xxx`, `7xxx`) hoặc gọi tới tổng đài tính phí cao (`1900xxxx`).
  * *Dấu hiệu:* Nội dung kiểu *"Thuê bao của bạn được tặng data, soạn DK gửi 88xx"*, *"Bạn có lời nhắn thoại, gọi 1900xxxx để nghe"*. Mục tiêu cuối cùng là trừ tiền tài khoản gốc điện thoại hoặc đăng ký gói cước tự động gia hạn, **không** đánh cắp dữ liệu cá nhân hay tài khoản ngân hàng.
* **2.3. Tin phát tán hàng loạt phi thương mại / Tin chuỗi (Chain Messages & Hoaxes):**
  * *Đặc điểm:* Các tin nhắn kêu gọi chuyển tiếp hàng loạt (tin đồn thất thiệt, bói toán, lời chúc sao chép hàng loạt) gây phiền nhiễu tài nguyên mạng nhưng không gắn kèm đường dẫn lừa đảo hay yêu cầu chuyển tiền.

---

### TẦNG 3: SCAM (Tin nhắn lừa đảo / Smishing & SMS Fraud)
**Định nghĩa cốt lõi:** Là hình thức tấn công kỹ thuật xã hội (*Social Engineering*) sử dụng tin nhắn làm phương tiện truyền tải kịch bản giả mạo có chủ đích (*Deception*), khai thác tâm lý sợ hãi, khẩn cấp hoặc lòng tham để điều hướng nạn nhân thực hiện hành vi nhằm **chiếm đoạt tài sản trực tiếp**, **đánh cắp thông tin định danh (OTP, mật khẩu, CCCD)** hoặc **cài đặt phần mềm độc hại (Malware)**.

* **3.1. Giả mạo tổ chức & Mạo danh thương hiệu (Brand & Authority Spoofing):**
  * *Đặc điểm:* Giả mạo ngân hàng, cơ quan nhà nước (Công an, Thuế, Điện lực, Tòa án), hoặc đơn vị giao vận để tạo kịch bản khẩn cấp/đe dọa.
  * *Dấu hiệu:* Kịch bản báo *"Tài khoản phát sinh giao dịch lạ/bị khóa"*, *"Thông báo phạt nguội"*, *"Cập nhật sinh trắc học/VNeID"*, *"Đơn hàng giao thất bại"*, đi kèm đường dẫn (URL) giả mạo có tên miền gần giống thương hiệu thật (*Typosquatting*, ví dụ: `vcb-digibank-vn.com`, `dichvucong-gov.xyz`).
* **3.2. Lừa đảo tài chính & Việc làm ảo (Financial & Task Scams):**
  * *Đặc điểm:* Đánh vào lòng tham hoặc nhu cầu kiếm tiền nhanh để dẫn dụ nạn nhân sang các nền tảng nhắn tin khác (Zalo, Telegram) hoặc website lừa đảo nhằm chiếm đoạt tiền nạp/tiền đặt cọc.
  * *Dấu hiệu:* Kịch bản *"Tuyển CTV chốt đơn Shopee/Lazada tại nhà lương 300k-500k/ngày"*, *"Hỗ trợ vay vốn giải ngân nhanh không cần thế chấp qua link..."*, *"Mời tham gia nhóm kéo lợi nhuận đầu tư"*.
* **3.3. Lừa đảo trúng thưởng & Quà tặng giả (Prize / Lottery Scams):**
  * *Đặc điểm:* Thông báo nạn nhân trúng giải thưởng có giá trị lớn (xe máy, điện thoại, tiền mặt) từ các chương trình không có thật.
  * *Dấu hiệu:* Yêu cầu truy cập đường dẫn lạ để điền thông tin tài khoản ngân hàng nhận thưởng, hoặc yêu cầu chuyển khoản trước một khoản "phí hồ sơ / thuế thu nhập cá nhân" để nhận giải.
* **3.4. Phát tán mã độc chiếm quyền điều khiển (Malware / Spyware Delivery):**
  * *Đặc điểm:* Dẫn dụ người dùng tải và cài đặt tệp tin thực thi độc hại lên điện thoại thông minh (thường nhắm vào hệ điều hành Android).
  * *Dấu hiệu:* Kèm đường dẫn trực tiếp tới tệp cài đặt (`.apk`) hoặc trang web giả mạo kho ứng dụng yêu cầu tải ứng dụng cập nhật dịch vụ công, ngân hàng, thanh toán tiền điện để chiếm quyền đọc tin nhắn OTP và điều khiển thiết bị từ xa.

---

## 3. MA TRẬN ĐẶC TRƯNG NHẬN DIỆN CHO AI AGENT (SIGNAL MATRIX)

Agent cần trích xuất và đối chiếu 5 nhóm tín hiệu sau trước khi đưa ra quyết định phân loại:

| Nhóm tín hiệu | HAM | SPAM | SCAM (Smishing) |
| :--- | :--- | :--- | :--- |
| **1. Định danh người gửi (Sender)** | Số cá nhân quen thuộc hoặc Brandname chính chủ hợp lệ. | SIM rác (10 số), đầu số dịch vụ (`8xxx`, `1900`), Brandname quảng cáo. | SIM rác, Brandname giả mạo (trạm BTS giả), hoặc số quốc tế/lạ. |
| **2. Đòn bẩy tâm lý (Psychological Trigger)** | Trung tính, thông tin thực tế theo ngữ cảnh. | Hấp dẫn thương mại (giảm giá, khuyến mãi) hoặc tò mò nhẹ. | **Sợ hãi/Khẩn cấp** (khóa TK, phạt nguội) hoặc **Lòng tham** (việc nhẹ lương cao, trúng thưởng lớn). |
| **3. Hành động mục tiêu (Rahman et al., 2022)** | Không yêu cầu hoặc chỉ xác nhận giao dịch nội bộ an toàn. | Đọc tin quảng cáo, gọi/nhắn đầu số dịch vụ viễn thông (`1900`, `8xxx`). | **CLICK** (link giả/tải APK), **REPLY** (gửi OTP/thông tin), **CALL/ADD** (liên hệ Zalo/Telegram kẻ gian). |
| **4. Phân tích liên kết (URL / Payload)** | Không có link, hoặc link thuộc tên miền chính thức cấp 1 của tổ chức. | Link giới thiệu sản phẩm thương mại thông thường (hiếm gặp trong SMS). | Link rút gọn (`bit.ly`, `tinyurl`), tên miền lạ (`.xyz`, `.top`, `.vip`), tên miền nhái thương hiệu, file `.apk`. |
| **5. Kỹ thuật lách bộ lọc (Obfuscation)** | Văn phong tự nhiên hoặc chuẩn mẫu thông báo hệ thống. | Viết tắt, chèn ký tự đặc biệt (`*`, `.`) giữa từ khóa (`v.a.y`, `b.a.n d.a.t`). | Cố tình viết sai chính tả từ khóa nhạy cảm (`t.à.i k.h.o.ả.n`, `l1nk`, `0TP`) để né bộ lọc nhà mạng. |

---

## 4. CÂY QUYẾT ĐỊNH & QUY TẮC XỬ LÝ VÙNG GIAO THOA (DECISION LOGIC)

Để tránh nhầm lẫn ở các trường hợp biên (Edge Cases), AI Agent phải thực thi chuỗi kiểm tra theo thứ tự ưu tiên từ trên xuống dưới:

### Bước 1: Kiểm tra yếu tố Lừa đảo / Chiếm đoạt (Ưu tiên cao nhất -> SCAM)
* **Câu hỏi:** Tin nhắn có chứa **ít nhất một** trong các yếu tố sau không?
  1. Đường dẫn (URL) lạ, link rút gọn, tên miền nhái thương hiệu/cơ quan nhà nước, hoặc liên kết tải tệp `.apk`.
  2. Mạo danh ngân hàng, cơ quan công quyền, sàn TMĐT để cảnh báo rủi ro khẩn cấp (khóa tài khoản, giao dịch lạ, phạt nguội) nhằm điều hướng người dùng thao tác bên ngoài.
  3. Mời chào việc làm online tại nhà ("chốt đơn", "tăng tương tác"), trúng thưởng giá trị lớn, hoặc yêu cầu cung cấp mã OTP, mật khẩu, chuyển tiền đặt cọc.
* **Kết luận:** Nếu **CÓ** $\rightarrow$ Gắn nhãn **`SCAM`**. (Dừng kiểm tra).

### Bước 2: Kiểm tra yếu tố Quảng cáo rác & Bẫy cước viễn thông (-> SPAM)
* **Câu hỏi:** Nếu không phải SCAM, tin nhắn có thuộc một trong các trường hợp sau không?
  1. Mời chào mua bán sản phẩm, dịch vụ (bất động sản, sim số, vay vốn, bảo hiểm...) từ số lạ và **không** có nhãn `[QC]` kèm cú pháp từ chối hợp lệ.
  2. Dụ người dùng nhắn tin tới đầu số dịch vụ (`8xxx`, `6xxx`, `7xxx`) hoặc gọi tổng đài tính phí (`1900`) bằng kịch bản câu dẫn (*"nhận data miễn phí"*, *"nghe lời nhắn thoại"*).
  3. Tin nhắn chuỗi phát tán hàng loạt không rõ nguồn gốc, mang tính làm phiền.
* **Kết luận:** Nếu **CÓ** $\rightarrow$ Gắn nhãn **`SPAM`**. (Dừng kiểm tra).

### Bước 3: Xác nhận tính hợp lệ (-> HAM)
* **Câu hỏi:** Tin nhắn là giao tiếp cá nhân thông thường, HOẶC là thông báo giao dịch/OTP chính chủ (không kèm link lừa đảo), HOẶC là tin nhắn quảng cáo từ Brandname có đầy đủ nhãn `[QC]` và cú pháp từ chối hợp pháp?
* **Kết luận:** Nếu **CÓ** $\rightarrow$ Gắn nhãn **`HAM`**.

---

## 5. BỘ VÍ DỤ CHUẨN HÓA CHO AGENT (FEW-SHOT EXAMPLES)

Dưới đây là tập mẫu chuẩn hóa để huấn luyện hoặc đưa vào ngữ cảnh (In-context Learning) cho Agent:

1. **Input:** `"Chieu nay 5h hop nhom do an o thu vien nhe, nho mang theo laptop."`
   * **Label:** `HAM` | **Sub-type:** `1.1. Giao tiếp cá nhân (P2P)`
   * **Reasoning:** Ngôn ngữ giao tiếp tự nhiên giữa cá nhân với nhau, không mang tính chất thương mại hay lừa đảo.

2. **Input:** `"[VCB] SD TK 001100xxxx -500,000 VND luc 14:20 24/11/2026. SD hien tai 12,450,000 VND. Ref: Chuyen tien an trua."`
   * **Label:** `HAM` | **Sub-type:** `1.2. Thông báo giao dịch xác thực`
   * **Reasoning:** Thông báo biến động số dư thuần túy từ ngân hàng, không chứa đường link lạ hay yêu cầu xác minh thông tin nhạy cảm.

3. **Input:** `"[QC] Viettel tang ban uu dai goi ST90K co ngay 30GB data/thang. De dang ky soan ST90K gui 191. Tu choi QC, soan TC gui 199."`
   * **Label:** `HAM` | **Sub-type:** `1.3. Quảng cáo hợp chuẩn (Opt-in)`
   * **Reasoning:** Tuân thủ Nghị định 91/2020/NĐ-CP với nhãn `[QC]`, đầu số chính thức (`191`) và cú pháp từ chối hợp lệ (`TC gui 199`).

4. **Input:** `"Mo ban dot cuoi can ho cao cap Quan 7, chiet khau len den 12%, ho tro lai suat 0%. Lien he PKD: 0908xxxxxx de xem nha mau."`
   * **Label:** `SPAM` | **Sub-type:** `2.1. Quảng cáo thương mại không mong muốn`
   * **Reasoning:** Tin nhắn tiếp thị bất động sản gửi hàng loạt không có sự đồng ý trước, thiếu nhãn `[QC]` và cú pháp từ chối, nhưng không nhằm chiếm đoạt tài khoản hay đánh cắp dữ liệu.

5. **Input:** `"Thue bao cua quy khach dang co 01 loi nhan thoai quan trong tu nguoi than. Goi ngay 19008xxx hoac soan LN gui 8777 de nghe lai."`
   * **Label:** `SPAM` | **Sub-type:** `2.2. Bẫy cước viễn thông (VAS Trap)`
   * **Reasoning:** Mặc dù dùng kịch bản gây tò mò ("có lời nhắn thoại"), nhưng mục tiêu thực chất là dụ người dùng gọi `1900` hoặc nhắn đầu số `8777` để trừ cước viễn thông, không kèm link độc hại hay đánh cắp tài khoản ngân hàng.

6. **Input:** `"TUYEN CTV chot don Lazada tai nha, khong can von, thu nhap 300k-500k/ngay. Lien he Zalo 038xxxxxxx de nhan viec ngay."`
   * **Label:** `SCAM` | **Sub-type:** `3.2. Lừa đảo tài chính & Việc làm ảo`
   * **Reasoning:** Mạo danh thương hiệu Lazada, đánh vào lòng tham ("việc nhẹ lương cao tại nhà") và điều hướng nạn nhân sang Zalo để thực hiện kịch bản lừa đảo nạp tiền chiếm đoạt tài sản.

7. **Input:** `"[Techcombank] Tai khoan cua quy khach vua phat sinh giao dich 18.500.000 VND tai nuoc ngoai. Neu khong phai ban thuc hien, truy cap ngay tcb-xacminh-vn.com de huy giao dich."`
   * **Label:** `SCAM` | **Sub-type:** `3.1. Giả mạo tổ chức / Phishing`
   * **Reasoning:** Mạo danh ngân hàng, tạo tâm lý hoảng loạn khẩn cấp và dẫn dụ người dùng nhấp vào tên miền giả mạo (`tcb-xacminh-vn.com`) nhằm đánh cắp thông tin đăng nhập và mã OTP.