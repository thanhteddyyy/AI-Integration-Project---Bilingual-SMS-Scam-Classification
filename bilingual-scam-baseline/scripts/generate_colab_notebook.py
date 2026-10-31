import json
from pathlib import Path

notebook = {
    'cells': [
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': [
                '# 🛡️ Bilingual SMS Scam Classification Baseline trên Google Colab\n',
                'Notebook này huấn luyện và đánh giá 3 mô hình (**Naive Bayes**, **Linear SVM**, và **Deep Learning CharCNN**) trên bộ dữ liệu **Tin nhắn lừa đảo Song ngữ Anh - Việt (Bilingual)**.\n',
                '\n',
                '---\n',
                '### ⚙️ Hướng dẫn chọn GPU trên Google Colab:\n',
                '1. Vào menu **Runtime** (Thời gian chạy) -> **Change runtime type** (Thay đổi loại thời gian chạy).\n',
                '2. Mục **Hardware accelerator** (Bộ tăng tốc phần cứng): chọn **T4 GPU** -> Nhấn **Save**.'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 1: Kiểm tra phần cứng GPU']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                'import torch\n',
                'print("PyTorch Version:", torch.__version__)\n',
                'print("CUDA Available:", torch.cuda.is_available())\n',
                'if torch.cuda.is_available():\n',
                '    print("🔥 Đang sử dụng GPU:", torch.cuda.get_device_name(0))\n',
                'else:\n',
                '    print("⚠️ Đang chạy bằng CPU! Hãy vào Runtime -> Change runtime type -> Chọn T4 GPU để tăng tốc CharCNN.")'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': [
                '### Bước 2: Nạp dữ liệu và giải nén vào Google Colab\n',
                '💡 **Cách làm đơn giản và không bao giờ lỗi:**\n',
                '1. Nhìn sang thanh công cụ bên trái màn hình Colab, nhấn vào biểu tượng **📁 Thư mục (Files)**.\n',
                '2. **Kéo thả** tệp `bilingual-scam-colab.zip` từ máy tính của bạn thả vào vùng trống ở thanh Files này.\n',
                '3. Đợi vòng tròn upload tải xong, sau đó bấm nút Play chạy ô code bên dưới!'
            ]
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                'import os, zipfile\n',
                'from pathlib import Path\n',
                '\n',
                '# Kiểm tra file zip ở các vị trí phổ biến trên Colab\n',
                'possible_paths = [\n',
                '    Path("/content/bilingual-scam-colab.zip"),\n',
                '    Path("/content/drive/MyDrive/bilingual-scam-colab.zip"),\n',
                ']\n',
                '\n',
                'zip_path = None\n',
                'for p in possible_paths:\n',
                '    if p.exists():\n',
                '        zip_path = p\n',
                '        break\n',
                '\n',
                '# Nếu chưa kéo thả file, mở hộp thoại chọn file trực tiếp\n',
                'if zip_path is None:\n',
                '    print("Chưa thấy file zip trong /content. Mở hộp thoại tải file:")\n',
                '    from google.colab import files\n',
                '    uploaded = files.upload()\n',
                '    for fname in uploaded.keys():\n',
                '        if fname.endswith(".zip"):\n',
                '            zip_path = Path(f"/content/{fname}")\n',
                '            break\n',
                '\n',
                'if zip_path and zip_path.exists():\n',
                '    print(f"📦 Đang giải nén: {zip_path}...")\n',
                '    with zipfile.ZipFile(zip_path, "r") as z:\n',
                '        z.extractall("/content")\n',
                '    print("✅ Giải nén thành công!")\n',
                'else:\n',
                '    raise FileNotFoundError("Chưa tìm thấy file zip! Hãy kéo thả bilingual-scam-colab.zip vào cột 📁 Files bên trái rồi chạy lại ô này.")\n',
                '\n',
                '# Chuyển vào thư mục dự án\n',
                '%cd /content/bilingual-scam-baseline\n',
                '!ls -la'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 3: Cài đặt và thiết lập môi trường Colab']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                '%cd /content/bilingual-scam-baseline\n',
                '!pip install -e . --no-deps\n',
                'import os\n',
                'os.environ["PYTHONPATH"] = "src"\n',
                'print("✅ Môi trường và PYTHONPATH đã sẵn sàng!")'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 4: Kiểm tra Dataset Song ngữ (Bilingual Dataset)']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                'import pandas as pd\n',
                'data_file = "data/processed_bilingual/modeling_data.csv"\n',
                'df = pd.read_csv(data_file)\n',
                'print("Tổng số mẫu song ngữ:", len(df), "dòng\\n")\n',
                'print("=== Phân bổ mẫu theo Split, Ngôn ngữ và 3 Nhãn ===")\n',
                'summary = df.groupby(["split", "language", "label_level_1"]).size().rename("rows").reset_index()\n',
                'display(summary)\n',
                '\n',
                'print("\\n=== Phân bố tập Train (Bilingual) cân bằng 1:1:1 ===")\n',
                'display(df[df["split"] == "train"].groupby("label_level_1").size())'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 5: Huấn luyện toàn bộ 3 mô hình (Naive Bayes, SVM, Deep Learning CharCNN)']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                '# Huấn luyện lần lượt Naive Bayes, Linear SVM và Deep Learning CharCNN trên GPU\n',
                '!python -m scam_baseline.cli --config configs/bilingual.yaml train --models nb svm charcnn'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 6: Xem bảng so sánh kết quả & Ma trận nhầm lẫn (Confusion Matrix)']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                'import os, pandas as pd, matplotlib.pyplot as plt\n',
                'from PIL import Image\n',
                '\n',
                '# 1. Bảng so sánh các chỉ số\n',
                'report_file = "reports/bilingual/model_comparison.csv"\n',
                'comparison = pd.read_csv(report_file)\n',
                'print("=== BẢNG SO SÁNH HIỆU NĂNG CÁC MÔ HÌNH ===")\n',
                'display(comparison.sort_values(by=["split", "macro_f1"], ascending=[True, False]))\n',
                '\n',
                '# 2. Hiển thị Ma trận nhầm lẫn của cả 3 mô hình\n',
                'models = ["naive_bayes", "svm", "charcnn"]\n',
                'fig, axes = plt.subplots(1, 3, figsize=(18, 5))\n',
                'for idx, m in enumerate(models):\n',
                '    img_path = f"artifacts/bilingual/{m}/confusion_matrix_test.png"\n',
                '    if os.path.exists(img_path):\n',
                '        img = Image.open(img_path)\n',
                '        axes[idx].imshow(img)\n',
                '        axes[idx].set_title(f"{m.upper()} Test Confusion Matrix", fontsize=13, fontweight="bold")\n',
                '        axes[idx].axis("off")\n',
                '    else:\n',
                '        axes[idx].set_title(f"{m.upper()} (Chưa có ảnh)")\n',
                '        axes[idx].axis("off")\n',
                'plt.tight_layout()\n',
                'plt.show()'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 7: Thử nghiệm Demo dự đoán tin nhắn thời gian thực']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                'test_messages = [\n',
                '    "Ma OTP xac thuc GD la 066595, hieu luc 3 phut tren VCB Digibank.",\n',
                '    "Tai khoan cua ban dang duoc dang nhap tren thiet bi khac, neu khong phai ban vui long vao https://vietcombank.vn-ctt.top de sua doi",\n',
                '    "(QC) May man danh cho thue bao nhan duoc tin nhan nay! Nhanh tay nap the tai https://gamebai789.vip nhan loc 100k",\n',
                '    "URGENT: Your Chase banking access has been suspended due to suspicious activity. Verify at https://chase-update-security.com immediately",\n',
                '    "Congratulations! You have won a 1000 GBP Walmart gift card. Call 0871234567 to claim your prize now!",\n',
                '    "Hi mom, are we having lunch together at 12 today?"\n',
                ']\n',
                '\n',
                'print("=== DỰ ĐOÁN VỚI LINEAR SVM ===\\n")\n',
                'for msg in test_messages:\n',
                '    print("-" * 60)\n',
                '    print("SMS:", msg)\n',
                '    !python -m scam_baseline.cli --config configs/bilingual.yaml predict --model svm --text "$msg"\n',
                '    print()\n',
                '\n',
                'print("=== DỰ ĐOÁN VỚI DEEP LEARNING CHARCNN ===\\n")\n',
                'for msg in test_messages[:3]:\n',
                '    print("-" * 60)\n',
                '    print("SMS:", msg)\n',
                '    !python -m scam_baseline.cli --config configs/bilingual.yaml predict --model charcnn --text "$msg"\n',
                '    print()'
            ]
        },
        {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['### Bước 8: Tự động đóng gói và tải kết quả về máy tính']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': [
                '!zip -r /content/bilingual_results.zip reports/bilingual artifacts/bilingual data/processed_bilingual/split_summary.csv\n',
                'from google.colab import files\n',
                'files.download("/content/bilingual_results.zip")\n',
                'print("✅ Đã kích hoạt tải file bilingual_results.zip về máy!")'
            ]
        }
    ],
    'metadata': {
        'accelerator': 'GPU',
        'colab': {
            'gpuType': 'T4',
            'provenance': []
        },
        'language_info': {'name': 'python'}
    },
    'nbformat': 4,
    'nbformat_minor': 0
}

if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    nb_path = root / 'notebooks' / 'bilingual_scam_colab.ipynb'
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, ensure_ascii=False, indent=2)
    print('Updated notebook at:', nb_path)
