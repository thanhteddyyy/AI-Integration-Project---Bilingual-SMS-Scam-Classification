from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ..evaluation import compute_metrics, evaluate_predictions
from ..io_utils import ensure_dir, set_global_seed, write_json


def _require_torch():
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "CharCNN requires PyTorch. Install the deep-learning extra with "
            "`pip install -e .[deep]`, or use the Kaggle runtime."
        ) from error
    return torch


class CharVocabulary:
    PAD = "<PAD>"
    UNK = "<UNK>"

    def __init__(self, token_to_id: dict[str, int]) -> None:
        self.token_to_id = token_to_id

    @classmethod
    def fit(
        cls, texts: Iterable[str], *, max_size: int, min_frequency: int
    ) -> "CharVocabulary":
        counter = Counter(char for text in texts for char in str(text))
        ordered = sorted(
            (
                (char, count)
                for char, count in counter.items()
                if count >= min_frequency
            ),
            key=lambda item: (-item[1], item[0]),
        )
        tokens = [cls.PAD, cls.UNK] + [char for char, _ in ordered[: max_size - 2]]
        return cls({token: index for index, token in enumerate(tokens)})

    def encode(self, text: str, max_length: int) -> list[int]:
        unk = self.token_to_id[self.UNK]
        encoded = [self.token_to_id.get(char, unk) for char in str(text)[:max_length]]
        return encoded + [self.token_to_id[self.PAD]] * (max_length - len(encoded))

    def __len__(self) -> int:
        return len(self.token_to_id)


def _build_torch_components():
    torch = _require_torch()
    nn = torch.nn
    functional = torch.nn.functional

    class SmsDataset(torch.utils.data.Dataset):
        def __init__(self, texts, labels, vocabulary, max_length):
            self.texts = list(texts)
            self.labels = list(labels)
            self.vocabulary = vocabulary
            self.max_length = max_length

        def __len__(self):
            return len(self.texts)

        def __getitem__(self, index):
            encoded = self.vocabulary.encode(self.texts[index], self.max_length)
            return torch.tensor(encoded, dtype=torch.long), torch.tensor(
                self.labels[index], dtype=torch.long
            )

    class CharCNN(nn.Module):
        def __init__(
            self,
            vocab_size,
            num_classes,
            embedding_dim,
            channels,
            kernels,
            dropout,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
            self.convolutions = nn.ModuleList(
                [nn.Conv1d(embedding_dim, channels, kernel) for kernel in kernels]
            )
            self.dropout = nn.Dropout(dropout)
            self.output = nn.Linear(channels * len(kernels), num_classes)

        def forward(self, inputs):
            embedded = self.embedding(inputs).transpose(1, 2)
            pooled = [
                functional.adaptive_max_pool1d(
                    functional.relu(convolution(embedded)), 1
                ).squeeze(-1)
                for convolution in self.convolutions
            ]
            return self.output(self.dropout(torch.cat(pooled, dim=1)))

    return torch, SmsDataset, CharCNN


def train_charcnn(frame: pd.DataFrame, config: dict) -> dict[str, dict]:
    torch, SmsDataset, CharCNN = _build_torch_components()
    set_global_seed(int(config["seed"]), include_torch=True)
    model_cfg = config["models"]["charcnn"]
    class_order = config["data"]["class_order"]
    label_to_id = {label: index for index, label in enumerate(class_order)}
    train = frame[frame["split"].eq("train")].reset_index(drop=True)
    validation = frame[frame["split"].eq("validation")].reset_index(drop=True)
    vocabulary = CharVocabulary.fit(
        train["text_clean"].astype(str),
        max_size=int(model_cfg["max_vocab_size"]),
        min_frequency=int(model_cfg["min_char_frequency"]),
    )
    max_length = int(model_cfg["max_length"])
    train_dataset = SmsDataset(
        train["text_clean"].astype(str),
        train["label_level_1"].map(label_to_id),
        vocabulary,
        max_length,
    )
    validation_dataset = SmsDataset(
        validation["text_clean"].astype(str),
        validation["label_level_1"].map(label_to_id),
        vocabulary,
        max_length,
    )
    generator = torch.Generator().manual_seed(int(config["seed"]))
    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=int(model_cfg["batch_size"]),
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    validation_loader = torch.utils.data.DataLoader(
        validation_dataset,
        batch_size=int(model_cfg["batch_size"]),
        shuffle=False,
        num_workers=0,
    )
    device_setting = str(model_cfg.get("device", "auto"))
    if device_setting == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_setting)
    model = CharCNN(
        len(vocabulary),
        len(class_order),
        int(model_cfg["embedding_dim"]),
        int(model_cfg["channels"]),
        list(model_cfg["kernels"]),
        float(model_cfg["dropout"]),
    ).to(device)

    class_counts = train["label_level_1"].value_counts()
    if model_cfg.get("class_weight") == "balanced":
        weights = [len(train) / (len(class_order) * class_counts[label]) for label in class_order]
        weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    else:
        weight_tensor = None
    criterion = torch.nn.CrossEntropyLoss(weight=weight_tensor)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(model_cfg["learning_rate"]),
        weight_decay=float(model_cfg["weight_decay"]),
    )
    artifact_dir = ensure_dir(Path(config["paths"]["artifacts_dir"]) / "charcnn")
    best_macro_f1 = -1.0
    best_epoch = 0
    patience_counter = 0
    history = []
    best_path = artifact_dir / "model.pt"
    for epoch in range(1, int(model_cfg["epochs"]) + 1):
        model.train()
        total_loss = 0.0
        for inputs, labels in train_loader:
            inputs = inputs.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().cpu()) * len(labels)
        val_predictions = _predict_ids(model, validation_loader, device, torch)
        val_labels = validation["label_level_1"].tolist()
        val_text_predictions = [class_order[index] for index in val_predictions]
        val_metrics = compute_metrics(val_labels, val_text_predictions, class_order)
        history.append(
            {
                "epoch": epoch,
                "train_loss": total_loss / max(1, len(train_dataset)),
                "validation_macro_f1": val_metrics["macro_f1"],
            }
        )
        if val_metrics["macro_f1"] > best_macro_f1 + 1e-8:
            best_macro_f1 = val_metrics["macro_f1"]
            best_epoch = epoch
            patience_counter = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "vocabulary": vocabulary.token_to_id,
                    "class_order": class_order,
                    "model_config": model_cfg,
                    "best_epoch": best_epoch,
                    "best_validation_macro_f1": best_macro_f1,
                },
                best_path,
            )
        else:
            patience_counter += 1
            if patience_counter >= int(model_cfg["patience"]):
                break
    checkpoint = torch.load(best_path, map_location=device)
    model.load_state_dict(checkpoint["state_dict"])
    write_json(history, artifact_dir / "training_history.json")
    write_json(
        {
            "best_epoch": best_epoch,
            "best_validation_macro_f1": best_macro_f1,
            "device": str(device),
            "training_rows": len(train),
            "vocabulary_size": len(vocabulary),
        },
        artifact_dir / "training_metadata.json",
    )

    metrics: dict[str, dict] = {}
    for split_name in ["validation", "test", "external_test"]:
        subset = frame[frame["split"].eq(split_name)].reset_index(drop=True)
        if subset.empty:
            continue
        dataset = SmsDataset(
            subset["text_clean"].astype(str),
            subset["label_level_1"].map(label_to_id),
            vocabulary,
            max_length,
        )
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=int(model_cfg["batch_size"]),
            shuffle=False,
            num_workers=0,
        )
        predictions = [class_order[index] for index in _predict_ids(model, loader, device, torch)]
        metrics[split_name] = evaluate_predictions(
            subset,
            predictions,
            model_name="charcnn",
            split_name=split_name,
            class_order=class_order,
            output_dir=artifact_dir,
        )
    write_json(metrics, artifact_dir / "metrics_all_splits.json")
    return metrics


def _predict_ids(model, loader, device, torch) -> list[int]:
    model.eval()
    predictions: list[int] = []
    with torch.no_grad():
        for inputs, _ in loader:
            logits = model(inputs.to(device))
            predictions.extend(logits.argmax(dim=1).cpu().tolist())
    return predictions


def predict_charcnn(model_path: str | Path, texts: list[str], device_name: str = "auto") -> list[str]:
    torch, SmsDataset, CharCNN = _build_torch_components()
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    checkpoint = torch.load(model_path, map_location=device)
    cfg = checkpoint["model_config"]
    vocabulary = CharVocabulary(checkpoint["vocabulary"])
    class_order = checkpoint["class_order"]
    model = CharCNN(
        len(vocabulary),
        len(class_order),
        int(cfg["embedding_dim"]),
        int(cfg["channels"]),
        list(cfg["kernels"]),
        float(cfg["dropout"]),
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    dummy_labels = [0] * len(texts)
    dataset = SmsDataset(texts, dummy_labels, vocabulary, int(cfg["max_length"]))
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=int(cfg["batch_size"]), shuffle=False, num_workers=0
    )
    return [class_order[index] for index in _predict_ids(model, loader, device, torch)]

