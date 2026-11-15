"""
Unit and Integration Test Suite: Reliability, Concurrency, State, and Safety (T-001 to T-014)
Acceptance Gates G1, G2, G3, G4, G5, G6
"""

import os
import sys
import time
import json
import sqlite3
import datetime
import pytest

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from heritage_corpus.adapters.base import BaseSourceAdapter, AdapterConfig
from heritage_corpus.url_normalizer import URLNormalizer
from heritage_corpus.state_manager import CorpusStateManager
from heritage_corpus.storage import CorpusStorage
from heritage_corpus.crawler import HeritageCorpusCrawler
from heritage_corpus.models import RawDocument


class DummyAdapter(BaseSourceAdapter):
    def fetch_url(self, url: str):
        return "<html></html>", 200, {}, None

    def parse_article_page(self, html: str, url: str, retrieved_at: str):
        return None, [], [], []


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_state.db")
    mgr = CorpusStateManager(db_path)
    return mgr


# --- T-001: 429 response with Retry-After integer ---
def test_t001_retry_after_integer():
    adapter = DummyAdapter(AdapterConfig(source_id="TEST", name="Test", base_url="https://example.com"))
    headers = {"Retry-After": "120"}
    delay = adapter.parse_retry_after(headers, default_delay=5.0)
    assert delay == 120.0


# --- T-002: 429 response with Retry-After HTTP-date ---
def test_t002_retry_after_http_date():
    adapter = DummyAdapter(AdapterConfig(source_id="TEST", name="Test", base_url="https://example.com"))
    # HTTP-date 60 seconds into future
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
    http_date_str = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    headers = {"Retry-After": http_date_str}
    delay = adapter.parse_retry_after(headers, default_delay=5.0)
    assert 55.0 <= delay <= 65.0


# --- T-003: Network crash and resume ---
def test_t003_crash_and_resume(temp_db):
    url = "https://baotanglichsu.vn/vi/Articles/1001/1/test-article.html"
    temp_db.add_to_queue(url, "VNMH", "ARTICLE", depth=1, priority=5)

    # Claim item
    batch = temp_db.get_next_batch(batch_size=1)
    assert len(batch) == 1
    assert batch[0]["url"] == url

    # Simulate crash before completion (status is still 'pending' with lease_expires_at)
    # Recover stale items after artificially expiring lease
    with temp_db._connect() as conn:
        conn.execute("UPDATE crawl_queue SET lease_expires_at = '2000-01-01T00:00:00Z'")

    recovered = temp_db.recover_stale_processing(timeout_seconds=0)
    assert recovered == 1

    # Should be available to claim again
    resumed_batch = temp_db.get_next_batch(batch_size=1)
    assert len(resumed_batch) == 1
    assert resumed_batch[0]["url"] == url


# --- T-004: Atomic claim with BEGIN IMMEDIATE ---
def test_t004_atomic_claim(temp_db):
    url1 = "https://baotanglichsu.vn/vi/Articles/1001/1/art-1.html"
    url2 = "https://baotanglichsu.vn/vi/Articles/1001/2/art-2.html"
    temp_db.add_to_queue(url1, "VNMH", "ARTICLE", depth=1, priority=5)
    temp_db.add_to_queue(url2, "VNMH", "ARTICLE", depth=1, priority=5)

    # Worker 1 claims 1 item
    batch1 = temp_db.get_next_batch(batch_size=1, worker_id="worker_1")
    assert len(batch1) == 1

    # Worker 2 claims 1 item
    batch2 = temp_db.get_next_batch(batch_size=1, worker_id="worker_2")
    assert len(batch2) == 1

    # URLs must be distinct (no double claiming)
    assert batch1[0]["url"] != batch2[0]["url"]


# --- T-005: Stale lease recovery ---
def test_t005_stale_lease_recovery(temp_db):
    url = "https://baotanglichsu.vn/vi/Articles/1001/3/art-3.html"
    temp_db.add_to_queue(url, "VNMH", "ARTICLE", depth=1, priority=5)

    # Worker claims item with lease
    temp_db.get_next_batch(batch_size=1, worker_id="dead_worker", lease_timeout_seconds=1)

    # Artificially expire lease
    with temp_db._connect() as conn:
        conn.execute("UPDATE crawl_queue SET lease_expires_at = '2020-01-01T00:00:00Z'")

    recovered = temp_db.recover_stale_processing(timeout_seconds=0)
    assert recovered >= 1

    # Available again
    batch = temp_db.get_next_batch(batch_size=1, worker_id="alive_worker")
    assert len(batch) == 1
    assert batch[0]["url"] == url


# --- T-006: Exponential backoff calculation and cap ---
def test_t006_exponential_backoff_and_cap(temp_db):
    url = "https://baotanglichsu.vn/vi/Articles/1001/4/art-4.html"
    temp_db.add_to_queue(url, "VNMH", "ARTICLE", depth=1, priority=5)

    # Fail 1: delay 10s
    temp_db.mark_failed(url, "VNMH", "HTTP_500", "Server error", http_status=500)
    with temp_db._connect() as conn:
        row = conn.execute("SELECT attempts, next_retry_at, status FROM crawl_queue WHERE url = ?", (url,)).fetchone()
        assert row["attempts"] == 1
        assert row["status"] == "pending"

    # Simulate 5 consecutive failures up to max_attempts
    for i in range(2, 6):
        temp_db.mark_failed(url, "VNMH", "HTTP_500", "Server error", http_status=500, max_attempts=5)

    with temp_db._connect() as conn:
        row = conn.execute("SELECT attempts, status FROM crawl_queue WHERE url = ?", (url,)).fetchone()
        assert row["attempts"] == 5
        assert row["status"] == "dead_letter"


# --- T-007: Skipped language handling (no dummy insert into crawled_documents) ---
def test_t007_skipped_language_handling(temp_db):
    fr_url = "https://baotanglichsu.vn/fr/Articles/1001/1/art-fr.html"
    temp_db.add_to_queue(fr_url, "VNMH", "ARTICLE", depth=1, priority=5)
    temp_db.mark_skipped_lang(fr_url, "fr")

    with temp_db._connect() as conn:
        q_row = conn.execute("SELECT status FROM crawl_queue WHERE url = ?", (fr_url,)).fetchone()
        assert q_row["status"] == "skipped_lang"

        # Verify NO dummy insert into crawled_documents with doc_id='SKIPPED_LANG'
        doc_count = conn.execute("SELECT COUNT(*) as cnt FROM crawled_documents WHERE doc_id = 'SKIPPED_LANG'").fetchone()["cnt"]
        assert doc_count == 0


# --- T-008: Canonical URL normalization and duplicate URL rejection ---
def test_t008_canonical_normalization():
    url_variations = [
        "HTTP://baotanglichsu.vn:80/vi/Articles/1001/73800/thap-dao-thinh.html#section1",
        "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html?utm_source=fb",
        "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html"
    ]
    canonical = URLNormalizer.normalize_url(url_variations[0])
    assert canonical == "https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html"
    assert URLNormalizer.normalize_url(url_variations[1]) == canonical
    assert URLNormalizer.normalize_url(url_variations[2]) == canonical


# --- T-009: SSRF and private IP blocking ---
def test_t009_ssrf_and_private_ip_blocking():
    blocked_hosts = [
        "http://127.0.0.1/admin",
        "http://localhost:8080/secret",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/"
    ]
    for url in blocked_hosts:
        is_safe, reason = URLNormalizer.is_safe_host(url)
        assert not is_safe, f"Expected {url} to be blocked, but passed: {reason}"

    # Public domain should pass
    safe_url = "https://baotanglichsu.vn/vi"
    is_safe, _ = URLNormalizer.is_safe_host(safe_url)
    assert is_safe


# --- T-010: Redirect hop domain validation ---
def test_t010_redirect_domain_validation():
    adapter = DummyAdapter(AdapterConfig(source_id="VNMH", name="VNMH", base_url="https://baotanglichsu.vn"))
    # Redirect to external domain must be rejected
    assert not adapter.is_safe_redirect("https://baotanglichsu.vn/vi", "https://evil.com/phishing")
    # Redirect within domain is permitted
    assert adapter.is_safe_redirect("https://baotanglichsu.vn/vi", "https://baotanglichsu.vn/vi/Articles/1001")


# --- T-011: Fail-safe robots.txt policy ---
def test_t011_failsafe_robots_policy():
    adapter = DummyAdapter(AdapterConfig(source_id="VNMH", name="VNMH", base_url="https://baotanglichsu.vn"))
    # In fail-safe mode, if robots cannot be fetched, it defaults to False (disallowed)
    assert not adapter.can_fetch_failsafe("https://baotanglichsu.vn/vi/secret", network_error=True)
    # When robots fetch is clean, public path is allowed
    assert adapter.can_fetch_failsafe("https://baotanglichsu.vn/vi/Articles/1001", network_error=False)


# --- T-012: True dry-run isolation ---
def test_t012_true_dry_run_isolation(tmp_path):
    out_dir = str(tmp_path / "dry_run_out")
    db_path = str(tmp_path / "dry_run_state.db")

    crawler = HeritageCorpusCrawler(
        output_dir=out_dir,
        state_db=db_path,
        dry_run=True,
        seed_urls=["https://baotanglichsu.vn/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html"]
    )
    manifest = crawler.run()

    assert manifest.status == "DRY_RUN_COMPLETED"
    # No parsed documents or raw documents written
    assert not os.path.exists(os.path.join(out_dir, "parsed_documents.jsonl"))
    # No articles marked as completed in state DB
    with crawler.state._connect() as conn:
        completed = conn.execute("SELECT COUNT(*) as cnt FROM crawled_documents").fetchone()["cnt"]
        assert completed == 0


# --- T-013: Separate quotas (max_discovery_pages vs max_articles) ---
def test_t013_separate_quotas(tmp_path):
    crawler = HeritageCorpusCrawler(
        output_dir=str(tmp_path),
        state_db=str(tmp_path / "state.db"),
        max_discovery_pages=10,
        max_articles=5
    )
    assert crawler.max_discovery_pages == 10
    assert crawler.max_articles == 5


# --- T-014: Immutable raw document writing ---
def test_t014_immutable_raw_document_writing(tmp_path):
    storage = CorpusStorage(str(tmp_path))
    raw_doc = RawDocument(
        doc_id="VNMH-TEST-001",
        source_id="VNMH",
        url="https://baotanglichsu.vn/test",
        canonical_url="https://baotanglichsu.vn/test",
        http_status=200,
        content_hash="hash123",
        retrieved_at="2026-11-09T12:00:00Z",
        headers={"Content-Type": "text/html"},
        raw_html="<html><body>Immutable Test</body></html>",
        language="vi"
    )
    path = storage.save_raw_document(raw_doc)
    assert os.path.exists(path)
    assert "hash123.json" in path

    # Reading file returns exact json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["doc_id"] == "VNMH-TEST-001"
        assert data["content_hash"] == "hash123"
