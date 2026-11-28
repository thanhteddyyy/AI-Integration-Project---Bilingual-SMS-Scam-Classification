# Thí nghiệm rerank: kết hợp điểm Linear SVM + CharCNN cho tầng 1 (ham / spam / scam)

Ngày: 26/11/2026. Liên quan: [`NHAT_KY_THAY_DOI_DU_LIEU.md`](NHAT_KY_THAY_DOI_DU_LIEU.md) (mục 3, 3.1), `reports/tier1/`.

---

## 1. Vì sao làm thí nghiệm này

- Theo quy tắc chọn cố định (F2 lớp scam trên validation), **Linear SVM thắng** ở cả 3 thiết lập
  (Kaggle lần 2, `results_2.zip`). Ở **song ngữ**, CharCNN gần như hòa (val F2 93,5 vs 93,6).
- Hai model **sai ở những tin khác nhau**. Thử nhanh luật OR (1 trong 2 nói scam → scam) trên dự đoán có sẵn:
  validation F2 93,6 → 95,4, recall test tiếng Việt 67% → 91%, nhưng **báo nhầm tăng ~3 lần**
  (tin tiếng Việt thật `vie_sms` 1,0% → 3,6%; validation 4,2% → 11,7%). Luật AND thì mất nhiều recall.
- Luật OR/AND chỉ dùng **nhãn cuối**. Rerank dùng **điểm số** của cả hai model: khi một model phân vân,
  model kia kéo kết luận về đúng hướng.

## 2. Ý tưởng (giải thích đơn giản)

Hai "giám khảo" chấm mỗi tin một **điểm lừa đảo 0–1**: SVM (dựa trên từ ngữ) và CharCNN (dựa trên chuỗi ký tự).
Điểm chung = trung bình có trọng số của hai điểm. Tin có điểm chung ≥ ngưỡng → `scam`.

| Tin (minh họa) | Thật | SVM | CharCNN | Điểm chung | Ngưỡng 0,55 |
|---|---|---|---|---|---|
| "Vietcombank… dang nhap vevietcombanks.cc" | scam | 0,90 | 0,95 | 0,92 | scam ✔ |
| "Khoản phạt giao thông… gov-vndichvucong.com" | scam | 0,45 | 0,85 | 0,65 | scam ✔ (SVM đơn bỏ sót) |
| "Mẹ ơi con hết tiền, chuyển con 500k nhé" | ham | 0,20 | 0,70 | 0,45 | không ✔ (CharCNN đơn báo nhầm) |
| "Mai họp lúc 8h nhé" | ham | 0,05 | 0,10 | 0,07 | không ✔ |

## 3. Phương pháp (cố định TRƯỚC khi chạy)

**Dữ liệu và model:** đúng các split đã chốt; model SVM (`artifacts/<thiết lập>/svm/model.joblib`) và CharCNN
(`artifacts/<thiết lập>/charcnn/model.pt`, Kaggle lần 2). **Không train lại** model nào.

**Điểm của từng model:**
- CharCNN: xác suất softmax của lớp `scam`.
- SVM: không có xác suất sẵn → lấy điểm quyết định (`decision_function`) của lớp `scam`, quy về 0–1 bằng
  hồi quy logistic 1 biến (Platt scaling) **khớp trên validation**.

**Luật kết hợp:** `điểm chung = w · điểm_SVM + (1 − w) · điểm_CharCNN`.
- Nếu `điểm chung ≥ t` → `scam`.
- Ngược lại → nhãn SVM có điểm cao nhất trong {`legitimate`, `spam`} (tầng 1 vẫn phân biệt ham/spam như SVM).

**Dò tham số trên VALIDATION:** `w ∈ {0,0; 0,1; …; 1,0}`, `t ∈ {0,05; 0,06; …; 0,95}`.

**Quy tắc chọn:**
1. Ràng buộc: tỉ lệ báo nhầm scam trên validation **không vượt quá** của SVM đơn.
2. Trong các cặp (w, t) thỏa ràng buộc: F2 lớp scam trên validation cao nhất;
   hòa → báo nhầm thấp hơn → macro-F1 cao hơn → `w` lớn hơn (nghiêng về SVM, đơn giản hơn).
3. **Chỉ nhận bản kết hợp nếu** F2 validation cao hơn SVM đơn. Nếu không → giữ SVM đơn.

**Báo cáo (không dùng để chọn):** test (song ngữ: tách tiếng Việt / tiếng Anh); external theo nguồn
(SmishX, `vie_sms` holdout, VI crawl tập sạch); tập lừa đảo tiếng Việt đầy đủ (SMS khuôn mới / khuôn đã biết / chat).
So với: SVM đơn, CharCNN đơn, OR, AND.

**Thiết lập:** chính = **song ngữ** (dự kiến dùng cho demo); phụ = tiếng Việt, tiếng Anh.

## 4. Lưu ý trung thực (ghi trước khi chạy)

- Ràng buộc "báo nhầm không vượt SVM đơn" được đặt **sau khi** đã thấy kết quả OR/AND ở mục 1.
  Lựa chọn tầng 1 theo quy tắc gốc vẫn là **SVM đơn**; rerank là **thí nghiệm bổ sung**.
- Hiệu chỉnh SVM và chọn (w, t) cùng dùng validation → có thể hơi lạc quan. Kết luận dựa vào test + external.
- Validation song ngữ có 2.342 tin scam, phần lớn tiếng Anh (IMC25) → ngưỡng có thể nghiêng theo tiếng Anh.
  Validation tiếng Việt chỉ có 56 tin scam → dao động lớn.
- Tập lừa đảo tiếng Việt thật nhỏ (22 tin khuôn mới) → chênh 1–2 tin không có ý nghĩa thống kê.

## 5. Cách chạy

```
PYTHONPATH=src python scripts/rerank_experiment.py
```
Kết quả: `reports/rerank/` (`grid_<thiết lập>.csv`, `results.csv`, `summary.md`).

## 6. Kết quả (chạy 26/11/2026)

Kiểm tra trước: các dòng SVM / CharCNN chấm lại trên máy (CPU) **khớp** số liệu Kaggle (GPU), ví dụ song ngữ: SVM bắt 19/22
lừa đảo thật, CharCNN 12/22; báo nhầm `vie_sms` 1,0% / 3,6%. Bảng đầy đủ: `reports/rerank/summary.md`.

### 6.1 Tham số chọn trên validation

| Thiết lập | w (trọng số SVM) | t | Val F2 rerank | Val F2 SVM đơn | Val báo nhầm (rerank / SVM) | Quyết định theo quy tắc |
|---|---|---|---|---|---|---|
| **Song ngữ (chính)** | 0,8 | 0,71 | 92,1 | **93,6** | 4,1% / 4,2% | **Không nhận** → giữ SVM |
| Tiếng Việt | 0,6 | 0,30 | **93,5** | 92,1 | 0,3% / 0,3% | Nhận (hơn 1 tin / 56) |
| Tiếng Anh | 0,8 | 0,69 | 92,8 | **93,8** | 6,9% / 7,0% | **Không nhận** → giữ SVM |

Song ngữ / tiếng Anh: dưới ràng buộc báo nhầm, không cặp (w, t) nào vượt SVM đơn. Lý do: SVM đơn quyết định bằng
cách so 3 điểm ham/spam/scam với nhau, còn rerank chỉ đặt ngưỡng trên điểm scam – muốn giữ báo nhầm thấp thì phải đặt
ngưỡng cao, và mất recall.

### 6.2 Kết quả báo cáo (không dùng để chọn)

**Song ngữ** – recall lớp scam / báo nhầm:

| Tập | SVM | CharCNN | OR | AND | Rerank |
|---|---|---|---|---|---|
| Test tiếng Việt (104 scam) | 67,3 / 3,3% | 78,8 / 12,4% | **91,3** / 12,6% | 54,8 / 3,0% | 58,7 / **2,2%** |
| Test tiếng Anh (1.958) | 92,3 / 8,8% | 93,4 / 14,7% | **96,1** / 16,8% | 89,7 / 6,8% | 90,2 / 7,1% |
| SmishX (163) | 84,7 / 9,9% | 83,4 / 12,9% | **90,8** / 15,0% | 77,3 / 7,8% | 77,3 / 8,8% |
| Lừa đảo VI thật, khuôn mới (22) | 19 | 12 | **20** | 11 | 15 |
| Tin VI thật `vie_sms` (báo nhầm) | **1,0%** | 3,6% | 3,6% | **0,9%** | 1,0% |
| Zalo/Messenger (12) | 1 | 2 | 2 | 1 | 0 |

**Tiếng Việt** (bản được nhận theo quy tắc):

| Tập | SVM | Rerank (w 0,6 · t 0,30) |
|---|---|---|
| Validation (56 scam) | 91,1 / 0,3% | 92,9 / 0,3% (hơn 1 tin) |
| Test (104 scam) | 70,2 / 3,5% | **82,7** / 6,3% |
| Lừa đảo VI thật, khuôn mới (22) | 19 | 19 |
| Tin VI thật `vie_sms` (báo nhầm) | **0,1%** | 0,3% |

### 6.3 Kết luận

1. **Thiết lập chính (song ngữ): rerank không hơn SVM đơn** → theo quy tắc đặt trước, **tầng 1 giữ Linear SVM**.
   Rerank chỉ đổi recall lấy báo nhầm theo một đường kém hơn chính SVM.
2. **Tiếng Việt: rerank được nhận nhưng bằng chứng yếu.** Trên validation chỉ hơn **1 tin**; trên test recall tăng
   70 → 83% nhưng báo nhầm gần gấp đôi (3,5 → 6,3%); trên dữ liệu thật **không bắt thêm tin nào** (19/22) và báo nhầm
   `vie_sms` tăng 0,1 → 0,3%. Không đủ để thay SVM.
3. **Luật OR** cho recall cao nhất ở mọi tập (test VI 91%, SmishX 91%, lừa đảo VI thật 20/22) nhưng báo nhầm
   tăng ~1,5–4 lần. Chỉ hợp lý nếu sản phẩm chấp nhận nhiều cảnh báo nhầm (vd. chỉ "gắn cờ cần xem lại", không chặn).
4. **CharCNN không bổ sung được cho SVM một cách "miễn phí"**: mọi lợi ích về recall đều đi kèm báo nhầm.
   Điểm yếu Zalo/Messenger không đổi ở mọi cách kết hợp (0–2/12) → giới hạn nằm ở dữ liệu train.

**Quyết định tầng 1: Linear SVM đơn** (đơn giản, nhanh, không cần PyTorch khi chạy demo). Rerank / OR ghi trong báo cáo
như thí nghiệm bổ sung; OR có thể nêu là phương án "ưu tiên bắt lừa đảo" nếu chấp nhận báo nhầm cao hơn.
