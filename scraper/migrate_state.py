"""
Museum Platform - State Migration & Reconciliation
---------------------------------------------------
Di chuyển và đối chiếu trạng thái giữa:
1. crawled_artifacts_new.csv (3.201 bản ghi sạch)
2. archive_artifacts.csv (1.430 bản ghi cách ly C01/C02)
3. visited_urls.txt (6.820 URLs cũ)
nạp vào cơ sở dữ liệu SQLite crawler_state.db.
"""

import csv
import os
import re
import urllib.parse
from state_manager import CrawlStateManager

def run_migration():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    clean_csv = os.path.join(base_dir, "crawled_artifacts_new.csv")
    archive_csv = os.path.join(base_dir, "archive_artifacts.csv")
    visited_txt = os.path.join(base_dir, "visited_urls.txt")
    
    state = CrawlStateManager()
    print("=" * 70)
    print("🚀 BẮT ĐẦU DI CƯ & ĐỒNG BỘ TRẠNG THÁI VÀO CRAWLER_STATE.DB")
    print("=" * 70)

    # 1. Nạp 3.201 bản ghi sạch vào `pages`
    clean_count = 0
    if os.path.exists(clean_csv):
        with open(clean_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                art_id = int(row.get("ID", 0)) if row.get("ID", "").isdigit() else 0
                if not name or not art_id:
                    continue
                safe_title = name.replace(" ", "_")
                quoted = urllib.parse.quote(safe_title)
                canonical_url = f"https://vi.wikipedia.org/wiki/{quoted}"
                
                # Cập nhật vào SQLite
                state.mark_completed(
                    page_id=art_id,
                    title=name,
                    canonical_url=canonical_url,
                    namespace=0,
                    discovered_via="migration_clean_csv"
                )
                clean_count += 1
        print(f"✅ Đã nạp {clean_count} bản ghi sạch từ crawled_artifacts_new.csv vào 'pages'.")

    # 2. Nạp 1.430 bản ghi cách ly từ archive_artifacts.csv vào `quarantine_archive`
    # và tách riêng các bài viết hợp lệ trước đây bị bấm nhầm link edit để đưa vào crawl_queue
    quarantine_count = 0
    requeued_count = 0
    if os.path.exists(archive_csv):
        with open(archive_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                reason = row.get("Archive Reason", "").strip() or "C01_OR_C02"
                art_id = int(row.get("ID", 0)) if row.get("ID", "").isdigit() else None
                
                raw_url = f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(name.replace(' ', '_'))}"
                state.mark_quarantined(
                    url=raw_url,
                    title=name,
                    reason_code=reason,
                    page_id=art_id,
                    details=f"From archive_artifacts.csv ID {art_id}"
                )
                quarantine_count += 1

                # Nếu là C01 bắt đầu bằng "Tạo " (ví dụ "Tạo Hai thiếu nữ và em bé"),
                # bóc tách tên bài thật để đưa vào hàng đợi cào bằng API
                if name.startswith("Tạo ") and len(name) > 4:
                    real_title = name[4:].strip()
                    # Kiểm tra xem tên bài thật có chứa namespace rác không
                    if not any(ns in real_title for ns in ["Thảo luận", "Bản mẫu", "Thành viên", "Trợ giúp", "Wikipedia:"]):
                        real_url = f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(real_title.replace(' ', '_'))}"
                        # Thêm vào hàng đợi để cào lại
                        if state.add_to_queue(url=real_url, title=real_title, depth=1, priority=2):
                            requeued_count += 1

        print(f"✅ Đã nạp {quarantine_count} bản ghi vào 'quarantine_archive'.")
        print(f"✨ Đã khôi phục và nạp lại {requeued_count} bài viết thật từ C01 vào hàng đợi 'crawl_queue'.")

    # 3. Đối chiếu visited_urls.txt
    new_visited_set = set()
    old_visited_count = 0
    if os.path.exists(visited_txt):
        with open(visited_txt, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if not u:
                    continue
                old_visited_count += 1
                unq = urllib.parse.unquote(u)
                
                # Bỏ qua nếu là URL edit / redlink
                if "action=edit" in u or "redlink=1" in u:
                    continue
                # Bỏ qua các namespace rác
                if any(ns in unq for ns in ["/wiki/Thảo_luận:", "/wiki/Bản_mẫu:", "/wiki/Thành_viên:", "/wiki/Wikipedia:", "/wiki/Trợ_giúp:", "/wiki/Đặc_biệt:"]):
                    continue
                
                new_visited_set.add(u)

        # Sao lưu visited_urls.txt cũ
        backup_txt = os.path.join(base_dir, "visited_urls_backup.txt")
        if not os.path.exists(backup_txt):
            os.rename(visited_txt, backup_txt)
            print(f"📁 Đã sao lưu visited_urls.txt cũ thành: {os.path.basename(backup_txt)}")

        # Ghi visited_urls.txt đã được làm sạch
        with open(visited_txt, "w", encoding="utf-8") as f:
            for u in sorted(new_visited_set):
                f.write(u + "\n")
        print(f"✅ Đã tinh lọc visited_urls.txt: {old_visited_count} -> {len(new_visited_set)} URLs (loại bỏ link rác/edit).")

    metrics = state.get_metrics()
    print("=" * 70)
    print("📊 TỔNG HỢP TRẠNG THÁI CRAWLER_STATE.DB:")
    print(f"- Số trang hợp lệ đã cào (crawled_pages): {metrics['crawled_pages']}")
    print(f"- Số trang đã cách ly (quarantined_pages): {metrics['quarantined_pages']}")
    print(f"- Số URL đang đợi trong hàng đợi (queued_urls): {metrics['queued_urls']}")
    print("=" * 70)
    state.close()

if __name__ == "__main__":
    run_migration()

