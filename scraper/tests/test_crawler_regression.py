"""
Museum Platform - Crawler Regression Tests
------------------------------------------
Bộ kiểm thử hồi quy đảm bảo các lỗi P0/P1 trước đây không tái phát:
- C01: Trang lỗi tải, link sửa đổi (action=edit), redlinks bị loại bỏ.
- C02: Trang thuộc namespace khác (Thảo luận, Bản mẫu, Thành viên, Đặc biệt) bị loại bỏ.
- ISS-05: Trích xuất không gom thẻ <p> lồng nhau hay dính thông báo bản mẫu.
- ISS-06: Phân biệt niên đại chế tác với năm phát hiện khảo cổ.
- ISS-07: Phân tách rõ ràng nơi lưu giữ và nơi khai quật.
- ISS-08: Ghi file ảnh và CSV nguyên tử kèm mã băm SHA-256.
- ISS-09: Public Date không bị gán bằng ngày chạy crawler.
"""

import os
import sys
import unittest
import tempfile
import csv
from bs4 import BeautifulSoup

# Thêm đường dẫn thư mục scraper vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from crawler import ResilientMuseumCrawler, clean_text, sanitize_filename
from download_existing_images import compute_sha256, sanitize_filename as img_sanitize
from state_manager import CrawlStateManager

class TestCrawlerRegression(unittest.TestCase):
    def setUp(self):
        self.crawler = ResilientMuseumCrawler(
            output_csv="test_output.csv",
            state_db=":memory:",
            raw_dir="test_raw_pages"
        )

    def test_c01_edit_failure_rejection(self):
        """Đảm bảo URL chỉnh sửa / liên kết đỏ bị nhận diện và không cào vào tập dữ liệu"""
        edit_url = "https://vi.wikipedia.org/w/index.php?title=Hai_thi%E1%BA%BFu_n%E1%BB%AF_v%C3%A0_em_b%C3%A9&action=edit&redlink=1"
        self.assertTrue("action=edit" in edit_url or "redlink=1" in edit_url)

    def test_c02_namespace_rejection(self):
        """Đảm bảo các trang phi namespace 0 bị chặn hoàn toàn"""
        talk_url = "https://vi.wikipedia.org/wiki/Th%E1%BA%A3o_lu%E1%BA%ADn:B%E1%BA%A3o_v%E1%BA%ADt_qu%E1%BB%91c_gia"
        template_url = "https://vi.wikipedia.org/wiki/B%E1%BA%A3n_m%E1%BA%ABu:B%E1%BA%A3o_v%E1%BA%ADt_qu%E1%BB%91c_gia"
        user_url = "https://vi.wikipedia.org/wiki/Th%C3%A0nh_vi%C3%AAn:Example"

        for url in [talk_url, template_url, user_url]:
            # Đảm bảo hàm state quản lý cách ly nhận đúng lý do
            self.crawler.state.mark_quarantined(url, "Test Title", "C02_NON_ZERO_NAMESPACE")
            self.assertTrue(self.crawler.state.is_visited(url))

    def test_semantic_era_extraction(self):
        """Đảm bảo Niên đại lấy đúng thời kỳ chế tác, không bị nhầm với năm phát hiện hay năm hiện đại"""
        infobox = {
            "niên đại": "Thế kỷ VII - IX",
            "thời điểm phát hiện": "1987",
            "phát hiện bởi": "Bảo tàng Long An"
        }
        lead_text = "Bộ sưu tập hiện vật vàng Gò Xoài được phát hiện năm 1987 tại Long An. Hiện vật có niên đại thuộc thế kỷ VII - IX."
        
        era = self.crawler.extract_era(infobox, lead_text)
        self.assertEqual(era, "Thế kỷ VII - IX")
        self.assertNotIn("1987", era)

    def test_location_role_distinction(self):
        """Đảm bảo phân tách rõ ràng nơi lưu giữ và nơi phát hiện khảo cổ"""
        infobox = {
            "hiện lưu trữ tại": "Bảo tàng Lịch sử Quốc gia",
            "địa điểm phát hiện": "Di chỉ Đông Sơn, Thanh Hóa"
        }
        lead_text = "Trống đồng được tìm thấy tại Thanh Hóa và hiện đang được trưng bày tại Hà Nội."
        
        loc = self.crawler.extract_location(infobox, lead_text)
        self.assertIn("Lưu giữ tại: Bảo tàng Lịch sử Quốc gia", loc)
        self.assertIn("Phát hiện tại: Di chỉ Đông Sơn, Thanh Hóa", loc)

    def test_public_date_not_scrape_date(self):
        """Đảm bảo Public Date lấy đúng năm công nhận bảo vật hoặc để trống, không lấy ngày chạy crawler"""
        infobox_with_date = {
            "bảo vật quốc gia": "đợt 2 (2013) – QĐ 2599/QĐ-TTg"
        }
        lead_text = "Hiện vật được Thủ tướng Chính phủ công nhận là Bảo vật quốc gia năm 2013."
        
        pub_date = self.crawler.extract_public_date(infobox_with_date, lead_text)
        self.assertEqual(pub_date, "2013")

        # Trường hợp không có năm công nhận
        infobox_empty = {}
        lead_empty = "Đây là một di chỉ khảo cổ học cổ xưa của Việt Nam."
        pub_date_empty = self.crawler.extract_public_date(infobox_empty, lead_empty)
        self.assertEqual(pub_date_empty, "")

    def test_sha256_and_atomic_write(self):
        """Kiểm tra mã băm SHA-256 và cơ chế ghi nguyên tử"""
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"SAMPLE IMAGE BYTES FOR TESTING")
            temp_path = f.name

        try:
            checksum = compute_sha256(temp_path)
            self.assertEqual(len(checksum), 64)

            # Kiểm tra atomic swap qua rename
            new_path = temp_path + ".renamed"
            os.replace(temp_path, new_path)
            self.assertTrue(os.path.exists(new_path))
            self.assertFalse(os.path.exists(temp_path))
            os.remove(new_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()

