"""
Museum Platform - Requeue Migrated Artifacts with Original IDs
--------------------------------------------------------------
1. Xóa các bản ghi 'migration_clean_csv' khỏi bảng 'pages' để giải phóng trạng thái khóa.
2. Nạp toàn bộ các hiện vật cũ chưa có trong crawled_artifacts_v2.csv vào 'crawl_queue':
   - URL: Canonical Wikipedia URL
   - page_id: ID gốc nguyên bản (1, 2, 3...)
   - Title: Tên hiện vật
   - Priority: 3 (Ưu tiên tuyệt đối)
   - Status: 'queued'
"""

import csv
import os
import sqlite3
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

def requeue_artifacts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_old = os.path.join(base_dir, "crawled_artifacts_new.csv")
    csv_v2 = os.path.join(base_dir, "crawled_artifacts_v2.csv")
    db_path = os.path.join(base_dir, "crawler_state.db")

    if not os.path.exists(csv_old):
        print(f"❌ Không tìm thấy {csv_old}")
        return

    # 1. Đọc danh sách các ID/tên đã cào thành công trong v2
    v2_names = set()
    v2_ids = set()
    if os.path.exists(csv_v2):
        with open(csv_v2, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                name = r.get("Name", "").strip().lower()
                art_id = r.get("ID", "").strip()
                if name:
                    v2_names.add(name)
                if art_id:
                    v2_ids.add(art_id)

    print(f"📊 Trong {os.path.basename(csv_v2)} đã có {len(v2_ids)} hiện vật duy nhất.")

    # 2. Đọc file cũ và chuẩn bị danh sách cần cào
    candidates = []
    seen_urls = set()
    seen_ids = set()

    with open(csv_old, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            art_id_str = r.get("ID", "").strip()
            name = r.get("Name", "").strip()
            if not (art_id_str.isdigit() and name):
                continue
            
            art_id = int(art_id_str)

            # Bỏ qua nếu đã có trong v2 (cả theo ID hoặc theo tên)
            if art_id_str in v2_ids or name.lower() in v2_names:
                continue

            # Xử lý tên thực (loại bỏ tiền tố 'Tạo ')
            real_title = name[4:].strip() if name.startswith("Tạo ") and len(name) > 4 else name
            
            # Loại bỏ nếu chứa namespace Wikipedia rác
            if any(ns in real_title.lower() for ns in ["thảo luận", "bản mẫu", "thành viên", "trợ giúp", "wikipedia:", "template:"]):
                continue

            if real_title.lower() in v2_names:
                continue

            safe_title = real_title.replace(" ", "_")
            canonical_url = f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(safe_title)}"

            if canonical_url in seen_urls or art_id in seen_ids:
                continue

            seen_urls.add(canonical_url)
            seen_ids.add(art_id)
            candidates.append((canonical_url, art_id, real_title))

    print(f"📦 Số hiện vật cũ hợp lệ cần nạp vào hàng đợi: {len(candidates)}")

    # 3. Thao tác trên SQLite
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Xóa các bản ghi migration_clean_csv cũ trong bảng 'pages'
    cur.execute("DELETE FROM pages WHERE discovered_via = 'migration_clean_csv'")
    deleted_pages = cur.rowcount
    print(f"🗑️ Đã giải phóng {deleted_pages} bản ghi cũ bị khóa trong bảng 'pages'.")

    # Upsert vào crawl_queue với priority = 3
    upserted_count = 0
    for url, art_id, title in candidates:
        cur.execute("""
            INSERT INTO crawl_queue (url, page_id, title, depth, priority, status)
            VALUES (?, ?, ?, 1, 3, 'queued')
            ON CONFLICT(url) DO UPDATE SET
                page_id = excluded.page_id,
                title = excluded.title,
                priority = 3,
                status = 'queued'
        """, (url, art_id, title))
        upserted_count += 1

    conn.commit()

    # Kiểm tra lại trạng thái hàng đợi
    queue_counts = dict(cur.execute("SELECT status, count(*) FROM crawl_queue GROUP BY status").fetchall())
    conn.close()

    print("=" * 65)
    print("🎉 HOÀN TẤT NẠP HÀNG ĐỢI VỚI ID GỐC")
    print(f"👉 Số hiện vật cũ đã nạp vào crawl_queue: {upserted_count}")
    print(f"👉 Trạng thái hàng đợi hiện tại: {queue_counts}")
    print("=" * 65)

if __name__ == "__main__":
    requeue_artifacts()
