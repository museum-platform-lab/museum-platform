"""
Museum Platform - Production Final Polish & Audit Remediation
------------------------------------------------------------
Giải quyết triệt để toàn bộ 6 hành động đề xuất từ bản Audit mới (09/11/2026):
1. Snapshot & Hashes: Bảo toàn các mốc snapshot b501a27d..., a951e074...
2. URL Unquoting & Heuristic Image Purge:
   - Áp dụng urllib.parse.unquote để bắt toàn bộ tên file mã hóa URL (ví dụ: C%E1%BB%95ng_B%E1%BA%AFc...).
   - Purge triệt để các ảnh generic, bản đồ hành chính, cờ, logo, Wikimedia badges (ambox, shackle, question mark),
     ảnh ga Đà Lạt gán nhầm cho đình làng Phan Thiết, ảnh Cổng Bắc Thăng Long gán nhầm cho Đình Tường Phiêu (ID 236),...
   - Để trống ("") để frontend hiển thị placeholder chuyên nghiệp theo khuyến nghị.
3. Đồng bộ Local Image Path: Đảm bảo chỉ trỏ file thực sự tồn tại trên đĩa (> 200 bytes).
4. Tách raw_categories & Xuất Source Quality Flags (source_quality_flags.json):
   - Lưu trữ toàn bộ 167 nhãn 'không nguồn', 122 'cần biên tập', 68 'nhiều vấn đề', CS1, Wikidata...
5. ID Migration Map (id_migration_map.json):
   - Ghi nhận 4836 -> 523 cho 'Tử Cấm thành (Huế)' kèm cảnh báo xung đột khóa backend.
6. Provenance Manifest (production_provenance_manifest.json):
   - Tách crawled_at (ISO-8601) độc lập với Public Date (năm công nhận 4 chữ số).
   - Tính SHA-256 xác thực snapshot cuối cùng.
"""

import csv
import hashlib
import json
import os
import sys
import urllib.parse
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def is_generic_or_reused_image(entity_id: str, entity_name: str, url: str, count: int, auditor_flagged: bool) -> bool:
    if not url:
        return False
    
    # 1. Giải mã URL percent-encoding
    decoded_url = urllib.parse.unquote(url).lower()
    filename = decoded_url.split("/")[-1]
    name_low = entity_name.lower()

    # Trường hợp ngoại lệ đặc thù: thực thể chính là đối tượng đó
    if "cột cờ hà nội" in name_low and "flag_tower" in filename:
        return False
    if "eiffel" in name_low and "eiffel" in filename:
        return False
    if "louvre" in name_low and "louvre" in filename:
        return False
    if "bản đồ hồng đức" in name_low and "hồng_đức" in filename:
        return False
    if "đền đô" in name_low and "đền_đô" in filename and count <= 3:
        # Giữ lại cho chính Đền Đô (ID 200), không giữ cho Từ Sơn
        return entity_id != "200"
    if ("chùa keo" in name_low or "chùa keo thái bình" in name_low) and "chuakeothaibinh" in filename:
        return entity_id not in ["54", "183"]

    # 2. Danh sách mẫu file generic, biểu tượng, bản đồ, logo, badge
    generic_patterns = [
        "dharma_wheel", "blank.png", "logo_", "emblem_", "osm-intl", "wikisource",
        "without_photo", "no_image", "placeholder", "flag_of_", "hiero_", "disambig",
        "timeline", "red_pog", "crystal_", "commons-logo", "question_book",
        "location_map", "locator_map", "relief_location", "bản_đồ", "vietnam_location",
        "symbol_", "icon_", "sign_", "cổng_bắc_hoàng_thành_thăng_long", "cổng bắc hoàng thành thăng long",
        "phong_nha-ke_bang_cave3.jpg", "thac_ban_gioc.jpg", "chuamotcot2.jpg", "thienmupagoda.jpg",
        "shackle", "padlock", "question_mark", "wiktionary", "wikiquote", "wikibooks", "wikidata",
        "wikispecies", "4chan", "eighty-six", "status_iucn", "communist_party", "vietnam_region_map",
        "coat_of_arms", "national_emblem", "ambox", "delicatearch", "da_lat_train_station",
        "appointment.svg", "merge-arrows.svg", "hangugeo-chosonmal.svg", "_districts.png",
        "in_turkey.svg", "khong_hinh_tu_do.svg", "nuvola_apps_", "p_literature.svg",
        "history.svg", "fiav_historical.svg", "中華人民共和國國徽", "gnome-timezone.svg",
        "black_flag", "long_tinh_flag", "map-of-southeast-asia", "battle_of_bạch_đằng",
        "four_freedoms_flag", "hinduism_percent", "french_government_logo",
        "tet_offensive_map", "three_kingdoms_of_korea_map", "warsaw_pact",
        "sea_of_japan_map", "map_pointer", "pacific_hurricane", "indo-european",
        "delhi_sultanate_flag", "tibetan_buddhist_flag", "administrative_division",
        "blank_map", "binh_tri_thien_province_in_vietnam_map", "vietnam_ct.",
        "_in_dong_thap_province_map", "dong_thap_bus_map"
    ]

    for pat in generic_patterns:
        if pat in decoded_url:
            return True

    # 3. Phân loại theo định dạng file SVG (thường là biểu đồ, huy hiệu hoặc icon trên wiki)
    if filename.endswith(".svg"):
        # Chỉ giữ nếu tên thực thể rõ ràng là ấn triều Nguyễn và tên file chứa 'ấn'
        if ("ấn" in name_low or "kim ấn" in name_low or "ngọc tỷ" in name_low) and "_ấn_" in filename:
            return False
        return True

    # 4. Ảnh bị kiểm toán viên đánh dấu generic candidate và không khớp với thực thể
    if auditor_flagged and count >= 2:
        return True

    # 5. Tần suất xuất hiện từ 4 lần trở lên
    if count >= 4:
        return True

    return False

def run():
    base_dir = r"d:\project\museum-platform\scraper"
    prod_path = os.path.join(base_dir, "crawled_artifacts_production.csv")
    backup_path = os.path.join(base_dir, "crawled_artifacts_production_backup_pre_final_polish.csv")
    pre_refine_path = os.path.join(base_dir, "crawled_artifacts_production_backup_pre_refine.csv")
    review_csv_path = r"d:\quick-access\museum_production_new_vs_old_review.csv"
    
    migration_map_path = os.path.join(base_dir, "id_migration_map.json")
    manifest_path = os.path.join(base_dir, "production_provenance_manifest.json")
    quality_flags_path = os.path.join(base_dir, "source_quality_flags.json")

    # 1. Đọc auditor flags
    auditor_flags = {}
    if os.path.exists(review_csv_path):
        with open(review_csv_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                eid = row["ID"]
                flags = [x.strip() for x in row["flags"].split(";") if x.strip()]
                auditor_flags[eid] = flags

    # 2. Đọc file sản xuất
    with open(prod_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    # Đếm tần suất xuất hiện URL (đã chuẩn hóa)
    url_counts = Counter(r["Main Image URL"].strip() for r in rows if r.get("Main Image URL", "").strip())

    cleared_generic_images = 0
    cleared_invalid_local_paths = 0
    preserved_authentic_images = 0
    preserved_local_files = 0

    for r in rows:
        eid = r["ID"]
        name = r["Name"]
        img_url = r.get("Main Image URL", "").strip()
        local_path = r.get("Local Image Path", "").strip()
        count = url_counts.get(img_url, 0)
        is_flagged = bool("GENERIC_IMAGE_CANDIDATE" in auditor_flags.get(eid, []) or "REUSED_IMAGE_10_PLUS" in auditor_flags.get(eid, []))

        # Kiểm tra ảnh generic
        if is_generic_or_reused_image(eid, name, img_url, count, is_flagged):
            r["Main Image URL"] = ""
            r["Local Image Path"] = ""
            cleared_generic_images += 1
        elif img_url:
            preserved_authentic_images += 1
            # Kiểm tra local image path
            if local_path:
                full_local = os.path.join(base_dir, local_path)
                if os.path.exists(full_local) and os.path.getsize(full_local) > 200:
                    preserved_local_files += 1
                else:
                    r["Local Image Path"] = ""
                    cleared_invalid_local_paths += 1

    # 3. Ghi file production
    tmp_path = prod_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    os.replace(tmp_path, prod_path)
    final_sha = compute_sha256(prod_path)

    # 4. Trích xuất và xuất Source Quality Flags (giải quyết Action 4)
    quality_signals = [
        "hoàn toàn không có nguồn tham khảo", "trang cần được biên tập lại",
        "bài có nhiều vấn đề", "bài viết sơ khai", "cần thêm nguồn",
        "chưa được kiểm chứng", "bài chất lượng kém", "bài viết tự xuất bản",
        "nghi vấn về độ nổi bật", "trung lập đang bị tranh cãi",
        "tất cả bài viết sơ khai", "tọa độ trên wikidata", "nguồn cs1", "bản mẫu webarchive"
    ]
    
    source_quality_data = {
        "metadata": {
            "description": "Lưu trữ đầy đủ các tín hiệu chất lượng và nhãn kiểm thử nguồn gốc Wikipedia bị tách khỏi taxonomy hiển thị",
            "extracted_from": os.path.basename(pre_refine_path),
            "generated_at": "2026-11-09T10:28:00Z"
        },
        "records": {}
    }

    if os.path.exists(pre_refine_path):
        with open(pre_refine_path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                eid = r["ID"]
                name = r["Name"]
                raw_cats = [c.strip() for c in r["Categories"].split(",") if c.strip()]
                found_flags = []
                for cat in raw_cats:
                    cat_low = cat.lower()
                    for sig in quality_signals:
                        if sig in cat_low:
                            found_flags.append(cat)
                            break
                if found_flags:
                    source_quality_data["records"][eid] = {
                        "name": name,
                        "source_quality_flags": found_flags,
                        "raw_categories_count": len(raw_cats)
                    }

    with open(quality_flags_path, "w", encoding="utf-8") as f:
        json.dump(source_quality_data, f, ensure_ascii=False, indent=2)

    # 5. Xuất ID Migration Map (giải quyết Action 5)
    migration_map = {
        "manifest_version": "1.1",
        "title": "Museum Platform Entity ID Migration Map",
        "description": "Theo dõi việc khôi phục khóa ID legacy và cảnh báo tích hợp backend",
        "entity_id_migrations": [
            {
                "entity_name": "Tử Cấm thành (Huế)",
                "legacy_v1_id": "523",
                "temporary_v2_id": "4836",
                "final_production_id": "523",
                "action": "RESTORED_TO_LEGACY_KEY",
                "rationale": "Khôi phục ID 523 để đồng bộ với định danh gốc trong crawled_artifacts_new.csv và thư mục images/523_..., triệt tiêu bản ghi trùng tên 'Tạo Tử cấm thành (Huế)'.",
                "backend_impact_warning": "LƯU Ý: Trong seed data cũ (backend/src/main/resources/artifacts.csv - 1.123 dòng), ID 523 từng thuộc về 'Tranh vẽ bình phong trước viện Cơ mật'. Khi import dataset mới vào backend, cần thực hiện migrate database schema hoặc re-seed toàn bộ để tránh xung đột khóa chính."
            }
        ]
    }
    with open(migration_map_path, "w", encoding="utf-8") as f:
        json.dump(migration_map, f, ensure_ascii=False, indent=2)

    # 6. Xuất Provenance Manifest (giải quyết Action 6)
    manifest_data = {
        "manifest_version": "2.4",
        "dataset_name": "Museum Platform Production Verified Dataset",
        "file": os.path.basename(prod_path),
        "sha256": final_sha,
        "total_records": len(rows),
        "crawled_at": "2026-11-08T18:53:21Z",
        "audit_resolution": {
            "blockers_resolved": 3,
            "out_of_scope_quarantined": 30,
            "fake_crawl_timestamps_cleared": 3840,
            "maintenance_tags_cleaned_rows": 3697,
            "unquoted_and_generic_images_purged": cleared_generic_images
        },
        "image_statistics": {
            "total_authentic_main_images": preserved_authentic_images,
            "total_local_files_verified_on_disk": preserved_local_files,
            "generic_or_reused_images_purged": cleared_generic_images,
            "invalid_local_paths_cleared": cleared_invalid_local_paths,
            "ui_placeholder_recommended_count": len(rows) - preserved_authentic_images
        },
        "recognition_year_statistics": {
            "verified_years_count": sum(1 for r in rows if r.get("Public Date")),
            "description": "Năm công nhận bảo vật quốc gia / xếp hạng di tích (4 chữ số)."
        },
        "snapshots_lineage": {
            "snapshot_0_pre_refine_sha256": "b501a27d66bf8ff6655aee5c2b01a06e04afa9270f38c2edd0893b061e99d9f1",
            "snapshot_1_pre_final_polish_sha256": "a951e074180933174c6f562754da4a4a8f49e6eb3283cdca24c430b1350a4d64",
            "final_production_sha256": final_sha
        }
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("🎉 HOÀN THIỆN TOÀN BỘ 6 KHUYẾN NGHỊ AUDIT")
    print(f"👉 File đích: {os.path.basename(prod_path)}")
    print(f"👉 Tổng số bản ghi: {len(rows)}")
    print(f"👉 Ảnh biểu tượng/dùng chung/URL mã hóa đã xóa: {cleared_generic_images}")
    print(f"👉 Ảnh thực thể chân thực giữ lại: {preserved_authentic_images}")
    print(f"👉 Ảnh cục bộ có sẵn và hợp lệ trên đĩa: {preserved_local_files}")
    print(f"👉 SHA-256 xác thực: {final_sha}")
    print(f"📁 Quality Flags: {os.path.basename(quality_flags_path)}")
    print(f"📁 ID Migration Map: {os.path.basename(migration_map_path)}")
    print(f"📁 Provenance Manifest: {os.path.basename(manifest_path)}")
    print("=" * 70)

if __name__ == "__main__":
    run()
