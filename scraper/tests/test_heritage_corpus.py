"""
Museum Platform - Heritage Corpus Automated Test Suite
Covers:
- URL normalization & deduplication
- Category & pagination traversal
- Parser fidelity & metadata extraction (LSb., dimensions, decree)
- Parser contamination resistance (no nav/footer/share pollution)
- Media metadata & caption extraction
- RAG section chunks & exact evidence spans
- KG candidate relations with epistemic status (ASSERTED/DERIVED/HYPOTHESIZED) & PENDING_REVIEW
- Legacy dataset matching (multi-attribute & registration number)
- State machine checkpoint, resume & failure ledger with exponential backoff
- Source registry & multi-source adapters
"""

import os
import sys
import unittest
import tempfile
import json
import sqlite3

# Add scraper to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from heritage_corpus.url_normalizer import URLNormalizer
from heritage_corpus.vnmh_parser import VNMHParser
from heritage_corpus.rag_preparer import RAGPreparer
from heritage_corpus.kg_preparer import KGPreparer
from heritage_corpus.legacy_matcher import LegacyMatcher
from heritage_corpus.state_manager import CorpusStateManager
from heritage_corpus.source_registry import SourceRegistry
from heritage_corpus.storage import CorpusStorage
from heritage_corpus.models import ParsedDocument


MOCK_ARTICLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bảo vật quốc gia: Thạp Đào Thịnh</title>
</head>
<body>
    <form id="form1">
        <div class="top-header">Navigation Header Should Be Ignored</div>
        <nav class="navbar"><a href="/vi/Articles/1001/bao-vat-quoc-gia">Menu</a></nav>
        
        <div class="container">
            <div class="col-lg-12">
                <ol class="breadcrumb">
                    <li><a href="/vi">Trang chủ</a></li>
                    <li><a href="/vi/Articles/1001/bao-vat-quoc-gia">Bảo vật quốc gia</a></li>
                </ol>
                <h2 class="page-header">Bảo vật quốc gia: Thạp Đào Thịnh</h2>
                
                <div class="row blogpost-stat">
                    <div class="col-sm-6">
                        <i class="fa fa-calendar"></i> 27/03/2023
                        <i class="fa fa-clock-o"></i> 10:46
                        <i class="fa fa-eye"></i> 15230
                    </div>
                    <div class="col-sm-6 text-right">
                        <span class="starrr">Rating to ignore</span>
                    </div>
                </div>

                <div class="text-justify article-abstracts">
                    Thạp đồng Đào Thịnh là một bảo vật khảo cổ học vô giá thuộc nền văn hóa Đông Sơn.
                </div>

                <div class="text-justify article-detail">
                    <p><strong>Số đăng ký:</strong> LSb. 32967</p>
                    <p><strong>Chất liệu:</strong> Đồng thau</p>
                    <p><strong>Kích thước:</strong> Đường kính miệng 61cm, cao 90cm</p>
                    <p><strong>Niên đại:</strong> Văn hóa Đông Sơn, khoảng 2500 - 2000 năm cách ngày nay</p>
                    <p><strong>Quyết định công nhận số:</strong> 1426/QĐ-TTg ngày 1/10/2012 của Thủ tướng Chính phủ</p>
                    <p>Thạp được phát hiện tại thôn Đào Thịnh, huyện Trấn Yên, tỉnh Yên Bái.</p>

                    <h3>Đặc điểm hình thái và hoa văn</h3>
                    <p>Nắp thạp có hình nón cụt, trên nắp đúc nổi bốn khối tượng nam nữ giao hoan đặc sắc.</p>
                    <div>
                        <img src="/DataFiles/2023/03/Thap_Dao_Thinh_1.jpg" alt="Thạp đồng Đào Thịnh">
                    </div>
                    <p align="center"><em>Hiện vật Thạp đồng Đào Thịnh tại phòng trưng bày</em></p>

                    <h3>Giá trị lịch sử và nghệ thuật</h3>
                    <p>Đây là chiếc thạp có kích thước lớn nhất và hoa văn trang trí tinh xảo nhất trong các thạp Đông Sơn.</p>
                    <p>Hiện vật đang được lưu giữ tại: Bảo tàng Lịch sử quốc gia, Hà Nội.</p>
                    <p><a href="https://baotanglichsu.vn/vi/Articles/1001/73801/lien-ket.html">Xem thêm tài liệu liên quan</a></p>
                    
                    <p align="right">Lê Thị Hồng Thu</p>
                </div>

                <div class="article-source">Bảo tàng Lịch sử quốc gia</div>
                <hr>
                <div class="row">Chia sẻ: Facebook, Zalo</div>
                <footer>Bản quyền thuộc về BTLSQG</footer>
            </div>
        </div>
    </form>
</body>
</html>
"""

MOCK_HUB_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="container">
        <div class="thumb">
            <h4><a href="/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html">Thạp Đào Thịnh</a></h4>
        </div>
        <div class="thumb">
            <h4><a href="/vi/Articles/1001/76300/so-vang.html">Sổ vàng</a></h4>
        </div>
        <ul class="pagination">
            <li class="active"><span>1</span></li>
            <li><a href="/vi/Articles/1001/bao-vat-quoc-gia/Page2">2</a></li>
            <li><a href="/vi/Articles/1001/bao-vat-quoc-gia/Page3">3</a></li>
        </ul>
    </div>
</body>
</html>
"""


class TestHeritageCorpus(unittest.TestCase):

    def test_url_normalization_and_deduplication(self):
        base = "https://baotanglichsu.vn"

        # 1. Relative link resolution
        rel_url = "/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html"
        norm = URLNormalizer.normalize_url(rel_url, base)
        self.assertEqual(norm, "https://baotanglichsu.vn/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html")

        # 2. Tracking params and fragments
        dirty = "https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia/?utm_source=fb&fbclid=123#overview"
        clean = URLNormalizer.normalize_url(dirty)
        self.assertEqual(clean, "https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia")

        # 3. Path parsing & Stable ID
        p_info = URLNormalizer.parse_vnmh_path(norm)
        self.assertTrue(p_info["is_valid_vnmh"])
        self.assertEqual(p_info["language"], "vi")
        self.assertEqual(p_info["category_id"], "1001")
        self.assertEqual(p_info["article_id"], "73800")
        self.assertEqual(p_info["stable_doc_id"], "VNMH-VI-1001-73800")

        # 4. Out of scope / loop rejection
        self.assertIsNone(URLNormalizer.normalize_url("https://external-website.com/news"))
        self.assertIsNone(URLNormalizer.normalize_url("javascript:void(0)"))
        self.assertIsNone(URLNormalizer.normalize_url("/vi/Search?query=trong+dong"))

    def test_pagination_and_hub_extraction(self):
        hub_url = "https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia"
        links = VNMHParser.extract_hub_links(MOCK_HUB_HTML, hub_url)

        self.assertEqual(len(links["articles"]), 2)
        self.assertIn("https://baotanglichsu.vn/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html", links["articles"])
        self.assertIn("https://baotanglichsu.vn/vi/Articles/1001/76300/so-vang.html", links["articles"])

        self.assertEqual(len(links["paginations"]), 2)
        self.assertIn("https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia/Page2", links["paginations"])
        self.assertIn("https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia/Page3", links["paginations"])

    def test_parser_metadata_and_fidelity(self):
        url = "https://baotanglichsu.vn/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html"
        retrieved_at = "2026-11-09T16:00:00Z"
        doc, sections, links, media = VNMHParser.parse_article(MOCK_ARTICLE_HTML, url, retrieved_at)

        # Title & Author
        self.assertEqual(doc.title, "Bảo vật quốc gia: Thạp Đào Thịnh")
        self.assertEqual(doc.author, "Lê Thị Hồng Thu")

        # Temporal published date (NOT crawl date!)
        self.assertEqual(doc.published_at, "2023-03-27T10:46:00")
        self.assertEqual(doc.view_count, 15230)

        # Structured metadata
        meta = doc.metadata_fields
        self.assertEqual(meta.get("registration_number"), "LSb. 32967")
        self.assertIn("Đồng", meta.get("material", ""))
        self.assertIn("Đông Sơn", meta.get("era_culture", ""))
        self.assertIn("1426/QĐ-TTg", meta.get("recognition_decree", ""))
        self.assertIn("Yên Bái", meta.get("discovery_location", ""))
        self.assertIn("Bảo tàng Lịch sử quốc gia", meta.get("storage_location", ""))

        # Classification
        self.assertEqual(doc.classification, "ARTIFACT_PROFILE")

        # Media & Caption association
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0].alt_text, "Thạp đồng Đào Thịnh")
        self.assertEqual(media[0].caption, "Hiện vật Thạp đồng Đào Thịnh tại phòng trưng bày")
        self.assertFalse(media[0].download_permitted)  # Safety first: metadata only

        # Outgoing links
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].link_type, "INTERNAL_ARTICLE")

    def test_parser_contamination_resistance(self):
        url = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap.html"
        doc, sections, _, _ = VNMHParser.parse_article(MOCK_ARTICLE_HTML, url, "2026-11-09T16:00:00Z")

        # Content must NOT contain header, nav, share or footer
        self.assertNotIn("Navigation Header", doc.content_text)
        self.assertNotIn("Chia sẻ:", doc.content_text)
        self.assertNotIn("Rating to ignore", doc.content_text)
        self.assertNotIn("Bản quyền thuộc về BTLSQG", doc.content_text)

    def test_rag_evidence_spans(self):
        url = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap.html"
        doc, sections, _, _ = VNMHParser.parse_article(MOCK_ARTICLE_HTML, url, "2026-11-09T16:00:00Z")
        chunks = RAGPreparer.prepare_chunks(doc, sections)

        self.assertGreater(len(chunks), 1)
        # Check first chunk (Summary)
        c0 = chunks[0]
        self.assertEqual(c0.heading_path, ["Bảo vật quốc gia: Thạp Đào Thịnh", "Tóm tắt"])
        self.assertTrue(c0.index_eligibility)
        self.assertIn("Đông Sơn", c0.temporal_context or "")
        self.assertEqual(c0.char_start, 0)
        self.assertGreater(c0.char_end, 0)

    def test_kg_candidate_edges(self):
        url = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap.html"
        doc, sections, _, _ = VNMHParser.parse_article(MOCK_ARTICLE_HTML, url, "2026-11-09T16:00:00Z")
        mentions, edges = KGPreparer.extract_kg_candidates(doc)

        # Check entity mentions
        entity_types = {m.entity_type for m in mentions}
        self.assertIn("ARTIFACT", entity_types)
        self.assertIn("INSTITUTION", entity_types)
        self.assertIn("CULTURE", entity_types)
        self.assertIn("LOCATION", entity_types)
        self.assertIn("PERSON", entity_types)

        # Check candidate relations
        rel_types = {e.relation_type for e in edges}
        self.assertIn("CURRENTLY_HELD_BY", rel_types)
        self.assertIn("ASSOCIATED_WITH_CULTURE", rel_types)
        self.assertIn("DISCOVERED_AT", rel_types)
        self.assertIn("CREATED_BY", rel_types)

        # Epistemic status & Review Status
        for e in edges:
            self.assertEqual(e.review_status, "PENDING_REVIEW")
            self.assertIn(e.epistemic_status, ("ASSERTED", "DERIVED", "HYPOTHESIZED"))

    def test_legacy_matching(self):
        url = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap.html"
        doc, _, _, _ = VNMHParser.parse_article(MOCK_ARTICLE_HTML, url, "2026-11-09T16:00:00Z")
        
        matcher = LegacyMatcher()
        matches = matcher.find_matches(doc)

        # Thạp Đào Thịnh should match legacy ID 3 with high confidence
        matched_ids = [m.legacy_artifact_id for m in matches]
        self.assertIn(3, matched_ids)

        match_record = next(m for m in matches if m.legacy_artifact_id == 3)
        self.assertGreaterEqual(match_record.confidence_score, 0.8)
        self.assertEqual(match_record.review_status, "PENDING_REVIEW")
        self.assertIn("Thạp đồng Đào Thịnh", match_record.evidence_notes)
        self.assertIn("Đông Sơn", match_record.evidence_notes)

    def test_state_manager_resume_and_failure_ledger(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name

        state = None
        state_resumed = None
        try:
            state = CorpusStateManager(temp_db)
            url1 = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap.html"
            url2 = "https://baotanglichsu.vn/vi/Articles/1001/failed.html"

            # Add to queue
            self.assertTrue(state.add_to_queue(url1, "VNMH", "ARTICLE", priority=5))
            self.assertTrue(state.add_to_queue(url2, "VNMH", "ARTICLE", priority=5))
            # Duplicate rejected
            self.assertFalse(state.add_to_queue(url1, "VNMH", "ARTICLE"))

            # Complete url1
            state.mark_completed("VNMH-VI-1001-73800", url1, "VNMH", "vi", "hash123", 200)
            self.assertTrue(state.is_visited(url1))

            # Fail url2 (attempt 1)
            state.mark_failed(url2, "VNMH", "HTTP_ERROR", "HTTP 500 Internal Error", http_status=500, max_retries=3)
            self.assertFalse(state.is_visited(url2))  # Failed is NOT visited/completed!

            stats = state.get_queue_stats()
            self.assertEqual(stats["completed"], 1)
            self.assertEqual(stats["total_crawled"], 1)
            self.assertEqual(stats["unresolved_failures"], 1)

            state.close()
            state = None

            # Resume from same DB
            state_resumed = CorpusStateManager(temp_db)
            self.assertTrue(state_resumed.is_visited(url1))
            self.assertFalse(state_resumed.is_visited(url2))
            state_resumed.close()
            state_resumed = None
        finally:
            if state:
                state.close()
            if state_resumed:
                state_resumed.close()
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    def test_source_registry_and_multi_source(self):
        reg = SourceRegistry()
        sources = reg.list_sources()
        source_ids = {s.source_id for s in sources}

        self.assertIn("VNMH", source_ids)
        self.assertIn("DCH", source_ids)
        self.assertIn("UNESCO_WH", source_ids)
        self.assertIn("UNESCO_ICH", source_ids)
        self.assertIn("WIKIDATA", source_ids)
        self.assertIn("COMMONS", source_ids)
        self.assertIn("SCHOLARLY", source_ids)

        vnmh = reg.get("VNMH")
        self.assertTrue(vnmh.enabled)
        self.assertEqual(vnmh.provenance_tier, "OFFICIAL_MUSEUM")


if __name__ == "__main__":
    unittest.main()
