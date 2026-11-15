"""
Museum Platform - Resilient MediaWiki Crawler (Cào vét cạn Di sản & Hiện vật Việt Nam)
-------------------------------------------------------------------------------------
Kiến trúc mới:
1. MediaWiki Action API chuẩn: phân trang `gcmcontinue`, định danh Page ID, tự động resolve redirects.
2. Bộ lọc Namespace nghiêm ngặt: Chỉ nhận namespace 0 (Main Article); tự động loại bỏ mọi trang rác.
3. State Machine SQLite (`crawler_state.db`): Hàng đợi bền vững, ghi nhận hoàn tất nguyên tử.
4. Raw Storage (`raw_pages/`): Lưu toàn vẹn dữ liệu gốc JSON ({page_id}_{revision_id}.json) để tái xử lý offline.
5. Bộ trích xuất chính xác: Bóc tách riêng Infobox và Lead Section, phân định Niên đại và Địa điểm, chuẩn hóa Public Date.
6. Crawl Manifest (`crawl_manifest.json`): Báo cáo độ phủ và kiểm soát chất lượng thời gian thực.
7. Tách biệt hoàn toàn khỏi Backend: Không ghi đè trực tiếp vào production database.
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from state_manager import CrawlStateManager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_ENDPOINT = "https://vi.wikipedia.org/w/api.php"

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

INDEX_PAGES = [
    "bảo_vật_quốc_gia_(việt_nam)",
    "di_tích_quốc_gia_đặc_biệt_(việt_nam)",
    "danh_sách_di_tích_quốc_gia_đặc_biệt_việt_nam",
    "danh_sách_bảo_vật_quốc_gia_việt_nam",
    "danh_sách_bảo_tàng_tại_việt_nam"
]

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name.strip("_")

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

class ResilientMuseumCrawler:
    def __init__(
        self,
        output_csv: str = "crawled_artifacts_verified.csv",
        state_db: str = "crawler_state.db",
        raw_dir: str = "raw_pages",
        manifest_file: str = "crawl_manifest.json",
        delay: float = 0.3,
        max_items: int = 0,
        seeds: Optional[List[str]] = None,
        download_images: bool = False,
        image_dir: str = "images"
    ):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_csv = os.path.abspath(os.path.join(base_dir, output_csv)) if not os.path.isabs(output_csv) else output_csv
        if state_db != ":memory:":
            self.state_db = os.path.abspath(os.path.join(base_dir, state_db)) if not os.path.isabs(state_db) else state_db
        else:
            self.state_db = ":memory:"
        self.raw_dir = os.path.abspath(os.path.join(base_dir, raw_dir)) if not os.path.isabs(raw_dir) else raw_dir
        self.manifest_file = os.path.abspath(os.path.join(base_dir, manifest_file)) if not os.path.isabs(manifest_file) else manifest_file
        self.image_dir = os.path.abspath(os.path.join(base_dir, image_dir)) if not os.path.isabs(image_dir) else image_dir
        
        self.delay = delay
        self.max_items = max_items
        self.seeds = seeds or DEFAULT_SEEDS
        self.download_images = download_images
        
        os.makedirs(self.raw_dir, exist_ok=True)
        if self.download_images:
            os.makedirs(self.image_dir, exist_ok=True)

        self.state = CrawlStateManager(self.state_db)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MuseumPlatformCrawler/2.0 (Cultural Heritage Research; contact@museum.local) Mozilla/5.0"
        })

        self.known_id_map = self._init_known_ids()
        self.saved_ids = self._init_saved_ids()
        self.current_id = self._init_id()
        self.context_cache = {}  # url -> {era, location, main_image, name}
        self.items_crawled_session = 0

    def _init_saved_ids(self) -> set:
        saved = set()
        if os.path.exists(self.output_csv):
            try:
                with open(self.output_csv, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        val = r.get("ID", "").strip()
                        if val:
                            saved.add(val)
            except Exception:
                pass
        return saved

    def _init_known_ids(self) -> Dict[str, str]:
        mapping = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        clean_csv = os.path.join(base_dir, "crawled_artifacts_new.csv")
        if os.path.exists(clean_csv):
            try:
                with open(clean_csv, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        art_id = r.get("ID", "").strip()
                        name = r.get("Name", "").strip()
                        if art_id.isdigit() and name:
                            mapping[name.lower()] = art_id
                            clean_name = name[4:].strip() if name.startswith("Tạo ") else name
                            mapping[clean_name.lower()] = art_id
                            safe_title = clean_name.replace(" ", "_")
                            quoted = urllib.parse.quote(safe_title)
                            canonical = f"https://vi.wikipedia.org/wiki/{quoted}"
                            mapping[canonical.lower()] = art_id
            except Exception:
                pass
        return mapping

    def _init_id(self) -> int:
        max_id = 0
        base_dir = os.path.dirname(os.path.abspath(__file__))
        check_files = [
            self.output_csv,
            os.path.join(base_dir, "crawled_artifacts_new.csv"),
            os.path.join(base_dir, "crawled_artifacts.csv")
        ]
        for p in check_files:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8-sig") as f:
                        reader = csv.reader(f)
                        next(reader, None)
                        for row in reader:
                            if row and row[0].isdigit():
                                val = int(row[0])
                                if val > max_id:
                                    max_id = val
                except Exception:
                    pass
        return max_id + 1 if max_id > 0 else 1

    def is_relevant(self, title: str, text: str, categories: List[str]) -> bool:
        combined = (title + " " + " ".join(categories) + " " + text[:600]).lower()
        return any(k in combined for k in RELEVANT_KEYWORDS)

    def is_index_or_category(self, url: str) -> bool:
        unquoted = urllib.parse.unquote(url).lower()
        if "/wiki/thể_loại:" in unquoted or "/wiki/category:" in unquoted:
            return True
        for idx in INDEX_PAGES:
            if idx in unquoted:
                return True
        if "/wiki/danh_sách" in unquoted:
            return True
        return False

    def fetch_category_via_api(self, category_title: str) -> Tuple[List[str], List[str]]:
        """
        Dùng MediaWiki API duyệt thể loại với token phân trang `gcmcontinue`.
        Trả về (danh_sách_bài_viết, danh_sách_thể_loại_con).
        Chỉ nhận namespace 0 (bài viết) và namespace 14 (thể loại con).
        """
        if not category_title.startswith("Thể loại:") and not category_title.startswith("Category:"):
            category_title = f"Thể loại:{category_title}"
        category_title = category_title.replace("_", " ")

        # Resolve redirect nếu thể loại đổi hướng
        try:
            redir_resp = self.session.get(API_ENDPOINT, params={
                "action": "query",
                "titles": category_title,
                "redirects": "1",
                "format": "json"
            }, timeout=10)
            if redir_resp.status_code == 200:
                pdict = redir_resp.json().get("query", {}).get("pages", {})
                for _, pobj in pdict.items():
                    if pobj.get("title"):
                        category_title = pobj["title"]
        except Exception:
            pass

        articles = []
        subcategories = []
        gcmcontinue = None

        while True:
            params = {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": category_title,
                "gcmnamespace": "0|14",
                "gcmlimit": "500",
                "prop": "info",
                "inprop": "url",
                "format": "json"
            }
            if gcmcontinue:
                params["gcmcontinue"] = gcmcontinue

            try:
                resp = self.session.get(API_ENDPOINT, params=params, timeout=15)
                if resp.status_code != 200:
                    break
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})

                for pid, pdata in pages.items():
                    ns = pdata.get("ns")
                    canonical_url = pdata.get("canonicalurl")
                    title = pdata.get("title")
                    if not canonical_url:
                        continue

                    if ns == 0:
                        articles.append(canonical_url)
                    elif ns == 14:
                        subcategories.append(title)

                gcmcontinue = data.get("continue", {}).get("gcmcontinue")
                if not gcmcontinue:
                    break
                time.sleep(self.delay)
            except Exception as e:
                print(f"      [MediaWiki API] Lỗi phân trang thể loại '{category_title}': {e}")
                break

        return articles, subcategories

    def fetch_article_api(self, title_or_url: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin bài viết qua MediaWiki API: canonical url, lead text, categories, image"""
        if title_or_url.startswith("http"):
            title = urllib.parse.unquote(title_or_url.split("/wiki/")[-1])
        else:
            title = title_or_url

        params = {
            "action": "query",
            "titles": title,
            "prop": "info|extracts|pageimages|categories|revisions",
            "inprop": "url|displaytitle",
            "explaintext": "1",
            "exintro": "1",
            "piprop": "original|thumbnail",
            "pilicense": "any",
            "redirects": "1",
            "cllimit": "max",
            "format": "json"
        }

        try:
            resp = self.session.get(API_ENDPOINT, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                if pid == "-1" or "missing" in pdata:
                    return {"page_id": -1, "missing": True, "title": pdata.get("title", title)}
                pdata["page_id"] = int(pid)
                return pdata
        except Exception as e:
            print(f"      [API Error] Lỗi fetch bài viết '{title}': {e}")
            return None
        return None

    def fetch_article_parse(self, page_id: int) -> Tuple[Optional[BeautifulSoup], List[str]]:
        """Lấy HTML đã parse qua MediaWiki API để trích xuất Infobox và danh sách ảnh chất lượng cao"""
        params = {
            "action": "parse",
            "pageid": str(page_id),
            "prop": "text|images",
            "format": "json"
        }
        try:
            resp = self.session.get(API_ENDPOINT, params=params, timeout=15)
            if resp.status_code != 200:
                return None, []
            data = resp.json()
            html = data.get("parse", {}).get("text", {}).get("*", "")
            images = data.get("parse", {}).get("images", [])
            soup = BeautifulSoup(html, "html.parser")
            return soup, images
        except Exception:
            return None, []

    def extract_infobox(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Trích xuất dữ liệu cặp khóa-giá trị từ Infobox"""
        infobox_data = {}
        if not soup:
            return infobox_data

        infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
        if not infobox:
            return infobox_data

        for tr in infobox.find_all("tr"):
            th = tr.find(["th", "td"], class_=lambda c: c and any(k in c for k in ["header", "label"])) or tr.find("th")
            td = tr.find("td", class_=lambda c: c and "data" in c) or (tr.find_all("td")[-1] if tr.find_all("td") else None)
            if th and td:
                k = clean_text(th.get_text()).lower()
                v = clean_text(td.get_text())
                if k and v:
                    infobox_data[k] = v

        return infobox_data

    def extract_era(self, infobox: Dict[str, str], lead_text: str) -> str:
        """Trích xuất Niên đại ngữ nghĩa từ Infobox hoặc câu định nghĩa mở đầu"""
        for k, v in infobox.items():
            if any(w in k for w in ["niên đại", "thời kỳ", "khởi công", "xây dựng", "hoàn thành", "thế kỷ"]):
                return v

        first_sentence = lead_text.split(".")[0] if lead_text else ""
        patterns = [
            r"(thế kỷ\s+[IVXLCDM\d]+(?:\s*[-–]\s*[IVXLCDM\d]+)?(?:\s*TCN)?)",
            r"(cách ngày nay\s+[\d\s.,–-]+năm)",
            r"(khoảng năm\s+\d+(?:\s*[-–]\s*\d+)?)",
            r"(thời\s+(?:Hồng Bàng|Đông Sơn|Sa Huỳnh|Óc Eo|Chăm Pa|Đinh|Tiền Lê|Lý|Trần|Hồ|Hậu Lê|Lê sơ|Lê Trung hưng|Mạc|Tây Sơn|Nguyễn|Pháp thuộc|Bắc thuộc))"
        ]
        for p in patterns:
            m = re.search(p, first_sentence, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def extract_location(self, infobox: Dict[str, str], lead_text: str) -> str:
        """Trích xuất Địa điểm (nơi lưu giữ / nơi khai quật)"""
        holding = ""
        discovered_loc = ""
        general_loc = ""

        for k, v in infobox.items():
            if any(w in k for w in ["hiện lưu trữ", "lưu trữ tại", "nơi lưu giữ", "bảo quản tại"]):
                holding = v
            elif any(w in k for w in ["địa điểm phát hiện", "nơi phát hiện", "khai quật"]):
                discovered_loc = v
            elif any(w in k for w in ["vị trí", "địa điểm", "địa chỉ", "tỉnh", "thành phố"]):
                general_loc = v

        parts = []
        if holding:
            parts.append(f"Lưu giữ tại: {holding}")
        if discovered_loc:
            parts.append(f"Phát hiện tại: {discovered_loc}")
        if not parts and general_loc:
            parts.append(general_loc)

        if parts:
            return " | ".join(parts)

        m = re.search(r"(Bảo tàng\s+[^\.,;\n\)]+)", lead_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    def extract_public_date(self, infobox: Dict[str, str], lead_text: str) -> str:
        """Trích xuất năm công nhận Bảo vật / Xếp hạng di tích (nếu có); không lấy ngày cào dữ liệu!"""
        for k, v in infobox.items():
            if any(w in k for w in ["công nhận", "xếp hạng", "bảo vật quốc gia", "quyết định"]):
                m = re.search(r"(?:năm\s+)?(19\d\d|20\d\d)", v)
                if m:
                    return m.group(1)

        m = re.search(r"(?:công nhận|xếp hạng|cấp bằng).*?(?:năm|ngày\s+\d+/\d+/)\s*(19\d\d|20\d\d)", lead_text, re.IGNORECASE)
        if m:
            return m.group(1)

        return ""

    def save_raw_page(self, page_id: int, rev_id: int, raw_data: Dict[str, Any]):
        filepath = os.path.join(self.raw_dir, f"{page_id}_{rev_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"      [Raw Storage] Lỗi lưu raw page {page_id}: {e}")

    def save_artifact_csv(self, artifact: Dict[str, str]):
        file_exists = os.path.exists(self.output_csv)
        with open(self.output_csv, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER, quoting=csv.QUOTE_ALL)
            if not file_exists or os.path.getsize(self.output_csv) == 0:
                writer.writeheader()
            writer.writerow(artifact)
            f.flush()

    def update_manifest(self):
        metrics = self.state.get_metrics()
        manifest_data = {
            "manifest_version": "2.0",
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "output_csv": os.path.basename(self.output_csv),
            "total_crawled_verified": metrics["crawled_pages"],
            "total_quarantined": metrics["quarantined_pages"],
            "remaining_in_queue": metrics["queued_urls"],
            "failed_retries": metrics["failed_urls"],
            "session_crawled": self.items_crawled_session
        }
        try:
            with open(self.manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def parse_table_items(self, soup: BeautifulSoup, page_url: str):
        """Trích xuất liên kết và ngữ cảnh từ các bảng Wikitable tổng hợp"""
        tables = soup.find_all("table", class_="wikitable")
        discovered = 0
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            header_cells = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
            name_idx = None
            era_idx = None
            loc_idx = None
            for idx, h in enumerate(header_cells):
                if any(k in h for k in ["tên", "di tích", "hiện vật"]):
                    if name_idx is None:
                        name_idx = idx
                elif any(k in h for k in ["niên đại", "thời", "văn hóa"]):
                    era_idx = idx
                elif any(k in h for k in ["địa phương", "địa điểm", "chủ sở hữu", "đơn vị"]):
                    loc_idx = idx

            if name_idx is None:
                continue

            for r in rows[1:]:
                cells = r.find_all(["td", "th"])
                if len(cells) <= name_idx:
                    continue
                name_cell = cells[name_idx]
                era = clean_text(cells[era_idx].get_text()) if era_idx is not None and era_idx < len(cells) else ""
                loc = clean_text(cells[loc_idx].get_text()) if loc_idx is not None and loc_idx < len(cells) else ""

                for a in name_cell.find_all("a", href=True):
                    href = a["href"]
                    if not href.startswith("http"):
                        href = urllib.parse.urljoin("https://vi.wikipedia.org", href)
                    clean_href = href.split("#")[0]
                    if "/wiki/" in clean_href and not any(ns in clean_href for ns in ["Thảo_luận", "Bản_mẫu", "Thành_viên", "Special", "Help"]):
                        self.context_cache[clean_href] = {
                            "era": era,
                            "location": loc
                        }
                        if self.state.add_to_queue(url=clean_href, priority=2):
                            discovered += 1

        if discovered > 0:
            print(f"   [Bảng dữ liệu] +{discovered} liên kết hiện vật ưu tiên cao được nạp vào queue.")

    def run(self):
        print("=" * 75)
        print("🏛️ BẮT ĐẦU CÀO VÉT CẠN DỮ LIỆU HIỆN VẬT (MEDIAWIKI API & STATE ENGINE)")
        print(f"👉 File xuất: {self.output_csv}")
        print(f"👉 CSDL trạng thái: {self.state_db}")
        print(f"👉 Thư mục Raw Storage: {self.raw_dir}")
        print(f"👉 Crawl Manifest: {self.manifest_file}")
        print(f"👉 ID tiếp tục: {self.current_id}")
        print(f"👉 Giới hạn phiên: {'Không giới hạn' if self.max_items == 0 else f'{self.max_items} hiện vật'}")
        print("=" * 75)

        metrics = self.state.get_metrics()
        if metrics["queued_urls"] == 0:
            for s in self.seeds:
                clean_s = s.split("#")[0]
                self.state.add_to_queue(url=clean_s, priority=3)

        while True:
            if self.max_items > 0 and self.items_crawled_session >= self.max_items:
                print(f"\n🎉 Đã đạt giới hạn phiên {self.max_items} hiện vật.")
                break

            item = self.state.pop_queue()
            if not item:
                print("\n✅ Hàng đợi thu thập đã rỗng! Hoàn tất chu trình.")
                break

            current_url = item["url"]
            depth = item["depth"]
            item_art_id = item.get("page_id")

            if self.is_index_or_category(current_url):
                print(f"📂 [DANH MỤC] Duyệt thể loại / danh sách: {urllib.parse.unquote(current_url)}")
                unquoted = urllib.parse.unquote(current_url)
                if "/wiki/thể_loại:" in unquoted.lower() or "/wiki/category:" in unquoted.lower():
                    cat_name = unquoted.split("/wiki/")[-1].replace("Thể_loại:", "").replace("Category:", "")
                    articles, subcats = self.fetch_category_via_api(cat_name)
                    print(f"   + Đã tìm thấy {len(articles)} bài viết và {len(subcats)} thể loại con.")
                    for art_url in articles:
                        self.state.add_to_queue(url=art_url, depth=depth + 1, priority=1)
                    for sc in subcats:
                        sc_url = f"https://vi.wikipedia.org/wiki/Th%E1%BB%83_lo%E1%BA%A1i:{urllib.parse.quote(sc.replace(' ', '_'))}"
                        self.state.add_to_queue(url=sc_url, depth=depth + 1, priority=2)
                else:
                    try:
                        resp = self.session.get(current_url, timeout=15)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.content, "html.parser")
                            self.parse_table_items(soup, current_url)
                    except Exception as e:
                        print(f"   ⚠️ Lỗi tải trang bảng: {e}")

                time.sleep(self.delay)
                continue

            api_data = self.fetch_article_api(current_url)
            if not api_data:
                self.state.mark_failed(current_url, "Network or API timeout")
                continue

            if api_data.get("missing"):
                self.state.mark_quarantined(
                    url=current_url,
                    title=api_data.get("title", ""),
                    reason_code="C01_MISSING_PAGE"
                )
                continue

            ns = api_data.get("ns", 0)
            if ns != 0:
                self.state.mark_quarantined(
                    url=current_url,
                    title=api_data.get("title", ""),
                    reason_code="C02_NON_ZERO_NAMESPACE",
                    page_id=api_data.get("page_id")
                )
                print(f"   ⛔ [CÁCH LY] Bỏ qua trang ngoài namespace 0: {api_data.get('title')} (NS={ns})")
                continue

            page_id = api_data["page_id"]
            title = clean_text(api_data.get("title", ""))
            canonical_url = api_data.get("canonicalurl", current_url)
            revisions = api_data.get("revisions", [])
            rev_id = revisions[0].get("revid", 0) if revisions else 0
            lead_extract = clean_text(api_data.get("extract", ""))
            raw_categories = [c.get("title", "").replace("Thể loại:", "") for c in api_data.get("categories", [])]

            if self.state.is_page_id_crawled(page_id):
                continue

            original_img = api_data.get("original", {}).get("source") or api_data.get("thumbnail", {}).get("source") or ""
            original_img = get_fullres_image(original_img)

            soup, parsed_images = self.fetch_article_parse(page_id)
            infobox = self.extract_infobox(soup)

            if not self.is_relevant(title, lead_extract, raw_categories):
                self.state.mark_quarantined(
                    url=canonical_url,
                    title=title,
                    reason_code="IRRELEVANT_CONTENT",
                    page_id=page_id,
                    details="Lead text and categories do not match cultural keywords"
                )
                continue

            raw_payload = {
                "page_id": page_id,
                "revision_id": rev_id,
                "title": title,
                "canonical_url": canonical_url,
                "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "lead_extract": lead_extract,
                "categories": raw_categories,
                "infobox": infobox,
                "main_image": original_img,
                "images": parsed_images
            }
            self.save_raw_page(page_id, rev_id, raw_payload)

            ctx = self.context_cache.get(current_url, {})
            era = ctx.get("era") or self.extract_era(infobox, lead_extract)
            location = ctx.get("location") or self.extract_location(infobox, lead_extract)
            public_date = self.extract_public_date(infobox, lead_extract)

            short_desc = lead_extract.split(".")[0] if lead_extract else ""
            if len(short_desc) > 300:
                short_desc = short_desc[:300] + "..."

            system_tags = []
            combined_tag_text = (title + " " + " ".join(raw_categories) + " " + lead_extract[:500]).lower()
            if "bảo vật quốc gia" in combined_tag_text:
                system_tags.append("Bảo vật quốc gia")
            if "di tích quốc gia đặc biệt" in combined_tag_text:
                system_tags.append("Di tích quốc gia đặc biệt")
            elif "di tích quốc gia" in combined_tag_text:
                system_tags.append("Di tích quốc gia")
            if "di sản thế giới" in combined_tag_text:
                system_tags.append("Di sản thế giới")
            if any(w in combined_tag_text for w in ["kiến trúc", "chùa", "đền", "tháp", "đình", "lăng", "thành cổ"]):
                system_tags.append("Kiến trúc")
            if any(w in combined_tag_text for w in ["điêu khắc", "tượng", "phù điêu"]):
                system_tags.append("Điêu khắc")
            if any(w in combined_tag_text for w in ["phật giáo", "chùa"]):
                system_tags.append("Phật giáo")
            if any(w in combined_tag_text for w in ["khảo cổ", "đông sơn", "sa huỳnh", "óc eo"]):
                system_tags.append("Khảo cổ học")

            clean_cats = [c for c in raw_categories if not any(skip in c for skip in ["Bài viết", "Dọn dẹp", "Sơ khai", "Trang có", "Wikipedia"])]
            final_categories = list(dict.fromkeys(system_tags + clean_cats))

            # ID Mapping: Ưu tiên dùng ID gốc từ crawl_queue hoặc known_id_map để khớp ảnh cục bộ
            mapped_id = None
            if item_art_id and int(item_art_id) > 0:
                mapped_id = str(item_art_id)
            elif title.lower() in self.known_id_map:
                mapped_id = self.known_id_map[title.lower()]
            elif canonical_url.lower() in self.known_id_map:
                mapped_id = self.known_id_map[canonical_url.lower()]

            if mapped_id:
                final_id = mapped_id
            else:
                while str(self.current_id) in self.saved_ids:
                    self.current_id += 1
                final_id = str(self.current_id)
                self.current_id += 1

            if final_id in self.saved_ids:
                print(f"   ⏩ Đã tồn tại #{final_id} ({title}) trong CSV, bỏ qua ghi trùng.")
                self.state.mark_completed(
                    page_id=page_id,
                    title=title,
                    canonical_url=canonical_url,
                    revision_id=rev_id,
                    namespace=0,
                    discovered_via=current_url
                )
                continue

            self.saved_ids.add(final_id)

            artifact = {
                "ID": final_id,
                "Name": title,
                "Short Description": short_desc,
                "Description": lead_extract,
                "Categories": ", ".join(final_categories) if final_categories else "Di tích, Văn hóa Việt Nam",
                "Main Image URL": original_img,
                "Supporting Images": "; ".join([f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(img)}" for img in parsed_images[:5]]) if parsed_images else "",
                "Local Image Path": "",
                "Author": "Wikipedia / Wikimedia Commons",
                "Contributor": "(Crawler v2.0)",
                "Artifact Era": era,
                "Public Date": public_date,
                "Location": location
            }

            self.save_artifact_csv(artifact)
            self.state.mark_completed(
                page_id=page_id,
                title=title,
                canonical_url=canonical_url,
                revision_id=rev_id,
                namespace=0,
                discovered_via=current_url
            )

            self.items_crawled_session += 1

            img_status = "Có ảnh" if original_img else "Chưa có ảnh"
            print(f"   ✨ [LƯU #{artifact['ID']}] {title} | Niên đại: {era or 'N/A'} | Vị trí: {location or 'N/A'} | Công bố: {public_date or 'N/A'} | {img_status}")

            if self.items_crawled_session % 10 == 0:
                self.update_manifest()

            time.sleep(self.delay)

        self.update_manifest()
        self.state.close()
        print("=" * 75)
        print("🎉 PHIÊN THU THẬP KẾT THÚC THÀNH CÔNG")
        print(f"👉 Tổng hiện vật cào phiên này: {self.items_crawled_session}")
        print(f"👉 File kết quả: {self.output_csv}")
        print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Museum Platform MediaWiki API Crawler")
    parser.add_argument("--output", type=str, default="crawled_artifacts_verified.csv", help="Tên file CSV kết quả")
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số lượng hiện vật cần cào (0 = không giới hạn)")
    parser.add_argument("--delay", type=float, default=0.2, help="Thời gian chờ giữa các request (giây)")
    args = parser.parse_args()

    crawler = ResilientMuseumCrawler(
        output_csv=args.output,
        max_items=args.limit,
        delay=args.delay
    )
    crawler.run()
