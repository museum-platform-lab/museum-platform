"""
Data Cleaning Step: C02 — Wikipedia namespace
----------------------------------------------
Tiêu chí: Trang thảo luận, bản mẫu, trang người dùng (thành viên), trang hệ thống Wikipedia.
Hành động: Cách ly khỏi dữ liệu hiện vật, append vào archive_artifacts.csv, cập nhật crawled_artifacts_new.csv.
"""

import csv
import os

raw_path = r"d:\project\museum-platform\scraper\crawled_artifacts_new.csv"
archive_path = r"d:\project\museum-platform\scraper\archive_artifacts.csv"

# 1. Đọc dữ liệu chính hiện tại
with open(raw_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

archive_fieldnames = fieldnames + ["Archive Reason"] if "Archive Reason" not in fieldnames else fieldnames

# Danh sách từ khóa namespace cần cách ly
namespace_keywords = [
    "thảo luận bản mẫu:", "thảo luận thể loại:", "thảo luận thành viên:", "thảo luận wikipedia:", "thảo luận:",
    "bản mẫu:", "template:",
    "thành viên:", "user:",
    "wikipedia:", "trợ giúp:", "help:",
    "cổng thông tin:", "portal:",
    "tập tin:", "file:",
    "mediawiki:", "đặc biệt:", "special:"
]

c02_rows = []
valid_rows = []

for r in rows:
    name = r.get("Name", "").strip()
    name_lower = name.lower()

    is_c02 = False
    for kw in namespace_keywords:
        if name_lower.startswith(kw) or (":" in name and kw in name_lower):
            is_c02 = True
            break

    if is_c02:
        row_arch = dict(r)
        row_arch["Archive Reason"] = "C02 — Wikipedia namespace: Trang thảo luận / Bản mẫu / Thành viên / Hệ thống"
        c02_rows.append(row_arch)
    else:
        valid_rows.append(r)

# 2. Append vào archive_artifacts.csv
archive_exists = os.path.exists(archive_path) and os.path.getsize(archive_path) > 0
with open(archive_path, "a", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=archive_fieldnames, quoting=csv.QUOTE_ALL)
    if not archive_exists:
        writer.writeheader()
    writer.writerows(c02_rows)

# 3. Cập nhật lại file chính
with open(raw_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(valid_rows)

print("=" * 60)
print("✅ HOÀN TẤT XỬ LÝ TIÊU CHÍ C02 — WIKIPEDIA NAMESPACE")
print(f"👉 Tổng số bản ghi trước khi lọc: {len(rows)}")
print(f"👉 Số bản ghi C02 đã cách ly sang archive: {len(c02_rows)}")
print(f"👉 Số bản ghi hợp lệ còn lại: {len(valid_rows)}")
print(f"📁 File archive: {os.path.abspath(archive_path)}")
print(f"📁 File chính: {os.path.abspath(raw_path)}")
print("=" * 60)

