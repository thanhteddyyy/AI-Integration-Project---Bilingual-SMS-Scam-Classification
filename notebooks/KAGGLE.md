# Chạy baseline trên Kaggle

## Thiết lập

1. Tạo notebook mới và bật Internet chỉ khi cần cài package còn thiếu.
2. Chọn Accelerator `GPU T4 x2`, `GPU P100` hoặc GPU đang có nếu train CharCNN.
3. Add Data chứa project và ba CSV.
4. Copy project sang `/kaggle/working/` vì thư mục input là read-only.

Ví dụ cell đầu:

```python
from pathlib import Path
import shutil

source = Path("/kaggle/input/bilingual-scam-baseline/bilingual-scam-baseline")
target = Path("/kaggle/working/bilingual-scam-baseline")
shutil.copytree(source, target, dirs_exist_ok=True)
```

## Cài package

```python
%cd /kaggle/working/bilingual-scam-baseline
!python -m pip install -e . --no-deps
```

Kiểm tra GPU:

```python
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
```

## Preprocessing

```python
!python -m scam_baseline.cli --config configs/english.yaml audit
!python -m scam_baseline.cli --config configs/english.yaml prepare
```

## Train

```python
!python -m scam_baseline.cli --config configs/english.yaml train --models nb svm
!python -m scam_baseline.cli --config configs/english.yaml train --models charcnn
```

## Nén kết quả để tải về

```python
!zip -r /kaggle/working/baseline-results.zip artifacts reports data/processed/split_summary.csv
```

Không dùng SmishX để tune hyperparameter. Chỉ validation split được dùng để chọn model và cấu hình.

