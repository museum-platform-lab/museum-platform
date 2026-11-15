"""
Museum Platform - Safe Non-Destructive Snapshot Merger
------------------------------------------------------
Hợp nhất an toàn giữa snapshot Legacy (crawled_artifacts_new.csv)
và snapshot V2 (crawled_artifacts_v2.csv) theo quy trình 6 bước:
1. Tính mã băm SHA-256 xác thực snapshot gốc.
2. Cách ly 56 trang (định hướng) sang archive_artifacts.csv.
3. Không ghi đè rỗng lên giá trị đã có:
   - Giữ lại Description chi tiết của Legacy nếu V2 chỉ có tóm tắt ngắn.
   - Ưu tiên Short Description súc tích từ V2.
   - Giữ ảnh thật & Local Image Path của Legacy, loại bỏ 526 ảnh bản đồ vị trí chung.
   - Fallback Era & Location về Legacy nếu V2 trống.
   - Làm sạch toàn bộ maintenance tags trong Categories (sơ khai, webarchive...).
4. Bảo toàn các bản ghi sạch từ Legacy chưa có trong V2.
5. Xuất file crawled_artifacts_production.csv nguyên tử.
6. Xuất báo cáo kiểm định 20 trường hợp Smoke Test (merge_manifest.json).
"""

import csv
import hashlib
import json
import os
import re
import shutil
import sys
from typing import Dict, List, Any, Optional

sys.stdout.reconfigure(encoding="utf-8")

def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def clean_categories(cat_str: str) -> str:
    if not cat_str:
        return ""
    raw_cats = [c.strip() for c in cat_str.split(",") if c.strip()]
    noisy_patterns = [
        r"sơ khai", r"webarchive", r"bài viết", r"liên kết hỏng",
        r"chú thích", r"dọn dẹp", r"wikipedia", r"trang có",
        r"thiếu nguồn", r"cần thêm", r"hộp thông tin", r"đang mở rộng"
    ]
    regex = re.compile("|".join(noisy_patterns), re.IGNORECASE)
    
    clean = []
    for c in raw_cats:
        if regex.search(c):
            continue
        clean.append(c)
    
    # Giữ thứ tự và loại trùng lặp
    return ", ".join(list(dict.fromkeys(clean)))

def run_safe_merge():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    legacy_path = os.path.join(base_dir, "crawled_artifacts_new.csv")
    v2_path = os.path.join(base_dir, "crawled_artifacts_v2.csv")
    prod_path = os.path.join(base_dir, "crawled_artifacts_production.csv")
    archive_path = os.path.join(base_dir, "archive_artifacts.csv")
    manifest_path = os.path.join(base_dir, "merge_manifest.json")

    print("=" * 75)
    print("🚀 BẮT ĐẦU QUY TRÌNH HỢP NHẤT AN TOÀN SNAPSHOT (SAFE MERGE)")
    print("=" * 75)

    # 1. Tính SHA-256 các file nguồn
    legacy_sha = compute_sha256(legacy_path)
    v2_sha = compute_sha256(v2_path)
    print(f"📦 Legacy SHA-256: {legacy_sha}")
    print(f"📦 V2     SHA-256: {v2_sha}")

    # 2. Đọc snapshot Legacy
    legacy_by_id: Dict[str, Dict[str, str]] = {}
    legacy_by_name: Dict[str, Dict[str, str]] = {}
    with open(legacy_path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            art_id = r.get("ID", "").strip()
            name = r.get("Name", "").strip()
            if art_id:
                legacy_by_id[art_id] = r
            if name:
                legacy_by_name[name.lower()] = r
                if name.startswith("Tạo "):
                    legacy_by_name[name[4:].strip().lower()] = r

    print(f"✅ Đã nạp {len(legacy_by_id)} bản ghi Legacy vào bộ nhớ đối chiếu.")

    # 3. Đọc snapshot V2 và tiến hành hợp nhất
    prod_rows = []
    quarantined_disambiguation = []
    
    # Thống kê chi tiết quá trình merge
    stats = {
        "v2_total_processed": 0,
        "disambiguation_quarantined": 0,
        "legacy_matched": 0,
        "legacy_descriptions_preserved": 0,
        "legacy_images_preserved": 0,
        "map_images_replaced": 0,
        "era_fallback_to_legacy": 0,
        "location_fallback_to_legacy": 0,
        "public_date_fallback_to_legacy": 0,
        "v2_newly_discovered": 0,
        "legacy_only_added": 0,
        "total_production_artifacts": 0
    }

    seen_ids = set()
    seen_names = set()
    smoke_test_candidates = []

    with open(v2_path, "r", encoding="utf-8-sig") as f:
        v2_reader = list(csv.DictReader(f))

    fieldnames = [
        "ID", "Name", "Short Description", "Description", "Categories",
        "Main Image URL", "Supporting Images", "Local Image Path", "Author",
        "Contributor", "Artifact Era", "Public Date", "Location"
    ]

    for v2_row in v2_reader:
        stats["v2_total_processed"] += 1
        name = v2_row.get("Name", "").strip()
        art_id = v2_row.get("ID", "").strip()

        # Quy tắc 2: Cách ly trang (định hướng)
        if "(định hướng)" in name.lower() or "(disambiguation)" in name.lower():
            row_arch = dict(v2_row)
            row_arch["Archive Reason"] = "D01 — Disambiguation Page: Trang định hướng danh mục"
            quarantined_disambiguation.append(row_arch)
            stats["disambiguation_quarantined"] += 1
            continue

        # Tìm bản ghi đối ứng trong Legacy
        legacy_row = legacy_by_id.get(art_id) or legacy_by_name.get(name.lower())
        
        merged = dict(v2_row)
        provenance = []

        if legacy_row:
            stats["legacy_matched"] += 1
            
            # --- Quyết định Description ---
            v2_desc = v2_row.get("Description", "").strip()
            legacy_desc = legacy_row.get("Description", "").strip()
            
            # Nếu Legacy có mô tả dài, đầy đủ hơn V2 (vốn chỉ là exintro ngắn)
            if len(legacy_desc) > len(v2_desc) + 150 and len(legacy_desc) > 300:
                merged["Description"] = legacy_desc
                stats["legacy_descriptions_preserved"] += 1
                provenance.append("Description:Legacy")
            else:
                provenance.append("Description:V2")

            # --- Quyết định Short Description ---
            # V2 có tóm tắt lead ngắn rất tốt, ưu tiên V2
            if not merged.get("Short Description") and legacy_row.get("Short Description"):
                merged["Short Description"] = legacy_row["Short Description"]

            # --- Quyết định Main Image & Local Image Path ---
            v2_img = v2_row.get("Main Image URL", "").strip()
            legacy_img = legacy_row.get("Main Image URL", "").strip()
            legacy_local = legacy_row.get("Local Image Path", "").strip()
            
            # Kiểm tra ảnh bản đồ chung ở V2
            is_map_img = any(k in v2_img.lower() for k in ["location_map", "locator_map", "bản_đồ", "vietnam_location"])
            
            # Kiểm tra file ảnh cục bộ Legacy có tồn tại trên máy
            legacy_img_exists = False
            if legacy_local:
                full_local_path = os.path.join(base_dir, legacy_local)
                legacy_img_exists = os.path.exists(full_local_path) and os.path.getsize(full_local_path) > 200

            if legacy_img_exists:
                # Ưu tiên tuyệt đối ảnh đã tải sẵn trên máy
                merged["Local Image Path"] = legacy_local
                if is_map_img or not v2_img:
                    merged["Main Image URL"] = legacy_img
                    if is_map_img:
                        stats["map_images_replaced"] += 1
                stats["legacy_images_preserved"] += 1
                provenance.append("Image:LegacyLocal")
            elif is_map_img and legacy_img and not any(k in legacy_img.lower() for k in ["location_map", "bản_đồ"]):
                merged["Main Image URL"] = legacy_img
                stats["map_images_replaced"] += 1
                provenance.append("Image:LegacyURL")
            elif v2_img and not is_map_img:
                provenance.append("Image:V2")
            elif legacy_img:
                merged["Main Image URL"] = legacy_img
                provenance.append("Image:LegacyFallback")

            # --- Quyết định Artifact Era ---
            v2_era = v2_row.get("Artifact Era", "").strip()
            legacy_era = legacy_row.get("Artifact Era", "").strip()
            if not v2_era and legacy_era:
                merged["Artifact Era"] = legacy_era
                stats["era_fallback_to_legacy"] += 1
                provenance.append("Era:Legacy")
            elif v2_era:
                provenance.append("Era:V2")

            # --- Quyết định Location ---
            v2_loc = v2_row.get("Location", "").strip()
            legacy_loc = legacy_row.get("Location", "").strip()
            if not v2_loc and legacy_loc:
                merged["Location"] = legacy_loc
                stats["location_fallback_to_legacy"] += 1
                provenance.append("Location:Legacy")
            elif v2_loc:
                provenance.append("Location:V2")

            # --- Quyết định Public Date ---
            v2_pub = v2_row.get("Public Date", "").strip()
            legacy_pub = legacy_row.get("Public Date", "").strip()
            if not v2_pub and legacy_pub:
                merged["Public Date"] = legacy_pub
                stats["public_date_fallback_to_legacy"] += 1

            # --- Quyết định Categories ---
            cats_combined = v2_row.get("Categories", "") + ", " + legacy_row.get("Categories", "")
            merged["Categories"] = clean_categories(cats_combined) or "Di tích, Văn hóa Việt Nam"

        else:
            stats["v2_newly_discovered"] += 1
            provenance.append("Source:V2_Exclusive")
            merged["Categories"] = clean_categories(v2_row.get("Categories", "")) or "Di tích, Văn hóa Việt Nam"

        # Đóng nhãn provenance
        merged["Contributor"] = f"Merged ({'+'.join(provenance[:3])})"

        # Chống trùng ID / Name
        if merged["ID"] not in seen_ids and name.lower() not in seen_names:
            seen_ids.add(merged["ID"])
            seen_names.add(name.lower())
            prod_rows.append(merged)
            
            # Thu thập mẫu Smoke Test (20 ca đa dạng)
            if len(smoke_test_candidates) < 20:
                if legacy_row and any("Legacy" in p for p in provenance):
                    smoke_test_candidates.append({
                        "id": merged["ID"],
                        "name": merged["Name"],
                        "v2_desc_len": len(v2_row.get("Description", "")),
                        "prod_desc_len": len(merged["Description"]),
                        "era": merged["Artifact Era"],
                        "location": merged["Location"][:40] if merged["Location"] else "",
                        "local_image": bool(merged["Local Image Path"]),
                        "provenance": "+".join(provenance)
                    })

    # 4. Kiểm tra các bản ghi Legacy sạch chưa có trong V2
    for leg_id, leg_row in legacy_by_id.items():
        leg_name = leg_row.get("Name", "").strip()
        leg_name_low = leg_name.lower()
        
        # Bỏ qua nếu đã có trong production
        if leg_id in seen_ids or leg_name_low in seen_names:
            continue
            
        # Bỏ qua nếu là C01 hoặc C02 hoặc (định hướng)
        if leg_name.startswith("Tạo ") or "(định hướng)" in leg_name_low:
            continue
        if any(ns in leg_name_low for ns in ["thảo luận:", "bản mẫu:", "thành viên:", "trợ giúp:"]):
            continue

        leg_desc = leg_row.get("Description", "").strip()
        if not leg_desc or len(leg_desc) < 30:
            continue

        clean_row = dict(leg_row)
        clean_row["Categories"] = clean_categories(leg_row.get("Categories", "")) or "Di tích, Văn hóa Việt Nam"
        clean_row["Contributor"] = "Merged (LegacyPreserved)"
        
        seen_ids.add(leg_id)
        seen_names.add(leg_name_low)
        prod_rows.append(clean_row)
        stats["legacy_only_added"] += 1

    stats["total_production_artifacts"] = len(prod_rows)

    # 5. Ghi file production nguyên tử
    tmp_prod = prod_path + ".tmp"
    with open(tmp_prod, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(prod_rows)

    os.replace(tmp_prod, prod_path)
    prod_sha = compute_sha256(prod_path)
    print(f"🎉 Đã ghi thành công: {os.path.basename(prod_path)}")
    print(f"📦 Production SHA-256: {prod_sha}")

    # 6. Append các trang định hướng vào archive_artifacts.csv
    if quarantined_disambiguation:
        archive_fieldnames = fieldnames + ["Archive Reason"] if "Archive Reason" not in fieldnames else fieldnames
        archive_exists = os.path.exists(archive_path) and os.path.getsize(archive_path) > 0
        with open(archive_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=archive_fieldnames, quoting=csv.QUOTE_ALL)
            if not archive_exists:
                writer.writeheader()
            writer.writerows(quarantined_disambiguation)
        print(f"⛔ Đã cách ly {len(quarantined_disambiguation)} trang (định hướng) sang archive_artifacts.csv")

    # 7. Xuất merge_manifest.json
    manifest_data = {
        "manifest_version": "2.1",
        "generated_at": os.popen("powershell -Command Get-Date -Format o").read().strip(),
        "input_snapshots": {
            "legacy": {"file": os.path.basename(legacy_path), "sha256": legacy_sha},
            "v2": {"file": os.path.basename(v2_path), "sha256": v2_sha}
        },
        "output_production": {
            "file": os.path.basename(prod_path),
            "sha256": prod_sha,
            "total_records": len(prod_rows)
        },
        "merge_statistics": stats,
        "smoke_test_20_cases": smoke_test_candidates[:20]
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print("=" * 75)
    print("📊 BÁO CÁO THỐNG KÊ HỢP NHẤT DỮ LIỆU:")
    print(f"👉 Tổng bản ghi đầu ra Production: {stats['total_production_artifacts']}")
    print(f"👉 Số mô tả dài Legacy được giữ lại: {stats['legacy_descriptions_preserved']}")
    print(f"👉 Số ảnh thật/cục bộ Legacy được bảo toàn: {stats['legacy_images_preserved']}")
    print(f"👉 Số ảnh bản đồ chung được thay bằng ảnh thật: {stats['map_images_replaced']}")
    print(f"👉 Số niên đại được fallback bổ trợ từ Legacy: {stats['era_fallback_to_legacy']}")
    print(f"👉 Số địa điểm được fallback bổ trợ từ Legacy: {stats['location_fallback_to_legacy']}")
    print(f"👉 Số bài viết mới phát hiện từ V2: {stats['v2_newly_discovered']}")
    print(f"👉 Số bài viết đặc trưng sạch từ Legacy: {stats['legacy_only_added']}")
    print(f"👉 Số trang định hướng đã cách ly: {stats['disambiguation_quarantined']}")
    print(f"📁 Báo cáo kiểm định: {os.path.basename(manifest_path)}")
    print("=" * 75)

if __name__ == "__main__":
    run_safe_merge()
