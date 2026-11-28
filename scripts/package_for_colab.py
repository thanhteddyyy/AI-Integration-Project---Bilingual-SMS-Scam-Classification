import zipfile
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def package_project():
    root = Path(__file__).resolve().parent.parent
    zip_path = root / "bilingual-scam-colab.zip"  # repo root (ignored by *.zip)
    
    print(f"Creating Colab deployment zip at: {zip_path}")
    
    include_dirs = ['configs', 'src', 'scripts', 'notebooks']
    include_files = ['requirements.txt', 'pyproject.toml', 'README.md']
    
    # We also include data/processed_bilingual so Colab can train immediately without preprocessing
    include_data_dirs = ['data/processed_bilingual', 'data/processed_en_balanced', 'data/processed_vi_balanced']
    include_data_files = [
        # full real-scam Vietnamese crawl set runs 1-2, scored outside the pipeline (scripts/score_vi_crawl_full.py)
        'data/raw/vi_crawl_external_full.csv',
        # tier 2 (scripts/train_tier2.py, configs/tier2_vietnamese.yaml): every Tuan scam row (v3 labels) ...
        'data/raw/train_dataset_spamscam_v3.csv',
        'data/raw/test_dataset_spamscam_v3.csv',
        'data/review/vi_tuan_train_removed_family_overlap.csv',
        # ... + crawl runs 1-2 added to tier-2 train, crawl run 3 = tier-2 external test
        'data/raw/vi_crawl_tier2_train.csv',
        'data/raw/vi_crawl_tier2_external.csv',
    ]
    
    missing = [f for f in include_data_files if not (root / f).exists()]
    if missing:
        raise SystemExit(f"missing data files (build them first): {missing}")

    total_files = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        for fname in include_files:
            fpath = root / fname
            if fpath.exists():
                arcname = f"bilingual-scam-baseline/{fname}"
                zipf.write(fpath, arcname)
                total_files += 1
                
        # Add source dirs
        for dname in include_dirs:
            dpath = root / dname
            if dpath.exists():
                for fpath in dpath.rglob('*'):
                    if fpath.is_file() and '__pycache__' not in fpath.parts and not fpath.name.endswith('.pyc'):
                        rel = fpath.relative_to(root)
                        arcname = f"bilingual-scam-baseline/{rel.as_posix()}"
                        zipf.write(fpath, arcname)
                        total_files += 1
                        
        # Add prepared bilingual data
        for dname in include_data_dirs:
            dpath = root / dname
            if dpath.exists():
                for fpath in dpath.glob('*.csv'):
                    rel = fpath.relative_to(root)
                    arcname = f"bilingual-scam-baseline/{rel.as_posix()}"
                    zipf.write(fpath, arcname)
                    total_files += 1
        for fname in include_data_files:
            zipf.write(root / fname, f"bilingual-scam-baseline/{fname}")
            total_files += 1

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Successfully packaged {total_files} files into: {zip_path}")
    print(f"Archive size: {size_mb:.2f} MB")
    print("You can upload this zip directly to Google Colab or Google Drive!")

if __name__ == '__main__':
    package_project()

