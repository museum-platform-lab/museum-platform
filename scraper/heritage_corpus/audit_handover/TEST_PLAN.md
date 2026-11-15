# Comprehensive Quality Assurance Test Plan (T-001 to T-028)

**Document Reference**: `TEST_PLAN.md`  
**Test Suite**: `run_all_tests.py`  
**Execution Target**: 28 Automated Unit & Integration Tests  
**Target Pass Rate**: 100% (28/28 Passing)  

---

## 1. Test Objectives & Quality Gates

This test plan exercises all functional, reliability, security, and data integrity requirements established in `02_PROMPT_SUA_CODE_CRAWLER_VA_BAN_GIAO.docx`. It maps every test case to one of the six formal acceptance gates:

| Gate | Focus Area | Acceptance Invariant | Test Coverage |
| :---: | :--- | :--- | :--- |
| **G1** | Foreign Key & Referential Integrity | 100% of mentions and KG edges reference existing section IDs | T-018, T-019, T-028 |
| **G2** | RAG Substring Slicing & Token Cap | Exact substring match `ref_text[start:end] == chunk_text` | T-015, T-016, T-017, T-023..T-027 |
| **G3** | Knowledge Graph Grounding & Ontology | Zero author-as-maker, zero ungrounded custody, verbatim quotes | T-020, T-021, T-022 |
| **G4** | Concurrency, State Machine & Retries | Atomic claims, worker lease expiry, scheduled backoff | T-001..T-006, T-013 |
| **G5** | Network Safety, SSRF & Policy | Chained redirect check, fail-closed robots, pure dry-run | T-007, T-009, T-010, T-011, T-012 |
| **G6** | Raw Archive Immutability & Replay | Atomic file replacement, immutable content hashed paths | T-014, verify_corpus |

---

## 2. Test Execution Matrix (T-001 to T-028)

| Test ID | Category | Target Module | Test Scenario & Verification Criteria | Gate |
| :---: | :--- | :--- | :--- | :---: |
| **T-001** | Reliability | `adapters/base.py` | Verify integer `Retry-After: 120` parses to exact seconds | G4 |
| **T-002** | Reliability | `adapters/base.py` | Verify RFC 1123 HTTP-date `Retry-After` calculates correct remaining seconds | G4 |
| **T-003** | Reliability | `state_manager.py` | Verify crashed worker items with expired lease reset to queued upon recovery | G4 |
| **T-004** | Concurrency | `state_manager.py` | Verify atomic queue claim under `BEGIN IMMEDIATE` prevents double claims | G4 |
| **T-005** | Concurrency | `state_manager.py` | Verify worker lease expiry recovers stale URLs safely | G4 |
| **T-006** | Reliability | `state_manager.py` | Verify exponential backoff increases retry intervals and caps at dead-letter | G4 |
| **T-007** | Safety | `state_manager.py` | Verify skipped languages set `skipped_lang` without dummy table inserts | G5 |
| **T-008** | Extraction | `url_normalizer.py` | Verify canonical normalization strips tracking params, fragments, and port 80 | G2 |
| **T-009** | Safety | `url_normalizer.py` | Verify SSRF defense blocks loopback, 10.x, 192.168.x, and AWS 169.254.x | G5 |
| **T-010** | Safety | `adapters/base.py` | Verify redirect hop validation rejects off-domain redirect destinations | G5 |
| **T-011** | Safety | `adapters/base.py` | Verify fail-closed robots policy blocks crawling on network timeout | G5 |
| **T-012** | Safety | `crawler.py` | Verify true dry-run performs discovery only with zero disk side-effects | G5 |
| **T-013** | Reliability | `crawler.py` | Verify distinct enforcement of `max_discovery_pages` vs `max_articles` | G4 |
| **T-014** | Safety | `storage.py` | Verify atomic write with temporary file renaming prevents partial raw archives | G6 |
| **T-015** | RAG | `rag_preparer.py` | Verify 100% exact substring equality between chunk and source text | G2 |
| **T-016** | RAG | `rag_preparer.py` | Verify chunk boundary splitting on sentence/word boundaries without truncation | G2 |
| **T-017** | RAG | `rag_preparer.py` | Verify hard token and character cap (`HARD_CAP_CHARS = 1600`) | G2 |
| **T-018** | RAG | `rag_preparer.py` | Verify stable section ID generation format: `{doc_id}-SEC-{idx:03d}` | G1 |
| **T-019** | KG | `kg_preparer.py` | Verify 100% of candidate edge section FKs resolve to existing sections | G1 |
| **T-020** | KG | `kg_preparer.py` | Verify candidate edge `evidence_quote` is a literal verbatim excerpt of text | G3 |
| **T-021** | KG | `kg_preparer.py` | Verify article author maps to `AUTHORED_BY` document and NEVER `CREATED_BY` | G3 |
| **T-022** | KG | `kg_preparer.py` | Verify zero custody fabrication: `CURRENTLY_HELD_BY` emitted only with text | G3 |
| **T-023** | Extraction | `vnmh_parser.py` | Verify leaf-block DOM traversal eliminates ancestor-descendant duplication | G2 |
| **T-024** | Extraction | `vnmh_parser.py` | Verify anchored metadata label extraction produces valid `MetadataEvidence` | G2 |
| **T-025** | Extraction | `vnmh_parser.py` | Verify multiline dimensions extraction captures height, mouth, and base | G2 |
| **T-026** | Extraction | `vnmh_parser.py` | Verify false positive rejection (filters material `'s'` and era `'từ'`) | G2 |
| **T-027** | Extraction | `vnmh_parser.py` | Verify empty or deficient article bodies trigger parse quarantine | G2 |
| **T-028** | Legacy | `legacy_matcher.py` | Verify missing CSV resilience (`LEGACY_DATA_UNAVAILABLE`) and Unicode NFC | G1 |

---

## 3. Test Runner Architecture

The test suite runs via a dedicated runner `run_all_tests.py` using Python 3.13 standard libraries. It automatically outputs:
- **Human-readable console report** with per-test duration and status.
- **Machine-readable JSON report**: `audit_handover/evidence/test-results.json`.
- **Standard JUnit XML format**: `audit_handover/evidence/test-results.xml` (for CI/CD consumption).
