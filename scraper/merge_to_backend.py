"""
Merge Crawled Artifacts into Backend artifacts.csv
-------------------------------------------------
Công cụ hợp nhất dữ liệu từ file cào (crawled_artifacts.csv) vào file
artifacts.csv chính thức của backend Spring Boot.
Tự động lọc trùng lặp theo tên, đánh số ID tăng tiến an toàn.
"""

import csv
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def merge(crawled_path="crawled_artifacts.csv", backend_path="../backend/src/main/resources/artifacts.csv"):
    if not os.path.exists(crawled_path):
        print(f"❌ Không tìm thấy file dữ liệu cào: {crawled_path}")
        return

    if not os.path.exists(backend_path):
        print(f"❌ Không tìm thấy file backend: {backend_path}")
        return

    # 1. Đọc backend artifacts.csv
    existing_rows = []
    existing_names = set()
    max_id = 0

    with open(backend_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            existing_rows.append(row)
            if row[0].isdigit():
                max_id = max(max_id, int(row[0]))
            if len(row) > 1 and row[1]:
                existing_names.add(row[1].strip().lower())

    print(f"📊 Backend hiện có {len(existing_rows)} hiện vật (ID cao nhất: {max_id}).")

    # 2. Đọc file cào
    crawled_items = []
    with open(crawled_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            if not name:
                continue
            if name.lower() in existing_names:
                continue
            existing_names.add(name.lower())
            crawled_items.append(row)

    if not crawled_items:
        print("ℹ️ Không có hiện vật mới nào cần nạp (toàn bộ đã tồn tại hoặc file trống).")
        return

    # 3. Gán ID mới và ghi tiếp vào backend theo đúng các cột trong header của file đích
    added_count = 0
    with open(backend_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        for item in crawled_items:
            max_id += 1
            row_dict = dict(item)
            row_dict["ID"] = str(max_id)
            if not row_dict.get("Author"):
                row_dict["Author"] = "Wikipedia / Wikimedia Commons"
            if not row_dict.get("Contributor"):
                row_dict["Contributor"] = "(Crawler)"
            
            # Khớp động theo danh sách cột của header file đích
            row_data = [row_dict.get(col, "") for col in header]
            writer.writerow(row_data)
            added_count += 1

    print(f"✅ Đã hợp nhất thành công {added_count} hiện vật mới vào {backend_path}!")
    print(f"📈 Tổng số hiện vật sau khi gộp: {len(existing_rows) + added_count} (ID mới nhất: {max_id}).")

if __name__ == "__main__":
    crawled_file = sys.argv[1] if len(sys.argv) > 1 else "crawled_artifacts.csv"
    backend_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "backend", "src", "main", "resources", "artifacts.csv")
    merge(crawled_file, backend_file)
