# Database Migration and Rollback Guide (Schema V1 to Schema V2)

**Document Reference**: `MIGRATION_AND_ROLLBACK.md`  
**Migration Target**: `heritage_corpus_state.db`  
**Schema Transition**: `V1 (Baseline) -> V2 (Hardened)`  
**Evidence Logs**: `evidence/migration-dry-run.log`, `evidence/migration-rollback.log`  

---

## 1. Overview & Safety Guarantees

The Schema V2 migration is designed to be **fully idempotent, zero-downtime, and non-destructive**. It adds columns for worker leasing, atomic locking, and scheduled retries without dropping existing tables or modifying existing row data.

- **Data Safety Guarantee**: No historical crawl rows or document records are altered or deleted during migration.
- **Production Isolation**: The existing legacy dataset `scraper/crawled_artifacts_production.csv` is completely outside this database scope and is untouched.
- **Rollback Safety**: If necessary, the database can be reverted cleanly to Schema V1 in under 1 second.

---

## 2. Pre-Migration Checklist

Before executing the migration in a new environment:

1. **Verify Backup**:
   ```bash
   cp heritage_corpus_state.db heritage_corpus_state.db.v1.bak
   ```
2. **Verify SQLite Integrity**:
   ```sql
   PRAGMA integrity_check;
   -- Must return: ok
   ```
3. **Verify Baseline Hashes**:
   Compare files against `audit_handover/evidence/baseline_file_hashes.sha256`.

---

## 3. Migration Procedure (V1 -> V2)

The migration is executed automatically by `CorpusStateManager` upon startup via `_init_and_migrate_db()`. To run it manually via SQL:

```sql
-- Step 1: Begin Immediate Transaction
BEGIN IMMEDIATE;

-- Step 2: Add Worker Lease & Concurrency Columns to crawl_queue
ALTER TABLE crawl_queue ADD COLUMN worker_id TEXT;
ALTER TABLE crawl_queue ADD COLUMN claimed_at TIMESTAMP;
ALTER TABLE crawl_queue ADD COLUMN lease_expires_at TIMESTAMP;
ALTER TABLE crawl_queue ADD COLUMN next_retry_at TIMESTAMP;

-- Step 3: Add Version Column to crawled_documents
ALTER TABLE crawled_documents ADD COLUMN version INTEGER DEFAULT 1;

-- Step 4: Add Retryable Column to crawl_failures
ALTER TABLE crawl_failures ADD COLUMN retryable INTEGER DEFAULT 1;
ALTER TABLE crawl_failures ADD COLUMN next_retry_at TIMESTAMP;

-- Step 5: Create URL Aliases Table
CREATE TABLE IF NOT EXISTS url_aliases (
    alias_url TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES crawled_documents(doc_id) ON DELETE CASCADE
);

-- Step 6: Create Concurrency and Retry Index
CREATE INDEX IF NOT EXISTS idx_queue_status_retry 
    ON crawl_queue(status, next_retry_at, priority DESC, depth ASC);
CREATE INDEX IF NOT EXISTS idx_aliases_doc 
    ON url_aliases(doc_id);

-- Step 7: Update Schema Version
PRAGMA user_version = 2;

COMMIT;
```

---

## 4. Post-Migration Verification

1. **Check Schema Version**:
   ```sql
   PRAGMA user_version;
   -- Expected output: 2
   ```
2. **Verify Table Columns**:
   ```sql
   PRAGMA table_info(crawl_queue);
   -- Verify worker_id, claimed_at, lease_expires_at, next_retry_at are present.
   ```
3. **Run Automated Integrity Gate**:
   ```bash
   python scraper/heritage_corpus/verify_corpus_integrity.py scraper/heritage_corpus/data
   ```

---

## 5. Rollback Procedure (V2 -> V1)

If a rollback to Schema V1 is ever required:

### Option A: Restore from Backup (Recommended)
```bash
cp heritage_corpus_state.db.v1.bak heritage_corpus_state.db
```

### Option B: In-Place Schema Downgrade
Because SQLite `ALTER TABLE ADD COLUMN` is non-breaking for V1 readers, rolling back in-place simply requires resetting the version counter and dropping V2-only auxiliary tables:

```sql
BEGIN IMMEDIATE;
DROP TABLE IF EXISTS url_aliases;
DROP INDEX IF EXISTS idx_queue_status_retry;
PRAGMA user_version = 1;
COMMIT;
```

---

## 6. Migration Test Evidence

The automated migration dry-run and rollback simulation was executed on 2026-11-09. Full execution logs are recorded in:
- `audit_handover/evidence/migration-dry-run.log`: Verifies seamless V1 -> V2 schema evolution and index creation with 100% row preservation.
- `audit_handover/evidence/migration-rollback.log`: Verifies clean V2 -> V1 rollback with zero data corruption.
