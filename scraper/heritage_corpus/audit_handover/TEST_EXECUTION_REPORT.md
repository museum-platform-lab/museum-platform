# Automated Test Execution Report (Schema V2)

**Document Reference**: `TEST_EXECUTION_REPORT.md`  
**Execution Timestamp**: `2026-11-09T19:16:43Z`  
**Test Suite**: `run_all_tests.py`  
**Platform**: Windows 11 x64, Python 3.13  
**Verdict**: **PASS (100.0% Pass Rate)**  

---

## 1. Executive Summary

| Metric | Target | Actual Result | Status |
| :--- | :---: | :---: | :---: |
| **Total Test Cases** | 28 | **28** | Complete |
| **Passed Tests** | 28 | **28** | **100% Pass** |
| **Failed Tests** | 0 | **0** | Zero Regressions |
| **Total Execution Time** | < 10.0s | **0.923 seconds** | High Performance |
| **Acceptance Gates Passed** | 6 / 6 | **6 / 6 (G1..G6)** | **PASSED** |

---

## 2. Test Execution Details (T-001 to T-028)

| Test ID | Category | Test Description | Duration | Status |
| :---: | :--- | :--- | :---: | :---: |
| **T-001** | Reliability | 429 response with Retry-After integer delay | 1 ms | **PASSED** |
| **T-002** | Reliability | 429 response with Retry-After HTTP-date format | 1 ms | **PASSED** |
| **T-003** | Reliability | Network crash and resume recovery of stale queue items | 14 ms | **PASSED** |
| **T-004** | Concurrency | Atomic claim with BEGIN IMMEDIATE transaction isolation | 18 ms | **PASSED** |
| **T-005** | Concurrency | Worker lease expiry and stale worker recovery | 12 ms | **PASSED** |
| **T-006** | Reliability | Exponential backoff calculation and dead-letter capping | 15 ms | **PASSED** |
| **T-007** | Safety | Skipped language queue status without dummy crawled_documents insert | 12 ms | **PASSED** |
| **T-008** | Extraction | Canonical URL normalization and duplicate rejection | 2 ms | **PASSED** |
| **T-009** | Safety | SSRF protection and private IP blocking | 2 ms | **PASSED** |
| **T-010** | Safety | Redirect hop domain validation (external domain rejection) | 1 ms | **PASSED** |
| **T-011** | Safety | Fail-safe robots.txt policy on network error | 1 ms | **PASSED** |
| **T-012** | Safety | True dry-run isolation (zero body fetch, zero disk writes) | 48 ms | **PASSED** |
| **T-013** | Reliability | Separate quotas enforcement (max_discovery_pages vs max_articles) | 9 ms | **PASSED** |
| **T-014** | Safety | Immutable raw document writing with atomic temp file rename | 4 ms | **PASSED** |
| **T-015** | RAG | Exact substring slicing invariant for RAG sections | 3 ms | **PASSED** |
| **T-016** | RAG | Sentence and word boundary chunk splitting without truncation | 5 ms | **PASSED** |
| **T-017** | RAG | Token and hard character cap enforcement | 3 ms | **PASSED** |
| **T-018** | RAG | Stable section ID format {doc_id}-SEC-{idx:03d} | 2 ms | **PASSED** |
| **T-019** | KG | Section FK resolvability in KG candidate edges | 4 ms | **PASSED** |
| **T-020** | KG | Exact literal quote verification in KG candidate edges | 4 ms | **PASSED** |
| **T-021** | KG | Ontological separation: article author maps to AUTHORED_BY document | 3 ms | **PASSED** |
| **T-022** | KG | Zero custody fabrication without explicit in-text custody evidence | 3 ms | **PASSED** |
| **T-023** | Extraction | Leaf-block DOM extraction without text duplication | 2 ms | **PASSED** |
| **T-024** | Extraction | Anchored metadata label extraction with MetadataEvidence | 2 ms | **PASSED** |
| **T-025** | Extraction | Multiline dimensions parsing | 2 ms | **PASSED** |
| **T-026** | Extraction | Material & Era false positive rejection (no 's' or 'từ') | 2 ms | **PASSED** |
| **T-027** | Extraction | Parse quarantine for empty or missing article body | 2 ms | **PASSED** |
| **T-028** | Legacy | Legacy matcher missing CSV handling and Unicode NFC normalization | 2 ms | **PASSED** |

---

## 3. Machine-Readable Evidence Files

- **JSON Summary**: [`audit_handover/evidence/test-results.json`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/test-results.json)
- **JUnit XML Report**: [`audit_handover/evidence/test-results.xml`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/test-results.xml)
