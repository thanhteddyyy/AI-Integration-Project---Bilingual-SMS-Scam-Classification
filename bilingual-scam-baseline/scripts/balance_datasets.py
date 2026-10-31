import csv
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# =====================================================================
# 1. VIETNAMESE DATA AUGMENTATION & BALANCING
# =====================================================================

VI_BANKS = [
    'Vietcombank', 'Techcombank', 'ACB', 'BIDV', 'MBBank', 'Sacombank', 
    'VPBank', 'VietinBank', 'TPBank', 'Agribank', 'VIB', 'SHB', 'HDBank'
]

VI_SYNONYMS = [
    (r'\btai khoan\b', ['TK', 'tai khoan ca nhan', 'tai khoan ngan hang']),
    (r'\bkhoa\b', ['tam ngung', 'tam khoa', 'chan giao dich']),
    (r'\bthiet bi la\b', ['thiet bi khac', 'may la', 'thiet bi chua xac thuc']),
    (r'\bvui long\b', ['quy khach vui long', 'hay', 'de nghi quy khach']),
    (r'\bxac thuc\b', ['xac minh', 'cap nhat', 'kiem tra']),
    (r'\bthong bao\b', ['TB', 'canh bao khan', 'thong diep']),
    (r'\bngay\b', ['ngay lap tuc', 'hom nay', 'truoc 24h']),
    (r'\bkich hoat\b', ['dang nhap', 'mo dich vu', 'su dung'])
]

def augment_vietnamese_scam(text: str) -> str:
    """Generate high-quality entity-varied text for Vietnamese scam SMS."""
    new_text = text
    # 1. Swap Bank names if present
    for bank in VI_BANKS:
        if bank.lower() in new_text.lower():
            target_bank = random.choice([b for b in VI_BANKS if b.lower() != bank.lower()])
            pattern = re.compile(re.escape(bank), re.IGNORECASE)
            new_text = pattern.sub(target_bank, new_text)
            break
            
    # 2. Swap 1 or 2 synonym phrases
    applied = 0
    for pattern, replacements in VI_SYNONYMS:
        if re.search(pattern, new_text, re.IGNORECASE) and random.random() < 0.5:
            replacement = random.choice(replacements)
            new_text = re.sub(pattern, replacement, new_text, count=1, flags=re.IGNORECASE)
            applied += 1
            if applied >= 2:
                break
                
    # 3. Random money token perturbation if [MONEY] or digits present
    if '[MONEY]' in new_text and random.random() < 0.3:
        new_text = new_text.replace('[MONEY]', random.choice(['[MONEY]', '[MONEY] VND', 'so tien [MONEY]']))
        
    return new_text.strip()

def augment_vietnamese_spam(text: str) -> str:
    """Generate varied Vietnamese spam SMS without changing its spam semantics."""
    new_text = text
    # 1. Swap promotional / advertising synonyms if present
    spam_synonyms = [
        (r'\bkhuyen mai\b', ['KM', 'uu dai', 'chuong trinh KM']),
        (r'\bưu đãi\b', ['khuyến mãi', 'quà tặng', 'chương trình ưu đãi']),
        (r'\bmiễn phí\b', ['free', '0đ', 'hoàn toàn miễn phí']),
        (r'\bmien phi\b', ['free', '0d', 'hoan toan mien phi']),
        (r'\bnhận ngay\b', ['rinh ngay', 'nhận liền tay', 'sở hữu ngay']),
        (r'\bnhan ngay\b', ['rinh ngay', 'nhan lien tay', 'so huu ngay']),
        (r'\bliên hệ\b', ['LH', 'gọi ngay', 'inbox']),
        (r'\blien he\b', ['LH', 'goi ngay', 'inbox']),
    ]
    applied = 0
    for pattern, replacements in spam_synonyms:
        if re.search(pattern, new_text, re.IGNORECASE) and random.random() < 0.6:
            replacement = random.choice(replacements)
            new_text = re.sub(pattern, replacement, new_text, count=1, flags=re.IGNORECASE)
            applied += 1
            if applied >= 2:
                break

    # 2. Insert or vary common promo prefixes if still identical or randomly
    prefixes = ['[QC] ', '(QC) ', '[TB-KM] ', 'HOT: ', 'ƯU ĐÃI: ', 'KM: ']
    if new_text == text or random.random() < 0.5:
        clean_body = re.sub(r'^(\(TB\)|\(QC\)|\[QC\]|\[TB\]|HOT:)\s*', '', new_text, flags=re.IGNORECASE)
        new_text = random.choice(prefixes) + clean_body

    return new_text.strip()


def assert_zero_leakage_and_conflict(df: pd.DataFrame, dataset_name: str) -> None:
    """Verify 0 group_id leakage across active splits and 0 label conflicts."""
    active = df[df['split'].isin(['train', 'validation', 'test', 'external_test'])]
    leak_counts = active.groupby('group_id')['split'].nunique()
    leaking_groups = leak_counts[leak_counts > 1]
    if not leaking_groups.empty:
        raise AssertionError(
            f"[{dataset_name}] Found {len(leaking_groups)} leaking group_ids across splits!"
        )
    conflict_counts = active.groupby('group_id')['label_level_1'].nunique()
    conflict_groups = conflict_counts[conflict_counts > 1]
    if not conflict_groups.empty:
        raise AssertionError(
            f"[{dataset_name}] Found {len(conflict_groups)} label conflict group_ids!"
        )
    print(f"[{dataset_name}] Audit Check PASSED: 0 leaking groups, 0 label conflicts.")


def balance_vietnamese_dataset(project_root: Path, target_per_class: int = 500):
    print('\n' + '='*60)
    print('BALANCE VIETNAMESE DATASET (ANTI-LEAKAGE COMPLIANT)')
    print('='*60)
    
    input_modeling = project_root / 'data' / 'processed_vi_3class' / 'modeling_data.csv'
    output_dir = project_root / 'data' / 'processed_vi_balanced'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    df = pd.read_csv(input_modeling, dtype=str)
    print(f'Loaded {len(df)} total rows from {input_modeling}')
    
    train_df = df[df['split'] == 'train'].copy()
    val_df = df[df['split'] == 'validation'].copy()
    test_df = df[df['split'] == 'test'].copy()
    ext_df = df[df['split'] == 'external_test'].copy()
    
    print('Original Train counts:')
    print(train_df['label_level_1'].value_counts())
    
    # 1. Legitimate: Downsample to target_per_class
    legit_df = train_df[train_df['label_level_1'] == 'legitimate']
    if len(legit_df) > target_per_class:
        legit_sampled = legit_df.sample(n=target_per_class, random_state=RANDOM_SEED)
    else:
        legit_sampled = legit_df
        
    # 2. Spam: Strictly in-split train augmentation ONLY (NO borrowing from external_test!)
    spam_df = train_df[train_df['label_level_1'] == 'spam'].copy()
    needed_spam = target_per_class - len(spam_df)
    print(f'Spam count: {len(spam_df)}, needed (in-split augmentation): {needed_spam}')
    
    extra_spams = []
    if needed_spam > 0:
        aug_spams = []
        spam_pool = spam_df.to_dict('records')
        for i in range(needed_spam):
            base_row = random.choice(spam_pool).copy()
            aug_text = augment_vietnamese_spam(str(base_row['text_clean']))
            base_row['text_clean'] = aug_text
            base_row['source_record_id'] = f"aug_vi_spam_{i}"
            base_row['sample_id'] = f"sample_aug_vi_spam_{i}"
            aug_spams.append(base_row)
        extra_spams.append(pd.DataFrame(aug_spams))
        
    all_spam = pd.concat([spam_df] + extra_spams, ignore_index=True)
    if len(all_spam) > target_per_class:
        all_spam = all_spam.sample(n=target_per_class, random_state=RANDOM_SEED)
        
    # 3. Scam: Original train scam + in-split augmentation
    scam_df = train_df[train_df['label_level_1'] == 'scam'].copy()
    needed_scam = target_per_class - len(scam_df)
    print(f'Scam count: {len(scam_df)}, needed (in-split augmentation): {needed_scam}')
    
    aug_scams = []
    pool = scam_df.to_dict('records')
    for i in range(needed_scam):
        base_row = random.choice(pool).copy()
        base_row['text_clean'] = augment_vietnamese_scam(str(base_row['text_clean']))
        base_row['source_record_id'] = f"aug_scam_{i}"
        base_row['sample_id'] = f"sample_aug_vi_scam_{i}"
        aug_scams.append(base_row)
        
    all_scam = pd.concat([scam_df, pd.DataFrame(aug_scams)], ignore_index=True)
    if len(all_scam) > target_per_class:
        all_scam = all_scam.sample(n=target_per_class, random_state=RANDOM_SEED)
        
    # Combine balanced train
    balanced_train = pd.concat([legit_sampled, all_spam, all_scam], ignore_index=True)
    balanced_train = balanced_train.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)
    
    print('\nNew Balanced Train counts:')
    print(balanced_train['label_level_1'].value_counts())
    
    # Reassemble complete dataset (val, test, external test remain 100% untouched & isolated)
    full_balanced = pd.concat([balanced_train, val_df, test_df, ext_df], ignore_index=True)
    assert_zero_leakage_and_conflict(full_balanced, "Vietnamese Balanced")
    
    out_path = output_dir / 'modeling_data.csv'
    full_balanced.to_csv(out_path, index=False, encoding='utf-8')
    print(f'Saved balanced modeling data to: {out_path}')
    
    # Save split summary
    summary = full_balanced.groupby(['split', 'label_level_1']).size().rename('rows').reset_index()
    summary.to_csv(output_dir / 'split_summary.csv', index=False)
    print('\nSplit summary:')
    print(summary.to_string(index=False))

# =====================================================================
# 2. ENGLISH DATA BALANCING
# =====================================================================

EN_SYNONYMS = [
    (r'\burget\b', ['immediate', 'important', 'action required']),
    (r'\bcall\b', ['ring', 'contact', 'reach out to']),
    (r'\bfree\b', ['complimentary', 'no cost', 'bonus']),
    (r'\bwin\b', ['claim', 'receive', 'collect']),
    (r'\bprize\b', ['reward', 'gift', 'award']),
    (r'\baccount\b', ['profile', 'banking access', 'online account']),
    (r'\bsuspended\b', ['on hold', 'locked', 'restricted']),
    (r'\bverify\b', ['confirm', 'validate', 'update'])
]

def augment_english_spam(text: str) -> str:
    """Generate synonym-varied English spam SMS."""
    new_text = text
    applied = 0
    for pattern, replacements in EN_SYNONYMS:
        if re.search(pattern, new_text, re.IGNORECASE) and random.random() < 0.5:
            replacement = random.choice(replacements)
            new_text = re.sub(pattern, replacement, new_text, count=1, flags=re.IGNORECASE)
            applied += 1
            if applied >= 2:
                break
    return new_text.strip()

def balance_english_dataset(project_root: Path, target_per_class: int = 2000):
    print('\n' + '='*60)
    print('BALANCE ENGLISH DATASET')
    print('='*60)
    
    input_modeling = project_root / 'data' / 'processed' / 'modeling_data.csv'
    output_dir = project_root / 'data' / 'processed_en_balanced'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    df = pd.read_csv(input_modeling, dtype=str)
    print(f'Loaded {len(df)} total rows from {input_modeling}')
    
    train_df = df[df['split'] == 'train'].copy()
    val_df = df[df['split'] == 'validation'].copy()
    test_df = df[df['split'] == 'test'].copy()
    ext_df = df[df['split'] == 'external_test'].copy()
    
    print('Original Train counts:')
    print(train_df['label_level_1'].value_counts())
    
    # 1. Legitimate: Downsample from 3,007 to target_per_class
    legit_df = train_df[train_df['label_level_1'] == 'legitimate']
    legit_sampled = legit_df.sample(n=target_per_class, random_state=RANDOM_SEED)
    
    # 2. Scam: Downsample from 10,315 to target_per_class (stratified by scam_type if possible)
    scam_df = train_df[train_df['label_level_1'] == 'scam']
    # Stratified sample by scam_type to preserve diversity of subtypes
    if 'scam_type' in scam_df.columns:
        scam_sampled = scam_df.groupby('scam_type', group_keys=False).apply(
            lambda x: x.sample(frac=target_per_class / len(scam_df), random_state=RANDOM_SEED)
        )
        if len(scam_sampled) < target_per_class:
            diff = target_per_class - len(scam_sampled)
            extra = scam_df.drop(scam_sampled.index).sample(n=diff, random_state=RANDOM_SEED)
            scam_sampled = pd.concat([scam_sampled, extra])
        elif len(scam_sampled) > target_per_class:
            scam_sampled = scam_sampled.sample(n=target_per_class, random_state=RANDOM_SEED)
    else:
        scam_sampled = scam_df.sample(n=target_per_class, random_state=RANDOM_SEED)
        
    # 3. Spam: 1,080 samples -> augment to target_per_class
    spam_df = train_df[train_df['label_level_1'] == 'spam'].copy()
    needed_spam = target_per_class - len(spam_df)
    print(f'Spam count: {len(spam_df)}, needed: {needed_spam}')
    
    aug_spams = []
    pool = spam_df.to_dict('records')
    for i in range(needed_spam):
        base_row = random.choice(pool).copy()
        base_row['text_clean'] = augment_english_spam(str(base_row['text_clean']))
        base_row['source_record_id'] = f"aug_en_spam_{i}"
        aug_spams.append(base_row)
        
    all_spam = pd.concat([spam_df, pd.DataFrame(aug_spams)], ignore_index=True)
    if len(all_spam) > target_per_class:
        all_spam = all_spam.sample(n=target_per_class, random_state=RANDOM_SEED)
        
    # Combine balanced train
    balanced_train = pd.concat([legit_sampled, all_spam, scam_sampled], ignore_index=True)
    balanced_train = balanced_train.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)
    
    print('\nNew Balanced Train counts:')
    print(balanced_train['label_level_1'].value_counts())
    
    # Reassemble complete dataset (val, test, external test untouched)
    full_balanced = pd.concat([balanced_train, val_df, test_df, ext_df], ignore_index=True)
    assert_zero_leakage_and_conflict(full_balanced, "English Balanced")
    
    out_path = output_dir / 'modeling_data.csv'
    full_balanced.to_csv(out_path, index=False, encoding='utf-8')
    print(f'Saved balanced modeling data to: {out_path}')
    
    # Save split summary
    summary = full_balanced.groupby(['split', 'label_level_1']).size().rename('rows').reset_index()
    summary.to_csv(output_dir / 'split_summary.csv', index=False)
    print('\nSplit summary:')
    print(summary.to_string(index=False))

if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    balance_vietnamese_dataset(root, target_per_class=500)
    balance_english_dataset(root, target_per_class=2000)

