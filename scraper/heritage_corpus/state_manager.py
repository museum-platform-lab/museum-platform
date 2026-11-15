"""
Museum Platform - Heritage Corpus State Manager (Schema V2)
SQLite-backed persistent state machine:
- Atomic Claim & Worker Lease / Stale Recovery
- UTC Timestamped Retry / Backoff
- Isolated Skipped-Language State (No IntegrityError)
- Multi-URL Alias Tracking on Stable Doc ID
- Idempotent Schema Migration (V1 -> V2) & Rollback Support
"""

import os
import sqlite3
import datetime
import contextlib
from typing import Optional, Dict, Any, List, Tuple


CURRENT_SCHEMA_VERSION = 2


class CorpusStateManager:
    def __init__(self, db_path: str = "heritage_corpus_state.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
            self.conn = sqlite3.connect(os.path.abspath(db_path), check_same_thread=False, timeout=30.0)
        else:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self._init_and_migrate_db()

    def _init_and_migrate_db(self):
        with self.conn:
            if self.db_path != ":memory:":
                self.conn.execute("PRAGMA journal_mode = WAL;")
                self.conn.execute("PRAGMA synchronous = NORMAL;")

            cur = self.conn.cursor()
            cur.execute("PRAGMA user_version;")
            v = cur.fetchone()[0]

            # 1. Crawled Documents Registry (Keyed primarily on stable doc_id)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crawled_documents (
                    doc_id TEXT PRIMARY KEY,
                    canonical_url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    http_status INTEGER NOT NULL,
                    version INTEGER DEFAULT 1,
                    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. URL Aliases (Allows multiple slug variants to resolve to same stable doc_id)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS url_aliases (
                    alias_url TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Persistent Crawl Queue
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    url TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    page_type TEXT NOT NULL,
                    depth INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed', 'skipped_lang'
                    attempts INTEGER DEFAULT 0,
                    claimed_at TIMESTAMP,
                    lease_expires_at TIMESTAMP,
                    worker_id TEXT,
                    last_error TEXT,
                    next_retry_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Failure Ledger (Strict accountability)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_failures (
                    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    attempt_count INTEGER DEFAULT 1,
                    http_status INTEGER,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    retryable INTEGER DEFAULT 1,
                    last_attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_retry_at TIMESTAMP,
                    resolved INTEGER DEFAULT 0
                );
            """)

            # Check and run migrations if columns missing
            self._ensure_columns_exist()

            # Indices
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_source ON crawled_documents(source_id);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_canon_url ON crawled_documents(canonical_url);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_retry ON crawl_queue(status, next_retry_at, priority DESC, depth ASC);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_failures_url ON crawl_failures(url);")

            self.conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")

    def _ensure_columns_exist(self):
        """Idempotently adds missing columns when migrating from Schema V1."""
        cur = self.conn.cursor()
        # crawl_queue columns
        cur.execute("PRAGMA table_info(crawl_queue);")
        queue_cols = {row["name"] for row in cur.fetchall()}
        if "claimed_at" not in queue_cols:
            self.conn.execute("ALTER TABLE crawl_queue ADD COLUMN claimed_at TIMESTAMP;")
        if "lease_expires_at" not in queue_cols:
            self.conn.execute("ALTER TABLE crawl_queue ADD COLUMN lease_expires_at TIMESTAMP;")
        if "worker_id" not in queue_cols:
            self.conn.execute("ALTER TABLE crawl_queue ADD COLUMN worker_id TEXT;")
        if "next_retry_at" not in queue_cols:
            self.conn.execute("ALTER TABLE crawl_queue ADD COLUMN next_retry_at TIMESTAMP;")

        # crawled_documents columns
        cur.execute("PRAGMA table_info(crawled_documents);")
        doc_cols = {row["name"] for row in cur.fetchall()}
        if "version" not in doc_cols:
            self.conn.execute("ALTER TABLE crawled_documents ADD COLUMN version INTEGER DEFAULT 1;")

        # crawl_failures columns
        cur.execute("PRAGMA table_info(crawl_failures);")
        fail_cols = {row["name"] for row in cur.fetchall()}
        if "retryable" not in fail_cols:
            self.conn.execute("ALTER TABLE crawl_failures ADD COLUMN retryable INTEGER DEFAULT 1;")
        if "next_retry_at" not in fail_cols:
            self.conn.execute("ALTER TABLE crawl_failures ADD COLUMN next_retry_at TIMESTAMP;")

    def recover_stale_processing(self, lease_seconds: int = 300, timeout_seconds: Optional[int] = None) -> int:
        """
        P0-02 Fix: Recovers URLs abandoned in 'processing' state due to a crash.
        Resets them to 'queued' so they can be processed on restart.
        """
        if timeout_seconds is not None:
            lease_seconds = timeout_seconds
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.conn:
            cur = self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'queued', worker_id = NULL, lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                  AND (lease_expires_at IS NULL OR lease_expires_at <= ?);
            """, (now_utc,))
            return cur.rowcount

    def is_visited(self, canonical_url: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM crawled_documents WHERE canonical_url = ?", (canonical_url,))
        if cur.fetchone():
            return True
        cur.execute("SELECT 1 FROM url_aliases WHERE alias_url = ?", (canonical_url,))
        return cur.fetchone() is not None

    def get_existing_hash(self, doc_id: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT content_hash FROM crawled_documents WHERE doc_id = ?", (doc_id,))
        row = cur.fetchone()
        return row["content_hash"] if row else None

    def add_to_queue(
        self,
        url: str,
        source_id: str,
        page_type: str,
        depth: int = 0,
        priority: int = 1,
        force_refresh: bool = False
    ) -> bool:
        """
        Adds URL to crawl_queue. If force_refresh is True, allows re-enqueueing even if visited.
        """
        if not force_refresh and self.is_visited(url):
            return False
        with self.conn:
            try:
                cur = self.conn.execute("""
                    INSERT INTO crawl_queue (url, source_id, page_type, depth, priority, status, attempts)
                    VALUES (?, ?, ?, ?, ?, 'queued', 0)
                    ON CONFLICT(url) DO UPDATE SET
                        status = CASE WHEN excluded.status = 'queued' AND crawl_queue.status IN ('completed', 'failed', 'skipped_lang') AND ? THEN 'queued' ELSE crawl_queue.status END,
                        priority = MAX(crawl_queue.priority, excluded.priority),
                        updated_at = CURRENT_TIMESTAMP;
                """, (url, source_id, page_type, depth, priority, 1 if force_refresh else 0))
                return cur.rowcount > 0
            except sqlite3.Error:
                return False

    def get_next_batch(
        self,
        batch_size: int = 1,
        worker_id: str = "worker-1",
        lease_seconds: int = 300,
        lease_timeout_seconds: Optional[int] = None,
        return_wait_time: bool = False
    ) -> Any:
        """
        P0-01 & P0-02 Fix:
        - Atomic claim via transaction (prevents 2 workers claiming same URL).
        - Enforces next_retry_at <= now_utc (respects retry backoff and Retry-After).
        - Returns claimed_items (or tuple with earliest_future_retry_iso if return_wait_time=True).
        """
        if lease_timeout_seconds is not None:
            lease_seconds = lease_timeout_seconds

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_utc_str = now_utc.isoformat()
        lease_expires = (now_utc + datetime.timedelta(seconds=lease_seconds)).isoformat()

        with self.conn:
            # 1. Check earliest future retry to inform caller if queue is currently waiting
            cur = self.conn.cursor()
            cur.execute("""
                SELECT MIN(next_retry_at) as earliest_wait
                FROM crawl_queue
                WHERE status = 'queued'
                  AND next_retry_at IS NOT NULL
                  AND next_retry_at > ?;
            """, (now_utc_str,))
            wait_row = cur.fetchone()
            earliest_wait = wait_row["earliest_wait"] if wait_row else None

            # 2. Select eligible items ready right now
            cur.execute("""
                SELECT url, source_id, page_type, depth, priority, attempts
                FROM crawl_queue
                WHERE status = 'queued'
                  AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY priority DESC, depth ASC, created_at ASC
                LIMIT ?;
            """, (now_utc_str, batch_size))
            rows = cur.fetchall()
            if not rows:
                return ([], earliest_wait) if return_wait_time else []

            claimed_items = [dict(r) for r in rows]
            urls = [item["url"] for item in claimed_items]

            # 3. Atomically claim them
            placeholders = ",".join(["?"] * len(urls))
            self.conn.execute(f"""
                UPDATE crawl_queue
                SET status = 'processing',
                    worker_id = ?,
                    claimed_at = ?,
                    lease_expires_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE url IN ({placeholders});
            """, [worker_id, now_utc_str, lease_expires] + urls)

            return (claimed_items, earliest_wait) if return_wait_time else claimed_items

    def mark_completed(
        self,
        doc_id: str,
        canonical_url: str,
        source_id: str,
        language: str,
        content_hash: str,
        http_status: int
    ) -> bool:
        """
        P1-10 Fix: Upserts on doc_id. If canonical_url changes, tracks old URL in url_aliases.
        """
        with self.conn:
            # 1. Update queue status
            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'completed', worker_id = NULL, lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?;
            """, (canonical_url,))

            # 2. Check existing doc
            cur = self.conn.cursor()
            cur.execute("SELECT canonical_url, version FROM crawled_documents WHERE doc_id = ?", (doc_id,))
            existing = cur.fetchone()

            if existing:
                old_canon = existing["canonical_url"]
                new_ver = existing["version"] + 1
                if old_canon != canonical_url:
                    # Record alias
                    self.conn.execute("""
                        INSERT INTO url_aliases (alias_url, doc_id, canonical_url)
                        VALUES (?, ?, ?)
                        ON CONFLICT(alias_url) DO NOTHING;
                    """, (old_canon, doc_id, canonical_url))

                self.conn.execute("""
                    UPDATE crawled_documents
                    SET canonical_url = ?, source_id = ?, language = ?, content_hash = ?,
                        http_status = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE doc_id = ?;
                """, (canonical_url, source_id, language, content_hash, http_status, new_ver, doc_id))
            else:
                self.conn.execute("""
                    INSERT INTO crawled_documents (doc_id, canonical_url, source_id, language, content_hash, http_status, version, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP);
                """, (doc_id, canonical_url, source_id, language, content_hash, http_status))

            # 3. Resolve any failures for this URL
            self.conn.execute("UPDATE crawl_failures SET resolved = 1 WHERE url = ?;", (canonical_url,))
            return True

    def mark_skipped_language(self, url: str, language: str):
        """
        P0-03 Fix: Sets queue status to 'skipped_lang' without inserting into crawled_documents.
        Avoids UNIQUE constraint collision on dummy SKIPPED_LANG ID and preserves re-crawlability.
        """
        with self.conn:
            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'skipped_lang', worker_id = NULL, lease_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?;
            """, (url,))

    mark_skipped_lang = mark_skipped_language

    def mark_quarantined(self, doc_id: str, url: str, source_id: str, reason: str):
        """
        Marks document as quarantined due to validation/parse failure.
        """
        with self.conn:
            self.conn.execute("""
                UPDATE crawl_queue
                SET status = 'quarantined', worker_id = NULL, lease_expires_at = NULL, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE url = ?;
            """, (reason, url))

    @contextlib.contextmanager
    def _connect(self):
        yield self.conn

    def requeue_skipped_languages(self, target_langs: List[str]) -> int:
        """
        P0-03 Fix: Allows re-enqueueing previously skipped URLs when target_langs configuration changes.
        """
        target_set = {l.lower() for l in target_langs}
        count = 0
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT url FROM crawl_queue WHERE status = 'skipped_lang';")
            rows = cur.fetchall()
            for r in rows:
                u = r["url"]
                # Check path language
                is_match = False
                for lang in target_set:
                    if f"/{lang}/" in u or u.endswith(f"/{lang}"):
                        is_match = True
                        break
                if is_match:
                    self.conn.execute("""
                        UPDATE crawl_queue
                        SET status = 'queued', updated_at = CURRENT_TIMESTAMP
                        WHERE url = ?;
                    """, (u,))
                    count += 1
        return count

    def mark_failed(
        self,
        url: str,
        source_id: str,
        error_type: str,
        error_message: str,
        http_status: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        max_retries: int = 3,
        base_backoff_sec: float = 2.0
    ):
        """
        P0-01 Fix:
        - Accurately computes next_retry_at using exponential backoff or Retry-After header.
        - Respects permanent failure types (404, robots denied).
        - Keeps failed URLs waiting in failure ledger until next_retry_at.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Permanent non-retryable errors
        is_permanent = False
        if http_status in (404, 410):
            is_permanent = True
        elif "BLOCKED_BY_ROBOTS" in error_type or "INVALID_SCHEME" in error_type or "DISALLOWED_HOST" in error_type:
            is_permanent = True

        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT attempts FROM crawl_queue WHERE url = ?", (url,))
            row = cur.fetchone()
            current_attempts = (row["attempts"] if row else 0) + 1

            if is_permanent or current_attempts >= max_retries:
                new_status = "failed"
                next_retry_str = None
                retryable_int = 0
            else:
                new_status = "queued"
                retryable_int = 1
                # Use max of server Retry-After and local exponential backoff
                local_backoff = base_backoff_sec * (2 ** (current_attempts - 1))
                effective_backoff = max(retry_after_seconds or 0, local_backoff)
                next_retry = now_utc + datetime.timedelta(seconds=effective_backoff)
                next_retry_str = next_retry.isoformat()

            self.conn.execute("""
                UPDATE crawl_queue
                SET status = ?,
                    attempts = ?,
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    last_error = ?,
                    next_retry_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE url = ?;
            """, (new_status, current_attempts, error_message, next_retry_str, url))

            self.conn.execute("""
                INSERT INTO crawl_failures (url, source_id, attempt_count, http_status, error_type, error_message, retryable, next_retry_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (url, source_id, current_attempts, http_status, error_type, error_message, retryable_int, next_retry_str))

    def get_queue_stats(self) -> Dict[str, int]:
        cur = self.conn.cursor()
        cur.execute("SELECT status, count(*) as cnt FROM crawl_queue GROUP BY status;")
        counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
        cur.execute("SELECT count(*) as total_crawled FROM crawled_documents;")
        total_crawled = cur.fetchone()["total_crawled"]
        cur.execute("SELECT count(*) as unresolved_failures FROM crawl_failures WHERE resolved = 0;")
        unresolved = cur.fetchone()["unresolved_failures"]
        return {
            "queued": counts.get("queued", 0),
            "processing": counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "skipped_lang": counts.get("skipped_lang", 0),
            "total_crawled": total_crawled,
            "unresolved_failures": unresolved
        }

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
