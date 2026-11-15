# Museum Platform - Heritage Evidence Corpus Handover Index (Schema V2)

**Project**: Vietnamese Cultural Heritage Evidence Corpus  
**Version**: `2.0.0` (Schema V2)  
**Handover Date**: `2026-11-09`  
**Audit Finding Resolution**: **100% (25 / 25 Issues Resolved)**  
**Automated Tests**: **100% Passing (28 / 28 Tests Passed)**  
**Corpus Quality Gates**: **100% Passing across all Acceptance Gates (G1..G6)**  
**Release Recommendation**: **GO (Ready for Staging & Production Pilot)**  

---

## 1. Acceptance Gates Verification Matrix

| Gate | Focus Area | Required Criterion | Actual Measured Result | Status |
| :---: | :--- | :--- | :--- | :---: |
| **G1** | Referential & FK Integrity | 100% of mentions and edges resolve to existing sections | **100.0% Valid Foreign Keys** | **PASS** |
| **G2** | RAG Exact Slicing Invariant | `source_text[start:end] == section_text` (100% exact equality) | **100.0% Exact Substring Matches** | **PASS** |
| **G3** | Knowledge Graph Grounding | 0 author-as-maker, 0 ungrounded custody, 100% literal quotes | **0 Violations, 100.0% Literal Quotes** | **PASS** |
| **G4** | Concurrency & State Machine | Atomic claims, worker lease recovery, RFC `Retry-After` backoff | **100% Passing (T-001..T-006)** | **PASS** |
| **G5** | Network Safety & Legal Scope | SSRF blocking, hop validation, fail-closed robots, pure dry-run | **100% Passing (T-007..T-013)** | **PASS** |
| **G6** | Immutability & Replayability | Immutable raw storage, atomic writes, offline local replay | **100% Passing (T-014, verify_corpus)** | **PASS** |

---

## 2. Handover Documentation Directory

All documentation is located in [`scraper/heritage_corpus/audit_handover/`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/):

1. [`CHANGELOG_FIXES.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/CHANGELOG_FIXES.md): Comprehensive changelog mapping all 25 audit issues (P0-01 to P2-25) to exact code modifications.
2. [`ISSUE_TRACEABILITY.csv`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/ISSUE_TRACEABILITY.csv): Full traceability matrix covering Issue ID, Severity, Root Cause, Files Modified, Unit Tests, and Gate Status.
3. [`ARCHITECTURE_AFTER_FIX.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/ARCHITECTURE_AFTER_FIX.md): Complete architecture manual detailing multi-stage pipeline, DOM leaf parsing, and storage.
4. [`SCHEMA_V2.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/SCHEMA_V2.md): Schema V2 specification (Dataclasses, JSONL structures, and SQLite DDL).
5. [`MIGRATION_AND_ROLLBACK.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/MIGRATION_AND_ROLLBACK.md): Step-by-step procedures for database migration, dry-run checks, and rollback.
6. [`TEST_PLAN.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/TEST_PLAN.md): Comprehensive QA test plan and coverage matrix (T-001 to T-028).
7. [`TEST_EXECUTION_REPORT.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/TEST_EXECUTION_REPORT.md): Detailed automated test run report (28/28 Passed in 0.923s).
8. [`REPROCESS_REPORT.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/REPROCESS_REPORT.md): Fixture reprocessing report with before-vs-after metric improvements.
9. [`QUALITY_REPORT_EXPLAINED.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/QUALITY_REPORT_EXPLAINED.md): Mathematical definitions and formulas for all QualityReport V2 metrics.
10. [`SECURITY_AND_RIGHTS_REVIEW.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/SECURITY_AND_RIGHTS_REVIEW.md): Audit of robots policies, SSRF blocking, hop domain verification, and copyright terms.
11. [`OPERATIONS_RUNBOOK.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/OPERATIONS_RUNBOOK.md): Production CLI operational guide, discovery, pilot, scaling, and recovery.
12. [`HANDOVER_INDEX.md`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/HANDOVER_INDEX.md): Master sign-off index and release checklist.

---

## 3. Auditable Evidence Files

All verification logs and machine-readable evidence are filed in [`scraper/heritage_corpus/audit_handover/evidence/`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/):

- [`baseline_file_hashes.sha256`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/baseline_file_hashes.sha256): SHA-256 baseline lock before any code changes.
- [`fixture_manifest.json`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/fixture_manifest.json): Inventory of the 5 gold regression fixtures.
- [`reprocess-before-after.csv`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/reprocess-before-after.csv): Side-by-side metric comparison (Span match: 12.5% -> 100%, FK: 0% -> 100%).
- [`qa-integrity-report.json`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/qa-integrity-report.json): Complete offline QA verification report confirming zero defects.
- [`test-results.json`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/test-results.json): Machine-readable execution results for 28 automated tests.
- [`test-results.xml`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/test-results.xml): Standard JUnit XML report for CI/CD ingestion.
- [`migration-dry-run.log`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/migration-dry-run.log): Log verifying non-destructive V1 -> V2 schema migration.
- [`migration-rollback.log`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/migration-rollback.log): Log verifying clean V2 -> V1 schema rollback.
- [`offline-replay.log`](file:///d:/project/museum-platform/scraper/heritage_corpus/audit_handover/evidence/offline-replay.log): Full terminal output from offline replay command (`--reprocess-local`).

---

## 4. Production Dataset Integrity Notice

The production dataset [`crawled_artifacts_production.csv`](file:///d:/project/museum-platform/scraper/crawled_artifacts_production.csv) remains **100% pristine and unaltered**:
- **Verified SHA-256**: `44416c559675be23fb0fce91e12f1fff542bccac553dc1a26e5875843e466c90`
- **Record Count**: Exactly 6,254 rows.
- **Access Pattern**: Read-only via `LegacyMatcher`.

---

## 5. Formal Release Recommendation

**Verdict**: **GO**  
All 25 audit findings (P0-01 to P2-25) are systematically resolved. All 28 automated tests (T-001 to T-028) and all 6 Acceptance Gates (G1 to G6) pass with zero errors. The system is certified ready for production deployment and staged heritage evidence collection.
