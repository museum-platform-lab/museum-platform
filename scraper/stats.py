import csv
import json
import os
import sqlite3

base = os.path.dirname(os.path.abspath(__file__))
v2_csv = os.path.join(base, "crawled_artifacts_v2.csv")
manifest_path = os.path.join(base, "crawl_manifest.json")
db_path = os.path.join(base, "crawler_state.db")
raw_dir = os.path.join(base, "raw_pages")

v2_count = 0
first_few = []
last_few = []
if os.path.exists(v2_csv):
    with open(v2_csv, "r", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        header = next(r, None)
        all_rows = [row for row in r if row]
        v2_count = len(all_rows)
        first_few = all_rows[:3]
        last_few = all_rows[-3:] if len(all_rows) > 3 else []

manifest_data = {}
if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

db_metrics = {}
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Reset batched processing items back to queued if server stopped
    with conn:
        conn.execute("UPDATE crawl_queue SET status = 'queued' WHERE status = 'processing'")
    cur.execute("SELECT COUNT(*) FROM pages WHERE status = 'crawled'")
    crawled_pages = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM quarantine_archive")
    quarantined = cur.fetchone()[0]
    cur.execute("SELECT status, COUNT(*) FROM crawl_queue GROUP BY status")
    queue_counts = dict(cur.fetchall())
    db_metrics = {
        "total_crawled_pages_in_db": crawled_pages,
        "quarantined_pages": quarantined,
        "queue_status": queue_counts
    }

raw_count = len(os.listdir(raw_dir)) if os.path.exists(raw_dir) else 0

print("=" * 60)
print(f"📊 BÁO CÁO KẾT QUẢ ĐỢT CÀO MỚI:")
print(f"1. Số bản ghi thu thập mới trong crawled_artifacts_v2.csv: {v2_count}")
print(f"2. Số file JSON raw lưu trong raw_pages/: {raw_count}")
print(f"3. Thống kê Manifest: {json.dumps(manifest_data, ensure_ascii=False, indent=2)}")
print(f"4. Thống kê CSDL SQLite (crawler_state.db): {json.dumps(db_metrics, ensure_ascii=False, indent=2)}")
print("=" * 60)
if first_few:
    print("3 bản ghi đầu tiên trong v2:")
    for row in first_few:
        print(f"  - #{row[0]} {row[1]} | Niên đại: {row[10] or 'N/A'} | Công bố: {row[11] or 'N/A'}")
if last_few:
    print("3 bản ghi gần nhất trong v2:")
    for row in last_few:
        print(f"  - #{row[0]} {row[1]} | Niên đại: {row[10] or 'N/A'} | Công bố: {row[11] or 'N/A'}")
