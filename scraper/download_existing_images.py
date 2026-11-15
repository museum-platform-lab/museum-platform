"""
Museum Platform - Resilient Atomic Image Downloader
---------------------------------------------------
Tải hàng loạt hình ảnh từ CSV hiện vật với:
1. Ghi file ảnh nguyên tử qua `.tmp` và `os.replace`.
2. Kiểm tra tính toàn vẹn và tính mã băm SHA-256.
3. Ghi file CSV đầu ra nguyên tử (chống corrupt file khi bị kill giữa chừng).
4. Exponential Backoff khi gặp lỗi mạng hoặc HTTP 429/503.
"""

import argparse
import csv
import hashlib
import os
import re
import sys
import time
from typing import Optional, Tuple
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name.strip("_")

def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def download_single_image(
    session: requests.Session,
    img_url: str,
    target_path: str,
    max_retries: int = 3
) -> Tuple[bool, str]:
    """
    Tải 1 file ảnh với ghi file nguyên tử và exponential backoff.
    Trả về (thành_công, checksum_sha256).
    """
    tmp_path = target_path + ".tmp"
    headers = {
        "User-Agent": "MuseumPlatformImageDownloader/2.0 (Cultural Heritage; contact@museum.local) Mozilla/5.0"
    }

    for attempt in range(max_retries):
        try:
            resp = session.get(img_url, headers=headers, timeout=20, stream=True)
            if resp.status_code == 200:
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)

                # Kiểm tra dung lượng tối thiểu (tránh file lỗi 0 bytes hoặc trang lỗi HTML)
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
                    checksum = compute_sha256(tmp_path)
                    os.replace(tmp_path, target_path)
                    return True, checksum
                else:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    return False, ""
            elif resp.status_code in [429, 503]:
                # Wikimedia rate limit / server busy
                wait_time = 1.5 * (2 ** attempt)
                time.sleep(wait_time)
            else:
                return False, ""
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1.0 * (2 ** attempt))
            else:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                return False, ""

    return False, ""

def download_images_for_csv(
    csv_path: str,
    output_path: Optional[str] = None,
    image_dir: str = "images",
    frontend_public: bool = False,
    limit: int = 0
):
    if not os.path.exists(csv_path):
        print(f"❌ Không tìm thấy file CSV: {csv_path}")
        return

    output_path = output_path or csv_path
    if frontend_public:
        save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "artifacts"))
        url_prefix = "/artifacts"
    else:
        save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), image_dir)) if not os.path.isabs(image_dir) else image_dir
        url_prefix = ""

    os.makedirs(save_dir, exist_ok=True)

    session = requests.Session()

    # Đọc dữ liệu đầu vào
    rows = []
    header = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        for r in reader:
            if r:
                rows.append(r)

    if not header:
        print("❌ File CSV không có tiêu đề.")
        return

    col_map = {col: idx for idx, col in enumerate(header)}
    if "Main Image URL" not in col_map:
        print("❌ Không tìm thấy cột 'Main Image URL' trong file CSV.")
        return

    img_col_idx = col_map["Main Image URL"]
    id_col_idx = col_map.get("ID", 0)
    name_col_idx = col_map.get("Name", 1)

    if "Local Image Path" not in col_map:
        header.insert(img_col_idx + 2 if img_col_idx + 2 <= len(header) else len(header), "Local Image Path")
        local_col_idx = header.index("Local Image Path")
        for r in rows:
            r.insert(local_col_idx, "")
    else:
        local_col_idx = col_map["Local Image Path"]

    print("=" * 70)
    print("📸 BẮT ĐẦU TẢI HÌNH ẢNH NGUYÊN TỬ CHO CSV")
    print(f"👉 File nguồn: {os.path.abspath(csv_path)}")
    print(f"👉 Thư mục lưu ảnh: {save_dir}")
    print(f"👉 Tổng số dòng: {len(rows)}")
    print("=" * 70)

    downloaded = 0
    skipped = 0
    failed = 0

    for idx, r in enumerate(rows):
        if limit > 0 and downloaded >= limit:
            print(f"\n🎉 Đã đạt giới hạn {limit} ảnh yêu cầu.")
            break

        artifact_id = r[id_col_idx] if id_col_idx < len(r) else str(idx + 1)
        name = r[name_col_idx] if name_col_idx < len(r) else f"artifact_{artifact_id}"
        img_url = r[img_col_idx] if img_col_idx < len(r) else ""
        current_local = r[local_col_idx] if local_col_idx < len(r) else ""

        if current_local:
            skipped += 1
            continue

        if not img_url or not img_url.startswith("http"):
            continue

        safe_name = sanitize_filename(name)[:40]
        prefix = f"{artifact_id}_{safe_name}"

        clean_url = img_url.split("?")[0]
        ext = os.path.splitext(clean_url)[1].lower()
        if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".svg"]:
            ext = ".jpg"

        filename = f"{prefix}{ext}"
        filepath = os.path.join(save_dir, filename)

        # Nếu file đã tồn tại và hợp lệ (> 200 bytes)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 200:
            local_val = f"{url_prefix.rstrip('/')}/{filename}" if url_prefix else os.path.relpath(filepath, os.getcwd()).replace("\\", "/")
            r[local_col_idx] = local_val
            skipped += 1
            continue

        success, checksum = download_single_image(session, img_url, filepath)
        if success:
            local_val = f"{url_prefix.rstrip('/')}/{filename}" if url_prefix else os.path.relpath(filepath, os.getcwd()).replace("\\", "/")
            r[local_col_idx] = local_val
            downloaded += 1
            print(f"[{downloaded}] ✅ #{artifact_id} {name} (SHA: {checksum[:8]}...)")
        else:
            failed += 1
            print(f"[{failed}] ⚠️ Lỗi tải ảnh #{artifact_id} {name}: {img_url}")

    # Ghi file CSV đầu ra NGUYÊN TỬ: ghi ra .tmp rồi atomic replace
    tmp_output = output_path + ".tmp"
    with open(tmp_output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)

    os.replace(tmp_output, output_path)

    print("\n" + "=" * 70)
    print("✅ HOÀN TẤT TẢI ẢNH!")
    print(f"- Tải thành công: {downloaded} ảnh")
    print(f"- Đã có sẵn / Bỏ qua: {skipped} ảnh")
    print(f"- Thất bại: {failed} ảnh")
    print(f"📁 File CSV đã cập nhật an toàn: {os.path.abspath(output_path)}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tải ảnh hàng loạt từ CSV hiện vật (Nguyên tử & Checksum)")
    parser.add_argument("csv_file", nargs="?", default="crawled_artifacts_verified.csv", help="Đường dẫn file CSV")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file CSV cập nhật")
    parser.add_argument("--image-dir", type=str, default="images", help="Thư mục lưu ảnh")
    parser.add_argument("--frontend-public", action="store_true", help="Tải vào frontend/public/artifacts")
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số ảnh cần tải")
    args = parser.parse_args()

    download_images_for_csv(
        csv_path=args.csv_file,
        output_path=args.output,
        image_dir=args.image_dir,
        frontend_public=args.frontend_public,
        limit=args.limit
    )
