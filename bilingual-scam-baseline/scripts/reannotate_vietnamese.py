import csv
import sys
import re
import unicodedata
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def remove_accents(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    return ''.join([c for c in s if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D').lower()

def clean_noise(s: str) -> str:
    norm = remove_accents(s)
    # collapse consecutive repeated characters
    norm = re.sub(r'([a-z0-9])\1{2,}', r'\1', norm)
    # replace punctuation with space
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', norm)
    return re.sub(r'\s+', ' ', cleaned).strip()

def classify_label_1(msg: str) -> tuple[str, str]:
    """
    Classify a Vietnamese risky message (label 1) into either 'scam' or 'spam'.
    Returns (label_3class, category).
    """
    raw_norm = remove_accents(msg)
    cleaned = clean_noise(msg)
    
    # -------------------------------------------------------------
    # 1. SCAM / PHISHING / IMPERSONATION / MALICIOUS ATTACKS
    # -------------------------------------------------------------
    
    # Banking / FinTech phishing
    banks = [
        'vietcom', 'vcb', 'vietin', 'techcom', 'acb', 'mbbank', 'tpbank', 'sacombank', 
        'bidv', 'vpbank', 'agribank', 'shb', 'msb', 'vib', 'scb', 'hdbank', 'eximbank', 
        'ocb', 'seabank', 'bacabank', 'pvcombank', 'namabank', 'smartbanking', 'digibank',
        'momo', 'zalopay', 'viettel money', 'shb et', 'vietcompriority', 'tech com',
        'vietinbamk', 'vietcombank'
    ]
    if any(b in raw_norm or b in cleaned for b in banks):
        return 'scam', 'banking_phishing'
        
    # Telecom / Brand loyalty points phishing (VNPT, Viettel, Mobifone đổi điểm thưởng)
    if any(p in raw_norm for p in ['vnptdiem', 'vietteldiem', 'mobidiem', 'doi diem', 'priority', 'diem thuong']) and any(u in raw_norm for u in ['http', '.com', '.vn', '.top', '.vip', '.net']):
        return 'scam', 'loyalty_points_phishing'
        
    # Public service / Police / Legal / Traffic fine (VNeID, Dịch vụ công, Phạt nguội, Tòa án, Viện kiểm sát, BHTN)
    gov_keywords = [
        'dich vu cong', 'dichvucong', 'dichvucon', 'vneid', 'dinh danh', 'phat nguoi', 
        'cong an', 'canh sat', 'toa an', 'vien kiem sat', 'quy bhtn', 'bhtn', 'nq 116', 
        'nghi quyet 116', 'bhxh', 'can cuoc', 'phi giao thong', 'vi pham giao thong',
        'bien ban', 'so tu phap', 'cuc canh sat', 'tra tien phi giao thong'
    ]
    if any(p in raw_norm or p in cleaned for p in gov_keywords):
        return 'scam', 'gov_public_service_phishing'
        
    # Tech brand / Social / OTT account theft (Apple, iCloud, Netflix, WhatsApp, Telegram, Facebook, TikTok)
    brand_theft = [
        'apple inc', 'icloud', 'dinh vi hom nay', 'tim iphone', 'netflix', 'whatsapp', 
        'whastxpp', 'telegram', 'facebook', 'khoa tai khoan telegram', 'tiktok shop',
        'kich hoat tren thiet bi', 'thiet bi la', 'dang nhap tren thiet bi khac'
    ]
    if any(p in raw_norm or p in cleaned for p in brand_theft):
        return 'scam', 'brand_account_phishing'
        
    # Fake Job / Recruitment / Task scam (Shopee, Lazada, eBay, Amazon, Tuyển CTV, việc làm online)
    job_keywords = [
        'cong tac vien', 'ctv', 'tuyen dung', 'nhan su', 'lam nhiem vu', 
        'xem video', 'hoa hong ngay', 'shopee', 'lazada', 'viec lam tai nha',
        'tuyen nhan vien', 'kiem tien online', 'ebay', 'amazon', 'cong viec online',
        'kiem them thu nhap'
    ]
    if any(p in raw_norm or p in cleaned for p in job_keywords):
        return 'scam', 'job_task_scam'
        
    # Fake delivery / COD phishing
    if any(p in raw_norm for p in ['buu pham', 'buu kien', 'giao hang that bai', 'xac nhan dia chi', 'don hang ton']) and any(u in raw_norm for u in ['http', '.top', '.vip', '.icu', '.cc', '.com']):
        return 'scam', 'delivery_phishing'
        
    # Threat / Extortion (dọa khóa sim trong 2h / thu hồi sim / dọa tạm ngưng dịch vụ)
    threat_keywords = [
        'khoa sim', 'khoa thue bao sau 2h', 'khoa thue bao trong 2 gio', 'thu hoi sim', 
        'tam ngung su dung thue bao', 'tat vinh vien', 'khoa thue bao', 'khoa tai khoan'
    ]
    if any(p in raw_norm or p in cleaned for p in threat_keywords):
        return 'scam', 'threat_extortion_scam'

    # Phishing link claiming benefits/money with fake domain
    welfare_keywords = [
        'nhan tien ho tro', 'nhan tien tro cap', 'xac nhan thong tin thanh toan', 
        'dang nhap vao trang web chinh thuc', 'nhan tien theo nq', 'tro cap that nghiep',
        'thoi gian dang ky nhan'
    ]
    if any(p in raw_norm or p in cleaned for p in welfare_keywords):
        return 'scam', 'social_welfare_phishing'
        
    # Generic malicious shortlinks asking to login/verify
    if re.search(r'\.(top|icu|xyz|cc|online|site|club|buzz|ru|link|vip)/?', raw_norm):
        if any(w in raw_norm for w in ['dang nhap', 'xac thuc', 'xac minh', 'truy cap', 'lay tien', 'rut tien', 'xac nhan']):
            return 'scam', 'generic_phishing_link'

    # -------------------------------------------------------------
    # 2. SPAM (Gambling, loans, commercials, lottery, ads)
    # -------------------------------------------------------------
    
    # Gambling / Betting / Casino / Lottery / Obfuscated
    gambling_words = [
        'kubet', 'thabet', 'shbet', '789bet', 'hi88', 'f8bet', 'fun88', 'w88', 'm88', 
        'jun88', 'new88', 'okvip', 'go88', 'sunwin', 'rikvip', 'b52', 'hitclub', '79club',
        'tai xiu', 'no hu', 'quay hu', 'ban ca', 'game bai', 'song bac', 'casino', 
        'da ga', 'lo de', 'so de', 'danh de', 'keo nha cai', 'bach thu', 'cau lo', 
        'tang loc', 'tang code', 'tan thu', 'nap dau', 'gamevip', 'nhan loc', 'vong quay',
        'nhan tien cuoc', 'cuoc mien phi', 'keonhacai', 'nohu', 'rut tien', 'thang thi ban rut',
        'song bac uy tin', 'trianx2nap', 'hong lixi', 'bao li xi', 'lixi phat', 'nhan tien thuong',
        'quayhu', 'nohu online', 'keonhacai top', 'nhanloc lixi', 'xacminh ruttien', 'game bai',
        'thu van may', '79codethantai', 'ua49', 'tdtc', 'thien duong tro choi', 'li xi phong bi do',
        'phong bi do', 'tien nap'
    ]
    if any(g in raw_norm or g in cleaned for g in gambling_words):
        return 'spam', 'gambling_spam'
        
    # Obfuscated gambling / noise spam (repeated characters or tricks like Gomapple, kgoogle, bidv spoof with noise)
    if any(k in raw_norm for k in ['apple.com', 'google.com', 'gomapple', 'kgoogle', 'atuapple']) or re.search(r'([a-z])\1{3,}', raw_norm):
        return 'spam', 'obfuscated_spam'
        
    # Loan / Credit / Debt collection telesale
    loans = [
        'vay von', 'vay nong', 'vay tien', 'giai ngan', 'lai suat', 'vay tieu dung', 
        'ho tro vay', 'no xau', 'big dong', 'tra no', 'thanh toan khoan vay', 'khoan vay',
        'hop tac tra no', 'thu no', 'tat toan', 'khoan no'
    ]
    if any(l in raw_norm or l in cleaned for l in loans):
        return 'spam', 'loan_telesale_spam'
        
    # Commercial ads / survey / promotions / adult telegram spam / religion
    misc_ads = [
        'phap luan cong', 'boi toan', 'tu vi', 'phong thuy', 'sim so dep', 'tang doanh thu', 
        'khao sat', 'trai nghiem goi', 'quang cao', 'khuyen mai', 'tri an khach hang', 'uu dai',
        'mua ban sim', 'goi cuoc', 'live stream', 'xink dep', 't3le'
    ]
    if any(m in raw_norm or m in cleaned for m in misc_ads):
        return 'spam', 'commercial_promo_spam'
        
    # Remaining fallback: if has link to shady gambling domain or unknown domain
    if re.search(r'\.(top|vip|cc|club|icu|xyz|online|site|link|tech|vip|bid)', raw_norm):
        return 'spam', 'unspecified_link_spam'
        
    return 'spam', 'general_spam'


def reannotate_dataset(input_csv: Path, output_csv: Path) -> dict:
    """Reannotate full_dataset_spamscam.csv with 3 classes: legitimate, spam, scam."""
    rows_out = []
    stats = Counter()
    cats = Counter()
    
    with open(input_csv, 'r', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        if 'label_3class' not in fieldnames:
            fieldnames.append('label_3class')
        if 'category' not in fieldnames:
            fieldnames.append('category')
            
        for r in reader:
            orig_label = r['label'].strip()
            msg = r['message']
            
            if orig_label == '0':
                label_3class = 'legitimate'
                category = 'ham_service_otp'
            else:
                label_3class, category = classify_label_1(msg)
                
            r['label_3class'] = label_3class
            r['category'] = category
            rows_out.append(r)
            stats[label_3class] += 1
            cats[category] += 1
            
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
        
    return {
        'total': len(rows_out),
        'label_3class': dict(stats),
        'categories': dict(cats)
    }

if __name__ == '__main__':
    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / 'data' / 'raw'
    
    input_file = raw_dir / 'full_dataset_spamscam.csv'
    output_file = raw_dir / 'vietnamese_spamscam_reannotated.csv'
    
    print(f'Reading input from: {input_file}')
    res = reannotate_dataset(input_file, output_file)
    print(f'Successfully reannotated {res["total"]} rows -> Saved to {output_file}')
    print('\n=== Label Distribution (3 Classes) ===')
    for k, v in res['label_3class'].items():
        pct = (v / res['total']) * 100
        print(f'  {k:15s}: {v:5d} ({pct:5.2f}%)')
        
    # Also reannotate train and test files
    train_input = raw_dir / 'train_dataset_spamscam.csv'
    train_output = raw_dir / 'train_dataset_spamscam_reannotated.csv'
    res_train = reannotate_dataset(train_input, train_output)
    print(f'Train reannotated: {res_train["total"]} rows -> {res_train["label_3class"]}')

    test_input = raw_dir / 'test_dataset_spamscam.csv'
    test_output = raw_dir / 'test_dataset_spamscam_reannotated.csv'
    res_test = reannotate_dataset(test_input, test_output)
    print(f'Test reannotated: {res_test["total"]} rows -> {res_test["label_3class"]}')
