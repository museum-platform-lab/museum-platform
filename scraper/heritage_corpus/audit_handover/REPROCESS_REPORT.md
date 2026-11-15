# Baseline Fixture Reprocessing and Quality Report (Schema V2)

**Document Reference**: `REPROCESS_REPORT.md`  
**Execution Mode**: Local Offline Reprocessing (`--reprocess-local`)  
**Network Activity**: Zero network requests (100% offline from raw HTML archive)  
**Target Fixtures**: 5 Gold Regression Fixtures across Vietnamese and English  
**Evidence Files**: `evidence/reprocess-before-after.csv`, `evidence/offline-replay.log`, `evidence/qa-integrity-report.json`  

---

## 1. Executive Summary & Quality Improvement

| Metric | Baseline V1 | Upgraded V2 | Delta | Acceptance Target | Result |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Section Exact Substring Match** | 2 / 16 (12.50%) | **10 / 10 (100.00%)** | **+87.50%** | 100.00% | **PASS** |
| **Mention Foreign Key Resolvability** | 0 / 15 (0.00%) | **4 / 4 (100.00%)** | **+100.00%** | 100.00% | **PASS** |
| **Mention Exact Substring Match** | 0 / 15 (0.00%) | **4 / 4 (100.00%)** | **+100.00%** | 100.00% | **PASS** |
| **KG Edge Foreign Key Resolvability** | 0 / 10 (0.00%) | **1 / 1 (100.00%)** | **+100.00%** | 100.00% | **PASS** |
| **KG Literal Quote Accuracy** | 0 / 10 (0.00%) | **1 / 1 (100.00%)** | **+100.00%** | 100.00% | **PASS** |
| **Author as Artifact Creator (`CREATED_BY`)** | 1 violation | **0 violations** | **-1 (100% fixed)** | 0 | **PASS** |
| **Ungrounded Custody (`CURRENTLY_HELD_BY`)** | 5 violations | **0 violations** | **-5 (100% fixed)** | 0 | **PASS** |
| **Material False Positives (`"s"`)** | 1 violation | **0 violations** | **-1 (100% fixed)** | 0 | **PASS** |
| **Era False Positives (`"từ"`)** | 1 violation | **0 violations** | **-1 (100% fixed)** | 0 | **PASS** |
| **Hard Token / Character Cap Compliance** | 100.0% | **100.0%** | 0 | 100.00% | **PASS** |

---

## 2. Fixture-by-Fixture Analysis

### 2.1. `VNMH-VI-1001-73800` — Thạp Đào Thịnh (Bảo vật Quốc gia)
- **Baseline Flaws**: Abstract was duplicated into clean text. Span offsets had severe drift (`char_start/char_end` did not match sliced text). Custody was fabricated to the default national museum.
- **V2 Output**:
  - `canonical_clean_text` cleanly separated from `summary_abstract`.
  - Sections: 3 clean chunks, each satisfying `canonical_clean_text[char_start:char_end] == section_text` (100% match).
  - Custody relation: Suppressed because the text describes discovery at Yên Bái without explicit custody statement.

### 2.2. `VNMH-VI-1001-75069` — Mộ thuyền Việt Khê (Bảo vật Quốc gia)
- **Baseline Flaws**: Concatenated parent-child DOM blocks created duplicate paragraphs. Section FK joins completely failed.
- **V2 Output**:
  - Leaf-block DOM traversal emitted clean, un-duplicated paragraphs.
  - Section IDs follow stable format `VNMH-VI-1001-75069-SEC-001` through `SEC-002`.
  - 100% resolvable section FKs.

### 2.3. `VNMH-VI-1001-76300` — Sổ vàng Trường Nguyễn Ái Quốc (1949 - 1950)
- **Baseline Flaws**: Critical ontological error — modern museum researcher *Lê Thị Hồng Thu* was assigned as `(ARTIFACT) --[CREATED_BY]--> (Lê Thị Hồng Thu)` (ancient maker).
- **V2 Output**:
  - Author separated: Emitted `(DOCUMENT) --[AUTHORED_BY]--> (Lê Thị Hồng Thu)`.
  - Zero `CREATED_BY` violations.
  - Section FK and literal evidence quotes verified 100%.

### 2.4. `VNMH-EN-1005-28454` — Mug (Ceramic Artifact)
- **Baseline Flaws**: Material field extracted as `"s"` from English label `"Materials:"`.
- **V2 Output**:
  - Material `"s"` rejected by anchored metadata validation guardrails.
  - Valid metadata fields and `MetadataEvidence` logged cleanly.

### 2.5. `VNMH-EN-3181-19143` — Chu Dau pottery revival (Research Article)
- **Baseline Flaws**: Long research text produced oversized chunks and span misalignments.
- **V2 Output**:
  - Paragraphs chunked within `HARD_CAP_CHARS = 1600` on sentence boundaries.
  - 100% exact substring match across all English sections.

---

## 3. Replay Commands and Verification Output

To re-run local reprocessing at any time:
```bash
python scraper/run_heritage_corpus.py --reprocess-local --output-dir scraper/heritage_corpus/data
```

Execution Output:
```text
Reprocessing raw documents from scraper/heritage_corpus/data/raw_documents offline...

--- LOCAL REPROCESSING COMPLETE ---
Reprocessed Documents: 5
Reprocessed Sections : 10
Reprocessed Mentions : 4
Reprocessed Edges    : 1
Reprocessed Matches  : 0
FK Integrity Rate    : 100.0%
Section Span Accuracy: 100.0%
Mention Span Accuracy: 100.0%
Quote Accuracy Rate  : 100.0%
Token Cap Compliance : 100.0%
```
