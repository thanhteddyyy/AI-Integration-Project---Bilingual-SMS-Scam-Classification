"""Build demo_bundle/ (+ demo_bundle.zip): the 3 models + prediction code, for the teammate building the demo.

Usage (from bilingual-scam-baseline/):  py -3.11 scripts/package_demo.py
The bundle is NOT in git (models are large) – send the zip.
"""
from __future__ import annotations

import json
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scam_baseline.predict import MODEL_PATHS  # noqa: E402

OUT = ROOT / "demo_bundle"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "models").mkdir(parents=True)
    for rel in MODEL_PATHS.values():
        src = ROOT / "artifacts" / rel
        if not src.exists():
            raise SystemExit(f"missing model {src} – train it first")
        dst = OUT / "models" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copytree(ROOT / "src" / "scam_baseline", OUT / "scam_baseline",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "demo" / "README.md", OUT / "README.md")
    # try_pipeline.py without the repo paths
    script = (ROOT / "scripts" / "try_pipeline.py").read_text(encoding="utf-8")
    script = script.replace('sys.path.insert(0, str(ROOT / "src"))', 'sys.path.insert(0, str(ROOT))')
    script = script.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parent")
    script = script.replace("detector = ScamDetector(args.artifacts)", 'detector = ScamDetector(args.artifacts or ROOT / "models")')
    (OUT / "try_pipeline.py").write_text(script, encoding="utf-8")
    reqs = [f"scikit-learn=={version('scikit-learn')}", f"numpy=={version('numpy')}", f"scipy=={version('scipy')}",
            f"joblib=={version('joblib')}", f"pandas=={version('pandas')}", "# demo UI:", "gradio"]
    (OUT / "requirements.txt").write_text("\n".join(reqs) + "\n", encoding="utf-8")
    write_model_info()
    zip_path = shutil.make_archive(str(ROOT / "demo_bundle"), "zip", root_dir=ROOT, base_dir="demo_bundle")
    size = Path(zip_path).stat().st_size / 1e6
    print(f"-> {OUT}\n-> {zip_path} ({size:.1f} MB)")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_model_info() -> None:
    t2 = _load(ROOT / "artifacts" / "tier2_vi" / "final" / "training_metadata.json")
    lid = _load(ROOT / "artifacts" / "langid" / "metrics.json")
    lines = ["# Thông tin model trong gói demo", "",
             "| Model | File | Chọn theo | Số liệu chính |", "|---|---|---|---|",
             "| Tầng 1 – Linear SVM song ngữ (ham/spam/scam) | `models/bilingual/svm/model.joblib` | F2 lớp scam trên validation | "
             "Bắt 19/22 tin lừa đảo SMS tiếng Việt thật khuôn mới; báo nhầm 1,0% tin tiếng Việt thật; SmishX recall 84,7% |"]
    if lid:
        lines.append(f"| Nhận diện ngôn ngữ – NB cụm ký tự | `models/langid/model.joblib` | – | "
                     f"Accuracy test {100 * lid['test']['accuracy']:.1f}%; tiếng Việt bỏ dấu "
                     f"{100 * lid['test']['vi_without_diacritics']['accuracy']:.1f}% |")
    if t2:
        lines.append(f"| Tầng 2 – Linear SVM tiếng Việt (9 loại scam) | `models/tier2_vi/final/model.joblib` | CV macro-F1 5 lượt | "
                     f"CV macro-F1 {100 * t2['cv_macro_f1_mean']:.1f} ± {100 * t2['cv_macro_f1_std']:.1f}; "
                     f"train trên {t2['training_rows']} tin |")
    lines += ["", "Chi tiết: `docs/NHAT_KY_TANG2.md`, `reports/tier2_vi/summary.md`, `reports/langid/summary.md` trong repo."]
    (OUT / "MODEL_INFO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
