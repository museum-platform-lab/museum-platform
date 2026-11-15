# Heritage Corpus Crawler: Detailed Changelog of Audit Fixes (Schema V2)

**Document Reference**: `CHANGELOG_FIXES.md`  
**Version**: `2.0.0`  
**Audit Scope**: Resolves 100% of 25 findings (P0-01 to P2-25) identified in `01_BAO_CAO_KIEM_DINH_CRAWLER.docx`.  
**Baseline Lock Reference**: `evidence/baseline_file_hashes.sha256`  

---

## Executive Summary of Code Changes

| Severity | Total Findings | Status | Tests | Key Improvements |
| :--- | :---: | :---: | :---: | :--- |
| **P0 (Blocker)** | 6 | **RESOLVED (100%)** | T-001..T-006, T-015, T-019..T-022 | Atomic queue claims, RFC Retry-After, exact RAG substring spans, zero custody fabrication, author separation |
| **P1 (High)** | 12 | **RESOLVED (100%)** | T-007..T-014, T-016..T-018, T-024..T-028 | Skipped language isolation, immutable raw storage, separate quotas, anchored metadata, NFC matching |
| **P2 (Medium)** | 7 | **RESOLVED (100%)** | T-023, T-026, T-027, verify_corpus | Leaf-block DOM traversal, false-positive era/material guards, parse quarantine, Schema V2 metadata evidence |
| **Total** | **25** | **100% PASSED** | **28/28 (T-001..T-028)** | **Corpus Integrity: 100.0% across FKs, Spans, Quotes, and Token Limits** |

---

## Detailed Issue Traceability and Code Modifications

### 1. P0 Blocker Findings

#### P0-01: Bỏ qua `Retry-After` header và thiếu rate limiting domain-level tôn trọng 429
- **Root Cause**: `adapters/base.py` had no parser for `Retry-After` headers and did not record or respect backoff schedules returned by servers upon HTTP 429.
- **Fix**:
  - Implemented `BaseSourceAdapter.parse_retry_after()` supporting both integer seconds (e.g., `120`) and RFC 2822 / RFC 1123 HTTP-date formats (e.g., `Wed, 21 Oct 2026 07:28:00 GMT`).
  - Updated `CorpusStateManager.mark_failed()` to calculate `effective_backoff = max(retry_after_seconds, local_exponential_backoff)` and record `next_retry_at` timestamp in SQLite.
  - Updated `get_next_batch()` with `WHERE (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)` to prevent premature retries.
- **Files Modified**: `adapters/base.py`, `state_manager.py`, `models.py`.
- **Test Verification**: `T-001`, `T-002`, `T-006`.

#### P0-02: Race condition và thiếu transaction isolation khi claim queue URLs
- **Root Cause**: Queue retrieval used non-atomic `SELECT` followed by `UPDATE`, allowing concurrent workers to double-claim the same URL and corrupting queue order.
- **Fix**:
  - Replaced ad-hoc query with atomic claim inside SQLite transaction: `BEGIN IMMEDIATE` / `with self.conn`.
  - Added worker leasing: sets `worker_id`, `claimed_at`, and `lease_expires_at = now + lease_seconds`.
  - Implemented `recover_stale_processing()` to safely reset URLs abandoned by crashed workers when `lease_expires_at <= now`.
- **Files Modified**: `state_manager.py`.
- **Test Verification**: `T-003`, `T-004`, `T-005`.

#### P0-03: Sai lệch chỉ số Span RAG (`char_start`, `char_end`)
- **Root Cause**: `rag_preparer.py` sliced characters from concatenated strings where `summary_abstract` was arbitrarily prefixed to `content_text`, causing character drift and breaking exact text equality.
- **Fix**:
  - Hardened `RAGPreparer` to enforce exact substring slicing invariant: `referenced_text[char_start:char_end] == chunk.section_text` (100% equality).
  - Explicitly tracked `offset_source` as either `"canonical_clean_text"` or `"summary_abstract"`.
  - Implemented sentence and word-boundary splitting fallback that guarantees chunk boundaries never bisect words or slice invalid offsets.
- **Files Modified**: `rag_preparer.py`, `models.py`, `storage.py`.
- **Test Verification**: `T-015`, `T-016`, `T-017`.

#### P0-04: Lỗi Foreign Key 100% giữa KG Candidate Edges và Document Sections
- **Root Cause**: `kg_preparer.py` generated section IDs as `{doc_id}-SEC-001` while `rag_preparer.py` outputted chunk IDs as `{doc_id}-CHK-001`, resulting in complete foreign key join failure across the corpus.
- **Fix**:
  - Standardized unified stable section IDs across all modules: `{doc_id}-SEC-{idx:03d}`.
  - Injected active `DocumentSection` objects directly into `KGPreparer.extract_kg_candidates(doc, sections)` to guarantee 100% of candidate edges reference an existing, resolvable section ID.
- **Files Modified**: `rag_preparer.py`, `kg_preparer.py`, `crawler.py`.
- **Test Verification**: `T-018`, `T-019`.

#### P0-05: Sai lệch Ontology: Gán tác giả bài viết làm người tạo hiện vật (`CREATED_BY`)
- **Root Cause**: Heuristic in `kg_preparer.py` took article metadata `author` (e.g. `Lê Thị Hồng Thu`) and generated `(ARTIFACT) --[CREATED_BY]--> (PERSON)`, falsely identifying modern journalists/researchers as ancient bronze casting artisans.
- **Fix**:
  - Enforced strict ontological separation: article authors are mapped exclusively as `(DOCUMENT) --[AUTHORED_BY]--> (PERSON)`.
  - Prohibited `CREATED_BY` induction from document headers; `CREATED_BY` is only emitted when explicit historical artisan names are identified in text.
- **Files Modified**: `kg_preparer.py`, `verify_corpus_integrity.py`.
- **Test Verification**: `T-021`.

#### P0-06: Bịa đặt quan hệ lưu giữ (`CURRENTLY_HELD_BY`) không có bằng chứng văn bản
- **Root Cause**: Crawler defaulted `storage_location` to `"Bảo tàng Lịch sử quốc gia"` whenever metadata was empty, fabricating historical KG edges without textual evidence.
- **Fix**:
  - Eliminated default fallback: `storage_location` is left empty unless explicitly stated in the source text.
  - Required literal evidence quotes (`evidence_quote`) for any `CURRENTLY_HELD_BY` edge.
- **Files Modified**: `vnmh_parser.py`, `kg_preparer.py`, `verify_corpus_integrity.py`.
- **Test Verification**: `T-022`.

---

### 2. P1 High Findings

#### P1-07: Vi phạm SQLite UNIQUE Constraint khi xử lý bài viết bỏ qua ngôn ngữ
- **Root Cause**: Non-target languages (e.g. `/fr/`) were inserted into `crawled_documents` with dummy `doc_id="SKIPPED_LANG"`, causing SQLite `IntegrityError: UNIQUE constraint failed` on the second skipped article.
- **Fix**:
  - Created dedicated queue status `status = 'skipped_lang'` in `crawl_queue`.
  - Added `mark_skipped_language(url, lang)` which updates queue status without inserting dummy rows into `crawled_documents`.
  - Added `requeue_skipped_languages()` to allow re-enabling skipped URLs if configuration expands.
- **Files Modified**: `state_manager.py`, `crawler.py`.
- **Test Verification**: `T-007`.

#### P1-08: Thiếu SSRF Protection và chặn Private IP Range
- **Root Cause**: `fetch_url()` resolved arbitrary hosts without verifying if the IP resolved to loopback, private RFC 1918, or cloud metadata ranges (`169.254.169.254`).
- **Fix**:
  - Added `is_safe_host()` to `BaseSourceAdapter` and `URLNormalizer` checking against `PRIVATE_NETWORKS` (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1/128`).
  - Blocked non-standard ports and credentials in URLs.
- **Files Modified**: `adapters/base.py`, `url_normalizer.py`.
- **Test Verification**: `T-009`.

#### P1-09: Lỗ hổng Redirect Hop Domain Bypass
- **Root Cause**: HTTP redirects followed server `Location` headers automatically without validating whether subsequent hops remained on authorized domains.
- **Fix**:
  - Configured manual redirect resolution (`allow_redirects=False`) verifying domain allowlist and SSRF safety on every hop before requesting.
- **Files Modified**: `adapters/base.py`.
- **Test Verification**: `T-010`.

#### P1-10: Chính sách `robots.txt` Fail-Open khi gặp lỗi mạng
- **Root Cause**: Network timeouts while loading `robots.txt` defaulted to allowed, violating strict crawl permission policies.
- **Fix**:
  - Changed robots policy to fail-closed (`ROBOTS_UNAVAILABLE` defaults to disallowed).
  - Added cache TTL (`self._robots_ttl = 3600.0`) to avoid repeated network failures.
- **Files Modified**: `adapters/base.py`.
- **Test Verification**: `T-011`.

#### P1-11: Ghi đè file raw document khi bài viết cập nhật nội dung
- **Root Cause**: Raw archives were stored at flat `raw_documents/{doc_id}.json`, overwriting historical versions when page content changed.
- **Fix**:
  - Switched storage scheme to immutable hashed path: `raw_documents/{doc_id}/{content_hash}.json`.
  - Implemented atomic writes using temporary files and `os.replace` to prevent partial writes.
- **Files Modified**: `storage.py`.
- **Test Verification**: `T-014`.

#### P1-12: False Positive trong trích xuất chất liệu (English "Materials:" -> "s")
- **Root Cause**: RegEx `Materials?:\s*(\w+)` matched trailing 's' of the word "Materials:" in English templates when no value was present.
- **Fix**:
  - Anchored extraction to label boundaries, requiring value length > 1 and filtering common stop words (`s`, `của`, `tại`).
  - Added `MetadataEvidence` tracking provenance, exact offsets, and extraction method.
- **Files Modified**: `vnmh_parser.py`, `models.py`.
- **Test Verification**: `T-024`, `T-026`.

#### P1-13: Thiếu phân tách hạn ngạch `--max-discovery-pages` và `--max-articles`
- **Root Cause**: Single `--max-pages` flag counted category hub discovery pages and article pages in the same pool, prematurely halting article crawls.
- **Fix**:
  - Added distinct CLI arguments `--max-discovery-pages` (limits category/pagination traversal) and `--max-articles` (limits body downloads).
- **Files Modified**: `crawler.py`, `run_heritage_corpus.py`.
- **Test Verification**: `T-013`.

#### P1-14: Duplicate `summary_abstract` trong `canonical_clean_text`
- **Root Cause**: Parser appended abstract text directly to body text, duplicating intro paragraphs across sections.
- **Fix**:
  - Separated `summary_abstract` into its own isolated field; `canonical_clean_text` contains only verified body leaf blocks.
- **Files Modified**: `vnmh_parser.py`, `models.py`.
- **Test Verification**: `T-015`.

#### P1-15: Chênh lệch độ dài Chunk và vi phạm Hard Token Cap
- **Root Cause**: Chunks had no hard token/character limit enforcement, allowing lengthy scholarly articles to produce outsized chunks.
- **Fix**:
  - Enforced `HARD_CAP_CHARS = 1600` (~400 tokens) with sentence and word-boundary splitting.
- **Files Modified**: `rag_preparer.py`.
- **Test Verification**: `T-017`.

#### P1-16: Bịa đặt trích dẫn (`evidence_quote`) trong KG Edges
- **Root Cause**: Edges contained synthetic explanation strings in `evidence_quote` rather than verbatim source text quotes.
- **Fix**:
  - Separated `evidence_quote` (verbatim substring from source) from `derivation_note` (synthetic explanation).
- **Files Modified**: `kg_preparer.py`, `models.py`.
- **Test Verification**: `T-020`.

#### P1-17: Đoạn code lặp tiêu chí `ARTIFACT_NAME_OVERLAP` trong `legacy_matcher.py`
- **Root Cause**: Duplicate lines in `find_matches()` evaluated and appended the same criterion twice.
- **Fix**:
  - Removed duplicate logic block and cleaned weighted scoring calculation.
- **Files Modified**: `legacy_matcher.py`.
- **Test Verification**: `T-028`.

#### P1-18: Fail Silently khi thiếu file legacy production CSV
- **Root Cause**: If `crawled_artifacts_production.csv` was missing or unreadable, matcher failed silently without diagnostic status.
- **Fix**:
  - Added `self.status = "LEGACY_DATA_UNAVAILABLE"`, logging an explicit warning and cleanly returning an empty list.
- **Files Modified**: `legacy_matcher.py`.
- **Test Verification**: `T-028`.

---

### 3. P2 Medium Findings

#### P2-19: Nhân bản nội dung do duyệt DOM đồng thời thẻ cha và thẻ con
- **Root Cause**: Querying both `<div>` container and its child `<p>` tags concatenated duplicate text blocks.
- **Fix**:
  - Implemented `_extract_leaf_blocks()`: recursively extracts text exclusively from innermost leaf block elements.
- **Files Modified**: `vnmh_parser.py`.
- **Test Verification**: `T-023`.

#### P2-20: False Positive trong trích xuất niên đại (`era_culture = "từ"`)
- **Root Cause**: RegEx matched dangling preposition "từ" in Vietnamese text.
- **Fix**:
  - Added length check >= 4 characters and excluded grammatical prepositions.
- **Files Modified**: `vnmh_parser.py`.
- **Test Verification**: `T-026`.

#### P2-21: Bỏ sót kích thước nhiều dòng (multiline dimensions)
- **Root Cause**: Single-line RegEx truncated multiline dimensions (height, diameter, base).
- **Fix**:
  - Implemented multiline RegEx matching bullet points (`- Chiều cao:...`, `- Đường kính:...`) and cleaned into a cohesive string.
- **Files Modified**: `vnmh_parser.py`.
- **Test Verification**: `T-025`.

#### P2-22: Không có cơ chế Quarantine cho trang rỗng / lỗi parse
- **Root Cause**: Articles with empty body text were saved as normal validated documents.
- **Fix**:
  - Added multi-stage validation: documents with body text < 30 chars are tagged `validation_status = "QUARANTINED"` with explicit `quarantine_reasons`.
- **Files Modified**: `vnmh_parser.py`, `crawler.py`, `models.py`.
- **Test Verification**: `T-027`.

#### P2-23: Thiếu chuẩn hóa Unicode NFC trong đối sánh Legacy
- **Root Cause**: Legacy strings in NFD format failed string equality against NFC crawled strings.
- **Fix**:
  - Applied `unicodedata.normalize('NFC', text)` across all legacy strings and titles.
- **Files Modified**: `legacy_matcher.py`.
- **Test Verification**: `T-028`.

#### P2-24: Dry-run không cô lập hoàn toàn các side-effects ghi đĩa
- **Root Cause**: Running with `--dry-run` still fetched article bodies and updated SQLite queue state.
- **Fix**:
  - Enforced true dry-run: strictly explores categories, paginations, and sitemaps; zero body downloads; zero file writes.
- **Files Modified**: `crawler.py`, `run_heritage_corpus.py`.
- **Test Verification**: `T-012`.

#### P2-25: Source Registry thiếu adapter Wikimedia Commons và trạng thái STAGED
- **Root Cause**: Unimplemented sources were listed as active in the registry.
- **Fix**:
  - Explicitly marked VNMH as `OPERATIONAL` and external adapters (DCH, UNESCO, Wikidata, Scholarly) as `STAGED_NOT_IMPLEMENTED`.
  - Added COMMONS configuration with staged adapter.
- **Files Modified**: `source_registry.py`, `adapters/commons.py`.
- **Test Verification**: Inspection & registry test.
