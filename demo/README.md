# Gói demo – phát hiện tin nhắn lừa đảo song ngữ (cho bạn làm demo Gradio)

Gói này chứa **3 model đã train** và code dự đoán. Không cần GPU, không cần PyTorch.
Tạo gói bằng `py -3.11 scripts/package_demo.py` → thư mục `demo_bundle/` + file `demo_bundle.zip`
(model không có trong git, nên phải gửi file zip này).

## 1. Cài đặt

```bash
cd demo_bundle
python -m venv .venv            # Python 3.11 khuyến nghị
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt # scikit-learn ĐÚNG phiên bản ghi trong file (model lưu bằng joblib)
python try_pipeline.py --text "Tai khoan cua quy khach bi khoa, xac thuc tai vcb-xacminh.top"
```

## 2. Dùng trong code

```python
from scam_baseline.predict import ScamDetector
detector = ScamDetector("models")        # nạp 3 model 1 lần (~10 giây), rồi ~0,15 giây/tin
r = detector.predict("Mẹ ơi con đang cấp cứu, chuyển giúp con 5 triệu vào STK 0123456789")
print(r["label_vi"], r["scam_type_vi"], r["advice"], r["warnings"])
```

## 3. Kết quả trả về (`dict`) – giao diện cố định

| Khóa | Kiểu | Ý nghĩa |
|---|---|---|
| `input` | str | Tin gốc |
| `language`, `language_confidence` | str, float | `vi` / `en` và xác suất của bộ nhận diện ngôn ngữ |
| `label` | str | `legitimate` / `spam` / `scam` (tầng 1) |
| `label_vi` | str | Tên tiếng Việt của nhãn, dùng để hiển thị |
| `label_scores` | dict | Điểm SVM từng lớp. **Không phải xác suất**: lớn hơn = khả năng cao hơn |
| `label_margin` | float | Chênh lệch giữa 2 điểm cao nhất. Nhỏ (< 0,3) = model phân vân |
| `tier1_top_words` | list[(từ, điểm)] | Từ/cụm từ trong tin đẩy model về nhãn đã chọn (để giải thích) |
| `scam_type`, `scam_type_vi` | str \| None | Loại lừa đảo (tầng 2) – **chỉ khi `label == "scam"` và tin tiếng Việt** |
| `scam_group`, `scam_group_vi` | str \| None | Nhóm theo định nghĩa (3.1 Giả mạo tổ chức, 3.2 Tài chính & việc làm ảo, 3.3 Trúng thưởng, Mở rộng) |
| `scam_type_scores`, `scam_type_margin` | dict, float \| None | Điểm SVM tầng 2 |
| `tier2_top_words` | list | Từ đặc trưng của loại lừa đảo |
| `advice` | str \| None | Lời khuyên theo loại lừa đảo |
| `warnings` | list[str] | Cảnh báo bằng luật, **không đổi nhãn**. Hiện có: tin yêu cầu chuyển/mượn tiền → nhắc gọi điện xác minh |
| `notes` | list[str] | Ghi chú, ví dụ "Tầng 2 hiện chỉ hỗ trợ tiếng Việt" |
| `tier1_text`, `tier2_text` | str | Văn bản thực sự đưa vào model (đã che số), để debug |

9 loại lừa đảo: `banking_finance`, `gov_utility_services`, `delivery_logistics`, `job_task_scam`, `investment`, `loan_debt`,
`prize_lottery`, `social_impersonation`, `other_scam`.

## 4. Gợi ý Gradio tối thiểu

```python
import gradio as gr
from scam_baseline.predict import ScamDetector
detector = ScamDetector("models")

def run(text):
    r = detector.predict(text)
    if r.get("label") is None:
        return "Tin rỗng", "", ""
    head = r["label_vi"] + (f" – {r['scam_type_vi']}" if r["scam_type"] else "")
    why = ", ".join(w for w, _ in r["tier1_top_words"])
    extra = "\n".join(filter(None, [r["advice"], *r["warnings"], *r["notes"]]))
    return head, why, extra

gr.Interface(run, gr.Textbox(lines=4, label="Tin nhắn"),
             [gr.Textbox(label="Kết quả"), gr.Textbox(label="Từ khiến model nghi ngờ"), gr.Textbox(label="Lời khuyên / cảnh báo")],
             title="Phát hiện tin nhắn lừa đảo").launch()
```

## 5. Lưu ý khi trình bày

- **Tầng 2 chỉ có tiếng Việt.** Tin tiếng Anh dừng ở ham/spam/scam.
- **Điểm không phải xác suất.** Nếu muốn hiển thị "độ tin cậy", hãy dùng `label_margin` (chênh lệch điểm) và ghi rõ.
- **Tin "mượn tiền" giống tin người quen** thường bị đoán là ham: lừa đảo nằm ở việc tài khoản người gửi bị chiếm, nội dung tin
  không phân biệt được. Demo hiển thị cảnh báo trong `warnings`. Đây là **giới hạn đã nêu** trong báo cáo, không phải lỗi.
- Số điện thoại, số tiền, ngày giờ được tự động che (`[NUMBER]`, `[MONEY]`…) trước khi đưa vào model, giống dữ liệu lúc train.
- Phiên bản model và số liệu đánh giá: xem `MODEL_INFO.md` trong gói.
