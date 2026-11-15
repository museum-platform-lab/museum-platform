"""
Museum Platform - Exhaustive Deep Crawler (Cào vét cạn dữ liệu Di sản & Hiện vật)
----------------------------------------------------------------------------------
Thu thập dữ liệu đệ quy (BFS spider): Đi từ các bài viết danh sách, thể loại, bảo vật quốc gia,
di tích đặc biệt, bảo tàng; trích xuất toàn bộ bảng dữ liệu và tiếp tục bám theo mọi link nội bộ
liên quan để vét cạn toàn bộ hiện vật văn hóa lịch sử Việt Nam.
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.parse
from collections import deque
import requests
from bs4 import BeautifulSoup

# Hỗ trợ in tiếng Việt trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CSV_HEADER = [
    "ID",
    "Name",
    "Short Description",
    "Description",
    "Categories",
    "Main Image URL",
    "Supporting Images",
    "Local Image Path",
    "Author",
    "Contributor",
    "Artifact Era",
    "Public Date",
    "Location"
]

DEFAULT_SEEDS = [
    "https://vi.wikipedia.org/wiki/B%E1%BA%A3o_v%E1%BA%ADt_qu%E1%BB%91c_gia_(Vi%E1%BB%87t_Nam)",
    "https://vi.wikipedia.org/wiki/Di_t%C3%ADch_qu%E1%BB%91c_gia_%C4%91%E1%BA%B7c_bi%E1%BB%87t_(Vi%E1%BB%87t_Nam)",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:B%E1%BA%A3o_v%E1%BA%ADt_qu%E1%BB%91c_gia_c%E1%BB%A7a_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Hi%E1%BB%87n_v%E1%BA%ADt_kh%E1%BA%A3o_c%E1%BB%95_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Di_t%C3%ADch_qu%E1%BB%91c_gia_%C4%91%E1%BA%B7c_bi%E1%BB%87t_t%E1%BA%A1i_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Tr%E1%BB%91ng_%C4%91%E1%BB%93ng_%C4%90%C3%B4ng_S%C6%A1n",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:B%E1%BA%A3o_t%C3%A0ng_t%E1%BA%A1i_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Ki%E1%BA%BFn_tr%C3%BAc_c%E1%BB%95_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Ch%C3%B9a_t%E1%BA%A1i_Vi%E1%BB%87t_Nam",
    "https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:Th%C3%A1p_Ch%C4%83m"
]

RELEVANT_KEYWORDS = [
    "trống", "thạp", "tượng", "chuông", "bia", "mộ", "đỉnh", "đao", "kiếm", "ấn", "kim sách",
    "ngọc tỷ", "bảo vật", "di tích", "di vật", "hiện vật", "khảo cổ", "văn hóa", "thời", "triều",
    "chùa", "đền", "đình", "tháp", "miếu", "lăng", "thành", "phủ", "bảo tàng", "đông sơn",
    "sa huỳnh", "óc eo", "chăm pa", "đại việt", "phù điêu", "gốm", "sứ", "đồng", "vàng", "bạc",
    "khánh", "cổ vật", "hoàng thành", "cố đô", "di sản", "nghệ thuật cổ", "kiến trúc cổ"
]

EXCLUDE_NAMESPACES = (
    "/wiki/Đặc_biệt:",
    "/wiki/Special:",
    "/wiki/Trợ_giúp:",
    "/wiki/Help:",
    "/wiki/Thảo_luận:",
    "/wiki/Talk:",
    "/wiki/Tập_tin:",
    "/wiki/File:",
    "/wiki/Bản_mẫu:",
    "/wiki/Template:",
    "/wiki/Wikipedia:",
    "/wiki/Cổng_thông_tin:",
    "/wiki/Portal:",
    "/wiki/Trang_Chính",
    "/wiki/Tài_liệu:",
    "/wiki/MediaWiki:"
)

INDEX_PAGES = [
    "bảo_vật_quốc_gia_(việt_nam)",
    "di_tích_quốc_gia_đặc_biệt_(việt_nam)",
    "danh_sách_di_tích_quốc_gia_đặc_biệt_việt_nam",
    "danh_sách_bảo_vật_quốc_gia_việt_nam",
    "danh_sách_bảo_tàng_tại_việt_nam"
]

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def get_fullres_image(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    url = re.sub(r"\?.*$", "", url)
    m = re.match(r"https?://(?:thumb|upload)\.wikimedia\.org/(.*?)/thumb/(.*?)/[^/]+$", url)
    if m:
        return f"https://upload.wikimedia.org/{m.group(1)}/{m.group(2)}"
    return url

def extract_era_from_text(text: str) -> str:
    patterns = [
        r"(thế kỷ\s+[IVXLCDM\d]+(?:\s*[-–]\s*[IVXLCDM\d]+)?(?:\s*TCN)?)",
        r"(cách ngày nay\s+[\d\s.,–-]+năm)",
        r"(khoảng năm\s+\d+(?:\s*[-–]\s*\d+)?)",
        r"(năm\s+\d{3,4})",
        r"(thời\s+(?:Hồng Bàng|Đông Sơn|Sa Huỳnh|Óc Eo|Chăm Pa|Đinh|Tiền Lê|Lý|Trần|Hồ|Hậu Lê|Lê sơ|Lê Trung hưng|Mạc|Tây Sơn|Nguyễn|Pháp thuộc|Bắc thuộc))"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""

def extract_location_from_text(text: str) -> str:
    m = re.search(r"(Bảo tàng\s+[^\.,;\n\)]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(tại\s+[^\.,;\n]+(?:Hà Nội|TP\.?\s*HCM|Huế|Đà Nẵng|Quảng Nam|Bắc Ninh|Ninh Bình|Thanh Hóa|Phú Thọ|Hải Phòng|Nam Định|Quảng Ninh|Lâm Đồng|An Giang|Cần Thơ))", text, re.IGNORECASE)
    if m2:
        return m2.group(1).replace("tại", "").strip()
    return ""

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name.strip("_")

def download_image_file(session: requests.Session, img_url: str, save_dir: str, file_prefix: str, url_prefix: str = "") -> str:
    """Tải hình ảnh về máy, trả về đường dẫn lưu trữ để ghi vào cột CSV"""
    if not img_url:
        return ""
    try:
        os.makedirs(save_dir, exist_ok=True)
        clean_url = img_url.split("?")[0]
        ext = os.path.splitext(clean_url)[1].lower()
        if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".svg"]:
            ext = ".jpg"

        filename = f"{file_prefix}{ext}"
        filepath = os.path.join(save_dir, filename)

        # Trả về đường dẫn nếu file đã tồn tại và hợp lệ
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            if url_prefix:
                return f"{url_prefix.rstrip('/')}/{filename}"
            return os.path.relpath(filepath, os.getcwd()).replace("\\", "/")

        resp = session.get(img_url, timeout=15, stream=True)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            if url_prefix:
                return f"{url_prefix.rstrip('/')}/{filename}"
            return os.path.relpath(filepath, os.getcwd()).replace("\\", "/")
        else:
            print(f"      [Tải ảnh] HTTP {resp.status_code} khi tải {img_url}")
    except Exception as e:
        print(f"      [Tải ảnh] Lỗi tải {img_url}: {e}")
    return ""

class ExhaustiveMuseumCrawler:
    def __init__(self, output_csv="crawled_artifacts.csv", visited_file="visited_urls.txt", delay=0.3, max_items=0, backend_csv=None, seeds=None, download_images=True, image_dir="images", frontend_public=False):
        self.output_csv = output_csv
        self.visited_file = visited_file
        self.delay = delay
        self.max_items = max_items
        self.backend_csv = backend_csv
        self.seeds = seeds or DEFAULT_SEEDS
        self.download_images = download_images
        self.frontend_public = frontend_public

        if self.frontend_public:
            self.image_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "artifacts"))
            self.url_prefix = "/artifacts"
        else:
            self.image_dir = os.path.abspath(image_dir)
            self.url_prefix = ""

        self.visited = set()
        self.seen_names = set()
        self.queue = deque()
        self.context_cache = {}  # url -> {era, location, main_image, name}

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MuseumPlatformCrawler/2.0 (Cultural Heritage Project; contact@museum.local) Mozilla/5.0"
        })

        self.current_id = self.init_id()
        self.load_state()

    def init_id(self) -> int:
        max_id = 0
        paths = []
        if self.backend_csv and os.path.exists(self.backend_csv):
            paths.append(self.backend_csv)
        if os.path.exists(self.output_csv):
            paths.append(self.output_csv)

        for p in paths:
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and row[0].isdigit():
                            val = int(row[0])
                            if val > max_id:
                                max_id = val
            except Exception as e:
                print(f"[Init ID] Lưu ý khi đọc file {p}: {e}")

        return max_id + 1 if max_id > 0 else 1

    def load_state(self):
        # 1. Tải visited URLs
        if os.path.exists(self.visited_file):
            with open(self.visited_file, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u:
                        self.visited.add(u)
            print(f"[State] Đã tải {len(self.visited)} liên kết đã quét trước đó.")

        # 2. Tải danh sách tên đã có để tránh trùng
        check_files = []
        if self.backend_csv and os.path.exists(self.backend_csv):
            check_files.append(self.backend_csv)
        if os.path.exists(self.output_csv):
            check_files.append(self.output_csv)

        for cf in check_files:
            try:
                with open(cf, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("Name")
                        if name:
                            self.seen_names.add(name.strip().lower())
            except Exception as e:
                print(f"[State] Không thể đọc danh sách tên từ {cf}: {e}")

        print(f"[State] Đang theo dõi {len(self.seen_names)} hiện vật để chống lưu trùng lặp.")

    def save_visited(self, url: str):
        self.visited.add(url)
        with open(self.visited_file, "a", encoding="utf-8") as f:
            f.write(url + "\n")

    def save_artifact(self, artifact: dict):
        # Ghi vào file output CSV
        file_exists = os.path.exists(self.output_csv)
        with open(self.output_csv, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER, quoting=csv.QUOTE_ALL)
            if not file_exists or os.path.getsize(self.output_csv) == 0:
                writer.writeheader()
            writer.writerow(artifact)
            f.flush()

        # Đồng bộ trực tiếp vào backend nếu bật
        if self.backend_csv and os.path.exists(self.backend_csv):
            try:
                with open(self.backend_csv, "a", encoding="utf-8-sig", newline="") as bf:
                    writer = csv.DictWriter(bf, fieldnames=CSV_HEADER, quoting=csv.QUOTE_ALL)
                    writer.writerow(artifact)
                    bf.flush()
            except Exception as e:
                print(f"[Backend Sync] Lỗi khi ghi: {e}")

    def is_relevant(self, title: str, text: str, cats: list) -> bool:
        combined = (title + " " + " ".join(cats) + " " + text[:600]).lower()
        return any(k in combined for k in RELEVANT_KEYWORDS)

    def is_index_or_category(self, url: str) -> bool:
        unquoted = urllib.parse.unquote(url).lower()
        if "/wiki/thể_loại:" in unquoted or "/wiki/category:" in unquoted:
            return True
        for idx_page in INDEX_PAGES:
            if idx_page in unquoted:
                return True
        if unquoted.startswith("/wiki/danh_sách") or "/wiki/danh_sách" in unquoted:
            return True
        return False

    def parse_table_items(self, soup: BeautifulSoup, page_url: str):
        """Trích xuất hiện vật trực tiếp từ bảng Wikitable (Bảo vật quốc gia, Di tích đặc biệt)"""
        tables = soup.find_all("table", class_="wikitable")
        discovered_count = 0

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
            col_map = {}
            for idx, h in enumerate(header_cells):
                hl = h.lower()
                if "tên" in hl or "di tích" in hl or "hiện vật" in hl:
                    if "name" not in col_map:
                        col_map["name"] = idx
                elif "niên đại" in hl or "thời" in hl or "văn hóa" in hl or "hạng mục" in hl:
                    col_map["era"] = idx
                elif "chủ sở hữu" in hl or "đơn vị" in hl:
                    col_map["owner"] = idx
                elif "địa phương" in hl or "địa điểm" in hl:
                    col_map["location"] = idx
                elif "ảnh" in hl or "hình ảnh" in hl:
                    col_map["image"] = idx

            if "name" not in col_map:
                continue

            for r in rows[1:]:
                cells = r.find_all(["td", "th"])
                if len(cells) <= col_map["name"]:
                    continue

                name_cell = cells[col_map["name"]]
                raw_name = clean_text(name_cell.get_text())
                if not raw_name or len(raw_name) < 2:
                    continue

                era = clean_text(cells[col_map["era"]].get_text()) if "era" in col_map and col_map["era"] < len(cells) else ""
                owner = clean_text(cells[col_map["owner"]].get_text()) if "owner" in col_map and col_map["owner"] < len(cells) else ""
                loc = clean_text(cells[col_map["location"]].get_text()) if "location" in col_map and col_map["location"] < len(cells) else ""
                loc_full = f"{owner}, {loc}".strip(", ") if owner else loc

                # Tìm ảnh đại diện từ bảng
                img_url = ""
                if "image" in col_map and col_map["image"] < len(cells):
                    img_tag = cells[col_map["image"]].find("img")
                    if img_tag and img_tag.get("src"):
                        img_url = get_fullres_image(img_tag["src"])

                # Tìm các liên kết chi tiết để quét sâu hơn
                for a in name_cell.find_all("a", href=True):
                    href = a["href"]
                    if not href.startswith("http"):
                        href = urllib.parse.urljoin("https://vi.wikipedia.org", href)
                    unq = urllib.parse.unquote(href)
                    if "/wiki/" in href and not any(p in unq for p in EXCLUDE_NAMESPACES):
                        clean_href = href.split("#")[0]
                        self.context_cache[clean_href] = {
                            "era": era,
                            "location": loc_full,
                            "main_image": img_url,
                            "name": raw_name
                        }
                        if clean_href not in self.visited and clean_href not in self.queue:
                            self.queue.append(clean_href)
                            discovered_count += 1

        if discovered_count > 0:
            print(f"   [Bảng dữ liệu] +{discovered_count} liên kết hiện vật được nạp vào hàng đợi.")

    def parse_category_page(self, soup: BeautifulSoup, page_url: str):
        """Thu thập danh mục con và tất cả bài viết trong trang Thể loại"""
        cat_links = 0
        # 1. Các bài viết thuộc thể loại
        pages_div = soup.find("div", id="mw-pages")
        if pages_div:
            for a in pages_div.find_all("a", href=True):
                href = urllib.parse.urljoin("https://vi.wikipedia.org", a["href"]).split("#")[0]
                unq = urllib.parse.unquote(href)
                if "/wiki/" in href and not any(p in unq for p in EXCLUDE_NAMESPACES):
                    if href not in self.visited and href not in self.queue:
                        self.queue.append(href)
                        cat_links += 1

        # 2. Thể loại con
        subcats_div = soup.find("div", id="mw-subcategories")
        if subcats_div:
            for a in subcats_div.find_all("a", href=True):
                href = urllib.parse.urljoin("https://vi.wikipedia.org", a["href"]).split("#")[0]
                unq = urllib.parse.unquote(href)
                if "/wiki/Thể_loại:" in unq or "/wiki/Category:" in unq:
                    if href not in self.visited and href not in self.queue:
                        self.queue.append(href)
                        cat_links += 1

        print(f"   [Thể loại] +{cat_links} liên kết bài viết & thể loại con được nạp.")

    def parse_article_page(self, soup: BeautifulSoup, page_url: str) -> bool:
        """Trích xuất thông tin chi tiết của một hiện vật/di tích"""
        # Nếu là trang danh sách tổng hợp hoặc trang thể loại thì bỏ qua bước lưu hiện vật
        if self.is_index_or_category(page_url):
            return False

        heading = soup.find("h1", id="firstHeading")
        if not heading:
            return False

        title = clean_text(heading.get_text())
        if not title or title.lower() in self.seen_names:
            return False

        content_div = soup.find("div", id="mw-content-text")
        if not content_div:
            return False

        # Thể loại trên Wikipedia
        cat_div = soup.find("div", id="mw-normal-catlinks")
        categories = []
        if cat_div:
            categories = [clean_text(a.get_text()) for a in cat_div.find_all("a")[1:]
                          if not any(skip in a.get_text() for skip in ["Bài viết", "Dọn dẹp", "Sơ khai", "Trang có", "Wikipedia"])]

        # Lấy nội dung các đoạn văn bản
        paragraphs = []
        for p in content_div.find_all("p", recursive=True):
            pt = clean_text(p.get_text())
            if len(pt) > 30 and not pt.startswith("Tọa độ:") and not pt.startswith("Bản đồ"):
                paragraphs.append(pt)

        if not paragraphs:
            return False

        full_text = " ".join(paragraphs)
        if not self.is_relevant(title, full_text, categories):
            return False

        short_desc = paragraphs[0] if paragraphs else ""
        if len(short_desc) > 300:
            # Cắt gọn theo dấu câu kết thúc
            sentence_cut = re.split(r"(?<=[.!?])\s+", short_desc)
            if len(sentence_cut) > 1:
                short_desc = sentence_cut[0]

        desc = "\n\n".join(paragraphs[:6])

        # Trích xuất ảnh
        images = []
        ctx = self.context_cache.get(page_url, {})
        if ctx.get("main_image") and ctx["main_image"] not in images:
            images.append(ctx["main_image"])

        for img in content_div.find_all("img"):
            src = img.get("src", "")
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if not any(s in src.lower() for s in ["icon", "question", "edit", "stub", "20px", "symbol", "padlock", "ambox", "red_pawn", "wikimedia-button"]):
                    orig = get_fullres_image(src)
                    if orig and orig not in images:
                        images.append(orig)

        main_image_url = images[0] if images else ""
        supporting_images = "; ".join(images[1:6]) if len(images) > 1 else ""

        # Trích xuất Niên đại & Địa điểm từ Infobox hoặc Text
        era = ctx.get("era", "")
        location = ctx.get("location", "")

        infobox = soup.find("table", class_=re.compile(r"infobox"))
        if infobox:
            for tr in infobox.find_all("tr"):
                th = tr.find(["th", "td"], class_=re.compile(r"label|header")) or tr.find("th")
                td = tr.find("td", class_=re.compile(r"data")) or tr.find_all("td")[-1] if tr.find_all("td") else None
                if th and td:
                    k = clean_text(th.get_text()).lower()
                    v = clean_text(td.get_text())
                    if not era and any(w in k for w in ["niên đại", "thời kỳ", "khởi công", "xây dựng", "hoàn thành"]):
                        era = v
                    if not location and any(w in k for w in ["vị trí", "địa điểm", "địa chỉ", "tỉnh", "thành phố"]):
                        location = v

        if not era:
            era = extract_era_from_text(full_text)

        if not location:
            location = extract_location_from_text(full_text)

        pub_date = time.strftime("%d/%m/%Y")

        # Tải hình ảnh về máy nếu bật tính năng
        local_image_path = ""
        if self.download_images and main_image_url:
            safe_title = sanitize_filename(title)[:40]
            prefix = f"{self.current_id}_{safe_title}"
            local_image_path = download_image_file(self.session, main_image_url, self.image_dir, prefix, self.url_prefix)

        # Chuẩn hóa thẻ danh mục để khớp với hệ thống frontend
        system_tags = []
        combined_text = (title + " " + " ".join(categories) + " " + full_text[:800]).lower()
        if "bảo vật quốc gia" in combined_text:
            system_tags.append("Bảo vật quốc gia")
        if "di tích quốc gia đặc biệt" in combined_text:
            system_tags.append("Di tích quốc gia đặc biệt")
        elif "di tích quốc gia" in combined_text:
            system_tags.append("Di tích quốc gia")
        if "di sản thế giới" in combined_text:
            system_tags.append("Di sản thế giới")
        if any(w in combined_text for w in ["kiến trúc", "chùa", "đền", "tháp", "đình", "lăng", "thành cổ"]):
            system_tags.append("Kiến trúc")
        if any(w in combined_text for w in ["điêu khắc", "tượng", "phù điêu"]):
            system_tags.append("Điêu khắc")
        if any(w in combined_text for w in ["phật giáo", "chùa"]):
            system_tags.append("Phật giáo")
        if any(w in combined_text for w in ["âm nhạc", "chuông", "trống"]):
            system_tags.append("Âm nhạc")

        final_categories = list(dict.fromkeys(system_tags + categories))

        artifact = {
            "ID": str(self.current_id),
            "Name": title,
            "Short Description": short_desc,
            "Description": desc,
            "Categories": ", ".join(final_categories) if final_categories else "Di tích, Văn hóa Việt Nam",
            "Main Image URL": main_image_url,
            "Supporting Images": supporting_images,
            "Local Image Path": local_image_path,
            "Author": "Wikipedia / Wikimedia Commons",
            "Contributor": "(Crawler)",
            "Artifact Era": era,
            "Public Date": pub_date,
            "Location": location
        }

        self.seen_names.add(title.lower().strip())
        self.save_artifact(artifact)
        self.current_id += 1

        img_log = f"Ảnh online: Có | Đã tải: {os.path.basename(local_image_path)}" if local_image_path else ("Ảnh online: Có" if main_image_url else "Không có ảnh")
        print(f"   ✨ [LƯU HIỆN VẬT #{artifact['ID']}] {title} | Niên đại: {era or 'N/A'} | Vị trí: {location or 'N/A'} | {img_log}")
        return True

    def discover_links_in_content(self, soup: BeautifulSoup):
        """Vét cạn: Tìm mọi liên kết nội bộ liên quan trong toàn bộ trang"""
        content_div = soup.find("div", id="mw-content-text")
        if not content_div:
            return

        added = 0
        for a in content_div.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = urllib.parse.urljoin("https://vi.wikipedia.org", href)

            clean_href = href.split("#")[0]
            if not clean_href.startswith("https://vi.wikipedia.org/wiki/"):
                continue

            unquoted = urllib.parse.unquote(clean_href)
            if any(p in unquoted for p in EXCLUDE_NAMESPACES):
                continue

            link_text = clean_text(a.get_text())
            # Nếu link là category hoặc có chứa từ khóa văn hóa/lịch sử/di tích thì thêm vào hàng đợi
            is_cat = "/wiki/Thể_loại:" in unquoted or "/wiki/Category:" in unquoted
            has_kw = any(k in (link_text + " " + unquoted).lower() for k in RELEVANT_KEYWORDS)

            if is_cat or has_kw:
                if clean_href not in self.visited and clean_href not in self.queue:
                    self.queue.append(clean_href)
                    added += 1

        if added > 0:
            print(f"   [Vét cạn] +{added} liên kết mới được phát hiện. (Hàng đợi: {len(self.queue)})")

    def run(self):
        print("=" * 75)
        print("🏛️ BẮT ĐẦU CÀO VÉT CẠN DỮ LIỆU HIỆN VẬT & DI TÍCH (MUSEUM PLATFORM)")
        print(f"👉 File xuất: {os.path.abspath(self.output_csv)}")
        if self.download_images:
            print(f"👉 Tự động tải hình về: {os.path.abspath(self.image_dir)}")
        else:
            print("👉 Tải hình ảnh về máy: ĐÃ TẮT (Chỉ lưu link URL)")
        if self.backend_csv:
            print(f"👉 Đồng bộ trực tiếp vào Backend: {os.path.abspath(self.backend_csv)}")
        print(f"👉 ID tiếp tục: {self.current_id}")
        print(f"👉 Mục tiêu: {'VÉT CẠN LIÊN TỤC (KHÔNG GIỚI HẠN)' if self.max_items == 0 else f'{self.max_items} hiện vật'}")
        print("=" * 75)

        for s in self.seeds:
            clean_s = s.split("#")[0]
            if clean_s not in self.visited and clean_s not in self.queue:
                self.queue.append(clean_s)

        crawled_count = 0

        try:
            while self.queue:
                if self.max_items > 0 and crawled_count >= self.max_items:
                    print(f"\n🎉 Đã đạt số lượng {self.max_items} hiện vật yêu cầu.")
                    break

                current_url = self.queue.popleft()
                if current_url in self.visited:
                    continue

                self.save_visited(current_url)

                try:
                    slug = urllib.parse.unquote(current_url.split("/")[-1])
                    print(f"\n🌐 [Đã cào: {crawled_count} | Queue: {len(self.queue)}] Đang quét: {slug}")
                    resp = self.session.get(current_url, timeout=12)
                    if resp.status_code != 200:
                        print(f"   ⚠️ Mã phản hồi HTTP: {resp.status_code}")
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # 1. Quét trang Thể loại nếu có
                    unquoted_url = urllib.parse.unquote(current_url)
                    if "/wiki/Thể_loại:" in unquoted_url or "/wiki/Category:" in unquoted_url:
                        self.parse_category_page(soup, current_url)

                    # 2. Quét bảng dữ liệu hiện vật
                    self.parse_table_items(soup, current_url)

                    # 3. Trích xuất thông tin bài viết hiện vật
                    saved = self.parse_article_page(soup, current_url)
                    if saved:
                        crawled_count += 1

                    # 4. Vét cạn: Quét mọi liên kết nội dung để tiếp tục đi sâu
                    self.discover_links_in_content(soup)

                    # Tạm dừng ngắn để tránh nghẽn mạng / chặn IP
                    time.sleep(self.delay)

                except Exception as e:
                    print(f"   ❌ Lỗi khi xử lý URL: {e}")

        except KeyboardInterrupt:
            print("\n⚠️ Đã nhận tín hiệu dừng (Ctrl+C). Tiến trình cào được lưu an toàn.")

        print("\n" + "=" * 75)
        print(f"✅ TỔNG KẾT: Đã thu thập và lưu trữ thành công {crawled_count} hiện vật mới!")
        print(f"📁 Dữ liệu được lưu tại: {os.path.abspath(self.output_csv)}")
        print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exhaustive Cultural Heritage Web Crawler for Museum Platform")
    parser.add_argument("--max-items", type=int, default=0, help="Số hiện vật tối đa (0 = không giới hạn / vét cạn hoàn toàn)")
    parser.add_argument("--delay", type=float, default=0.3, help="Thời gian nghỉ giữa các trang (giây)")
    parser.add_argument("--output", type=str, default="crawled_artifacts.csv", help="Đường dẫn file CSV kết quả")
    parser.add_argument("--merge-backend", action="store_true", help="Ghi trực tiếp vào file backend/src/main/resources/artifacts.csv")
    parser.add_argument("--no-download-images", action="store_true", help="Tắt tính năng tải file ảnh về máy (chỉ lưu URL)")
    parser.add_argument("--image-dir", type=str, default="images", help="Thư mục lưu ảnh tải về (mặc định: images)")
    parser.add_argument("--frontend-public", action="store_true", help="Tải ảnh thẳng vào frontend/public/artifacts để web Next.js load được ngay")
    args = parser.parse_args()

    backend_target = None
    if args.merge_backend:
        cand = os.path.join(os.path.dirname(__file__), "..", "backend", "src", "main", "resources", "artifacts.csv")
        if os.path.exists(cand):
            backend_target = os.path.abspath(cand)

    crawler = ExhaustiveMuseumCrawler(
        output_csv=args.output,
        delay=args.delay,
        max_items=args.max_items,
        backend_csv=backend_target,
        download_images=not args.no_download_images,
        image_dir=args.image_dir,
        frontend_public=args.frontend_public
    )
    crawler.run()
