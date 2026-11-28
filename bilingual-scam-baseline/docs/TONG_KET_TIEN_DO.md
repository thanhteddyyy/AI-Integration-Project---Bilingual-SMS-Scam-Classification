# Tổng kết tiến độ đồ án – Phát hiện tin nhắn lừa đảo song ngữ Việt–Anh

Cập nhật: **26/11/2026** · Nhánh: `bilingual-meta-features` (commit `c35666f`)

Tài liệu chi tiết: [`NHAT_KY_THAY_DOI_DU_LIEU.md`](NHAT_KY_THAY_DOI_DU_LIEU.md) (dữ liệu, kết quả),
[`rerank_experiment.md`](rerank_experiment.md) (thí nghiệm kết hợp model),
[`HANDOFF_xu_ly_du_lieu_tieng_viet.md`](HANDOFF_xu_ly_du_lieu_tieng_viet.md) (kỹ thuật, lệnh chạy).
Chuẩn gán nhãn: [`definition_of_ham_spam_scam.md`](../definition_of_ham_spam_scam.md).

---

## 1. Hệ thống dự kiến

```
Tin nhắn
   │
   ▼
Tầng 1: Linear SVM song ngữ ──► ham / spam → dừng
   │ scam
   ▼
Nhận diện ngôn ngữ ──► tiếng Việt → Tầng 2 VI: loại scam (7 loại)     [đang làm]
                    └► tiếng Anh  → Tầng 2 EN (bổ sung sau)           [chưa làm]
   │
   ▼
Demo Gradio: nhãn + loại scam + các từ khiến model nghi ngờ           [chưa làm]
```

| Phần | Trạng thái |
|---|---|
| Dữ liệu (nhãn, chia tập, external) | ✅ Đã chốt |
| Tầng 1 (ham / spam / scam) | ✅ **Linear SVM song ngữ** |
| Tầng 2 tiếng Việt | ⬜ Sắp làm |
| Tầng 2 tiếng Anh | ⬜ Sau khi tầng 2 VI ổn |
| Demo | ⬜ Sau tầng 2 |
| Phân tích lỗi, báo cáo, slide | ⬜ |

---

## 2. Đã hoàn thành

### 2.1 Dữ liệu (24–26/11)
- **Nhãn tiếng Việt v3:** rà tay toàn bộ theo `definition.md` + quy tắc bổ sung. Tập Tuấn: 2.065 ham / 285 spam / 641 scam.
- **Nhãn tiếng Anh:** rà 711 tin nghi sai (524 đổi/bỏ); thống nhất placeholder giữa các nguồn.
- **Sửa rò rỉ:** chia train/val/test theo **họ mẫu** (Jaccard cụm 3 từ ≥ 0,5); 80% scam test từng có "anh em" trong train → nay = 0.
- **Sửa lối tắt "có dấu = scam":** thêm tin cá nhân (`vie_sms_corpus` dev) vào train → báo nhầm tin thật 24% → 0,1%.
- **Cân bằng dữ liệu:** giữ toàn bộ dữ liệu thật + `class_weight`; augment có kiểm soát chỉ cho train.
- **`scam_type` tiếng Việt:** rà lại theo nguyên tắc "đơn vị bị mạo danh trước" (89 tin đổi loại).
- **Lừa đảo tiếng Việt thật (crawl báo chí):**
  - Lần 1: 4 tin. Lần 2: 200 ứng viên → AI lọc + gắn nhãn sơ bộ (đọc ảnh gốc), **người dùng xác nhận 100%** tin giữ.
  - **Tập sạch** (trong pipeline): 22 tin SMS scam khuôn mới + 2 ham.
  - **Tập đầy đủ** (chấm ngoài pipeline): 44 scam (22 SMS khuôn mới, 10 SMS khuôn đã có trong Tuấn, 12 Zalo/Messenger) + 4 ham.
  - Loại một ảnh minh họa do AI vẽ; không dùng dữ liệu do LLM sinh (VNPhish).

**Quy mô dữ liệu đã chốt:**

| Thiết lập | Train | Validation | Test | External |
|---|---|---|---|---|
| Tiếng Việt | 4.899 (737 augment) | 712 | 565 (Tuấn) | 2.872 `vie_sms` + 24 crawl |
| Tiếng Anh | 8.120 | 3.175 | 2.829 | 1.023 SmishX |
| Song ngữ | 13.018 | 3.886 | 3.394 | 3.917 |

### 2.2 Tầng 1 – chọn mô hình (bản chính thức: Colab 28/11)
Quy tắc cố định trước: **F2 lớp scam cao nhất trên validation**; test/external chỉ để báo cáo.

> **Bản chính thức = lần chạy Colab 28/11** (`notebooks/colab_tier1_tier2.ipynb`, kết quả trong `reports/` và `artifacts/`).
> NB và SVM giống hệt từng con số lần chạy Kaggle 26/11 và lần chạy trên máy (model SVM cho dự đoán trùng 100%); chỉ CharCNN lệch nhẹ
> vì GPU không cho kết quả hoàn toàn giống nhau giữa các lần chạy. Số CharCNN của Kaggle 26/11 ghi trong ngoặc. Thí nghiệm rerank (mục 2.3)
> dùng model CharCNN của Kaggle 26/11, nên số trong `rerank_experiment.md` là của lần chạy đó.

| Thiết lập | Naive Bayes | **Linear SVM** | CharCNN |
|---|---|---|---|
| Tiếng Việt (val F2) | 79,6 | **92,1** ✅ | 84,8 (85,1) |
| Tiếng Anh (val F2) | 91,8 | **93,8** ✅ | 92,6 (92,4) |
| Song ngữ (val F2) | 92,3 | **93,6** ✅ | 92,9 (93,5) |

Kết quả thực tế của **SVM song ngữ** (lựa chọn cho demo):

| Đo gì | Kết quả |
|---|---|
| Bắt lừa đảo SMS tiếng Việt thật, khuôn mới | **19/22 (86%)**, khoảng tin cậy 95%: 67–95% |
| Bắt lừa đảo SMS tiếng Việt thật, khuôn đã biết | 10/10 |
| Bắt lừa đảo Zalo/Messenger | **1/12** – điểm yếu |
| Báo nhầm tin tiếng Việt thật (`vie_sms`) | 1,0% |
| SmishX (tiếng Anh thật): recall / báo nhầm | 84,7% / 9,9% |

Phát hiện đáng chú ý:
- CharCNN song ngữ ngang SVM trên **test** (F2 92,0 so với 91,9) nhưng kém hơn rõ trên **tin thật**: 13/22 tin SMS khuôn mới so với
  19/22, báo nhầm `vie_sms` 3,2% so với 1,0%; đợt 3 bắt 2/7 tin khuôn mới so với 5/7 (Kaggle 26/11: 12/22, báo nhầm 3,6%)
  → test tốt chưa chắc ngoài đời tốt. CharCNN cũng dao động giữa các lần chạy (tiếng Việt test F2 62,6 ở Kaggle, 69,4 ở Colab), SVM thì không.
- Mọi tin lừa đảo bị bỏ sót đều bị đoán là **ham**: tin giọng cá nhân (mượn tiền, bình chọn, "mẹ ơi…").
- NB song ngữ không dùng được cho tiếng Việt (3/22 tin thật).

### 2.3 Thí nghiệm kết hợp SVM + CharCNN ([chi tiết](rerank_experiment.md))
- Rerank theo điểm số (trọng số + ngưỡng chọn trên validation, ràng buộc báo nhầm ≤ SVM đơn):
  **không hơn SVM đơn ở song ngữ / tiếng Anh**; ở tiếng Việt chỉ hơn 1 tin trên validation, không bắt thêm tin thật nào.
- Luật OR bắt nhiều lừa đảo nhất (20/22 tin thật, SmishX 91%) nhưng báo nhầm tăng 1,5–4 lần.
- **Quyết định: tầng 1 = Linear SVM đơn** (đơn giản, nhanh, demo không cần PyTorch).

### 2.4 Công cụ đã có

| Việc | Lệnh / file |
|---|---|
| Thử tầng 1 trong terminal | `py -3.11 scripts/try_tier1.py` (cần `$env:PYTHONPATH="src"`) |
| Dựng tập crawl từ file đã duyệt | `scripts/build_vi_crawl_external.py` |
| Chấm lại external không train lại | `scripts/rescore_external.py --config ...` |
| Chấm tập lừa đảo VI đầy đủ | `scripts/score_vi_crawl_full.py` |
| So sánh + chọn tầng 1 | `scripts/compare_tier1.py` → `reports/tier1/` |
| Thí nghiệm rerank | `scripts/rerank_experiment.py` → `reports/rerank/` |
| Train 3 model trên Kaggle/Colab | `notebooks/tier1_compare_colab.ipynb` + `bilingual-scam-colab.zip` |

Model trên máy: `artifacts/<thiết lập>/{svm,naive_bayes}/model.joblib`, `artifacts/<thiết lập>/charcnn/model.pt`
(SVM song ngữ ≈ 7,5 MB). `artifacts/` và `reports/` không vào git.

### 2.5 Lỗi đã sửa trong quá trình
- Config tiếng Việt / tiếng Anh ghi `lr` thay vì `learning_rate` → CharCNN sẽ lỗi trên Kaggle.
- CharCNN dừng sớm theo macro-F1 (khác NB/SVM) → đổi sang F2; thêm 5 epoch khởi động (lần 1 chọn nhầm epoch 1).
- Notebook Kaggle không import được gói vừa cài → thêm `src/` vào đường dẫn.
- Adapter crawl không gộp được các bản cùng khuôn do lỗi OCR → thêm gộp theo họ mẫu.

---

## 3. Việc cần làm tiếp

| # | Việc | Ai | Ghi chú |
|---|---|---|---|
| 1 | **Tầng 2 tiếng Việt** | Agent | 🟡 27/11: 9 lớp đã áp, code xong, **chọn SVM** (CV 81,8). Còn: quy tắc nhà mạng, 2 thí nghiệm social, train model cuối. Nhật ký: [`NHAT_KY_TANG2.md`](NHAT_KY_TANG2.md) |
| 2 | **Bộ nhận diện ngôn ngữ** (vi / en, kể cả tiếng Việt không dấu) | Agent | ✅ 27/11: test 99,5%, bỏ dấu 97,5% (`reports/langid/summary.md`) |
| 3 | **Đánh giá cả chuỗi** tầng 1 → tầng 2 | Agent (code sẵn) + người dùng crawl đợt 3 | 🟡 28/11: đợt 3 duyệt sơ bộ (AI) còn 9 tin (`data/review/vi_crawl_run3_reviewed.csv`, chờ người dùng xác nhận); tầng 2 đúng 6/9, cả chuỗi 5/9 ([`PHAN_TICH_LOI.md`](PHAN_TICH_LOI.md) mục 7) |
| 4 | **Demo Gradio** + thư mục `demo/` tự chạy được | **Thành viên khác**; agent viết `predict_pipeline` | 🟡 27/11: `predict_pipeline` + `demo_bundle.zip` xong (`demo/README.md`); còn giao diện Gradio |
| 5 | **Phân tích lỗi** | Agent | ✅ 28/11: [`PHAN_TICH_LOI.md`](PHAN_TICH_LOI.md), `scripts/error_analysis.py`. Chờ người dùng quyết sửa quy tắc 1 (mục 6.2) |
| 6 | **Tầng 2 tiếng Anh** (phương án B) | Người dùng rà ~200–300 tin IMC25, agent train | ⬜ Nhãn loại IMC25 chưa rà, có lỗi thấy rõ |
| 7 | Meta-features cho SVM | Agent | ⬜ Tùy chọn, nếu còn thời gian |
| 8 | **Báo cáo + slide** | **Thành viên khác** | ⬜ Viết được chương dữ liệu, tầng 1, phần lớn tầng 2 |

### 3.1 Tầng 2 tiếng Việt – đã thống nhất
- **Chỉ tiếng Việt**; tin tiếng Anh dừng ở ham/spam/scam cho tới khi có việc 6.
- **Cập nhật 27/11 – đã có code, lần chạy đầu xong, chờ thảo luận chọn model:** `scripts/train_tier2.py` + `configs/tier2_vietnamese.yaml`
  + `src/scam_baseline/tier2.py` → `reports/tier2_vi/summary.md`. Dữ liệu tầng 2 **chia riêng**: 565 tin scam khác nhau (641 dòng, kể cả tin bỏ ở
  cách B), chia 70/15/15 theo khuôn, lớp nào cũng có ở cả 3 tập. Lần chạy đầu: SVM dẫn đầu (val macro-F1 86,6; test 61,6; trung bình 10 cách
  chia: test 72,5 ± 5,7); `social_impersonation` 0/3 trên test (khuôn "sếp nhờ" không có trong train).
- **Cập nhật 27/11 (2) – tin crawl đợt 1–2 vào train tầng 2:** mọi kênh, chỉ lấy tin lừa đảo chính (tin chat coi như SMS, bỏ tiêu
  chí kênh). 41 tin vào train, 3 tin bỏ vì cùng khuôn với val/test (`data/processed_tier2_vi/crawl_train_skipped.csv`); val/test giữ
  nguyên. Bản đóng băng: `data/raw/vi_crawl_tier2_train.csv`. **External tầng 2 = đợt crawl 3** (người dùng sẽ crawl,
  dựng ra `data/raw/vi_crawl_tier2_external.csv`, lệnh trong `configs/tier2_vietnamese.yaml`); trước khi có đợt 3 thì chưa có
  số liệu tin thật và chuỗi tầng 1 → tầng 2. Tầng 1 **không** đổi (tin "mượn tiền" không phân biệt được với tin thật chỉ từ chữ).
  Kết quả: SVM gần như không đổi (10 cách chia: test 72,5 → 71,4 ± 5,9); `social_impersonation` vẫn 0/3 trên test (khuôn "sếp nhờ" vẫn
  chưa có trong train); CharCNN dao động mạnh (val 82,7 → 71,7). Kết quả trước khi thêm: `reports/tier2_vi_run1_no_crawl_train/`.
- **Chốt 27/11 (3) – quy tắc chọn model tầng 2 = CV macro-F1** (5 lượt, chia theo khuôn trên train+val; CharCNN dừng sớm theo
  15% khuôn tách từ phần học của mỗi lượt). Bỏ báo cáo trung bình 10 cách chia (tùy chọn `--split-seeds`, mặc định tắt).
  Kết quả: **SVM 81,8 ± 1,4** > NB 73,0 ± 5,4 > CharCNN 64,0 ± 3,4 → **tầng 2 = SVM**. Nhân tiện sửa 1 nhãn Tuấn (COM_1477, OTP + tên
  miền evn.io.vn: banking → gov_utility, khớp tin crawl cùng khuôn).
- ~~**Dữ liệu:** ~640 tin scam của Tuấn; test = 104 tin scam test gốc~~ (thay bằng cách chia riêng ở trên); external = tin crawl có `scam_type` đã duyệt.
- **Model:** NB, SVM, CharCNN (CharCNN chạy CPU được vì dữ liệu nhỏ).
- **Chọn:** macro-F1 cao nhất trên validation. Dự đoán: SVM hoặc NB thắng, CharCNN thua vì ít dữ liệu.
- **Thiết kế mở rộng:** mỗi ngôn ngữ một model tầng 2 với danh sách lớp riêng → thêm tiếng Anh không phải sửa phần tiếng Việt.

### 3.2 Cần người dùng xác nhận
> **Cập nhật 27/11:** đã chốt **9 lớp** bám theo định nghĩa (tách `loan_debt`, gộp `telecom_account` vào `government_services` rồi đổi tên thành `gov_utility_services`,
> giữ riêng `social_impersonation`) và đã áp vào dữ liệu; tầng 1 không cần train lại. Lý do từng lớp:
> [`GIAI_THICH_TANG2_VA_META_FEATURES.md`](GIAI_THICH_TANG2_VA_META_FEATURES.md) mục 2.6. Việc 4 (demo) và 8 (báo cáo) giao thành viên khác.
> Danh sách 7 lớp bên dưới là đề xuất cũ.

- **Danh sách 7 lớp** (đề xuất): banking_finance 193, prize_lottery 109, government_services 88, job_task_scam 65,
  investment 55, delivery_logistics 28, other_scam 74 + social_impersonation 20 + telecom_account 9 = 103.
  Phương án khác: gộp telecom vào government.
- **Nơi demo:** laptop của người dùng + Hugging Face Spaces dự phòng (chốt khi làm việc 4).

---

## 4. Giới hạn cần nêu trong báo cáo
1. Lừa đảo tiếng Việt thật ít (22 tin SMS khuôn mới) → khoảng tin cậy rộng; nhãn crawl lần 2 do AI gắn sơ bộ, người xác nhận.
2. Scam tiếng Việt để train chỉ từ một nguồn (tập Tuấn), nhiều tin sinh theo mẫu.
3. **Model gần như không bắt được lừa đảo qua Zalo/Messenger** (1/12) và tin giọng cá nhân → hướng phát triển: bổ sung dữ liệu chat.
4. Test tiếng Anh lạc quan hơn thực tế (97% scam test là IMC25) → dùng SmishX làm con số thực tế.
5. Nhãn IMC25 (cả ham/scam lẫn loại scam) vẫn còn tin sai.
6. Validation tiếng Việt chỉ có 56 tin scam → chỉ số dao động mạnh.
7. Model song ngữ báo nhầm tin tiếng Việt thật 1,0% so với 0,1% của model tiếng Việt riêng – đánh đổi để không phải đoán ngôn ngữ.

## 5. Ghi chú môi trường
- `.venv` của dự án đang hỏng (trỏ tới Python 3.14 đã gỡ) → dùng `py -3.11` với `PYTHONPATH=src`. Test: 29/29 đạt.
- Các file lớn không vào git: `results.zip`, `results_2.zip` (kết quả Kaggle), `data/_before_crawl2_2026-11-26/` (sao lưu).
