# Corpus Quality Report: Metric Definitions & Mathematical Formulas (V2)

**Document Reference**: `QUALITY_REPORT_EXPLAINED.md`  
**Report Artifact**: `scraper/heritage_corpus/data/quality_report.json`  
**Target Schema**: `QualityReport` (Schema V2)  

---

## 1. Overview & Quality Objectives

`QualityReport` V2 provides an auditable, automated health assessment of the Vietnamese Cultural Heritage Evidence Corpus. Unlike naive crawler summaries that only count HTTP 200 responses, QualityReport V2 audits **referential integrity, character-exact span alignments, epistemic provenance, and token compliance**.

---

## 2. Core Metrics & Mathematical Formulations

### 2.1. Foreign Key Integrity Rate (`fk_integrity_metrics`)
Audits referential completeness across documents, sections, mentions, and candidate edges:

$$\text{FK Integrity Rate} = \frac{N_{\text{valid\_doc\_fks}} + N_{\text{valid\_mention\_fks}} + N_{\text{valid\_edge\_fks}}}{N_{\text{sections}} + N_{\text{mentions}} + N_{\text{edges}}} \times 100\%$$

- **Target Threshold**: **Strictly 100.0%** (Gate G1).
- **Failure Condition**: Any mention or edge pointing to a non-existent `section_id` fails the integrity gate.

### 2.2. Section Exact Substring Span Accuracy (`span_accuracy_metrics`)
Validates the RAG evidence invariant by verifying that every character slice extracts the exact chunk text:

$$\text{Section Span Accuracy} = \frac{\sum_{i=1}^{N_{\text{sec}}} \mathbb{I}(\text{source\_text}[s_i:e_i] == t_i)}{N_{\text{sec}}} \times 100\%$$

- **Target Threshold**: **Strictly 100.0%** (Gate G2).
- **Source Ground Truth**: Evaluated against `canonical_clean_text` (or `summary_abstract` if indicated by `offset_source`).

### 2.3. Mention Exact Substring Span Accuracy
Verifies that entity mentions accurately point to their verbatim occurrences in source text:

$$\text{Mention Span Accuracy} = \frac{\sum_{j=1}^{N_{\text{mnt}}} \mathbb{I}(\text{source\_text}[s_j:e_j] == m_j)}{N_{\text{mnt}}} \times 100\%$$

- **Target Threshold**: **Strictly 100.0%**.

### 2.4. KG Literal Quote Accuracy Rate
Guarantees that candidate relations are grounded in explicit source sentences rather than synthetic LLM text:

$$\text{Quote Accuracy Rate} = \frac{\sum_{k=1}^{N_{\text{edges}}} \mathbb{I}(q_k \subseteq \text{section\_text}_k)}{N_{\text{edges}}} \times 100\%$$

- **Target Threshold**: **Strictly 100.0%** (Gate G3).

### 2.5. Token Cap Compliance Rate (`token_cap_compliance_metrics`)
Ensures no single section exceeds the hard limit for vector embedding or context windows:

$$\text{Compliance Rate} = \frac{N_{\text{sections}} - N_{\text{violations}}}{N_{\text{sections}}} \times 100\%$$

- **Hard Limit**: $2500$ characters (~$625$ tokens).
- **Soft Target**: $\le 1600$ characters (~$400$ tokens).
- **Target Threshold**: **100.0% compliance (0 violations)**.

---

## 3. Metadata Validity Breakdown

For every extracted field, QualityReport V2 measures both **Presence Rate** and **Validity Rate**:

- **Presence Rate**: $\frac{N_{\text{present}}}{N_{\text{total\_docs}}} \times 100\%$
- **Validity Rate**: $\frac{N_{\text{valid}}}{N_{\text{present}}} \times 100\%$

Validation rules enforced:
- `material`: Must not equal `"s"`, stop words, or single characters.
- `era_culture`: Must not equal `"từ"` or prepositions.
- `registration_number`: Must follow museum accession formats (`LSb`, `LSa`, numeric).
- `dimensions`: Must contain valid measurement units (`cm`, `mm`, `m`, `cao`, `đk`).

---

## 4. Sample Quality Report JSON (V2 Verified)

```json
{
  "generated_at": "2026-11-09T19:16:30Z",
  "corpus_version": "2.0.0",
  "schema_version": "2.0.0",
  "total_logical_documents": 5,
  "language_distribution": {
    "vi": 3,
    "en": 2
  },
  "classification_breakdown": {
    "ARTIFACT_PROFILE": 4,
    "RESEARCH_ARTICLE": 1
  },
  "validation_status_breakdown": {
    "VALIDATED": 5
  },
  "field_presence_rates": {
    "registration_number": 60.0,
    "material": 60.0,
    "dimensions": 60.0,
    "era_culture": 60.0,
    "storage_location": 20.0,
    "published_at": 100.0
  },
  "field_validity_rates": {
    "registration_number": 100.0,
    "material": 100.0,
    "dimensions": 100.0,
    "era_culture": 100.0,
    "storage_location": 100.0,
    "published_at": 100.0
  },
  "fk_integrity_metrics": {
    "total_sections": 10,
    "sections_with_valid_doc_fk": 10,
    "total_mentions": 4,
    "mentions_with_valid_section_fk": 4,
    "total_edges": 1,
    "edges_with_valid_section_fk": 1,
    "fk_integrity_pct": 100.0
  },
  "span_accuracy_metrics": {
    "total_section_spans": 10,
    "section_span_matches": 10,
    "section_span_accuracy_pct": 100.0,
    "total_mention_spans": 4,
    "mention_span_matches": 4,
    "mention_span_accuracy_pct": 100.0,
    "total_edge_quotes": 1,
    "edge_quote_matches": 1,
    "edge_quote_accuracy_pct": 100.0
  },
  "token_cap_compliance_metrics": {
    "total_sections": 10,
    "sections_under_hard_cap": 10,
    "max_char_len": 1582,
    "max_token_len": 395,
    "hard_char_limit": 2500,
    "violations_count": 0,
    "compliance_pct": 100.0
  },
  "media_count": 12,
  "section_count": 10,
  "kg_edge_count": 1,
  "legacy_match_candidate_count": 0,
  "failure_count": 0,
  "quarantine_count": 0
}
```
