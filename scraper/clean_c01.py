"""
Data Cleaning Step: C01 — Crawl failure (Cách ly P0)
-----------------------------------------------------
Tiêu chí: Mô tả chứa thông báo trình soạn thảo Wikipedia, lỗi tải trang, nội dung lỗi redlink.
Hành động: Cách ly P0, append vào archive_artifacts.csv, giữ lại dữ liệu hợp lệ trong crawled_artifacts_new.csv.
"""

import csv
import os
import re
import shutil

raw_path = r"d:\project\museum-platform\scraper\crawled_artifacts_new.csv"
backup_path = r"d:\project\museum-platform\scraper\crawled_artifacts_new_raw_backup.csv"
archive_path = r"d:\project\museum-platform\scraper\archive_artifacts.csv"

# 1. Tạo backup file gốc nguyên vẹn
if not os.path.exists(backup_path):
    shutil.copy2(raw_path, backup_path)
    print(f"🔒 Đã tạo bản sao lưu an toàn: {backup_path}")

# 2. Đọc toàn bộ dữ liệu
with open(raw_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

archive_fieldnames = fieldnames + ["Archive Reason"]

c01_patterns = [
    r"trình soạn thảo sẽ tải bây giờ",
    r"nếu một chốc nữa thông điệp này vẫn xuất hiện",
    r"tải lại trang",
    r"chưa có bài viết với tên này",
    r"không có văn bản trong trang này",
    r"nhập nội dung vào khung",
    r"action=edit",
    r"redlink=1",
    r"404 not found",
    r"lỗi tải trang",
]
c01_regex = re.compile("|".join(c01_patterns), re.IGNORECASE)

c01_rows = []
valid_rows = []

for r in rows:
    name = r.get("Name", "").strip()
    short_desc = r.get("Short Description", "").strip()
    desc = r.get("Description", "").strip()
    combined = f"{name} {short_desc} {desc}"

    is_c01 = False
    if c01_regex.search(combined):
        is_c01 = True
    elif name.startswith("Tạo ") and ("trình soạn thảo" in combined.lower() or len(desc) < 150):
        is_c01 = True

    if is_c01:
        row_arch = dict(r)
        row_arch["Archive Reason"] = "C01 — Crawl failure: Trình soạn thảo / Lỗi tải trang / Redlink"
        c01_rows.append(row_arch)
    else:
        valid_rows.append(r)

# 3. Append vào file archive
archive_exists = os.path.exists(archive_path) and os.path.getsize(archive_path) > 0
with open(archive_path, "a", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=archive_fieldnames, quoting=csv.QUOTE_ALL)
    if not archive_exists:
        writer.writeheader()
    writer.writerows(c01_rows)

# 4. Cập nhật file chính với dữ liệu hợp lệ
with open(raw_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(valid_rows)

print("=" * 60)
print("✅ HOÀN TẤT XỬ LÝ TIÊU CHÍ C01 — CRAWL FAILURE (CÁCH LY P0)")
print(f"👉 Tổng số bản ghi ban đầu: {len(rows)}")
print(f"👉 Số bản ghi lỗi C01 đã cách ly: {len(c01_rows)}")
print(f"👉 Số bản ghi hợp lệ còn lại: {len(valid_rows)}")
print(f"📁 File lưu trữ lỗi: {os.path.abspath(archive_path)}")
print(f"📁 File dữ liệu chính: {os.path.abspath(raw_path)}")
print("=" * 60)

