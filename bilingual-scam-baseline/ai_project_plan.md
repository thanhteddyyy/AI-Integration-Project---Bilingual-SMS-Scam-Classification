---
title: Kế hoạch Đồ án Trí tuệ Nhân tạo (AI Project Plan)
description: Tài liệu hướng dẫn, yêu cầu kỹ thuật và lộ trình thực hiện đồ án môn học AI dành cho sinh viên.
start_date: 2026-09-07
deadline_registration: 2026-09-13
---

# KẾ HOẠCH ĐỒ ÁN TRÍ TUỆ NHÂN TẠO (AI)

## 1. Mục tiêu
- Làm quen cho sinh viên với cách làm việc đồ án (chuẩn bị cho đồ án chuyên ngành/tốt nghiệp).
- Sinh viên tham gia thực hiện **1 project với định hướng cụ thể (AI)**.
- SV cần nhận diện được các thành phần chính của 1 đồ án trong các công trình nghiên cứu trước đây (Không yêu cầu phải có "đóng góp mới"):
  1. Lý do chọn đề tài.
  2. Mục tiêu đề tài + [Optional: Phạm vi đề tài].
  3. Khảo sát các Kiến thức nền tảng, Công trình/Phương pháp/Nghiên cứu liên quan.
  4. Đề xuất Giải pháp.

## 2. Yêu cầu Kỹ thuật về AI (Rất quan trọng)
> **LƯU Ý DÀNH CHO AI ASSISTANT:** Khi sinh mã hoặc tư vấn giải pháp, phải tuân thủ tuyệt đối các ràng buộc dưới đây.

- **Framework:** Phải tự xây dựng được model trên 1 framework cụ thể (`Tensorflow`, `Pytorch`,...).
- **Dataset:** Phải train được model trên 1 dataset cụ thể.
- **Ràng buộc:** **KHÔNG CHẤP NHẬN** sử dụng API có sẵn hoặc các model đã build sẵn chỉ để infer (suy luận).
- **Kiến thức:** Áp dụng kiến thức đã học vào project (KTLT, DSA,...).
- **Mục tiêu cốt lõi:** Reproduce (tái hiện) lại một paper khoa học hoặc học được một project AI cụ thể.

## 3. Thang đánh giá & Báo cáo
- **Báo cáo giữa kì:** 30%
- **Báo cáo cuối kì:** 70%
- **Yêu cầu mỗi đợt báo cáo:** Phải có đủ 3 thành phần:
  1. `Slide` (Trình bày)
  2. `Demo` (Source code + Dataset)
  3. `Report` (Bản báo cáo)
- **Làm việc nhóm:** Tất cả thành viên cần tham gia làm việc. Nếu phát hiện 1 thành viên không tham gia, nhóm cần liên hệ ngay với GVHD.

## 4. Cách làm việc & Lịch trình
- **Hình thức:** 
  - Online: Telegram ([Link Nhóm](https://t.me/+6g3mELgUVqMwNDI1)), Google Meet (Thông báo trên Telegram).
  - Offline: Báo cáo cuối kỳ.
- **Thời gian thực hiện:** 11-14 tuần (Bắt đầu từ: **07/09/2026**).

### Lịch trình dự kiến
| Tuần | Mốc thời gian | Nhiệm vụ thực hiện |
| :---: | :--- | :--- |
| **1** | 07/09/2026 | Lập nhóm, chọn đề tài, xác định bài toán. |
| **2** | | Khảo sát các phương pháp giải quyết bài toán. Tìm Dataset. |
| **3-4** | | Tìm hiểu các độ đo (metrics) để đánh giá. Bắt đầu hiện thực code. |
| **5** | | **Báo cáo Giữa kỳ** (Google Meet). |
| **6-9** | | Tiếp tục hiện thực. Đánh giá kết quả (bằng metric) và giải thích kết quả. |
| **10** | | **Báo cáo Cuối kỳ** (Offline). |
| **11** | | Backup. |

## 5. Các chủ đề gợi ý
Mỗi nhóm có thể tự đề xuất chủ đề hoặc tham khảo bảng dưới đây:

| Thuật toán / Phương pháp | Hướng Bài toán / Sản phẩm |
| :--- | :--- |
| Thuật toán Di truyền (Genetic Algorithm) | Game bot, Demo giải thuật |
| Bài toán ràng buộc CSP (Constraint Satisfaction) | Game bot, Demo giải thuật |
| Adversarial Search | Game bot, Demo giải thuật |
| Naive Bayes | Bài toán Supervised / Classification |
| Giải thuật ID3 (Decision Tree), Random Forest | Bài toán Supervised / Classification |
| Support Vector Machine (SVM) | Bài toán Supervised / Classification |
| Feed forward NN (ANN), CNN, RNN | Tùy chọn (Computer Vision, NLP...) |
| Collaborative filtering / Content-based filtering | Recommender System (Gợi ý sản phẩm) |
| K-means | Bài toán Unsupervised / Clustering |
| DBSCAN | Bài toán Unsupervised / Clustering |
| OPTICS | Bài toán Unsupervised / Clustering |

## 6. Phương pháp Thực hiện (Quy trình)
- **Ngôn ngữ (Khuyến nghị):** `Python`
- **Thư viện đề xuất:** `numpy`, `pandas`, `tensorflow` (dễ), `pytorch` (khó, thường dành cho deep learning), `matplotlib`/`seaborn`.
- **Môi trường:** `Jupyter Notebook`...
- **Quy trình làm việc:**
  1. Tìm đọc blog trước -> sau đó đọc paper.
  2. Xác định bài toán.
  3. Tìm hiểu các phương pháp liên quan đến AI để giải quyết.
  4. Tìm tập dataset để thử nghiệm (tham khảo *kaggle.com*).
  5. Tìm hiểu các độ đo (metrics) để đánh giá.
  6. **Hiện thực 2-3 phương pháp** trên dataset, đánh giá kết quả và giải thích.

## 7. Yêu cầu Đăng ký Thực hiện
- **Sĩ số:** Lập nhóm từ 1-3 sinh viên.
- **Trình bày tổng quan:** Nhóm phải trình bày ngắn gọn được tổng thể về bài toán đặt ra.
- **Khảo sát:** Phải trình bày được **ít nhất 3 giải thuật/công trình khoa học** liên quan đến bài toán.
- **Thực thi:** Mô tả được đầu vào (Input), đầu ra (Output) và chạy code demo cho bài toán.
- **Thông tin đăng ký:**
  - Link đăng ký: `261-Dang-ky-nhom-DATH-AI.xlsx` (Google Sheets)
  - **Deadline:** 23:00 ngày **13/09/2026**