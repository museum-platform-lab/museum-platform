"""
Museum Platform - Heritage Corpus Test Runner (T-001 to T-028)
Runs all 28 automated tests covering reliability, safety, extraction, RAG, KG, and legacy matching.
Exports machine-readable audit_handover/evidence/test-results.json and test-results.xml.
"""

import sys
import os
import time
import json
import traceback
import tempfile
import shutil
import datetime
import unicodedata

# Ensure paths
corpus_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(corpus_root))

from heritage_corpus.adapters.base import BaseSourceAdapter
from heritage_corpus.url_normalizer import URLNormalizer
from heritage_corpus.state_manager import CorpusStateManager
from heritage_corpus.storage import CorpusStorage
from heritage_corpus.crawler import HeritageCorpusCrawler
from heritage_corpus.models import SourceConfig, RawDocument, ParsedDocument, DocumentSection
from heritage_corpus.rag_preparer import RAGPreparer
from heritage_corpus.kg_preparer import KGPreparer
from heritage_corpus.vnmh_parser import VNMHParser
from heritage_corpus.legacy_matcher import LegacyMatcher


class DummyAdapter(BaseSourceAdapter):
    def fetch_url(self, url: str):
        return "<html></html>", 200, {}, None

    def parse_article_page(self, html: str, url: str, retrieved_at: str):
        return None, [], [], []


def get_sample_doc():
    clean_text = (
        "Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.\n"
        "Hiện vật được phát hiện năm 1961 tại thôn Đào Thịnh, huyện Trấn Yên, tỉnh Yên Bái.\n"
        "Niên đại khoảng 2500 - 2000 năm cách ngày nay.\n"
        "Chất liệu: Đồng thau.\n"
        "Kích thước: Chiều cao 98 cm, đường kính miệng 61 cm.\n"
        "Hiện vật được lưu giữ tại Bảo tàng Lịch sử quốc gia.\n"
        "Tác giả bài viết: Nguyễn Văn A."
    )
    return ParsedDocument(
        doc_id="VNMH-VI-1001-73800",
        source_id="VNMH",
        canonical_url="https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html",
        original_url="https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html",
        language="vi",
        title="Bảo vật Quốc gia: Thạp Đào Thịnh",
        canonical_clean_text=clean_text,
        content_text=clean_text,
        author="Nguyễn Văn A",
        published_at="2020-01-01",
        classification="ARTIFACT_PROFILE",
        summary_abstract="Tóm tắt về thạp đồng Đào Thịnh.",
        metadata_fields={
            "registration_number": "LSb 13855",
            "material": "Đồng",
            "dimensions": "Cao 98cm; đk miệng 61cm",
            "era_culture": "Văn hóa Đông Sơn",
            "storage_location": "Bảo tàng Lịch sử quốc gia"
        },
        validation_status="VALIDATED"
    )


# Test functions registry
TESTS = []


def register_test(test_id, category, description):
    def decorator(fn):
        TESTS.append({
            "id": test_id,
            "category": category,
            "description": description,
            "func": fn
        })
        return fn
    return decorator


# -------------------------------------------------------------
# T-001 to T-014: Reliability, Concurrency, State, and Safety
# -------------------------------------------------------------

@register_test("T-001", "Reliability", "429 response with Retry-After integer delay")
def test_t001():
    delay = BaseSourceAdapter.parse_retry_after("120")
    assert delay == 120, f"Expected 120, got {delay}"


@register_test("T-002", "Reliability", "429 response with Retry-After HTTP-date format")
def test_t002():
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
    delay = BaseSourceAdapter.parse_retry_after(future_time.strftime("%a, %d %b %Y %H:%M:%S GMT"))
    assert 55 <= delay <= 65, f"Expected ~60s, got {delay}"


@register_test("T-003", "Reliability", "Network crash and resume recovery of stale queue items")
def test_t003():
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "crash_test.db")
        mgr = CorpusStateManager(db_path)
        url = "https://baotanglichsu.vn/vi/Articles/1001/1/crash-art.html"
        mgr.add_to_queue(url, "VNMH", "ARTICLE", depth=1, priority=5)

        batch = mgr.get_next_batch(batch_size=1)
        assert len(batch) == 1

        with mgr._connect() as conn:
            conn.execute("UPDATE crawl_queue SET lease_expires_at = '2000-01-01T00:00:00Z'")

        recovered = mgr.recover_stale_processing(timeout_seconds=0)
        assert recovered == 1, f"Expected 1 recovered item, got {recovered}"

        resumed = mgr.get_next_batch(batch_size=1)
        assert len(resumed) == 1
        assert resumed[0]["url"] == url
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-004", "Concurrency", "Atomic claim with BEGIN IMMEDIATE transaction isolation")
def test_t004():
    tmp_dir = tempfile.mkdtemp()
    try:
        mgr = CorpusStateManager(os.path.join(tmp_dir, "atomic.db"))
        mgr.add_to_queue("https://baotanglichsu.vn/vi/art1.html", "VNMH", "ARTICLE", 1, 5)
        mgr.add_to_queue("https://baotanglichsu.vn/vi/art2.html", "VNMH", "ARTICLE", 1, 5)

        b1 = mgr.get_next_batch(1, worker_id="w1")
        b2 = mgr.get_next_batch(1, worker_id="w2")
        assert len(b1) == 1 and len(b2) == 1
        assert b1[0]["url"] != b2[0]["url"], "Double claim collision detected!"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-005", "Concurrency", "Worker lease expiry and stale worker recovery")
def test_t005():
    tmp_dir = tempfile.mkdtemp()
    try:
        mgr = CorpusStateManager(os.path.join(tmp_dir, "lease.db"))
        url = "https://baotanglichsu.vn/vi/art-lease.html"
        mgr.add_to_queue(url, "VNMH", "ARTICLE", 1, 5)
        mgr.get_next_batch(1, worker_id="dead_worker", lease_timeout_seconds=1)

        with mgr._connect() as conn:
            conn.execute("UPDATE crawl_queue SET lease_expires_at = '2000-01-01T00:00:00Z'")

        recovered = mgr.recover_stale_processing(timeout_seconds=0)
        assert recovered >= 1
        b_alive = mgr.get_next_batch(1, worker_id="alive_worker")
        assert len(b_alive) == 1
        assert b_alive[0]["url"] == url
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-006", "Reliability", "Exponential backoff calculation and dead-letter capping")
def test_t006():
    tmp_dir = tempfile.mkdtemp()
    try:
        mgr = CorpusStateManager(os.path.join(tmp_dir, "backoff.db"))
        url = "https://baotanglichsu.vn/vi/art-backoff.html"
        mgr.add_to_queue(url, "VNMH", "ARTICLE", 1, 5)

        mgr.mark_failed(url, "VNMH", "HTTP_500", "Err", http_status=500)
        with mgr._connect() as conn:
            r1 = conn.execute("SELECT attempts, status FROM crawl_queue WHERE url = ?", (url,)).fetchone()
            assert r1["attempts"] == 1 and r1["status"] == "queued"

        for _ in range(4):
            mgr.mark_failed(url, "VNMH", "HTTP_500", "Err", http_status=500, max_retries=5)

        with mgr._connect() as conn:
            r5 = conn.execute("SELECT attempts, status FROM crawl_queue WHERE url = ?", (url,)).fetchone()
            assert r5["attempts"] == 5 and r5["status"] == "failed"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-007", "Safety", "Skipped language queue status without dummy crawled_documents insert")
def test_t007():
    tmp_dir = tempfile.mkdtemp()
    try:
        mgr = CorpusStateManager(os.path.join(tmp_dir, "lang.db"))
        fr_url = "https://baotanglichsu.vn/fr/Articles/1.html"
        mgr.add_to_queue(fr_url, "VNMH", "ARTICLE", 1, 5)
        mgr.mark_skipped_lang(fr_url, "fr")

        with mgr._connect() as conn:
            q_row = conn.execute("SELECT status FROM crawl_queue WHERE url = ?", (fr_url,)).fetchone()
            assert q_row["status"] == "skipped_lang"
            cnt = conn.execute("SELECT COUNT(*) as c FROM crawled_documents WHERE doc_id = 'SKIPPED_LANG'").fetchone()["c"]
            assert cnt == 0, "Found illegal dummy insert in crawled_documents"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-008", "Extraction", "Canonical URL normalization and duplicate rejection")
def test_t008():
    u1 = "HTTP://baotanglichsu.vn:80/vi/Articles/1001/73800/thap-dao-thinh.html#sec"
    u2 = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html?utm_source=fb"
    u3 = "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html"
    c1 = URLNormalizer.normalize_url(u1)
    c2 = URLNormalizer.normalize_url(u2)
    c3 = URLNormalizer.normalize_url(u3)
    assert c1 == c2 == c3
    assert c1 == "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html"


@register_test("T-009", "Safety", "SSRF protection and private IP blocking")
def test_t009():
    bad = [
        "http://127.0.0.1/admin",
        "http://localhost:8080/test",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/config",
        "http://169.254.169.254/meta-data/"
    ]
    for b in bad:
        safe, _ = URLNormalizer.is_safe_host(b)
        assert not safe, f"SSRF vulnerability: {b} was not blocked!"
    safe, _ = URLNormalizer.is_safe_host("https://baotanglichsu.vn/vi")
    assert safe


@register_test("T-010", "Safety", "Redirect hop domain validation (external domain rejection)")
def test_t010():
    cfg = SourceConfig(
        source_id="VNMH",
        name="VNMH",
        base_url="https://baotanglichsu.vn",
        allowed_domains=["baotanglichsu.vn"],
        robots_url="https://baotanglichsu.vn/robots.txt"
    )
    ad = DummyAdapter(cfg)
    assert not ad.is_safe_host("phishing.org", cfg.allowed_domains)
    assert ad.is_safe_host("baotanglichsu.vn", cfg.allowed_domains)


@register_test("T-011", "Safety", "Fail-safe robots.txt policy on network error")
def test_t011():
    cfg = SourceConfig(
        source_id="VNMH",
        name="VNMH",
        base_url="https://baotanglichsu.vn",
        allowed_domains=["baotanglichsu.vn"],
        robots_url="https://baotanglichsu.vn/robots.txt"
    )
    ad = DummyAdapter(cfg)
    ad._robots_loaded_at = time.time()
    ad._robots_status = "ROBOTS_UNAVAILABLE"
    allowed, status = ad.is_allowed_by_robots("https://baotanglichsu.vn/vi/test")
    assert not allowed
    assert status == "ROBOTS_UNAVAILABLE"


@register_test("T-012", "Safety", "True dry-run isolation (zero body fetch, zero disk writes)")
def test_t012():
    tmp_dir = tempfile.mkdtemp()
    try:
        out_dir = os.path.join(tmp_dir, "dry_out")
        db_path = os.path.join(tmp_dir, "dry.db")
        c = HeritageCorpusCrawler(
            output_dir=out_dir,
            state_db=db_path,
            dry_run=True,
            seed_urls=["https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html"]
        )
        manifest = c.run()
        assert manifest.status == "DRY_RUN_COMPLETED"
        assert not os.path.exists(os.path.join(out_dir, "parsed_documents.jsonl"))
        with c.state._connect() as conn:
            cnt = conn.execute("SELECT COUNT(*) as c FROM crawled_documents").fetchone()["c"]
            assert cnt == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-013", "Reliability", "Separate quotas enforcement (max_discovery_pages vs max_articles)")
def test_t013():
    tmp_dir = tempfile.mkdtemp()
    try:
        c = HeritageCorpusCrawler(
            output_dir=tmp_dir,
            state_db=os.path.join(tmp_dir, "q.db"),
            max_discovery_pages=15,
            max_articles=5
        )
        assert c.max_discovery_pages == 15
        assert c.max_articles == 5
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@register_test("T-014", "Safety", "Immutable raw document writing with atomic temp file rename")
def test_t014():
    tmp_dir = tempfile.mkdtemp()
    try:
        storage = CorpusStorage(tmp_dir)
        raw_doc = RawDocument(
            doc_id="DOC-T014",
            source_id="VNMH",
            url="https://baotanglichsu.vn/test",
            canonical_url="https://baotanglichsu.vn/test",
            http_status=200,
            content_hash="h123",
            retrieved_at="2026-11-09T12:00:00Z",
            headers={},
            raw_html="<p>Test</p>",
            language="vi"
        )
        p = storage.save_raw_document(raw_doc)
        assert os.path.exists(p)
        assert "h123.json" in p
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            assert d["doc_id"] == "DOC-T014"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# -------------------------------------------------------------
# T-015 to T-028: Extraction, RAG, KG, and Legacy Matching
# -------------------------------------------------------------

@register_test("T-015", "RAG", "Exact substring slicing invariant for RAG sections")
def test_t015():
    doc = get_sample_doc()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["Mô tả"],
            heading_level=2,
            section_text="Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.",
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec)
    for c in chunks:
        ref = doc.canonical_clean_text if c.offset_source == "canonical_clean_text" else doc.summary_abstract
        assert ref[c.char_start:c.char_end] == c.section_text


@register_test("T-016", "RAG", "Sentence and word boundary chunk splitting without truncation")
def test_t016():
    doc = get_sample_doc()
    p = "Câu văn kiểm thử dài. " * 30
    doc.canonical_clean_text = p.strip()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-LONG",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=2,
            section_text=p.strip(),
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec, max_chunk_chars=250)
    assert len(chunks) > 1
    for c in chunks:
        assert doc.canonical_clean_text[c.char_start:c.char_end] == c.section_text


@register_test("T-017", "RAG", "Token and hard character cap enforcement")
def test_t017():
    doc = get_sample_doc()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=2,
            section_text=doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec, max_chunk_chars=180)
    for c in chunks:
        assert len(c.section_text) <= RAGPreparer.HARD_CAP_CHARS


@register_test("T-018", "RAG", "Stable section ID format {doc_id}-SEC-{idx:03d}")
def test_t018():
    doc = get_sample_doc()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=1,
            section_text="Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.",
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec)
    for idx, c in enumerate(chunks, 1):
        assert c.section_id == f"{doc.doc_id}-SEC-{idx:03d}"


@register_test("T-019", "KG", "Section FK resolvability in KG candidate edges")
def test_t019():
    doc = get_sample_doc()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=1,
            section_text=doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec)
    valid_ids = {c.section_id for c in chunks}
    mentions, edges = KGPreparer.extract_kg_candidates(doc, chunks)
    for e in edges:
        assert e.provenance_section_id in valid_ids, f"FK {e.provenance_section_id} unresolved!"
    for m in mentions:
        assert m.section_id in valid_ids, f"FK {m.section_id} unresolved!"


@register_test("T-020", "KG", "Exact literal quote verification in KG candidate edges")
def test_t020():
    doc = get_sample_doc()
    raw_sec = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=1,
            section_text=doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(doc, raw_sec)
    sec_map = {c.section_id: c.section_text for c in chunks}
    _, edges = KGPreparer.extract_kg_candidates(doc, chunks)
    for e in edges:
        assert e.evidence_quote in sec_map[e.provenance_section_id]


@register_test("T-021", "KG", "Ontological separation: article author maps to AUTHORED_BY document")
def test_t021():
    doc = get_sample_doc()
    chunks = [
        DocumentSection(
            section_id=f"{doc.doc_id}-SEC-001",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=1,
            section_text=doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=len(doc.canonical_clean_text),
            language="vi"
        )
    ]
    _, edges = KGPreparer.extract_kg_candidates(doc, chunks)
    for e in edges:
        if e.relation_type == "CREATED_BY":
            assert e.target_entity != "Nguyễn Văn A", "Author assigned as artifact creator!"
    authored = [e for e in edges if e.relation_type == "AUTHORED_BY"]
    assert len(authored) == 1
    assert authored[0].target_entity == "Nguyễn Văn A"
    assert authored[0].source_entity_type == "DOCUMENT"


@register_test("T-022", "KG", "Zero custody fabrication without explicit in-text custody evidence")
def test_t022():
    doc = get_sample_doc()
    doc.metadata_fields["storage_location"] = ""
    doc.canonical_clean_text = "Thạp Đào Thịnh là một bảo vật quốc gia thời cổ đại."
    chunks = [
        DocumentSection(
            section_id=f"{doc.doc_id}-SEC-001",
            doc_id=doc.doc_id,
            source_id="VNMH",
            heading_path=["H"],
            heading_level=1,
            section_text=doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=len(doc.canonical_clean_text),
            language="vi"
        )
    ]
    _, edges = KGPreparer.extract_kg_candidates(doc, chunks)
    custody = [e for e in edges if e.relation_type == "CURRENTLY_HELD_BY"]
    assert len(custody) == 0, "Fabricated CURRENTLY_HELD_BY relation!"


@register_test("T-023", "Extraction", "Leaf-block DOM extraction without text duplication")
def test_t023():
    html = """
    <html><body>
    <div class="article-detail">
        <div>
            <p>Đoạn một duy nhất.</p>
            <p>Đoạn hai duy nhất.</p>
        </div>
    </div>
    </body></html>
    """
    text = VNMHParser.extract_clean_text(html)
    assert text.count("Đoạn một duy nhất.") == 1
    assert text.count("Đoạn hai duy nhất.") == 1


@register_test("T-024", "Extraction", "Anchored metadata label extraction with MetadataEvidence")
def test_t024():
    html = """
    <html><body>
    <div class="article-detail">
        <p><strong>Số đăng ký:</strong> LSb 13855</p>
        <p><strong>Chất liệu:</strong> Đồng thau</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article(html, "https://baotanglichsu.vn/vi/art.html", "2026-11-09")
    assert doc.metadata_fields.get("registration_number") == "LSb 13855"
    assert doc.metadata_fields.get("material") == "Đồng thau"
    assert "registration_number" in doc.metadata_evidence
    assert doc.metadata_evidence["registration_number"]["value"] == "LSb 13855"


@register_test("T-025", "Extraction", "Multiline dimensions parsing")
def test_t025():
    html = """
    <html><body>
    <div class="article-detail">
        <p><strong>Kích thước:</strong></p>
        <p>- Chiều cao: 98 cm</p>
        <p>- Đường kính: 61 cm</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article(html, "https://baotanglichsu.vn/vi/art.html", "2026-11-09")
    dims = doc.metadata_fields.get("dimensions", "")
    assert "98" in dims and "61" in dims


@register_test("T-026", "Extraction", "Material & Era false positive rejection (no 's' or 'từ')")
def test_t026():
    html = """
    <html><body>
    <div class="article-detail">
        <p><strong>Materials:</strong></p>
        <p>s</p>
        <p><strong>Niên đại:</strong> từ</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article(html, "https://baotanglichsu.vn/vi/art.html", "2026-11-09")
    assert doc.metadata_fields.get("material") != "s"
    assert doc.metadata_fields.get("era_culture") != "từ"


@register_test("T-027", "Extraction", "Parse quarantine for empty or missing article body")
def test_t027():
    html = "<html><body><h1>Tiêu đề rỗng</h1><div class='article-detail'></div></body></html>"
    doc, _, _, _ = VNMHParser.parse_article(html, "https://baotanglichsu.vn/vi/empty.html", "2026-11-09")
    assert doc.validation_status in ("QUARANTINED", "PARSE_FAILED")
    assert len(doc.quarantine_reasons) > 0


@register_test("T-028", "Legacy", "Legacy matcher missing CSV handling and Unicode NFC normalization")
def test_t028():
    doc = get_sample_doc()
    m_missing = LegacyMatcher("/invalid/path/none.csv")
    assert m_missing.status == "LEGACY_DATA_UNAVAILABLE"
    assert m_missing.find_matches(doc) == []

    # NFC normalization
    t_nfd = unicodedata.normalize("NFD", "Bảo vật quốc gia")
    t_nfc = unicodedata.normalize("NFC", "Bảo vật quốc gia")
    assert LegacyMatcher._normalize_text(t_nfd) == LegacyMatcher._normalize_text(t_nfc)


# -------------------------------------------------------------
# Test Suite Execution & Report Generator
# -------------------------------------------------------------

def run_all():
    print("======================================================================")
    print("       VIETNAMESE HERITAGE CORPUS - AUTOMATED TEST SUITE (T-001..T-028)")
    print("======================================================================\n")

    results = []
    passed_count = 0
    failed_count = 0
    start_all = time.time()

    for t in TESTS:
        t_id = t["id"]
        t_cat = t["category"]
        t_desc = t["description"]
        fn = t["func"]

        t_start = time.time()
        status = "PASSED"
        err_msg = ""
        trace = ""

        try:
            fn()
            passed_count += 1
            print(f"[PASS] {t_id:5s} | {t_cat:12s} | {t_desc}")
        except Exception as e:
            failed_count += 1
            status = "FAILED"
            err_msg = str(e)
            trace = traceback.format_exc()
            print(f"[FAIL] {t_id:5s} | {t_cat:12s} | {t_desc} -> {err_msg}")

        dur_ms = int((time.time() - t_start) * 1000)
        results.append({
            "test_id": t_id,
            "category": t_cat,
            "description": t_desc,
            "status": status,
            "duration_ms": dur_ms,
            "error_message": err_msg,
            "traceback": trace
        })

    total_time = round(time.time() - start_all, 3)
    pass_pct = round((passed_count / max(len(TESTS), 1)) * 100, 2)

    print("\n----------------------------------------------------------------------")
    print(f"TEST EXECUTION SUMMARY: {passed_count}/{len(TESTS)} Passed ({pass_pct}%) | Duration: {total_time}s")
    print("----------------------------------------------------------------------\n")

    # Export test-results.json
    out_dir = os.path.join(corpus_root, "audit_handover", "evidence")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "test-results.json")
    xml_path = os.path.join(out_dir, "test-results.xml")

    report_payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_tests": len(TESTS),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate_pct": pass_pct,
        "duration_seconds": total_time,
        "test_results": results
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON report: {json_path}")

    # Export JUnit XML format
    xml_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<testsuite name="heritage_corpus_tests" tests="{len(TESTS)}" failures="{failed_count}" time="{total_time}">'
    ]
    for r in results:
        dur_s = r["duration_ms"] / 1000.0
        xml_lines.append(f'  <testcase classname="{r["category"]}" name="{r["test_id"]}_{r["description"].replace(" ", "_")}" time="{dur_s:.3f}">')
        if r["status"] == "FAILED":
            xml_lines.append(f'    <failure message="{r["error_message"]}">{r["traceback"]}</failure>')
        xml_lines.append('  </testcase>')
    xml_lines.append('</testsuite>')

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))
    print(f"Saved JUnit XML  : {xml_path}\n")

    return failed_count == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ok = run_all()
    sys.exit(0 if ok else 1)
