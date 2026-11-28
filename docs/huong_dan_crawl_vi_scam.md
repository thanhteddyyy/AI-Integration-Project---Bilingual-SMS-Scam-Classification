# Hướng dẫn crawl tin nhắn lừa đảo tiếng Việt – v2 (bổ sung External Test)

Script: [`scripts/crawl_vi_scam.py`](../scripts/crawl_vi_scam.py)
Notebook Kaggle: [`notebooks/crawl_vi_scam_kaggle.ipynb`](../notebooks/crawl_vi_scam_kaggle.ipynb)
(sinh lại bằng `python scripts/make_crawl_notebook.py` mỗi khi sửa script)

> **Mục đích:** thu thập tin nhắn lừa đảo **thật** được trích trong các bài cảnh báo trên báo
> điện tử, dùng **chỉ cho tập external test** tiếng Việt (sau v3 hiện có 0 tin scam).
> Không đưa dữ liệu này vào train. Mục tiêu: ~200–400 ứng viên → ≥100 tin dùng được.
>
> **Về yêu cầu đồ án:** EasyOCR chỉ là **công cụ gõ hộ** khi thu thập dữ liệu. Mọi tin đều do
> người kiểm tra và sửa lại; mô hình phân loại của đồ án được xây dựng và train từ đầu.
> Không dùng CLIP/LLM/VLM nào để lọc hay đọc ảnh — bộ lọc ảnh là quy tắc viết tay.

---

## 1. Script làm gì

```
Sitemap ~13 báo (36 tháng) ─► chấm slug: tier 2 = từ kênh + từ lừa đảo, tier 1 = từ lừa đảo mạnh
        │ (tải song song nhiều báo, mỗi báo vẫn cách 1,5 s/request)
        ▼
Bài có nhắc "tin nhắn/SMS/brandname/đầu số..." ≥ 2 lần? ── không ─► bỏ
        │
        ├─ TEXT: chỉ câu trong ngoặc kép đứng SAU "tin nhắn có nội dung / nhắn / gửi tin / lý do như..."
        │        loại lời kể ("tôi...", "mình..."), lời khuyên ("1 là..."), câu của nhà báo
        └─ OCR : chỉ ảnh có chú thích / tên file / đoạn văn ngay trước nói về tin nhắn
                 (bỏ logo, ảnh nhỏ, ảnh minh họa) → EasyOCR → bỏ thanh trạng thái/giao diện
                 → tách từng BONG BÓNG tin nhắn → bỏ chữ trên infographic cảnh báo
                │
                ▼
  Điểm "giống SMS" ─► che [NUMBER]/[MONEY]/[TIME]/[DATE] (giống tập Tuấn, giữ URL)
  ─► gợi ý nhãn theo definition_of_ham_spam_scam.md ─► bỏ trùng & gần trùng ─► CSV + review.html
```

| Nguồn tự động (đã kiểm robots.txt 25/11/2026) | Kiểu sitemap |
|---|---|
| thanhnien, tuoitre, vtv, genk, kenh14 | theo ngày |
| dantri, vietnamnet, znews | theo ngày/tháng |
| cand (Công an nhân dân), vietnamplus, tienphong, sggp | theo tháng |
| vov | theo chuyên mục (pháp luật, công nghệ, xã hội, đời sống, kinh tế) |

| Không dùng | Lý do |
|---|---|
| tinnhiemmang.vn | robots.txt khai báo `Content-Signal: ai-train=no` |
| chongluadao.vn | Trang render bằng JavaScript |
| vnexpress.net | Sitemap theo ngày chuyển hướng bot về trang chủ |
| nld.com.vn | Sitemap theo ngày rỗng |
| plo.vn, laodong.vn, baochinhphu.vn, ictvietnam.vn | Không có sitemap dùng được |

Các trang trên (trừ tinnhiemmang) vẫn thêm **thủ công** được qua `--urls-file`.

---

## 2. Chạy trên Kaggle (khuyên dùng)

1. Kaggle → **Create → New Notebook → File → Import Notebook** → chọn `notebooks/crawl_vi_scam_kaggle.ipynb`.
2. **Settings**: **Internet → On**, **Accelerator → GPU T4** (EasyOCR dùng 1 GPU).
3. Chạy lần lượt: ô 1 cài `easyocr` → ô 2 ghi script → ô 3 **chạy thử** (1 tháng, 15 bài)
   → ô 4 **chạy đầy đủ** → ô 5 xem thống kê → ô 6 nén `vi_scam_crawl_v2.zip`.
4. Tải zip ở tab **Output** (hoặc *Save Version → Save & Run All*).

Bị ngắt giữa chừng: chạy lại ô 4, script bỏ qua bài đã xử lý. Một báo bị chặn: bỏ khỏi `--sources`.

Ước lượng thời gian (đo trên máy local): quét sitemap ~1,5 phút/tháng dữ liệu cho cả 13 báo;
tải bài 30–350 bài/phút tùy số ảnh; OCR ~0,5 s/ảnh trên T4.

---

## 3. Chạy ở máy local

```powershell
# chạy từ thư mục gốc của repo
pip install requests beautifulsoup4 lxml pillow
pip install easyocr            # tùy chọn, bật OCR (cài kèm PyTorch)

python scripts/crawl_vi_scam.py --no-ocr --months 1 --max-articles 20   # thử nhanh
python scripts/crawl_vi_scam.py --months 36 --max-articles 2500 --target 400
```

Kết quả mặc định ở `data/raw/vi_scam_crawl_v2/`.

---

## 4. Tham số

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--out-dir` | `/kaggle/working/vi_scam_crawl_v2` hoặc `data/raw/vi_scam_crawl_v2` | Thư mục kết quả |
| `--sources` | cả 13 báo | Ví dụ `--sources cand thanhnien` |
| `--months` | 36 | Quét sitemap bao nhiêu tháng |
| `--max-articles` | 1500 | Số bài tối đa mỗi lần chạy |
| `--target` | 0 | Dừng khi đủ N ứng viên (0 = không giới hạn) |
| `--min-tier` | 1 | `2` = chỉ bài có slug chứa cả từ kênh lẫn từ lừa đảo (ít bài, sạch hơn) |
| `--min-relevance` | 2 | Bài phải nhắc "tin nhắn/SMS/brandname/đầu số…" ít nhất N lần |
| `--urls-file` / `--no-discover` | – | Thêm URL thủ công / chỉ dùng URL thủ công |
| `--rediscover` | tắt | Bỏ qua `articles_queue.csv` đã lưu, quét sitemap lại |
| `--delay` | 1.5 | Giây giữa 2 request **cùng một báo** (đừng giảm dưới 1) |
| `--workers` | 8 | Số luồng tải song song (khác báo) |
| `--min-score` | 2 | Ngưỡng điểm "giống SMS" (câu trích có câu dẫn được giảm 1) |
| `--ocr` / `--no-ocr` | tự bật nếu có easyocr | Bật/tắt OCR |
| `--max-images` | 4 | Số ảnh tối đa OCR mỗi bài (sau khi lọc) |
| `--debug` | tắt | Ghi các câu/bong bóng bị loại kèm lý do vào `rejected_debug.csv` |

---

## 5. File đầu ra

```
vi_scam_crawl_v2/
├── vi_scam_candidates.csv   ← ứng viên
├── review.html              ← TRANG DUYỆT (mở bằng trình duyệt, cùng thư mục với images/)
├── images/                  ← chỉ những ảnh đã cho ra ít nhất 1 ứng viên
├── crawl_stats.json         ← số lượng ở từng khâu (bài → ảnh → bong bóng → ứng viên)
├── articles_queue.csv       ← bài tìm được (url, source, tier)
├── articles_done.txt        ← bài đã xử lý (để chạy tiếp)
└── rejected_debug.csv       ← (chỉ khi --debug)
```

| Cột | Ý nghĩa |
|---|---|
| `message` | Nội dung (đã che `[NUMBER]`, `[MONEY]`, `[TIME]`, `[DATE]`; **giữ nguyên URL**) |
| `label_suggested`, `scam_type_suggested`, `label_reason` | Nhãn **gợi ý** theo `definition.md` và lý do |
| `channel_suggested` | Kênh gợi ý: `sms`, `zalo`, `messenger`, `whatsapp`, `telegram`, `viber`, `unknown` |
| `sms_score`, `evidence_type` | Điểm "giống tin nhắn"; `text` (trích trong bài) / `ocr` (đọc từ ảnh) |
| `source_*`, `article_title`, `published_date`, `article_tier`, `article_relevance` | Nguồn gốc – **ghi vào báo cáo** |
| `image_url`, `image_path`, `image_rank`, `ocr_raw` | Ảnh và chữ OCR thô |
| `review_label`, `review_scam_type`, `review_channel`, `reject_reason`, `review_note` | **Người duyệt điền** |

---

## 6. Duyệt và gán nhãn (bắt buộc)

1. Giải nén zip, mở **`review.html`** bằng Chrome/Edge (để cạnh thư mục `images/`).
2. Mỗi thẻ: ảnh gốc bên trái, ô văn bản bên phải.
   - **Sửa `message`** cho đúng nguyên văn trong ảnh (OCR hay sai dấu, dính chữ giao diện). Chỉ giữ thân tin nhắn.
   - Chọn **Nhãn** (`scam`/`spam`/`legitimate`/`drop`), **Loại**, **Kênh**; nếu `drop` thì chọn **Lý do loại**
     (`not_message`, `journalism`, `ocr_garbage`, `fragment`, `duplicate`, `not_vietnamese`, `other`).
   - Nút **"= gợi ý"** chép nhãn gợi ý sang ô duyệt khi gợi ý đã đúng.
   - Trang **tự lưu trong trình duyệt**; tick "ẩn tin đã duyệt" để làm tiếp.
3. Bấm **Xuất CSV đã duyệt** → `vi_scam_candidates_reviewed.csv`.
4. Gán nhãn theo **`definition_of_ham_spam_scam.md`** + quy tắc bổ sung (HANDOFF mục 1).
5. (Nên làm) 2 người gán độc lập một phần, tính Cohen's kappa (≥ 0,8 là tốt).

**Kênh:** tin qua Zalo/Messenger/WhatsApp vẫn giữ (ghi ở cột kênh). External test chỉ dùng `sms`;
tin các kênh khác để dành cho Giai đoạn 2.

---

## 7. Sau khi có file đã duyệt

1. Adapter đọc file đã duyệt (`review_label`, `review_scam_type`, `review_channel`), bỏ dòng `drop`.
2. Khai báo `external_test` trong `configs/vietnamese_3class.yaml`.
3. SimHash loại tin trùng/gần trùng với **toàn bộ train** (kể cả augment).
4. Báo cáo **tách riêng** recall scam (tin crawl) và tỉ lệ báo nhầm trên ham/spam `vie_sms_corpus`
   (hai nguồn lệch thời gian 2015 ↔ 2024+, có dấu ↔ không dấu).

---

## 8. Đạo đức và giới hạn (nên ghi vào báo cáo)

- Chỉ crawl trang công khai, tuân thủ `robots.txt` và `Content-Signal`; mỗi báo cách 1,5 s/request.
- Chỉ lưu **đoạn trích tin nhắn**, đoạn ngữ cảnh ngắn và ảnh chụp tin nhắn có ứng viên; không lưu toàn văn bài.
- Thông tin cá nhân được che; URL lừa đảo được giữ vì là đặc trưng quan trọng.
- OCR là bản nháp; 100% tin được người kiểm tra.
- Giới hạn: tin trên báo là tin **đã được chọn để cảnh báo**, thiên về chiêu nổi bật; số lượng phụ thuộc
  số bài có ảnh chụp tin nhắn.

---

## Đợt 3 (27/11/2026) – external test của tầng 2

Đợt 1–2 nay nằm trong **train của tầng 2**, nên đợt 3 phải là dữ liệu **mới**:

1. Danh sách bài và tin của đợt 1–2 đã **nhúng sẵn trong notebook** – không cần tải gì lên Kaggle (sửa 27/11 sau khi lần chạy đầu
   dừng ở ô 4a vì chưa gắn Dataset). Sinh lại notebook bằng `scripts/make_crawl_notebook.py` nếu thư mục `vi_crawl_seen_run1_2` thay đổi.
2. Chạy notebook như cũ. Ô **4a** giải nén bản nhúng và truyền `--skip-from` → bỏ qua 2.502 bài và 239 tin của đợt 1–2.
   (Chạy tay: `python scripts/crawl_vi_scam.py ... --skip-from data/review/vi_crawl_seen_run1_2`.)
3. Tải `vi_scam_crawl_run3.zip`, mở `review.html`, duyệt (danh sách lớp đã là 9 lớp mới, có `loan_debt`), **Xuất CSV** →
   lưu thành `data/review/vi_crawl_run3_reviewed.csv`.
4. Dựng tập external tầng 2:
   `py -3.11 scripts/build_vi_crawl_external.py --inputs data/review/vi_crawl_run3_reviewed.csv --out data/processed_tier2_vi/_run3_clean.csv --full-out data/raw/vi_crawl_tier2_external.csv`
5. `$env:PYTHONPATH="src"; py -3.11 scripts/train_tier2.py` → báo cáo có thêm mục tin thật và chuỗi tầng 1 → tầng 2.

Nên ưu tiên tìm thêm kiểu **"sếp/đồng nghiệp nhờ chuyển tiền"**, **"người quen mượn tiền"** (lớp `social_impersonation` còn ít khuôn).
Chi tiết: [`NHAT_KY_TANG2.md`](NHAT_KY_TANG2.md) mục 5b.
