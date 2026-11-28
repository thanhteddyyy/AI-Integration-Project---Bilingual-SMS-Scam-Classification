import sys
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def merge_bilingual(project_root: Path):
    en_path = project_root / 'data' / 'processed_en_balanced' / 'modeling_data.csv'
    vi_path = project_root / 'data' / 'processed_vi_balanced' / 'modeling_data.csv'
    out_dir = project_root / 'data' / 'processed_bilingual'
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print('Reading English balanced data from:', en_path)
    df_en = pd.read_csv(en_path, dtype=str)
    print(f'English rows: {len(df_en):,}')
    
    print('Reading Vietnamese balanced data from:', vi_path)
    df_vi = pd.read_csv(vi_path, dtype=str)
    print(f'Vietnamese rows: {len(df_vi):,}')
    
    # Ensure language tag is set
    df_en['language'] = 'en'
    df_vi['language'] = 'vi'
    
    # Concatenate
    df_bilingual = pd.concat([df_en, df_vi], ignore_index=True)
    print(f'\nTotal merged rows (before cross-lingual audit): {len(df_bilingual):,}')

    # 1. Detect and resolve cross-lingual label conflicts across group_id
    label_nunique = df_bilingual.groupby('group_id')['label_level_1'].nunique()
    conflict_groups = set(label_nunique[label_nunique > 1].index)
    if conflict_groups:
        conflict_mask = df_bilingual['group_id'].isin(conflict_groups)
        print(
            f'Removing {conflict_mask.sum()} rows from {len(conflict_groups)} '
            f'cross-lingual label conflict group(s): {sorted(conflict_groups)}'
        )
        df_bilingual = df_bilingual[~conflict_mask].copy()

    # 2. Detect and resolve cross-lingual split leakage across group_id
    # These are untranslated English SMS rows inside Vietnamese external_test (social_spam_post / vie_sms_corpus)
    # that collide with original English sms_phishing rows. We remove the untranslated duplicates from VI external_test
    # so that English train/val/test distributions (exact 2000/2000/2000 balanced train) remain 100% intact.
    split_nunique = df_bilingual.groupby('group_id')['split'].nunique()
    leaking_groups = set(split_nunique[split_nunique > 1].index)
    if leaking_groups:
        rows_to_drop = []
        for gid in sorted(leaking_groups):
            grp_rows = df_bilingual[df_bilingual['group_id'] == gid]
            vi_ext_rows = grp_rows[(grp_rows['language'] == 'vi') & (grp_rows['split'] == 'external_test')]
            if not vi_ext_rows.empty and len(grp_rows) > len(vi_ext_rows):
                rows_to_drop.extend(vi_ext_rows.index.tolist())
            else:
                split_priority = {'external_test': 0, 'test': 1, 'validation': 2, 'train': 3}
                primary_split = min(grp_rows['split'], key=lambda s: split_priority.get(s, 99))
                rows_to_drop.extend(grp_rows[grp_rows['split'] != primary_split].index.tolist())
        print(
            f'Resolving {len(leaking_groups)} cross-lingual leaking group(s) '
            f'by removing {len(rows_to_drop)} untranslated overlapping row(s) from VI external_test.'
        )
        df_bilingual = df_bilingual.drop(index=rows_to_drop).reset_index(drop=True)

    # 3. Strict post-merge assertions: 0 label conflicts and 0 group leakage
    post_conflict = (df_bilingual.groupby('group_id')['label_level_1'].nunique() > 1).sum()
    post_leak = (df_bilingual.groupby('group_id')['split'].nunique() > 1).sum()
    assert post_conflict == 0, f'Found {post_conflict} label conflict groups after merge!'
    assert post_leak == 0, f'Found {post_leak} leaking groups after merge!'
    print(f'Post-merge Audit PASSED: 0 label conflicts, 0 leaking groups. Final rows: {len(df_bilingual):,}')
    
    # Save modeling_data.csv
    out_model = out_dir / 'modeling_data.csv'
    df_bilingual.to_csv(out_model, index=False, encoding='utf-8')
    print('Saved to:', out_model)
    
    # Save master_manifest.csv (for consistency)
    out_manifest = out_dir / 'master_manifest.csv'
    df_bilingual.to_csv(out_manifest, index=False, encoding='utf-8')
    
    # Generate split & language summary
    summary = df_bilingual.groupby(['split', 'language', 'label_level_1']).size().rename('rows').reset_index()
    out_summary = out_dir / 'split_summary.csv'
    summary.to_csv(out_summary, index=False)
    print('\n=== Bilingual Split Summary ===')
    print(summary.to_string(index=False))
    
    train_summary = df_bilingual[df_bilingual['split'] == 'train'].groupby(['label_level_1']).size()
    print('\n=== Total Train Distribution (Both Languages) ===')
    print(train_summary)

if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    merge_bilingual(root)

