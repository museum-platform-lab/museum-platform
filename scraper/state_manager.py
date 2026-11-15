"""
Museum Platform - Crawler State Manager
----------------------------------------
Quản lý trạng thái thu thập dữ liệu bằng SQLite:
- Persistent Queue (Hàng đợi bền vững, không mất khi tắt máy)
- Pages Registry (Danh mục trang đã cào, Page ID, Revision ID, Canonical URL)
- Quarantine Archive (Danh mục trang bị cách ly/loại bỏ: C01, C02, ...)
"""

import os
import sqlite3
import datetime
from typing import Optional, Dict, Any, List

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "crawler_state.db")

class CrawlStateManager:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        if db_path != ":memory:":
            self.db_path = os.path.abspath(db_path)
        else:
            self.db_path = ":memory:"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            if self.db_path != ":memory:":
                self.conn.execute("PRAGMA journal_mode = WAL;")
                self.conn.execute("PRAGMA synchronous = NORMAL;")
            
            # 1. Bảng quản lý trang đã cào / trang đã xác định
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    page_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    canonical_url TEXT NOT NULL UNIQUE,
                    revision_id INTEGER,
                    namespace INTEGER DEFAULT 0,
                    status TEXT NOT NULL, -- 'crawled', 'quarantined', 'failed'
                    quarantine_reason TEXT,
                    discovered_via TEXT,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Hàng đợi thu thập (Queue)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    url TEXT PRIMARY KEY,
                    page_id INTEGER,
                    title TEXT,
                    depth INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed'
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Bảng lưu trữ cách ly (Quarantine / Archive)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS quarantine_archive (
                    url TEXT PRIMARY KEY,
                    page_id INTEGER,
                    title TEXT,
                    reason_code TEXT NOT NULL,
                    details TEXT,
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Chỉ mục
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(canonical_url);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_prio ON crawl_queue(status, priority DESC, depth ASC);")

    def is_visited(self, url: str) -> bool:
        """Kiểm tra URL đã được cào thành công hoặc đang bị cách ly chưa"""
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM pages WHERE canonical_url = ? AND status = 'crawled'", (url,))
        if cur.fetchone():
            return True
        cur.execute("SELECT 1 FROM quarantine_archive WHERE url = ?", (url,))
        if cur.fetchone():
            return True
        return False

    def is_page_id_crawled(self, page_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM pages WHERE page_id = ? AND status = 'crawled'", (page_id,))
        return cur.fetchone() is not None

    def add_to_queue(self, url: str, page_id: Optional[int] = None, title: Optional[str] = None, depth: int = 0, priority: int = 1) -> bool:
        """Thêm URL vào hàng đợi nếu chưa từng cào và chưa có trong queue"""
        if self.is_visited(url):
            return False
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR IGNORE INTO crawl_queue (url, page_id, title, depth, priority, status)
                    VALUES (?, ?, ?, ?, ?, 'queued')
                """, (url, page_id, title, depth, priority))
            return True
        except Exception:
            return False

    def pop_queue(self) -> Optional[Dict[str, Any]]:
        """Lấy phần tử ưu tiên cao nhất trong queue để xử lý"""
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT url, page_id, title, depth, priority, attempts
                FROM crawl_queue
                WHERE status = 'queued'
                ORDER BY priority DESC, depth ASC, created_at ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                return None
            url = row["url"]
            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'processing', attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
            """, (url,))
            return dict(row)

    def mark_completed(self, page_id: int, title: str, canonical_url: str, revision_id: Optional[int] = None, namespace: int = 0, discovered_via: Optional[str] = None):
        """Đánh dấu thu thập thành công 1 bài viết"""
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT page_id FROM pages WHERE canonical_url = ?", (canonical_url,))
            existing = cur.fetchone()
            if existing:
                try:
                    self.conn.execute("""
                        UPDATE pages SET
                            page_id = ?,
                            title = ?,
                            revision_id = ?,
                            status = 'crawled',
                            discovered_via = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE canonical_url = ?
                    """, (page_id, title, revision_id, discovered_via, canonical_url))
                except sqlite3.IntegrityError:
                    self.conn.execute("""
                        UPDATE pages SET
                            title = ?,
                            revision_id = ?,
                            status = 'crawled',
                            discovered_via = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE canonical_url = ?
                    """, (title, revision_id, discovered_via, canonical_url))
            else:
                self.conn.execute("""
                    INSERT INTO pages (page_id, title, canonical_url, revision_id, namespace, status, discovered_via, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'crawled', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(page_id) DO UPDATE SET
                        title = excluded.title,
                        canonical_url = excluded.canonical_url,
                        revision_id = excluded.revision_id,
                        status = 'crawled',
                        updated_at = CURRENT_TIMESTAMP
                """, (page_id, title, canonical_url, revision_id, namespace, discovered_via))

            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE url = ? OR page_id = ?
            """, (canonical_url, page_id))

    def mark_quarantined(self, url: str, title: str, reason_code: str, page_id: Optional[int] = None, details: Optional[str] = None):
        """Đánh dấu cách ly một bản ghi lỗi/phi hiện vật"""
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO quarantine_archive (url, page_id, title, reason_code, details, archived_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (url, page_id, title, reason_code, details))

            if page_id:
                cur = self.conn.cursor()
                cur.execute("SELECT page_id FROM pages WHERE canonical_url = ?", (url,))
                existing = cur.fetchone()
                if existing:
                    try:
                        self.conn.execute("""
                            UPDATE pages SET
                                page_id = ?,
                                title = ?,
                                status = 'quarantined',
                                quarantine_reason = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE canonical_url = ?
                        """, (page_id, title or "", reason_code, url))
                    except sqlite3.IntegrityError:
                        self.conn.execute("""
                            UPDATE pages SET
                                title = ?,
                                status = 'quarantined',
                                quarantine_reason = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE canonical_url = ?
                        """, (title or "", reason_code, url))
                else:
                    self.conn.execute("""
                        INSERT INTO pages (page_id, title, canonical_url, status, quarantine_reason, updated_at)
                        VALUES (?, ?, ?, 'quarantined', ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(page_id) DO UPDATE SET
                            title = excluded.title,
                            canonical_url = excluded.canonical_url,
                            status = 'quarantined',
                            quarantine_reason = excluded.quarantine_reason,
                            updated_at = CURRENT_TIMESTAMP
                    """, (page_id, title or "", url, reason_code))

            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'quarantined', updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
            """, (url,))

    def mark_failed(self, url: str, error_msg: str, max_retries: int = 3):
        """Đánh dấu thất bại và lên lịch retry nếu chưa vượt quá số lần thử"""
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT attempts FROM crawl_queue WHERE url = ?", (url,))
            row = cur.fetchone()
            attempts = row["attempts"] if row else 1
            new_status = 'failed' if attempts >= max_retries else 'queued'

            self.conn.execute("""
                UPDATE crawl_queue
                SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
            """, (new_status, error_msg, url))

    def get_metrics(self) -> Dict[str, int]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pages WHERE status = 'crawled'")
        crawled_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM quarantine_archive")
        quarantine_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM crawl_queue WHERE status = 'queued'")
        queued_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM crawl_queue WHERE status = 'failed'")
        failed_count = cur.fetchone()[0]

        return {
            "crawled_pages": crawled_count,
            "quarantined_pages": quarantine_count,
            "queued_urls": queued_count,
            "failed_urls": failed_count
        }

    def close(self):
        self.conn.close()
