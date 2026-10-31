import json
import os
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.special import softmax

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def evaluate_ensemble(config_path: str = "configs/bilingual.yaml", svm_weight: float = 0.6):
    """
    Ensemble / Mix Linear SVM and Deep Learning CharCNN:
    Uses calibrated decision scores / softmax probabilities from both models.
    """
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    class_order = config["data"]["class_order"]
    artifacts_dir = Path(config["paths"]["artifacts_dir"])
    reports_dir = Path(config["paths"]["reports_dir"])
    
    svm_path = artifacts_dir / "svm" / "model.joblib"
    cnn_path = artifacts_dir / "charcnn" / "model.pt"
    
    if not svm_path.exists():
        print(f"Chưa tìm thấy model SVM tại {svm_path}. Hãy chạy train svm trước.")
        return
        
    print(f"Loading SVM model from {svm_path}...")
    svm_model = joblib.load(svm_path)
    
    # Check if CharCNN exists
    has_cnn = cnn_path.exists()
    cnn_model = None
    cnn_vocab = None
    cnn_cfg = None
    device = "cpu"
    
    if has_cnn:
        try:
            import torch
            from scam_baseline.models.charcnn import CharCNN, CharVocabulary
            print(f"Loading CharCNN model from {cnn_path}...")
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            checkpoint = torch.load(cnn_path, map_location=device)
            cnn_vocab = CharVocabulary(checkpoint["vocabulary"])
            cnn_cfg = checkpoint["model_config"]
            cnn_model = CharCNN(
                len(cnn_vocab),
                len(class_order),
                int(cnn_cfg["embedding_dim"]),
                int(cnn_cfg["channels"]),
                list(cnn_cfg["kernels"]),
                float(cnn_cfg["dropout"]),
            ).to(device)
            cnn_model.load_state_dict(checkpoint["state_dict"])
            cnn_model.eval()
            print("Successfully loaded CharCNN on device:", device)
        except Exception as e:
            print("Cannot load CharCNN:", e)
            has_cnn = False
            
    # Load test data
    data_path = Path(config["paths"]["processed_dir"]) / "modeling_data.csv"
    df = pd.read_csv(data_path)
    
    test_df = df[df["split"] == "test"].copy()
    y_true = test_df["label_level_1"].tolist()
    texts = test_df["text_clean"].astype(str).tolist()
    
    print(f"\nEvaluating Ensemble on Test set ({len(test_df)} samples)...")
    
    # 1. Get SVM decision scores
    svm_decisions = svm_model.decision_function(texts)
    # Calibrate decision scores into probabilities using softmax
    svm_probs = softmax(svm_decisions, axis=1)
    
    if has_cnn:
        # 2. Get CharCNN probabilities
        import torch
        max_len = int(cnn_cfg.get("max_length", 256))
        encoded_tensors = torch.tensor(
            [cnn_vocab.encode(t, max_len) for t in texts],
            dtype=torch.long,
            device=device
        )
        with torch.no_grad():
            cnn_logits = cnn_model(encoded_tensors)
            cnn_probs = torch.softmax(cnn_logits, dim=-1).cpu().numpy()
            
        # 3. Soft Voting / Weighted Averaging
        cnn_weight = 1.0 - svm_weight
        ensemble_probs = svm_weight * svm_probs + cnn_weight * cnn_probs
        y_pred = [class_order[idx] for idx in np.argmax(ensemble_probs, axis=1)]
        ensemble_name = f"ensemble_svm_{int(svm_weight*100)}_cnn_{int(cnn_weight*100)}"
    else:
        print("Chỉ có SVM (chưa có trọng số CharCNN). Dự đoán bằng SVM:")
        y_pred = [class_order[idx] for idx in np.argmax(svm_probs, axis=1)]
        ensemble_name = "svm_standalone"
        
    # Compute Metrics
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    prec, rec, f1s, _ = precision_recall_fscore_support(y_true, y_pred, labels=class_order, zero_division=0)
    
    print("\n" + "="*60)
    print(f"KẾT QUẢ ĐÁNH GIÁ MÔ HÌNH KẾT HỢP ({ensemble_name})")
    print("="*60)
    print(f"Accuracy:    {acc*100:6.2f}%")
    print(f"Macro-F1:    {macro_f1*100:6.2f}%")
    print(f"Weighted-F1: {weighted_f1*100:6.2f}%")
    print("\nChi tiết từng nhãn:")
    for idx, c in enumerate(class_order):
        print(f"  [{c:12s}] Precision: {prec[idx]*100:5.2f}% | Recall: {rec[idx]*100:5.2f}% | F1: {f1s[idx]*100:5.2f}%")

if __name__ == '__main__':
    evaluate_ensemble()
