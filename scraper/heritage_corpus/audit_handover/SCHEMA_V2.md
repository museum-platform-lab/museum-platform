# Heritage Evidence Corpus: Schema V2 Specification

**Document Reference**: `SCHEMA_V2.md`  
**Schema Version**: `2.0.0`  
**Migration Path**: `Schema V1 -> Schema V2` (backward compatible, zero data loss)  

---

## 1. Schema Evolution Summary

| Dimension | Schema V1 (Baseline) | Schema V2 (Hardened) | Problem Solved |
| :--- | :--- | :--- | :--- |
| **Section IDs** | `{doc_id}-CHK-{idx:03d}` | `{doc_id}-SEC-{idx:03d}` | Fixed 100% foreign key join failure with KG candidate edges |
| **Span Offsets** | Ambiguous string source | Explicit `offset_source` + exact substring slice | Eliminated character drift caused by abstract concatenation |
| **Metadata Tracking** | Flat dictionary of raw strings | `MetadataEvidence` dataclass with verbatim quote & offsets | Grounded field verification, eliminating false positives |
| **Raw Storage** | Flat `{doc_id}.json` | Immutable `{doc_id}/{content_hash}.json` | Prevented payload loss when article content updates |
| **KG Citations** | Synthetic paraphrase string | Verbatim substring quote (`evidence_quote`) + `derivation_note` | Resolved ungrounded citation fabrications |
| **State Machine** | Non-atomic claim, no retry scheduling | Atomic claim, worker lease, UTC `next_retry_at`, `url_aliases` | Eliminated race conditions, premature retries, and alias collisions |

---

## 2. Core Dataclass Specifications

### 2.1. `MetadataEvidence`
Tracks character-level provenance for extracted metadata properties:
```python
@dataclass
class MetadataEvidence:
    field_name: str                  # e.g., "registration_number", "material", "dimensions"
    value: Any                       # Extracted and validated value
    raw_evidence_quote: str          # Verbatim excerpt from DOM label and text
    char_start: int                  # Start offset within offset_source
    char_end: int                    # End offset within offset_source
    offset_source: str = "canonical_clean_text"
    extraction_method: str = "ANCHORED_LABEL_REGEX"  # ANCHORED_LABEL_REGEX, ANCHORED_LABEL_MULTILINE, DOM_LEAF
    confidence: float = 1.0
    validation_status: str = "VALIDATED"             # VALIDATED, UNCERTAIN, INVALID
```

### 2.2. `ParsedDocument`
Primary logical document representation:
```python
@dataclass
class ParsedDocument:
    doc_id: str                      # Format: VNMH-{LANG}-{CAT_ID}-{ARTICLE_ID}
    source_id: str                   # "VNMH"
    canonical_url: str               # Normalized HTTPS canonical URL
    original_url: str                # Raw requested URL
    language: str                    # "vi" or "en"
    title: str                       # Article title (stripped of generic CMS prefixes)
    canonical_clean_text: str        # Verified leaf-node body text (RAG ground truth)
    author: Optional[str] = None     # Article author / journalist (NOT artifact maker)
    published_at: Optional[str] = None   # ISO 8601 UTC timestamp
    updated_at: Optional[str] = None
    view_count: Optional[int] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    breadcrumbs: List[str] = field(default_factory=list)
    summary_abstract: str = ""       # Standalone abstract (isolated from body)
    content_text: str = ""           # Backward-compatible alias for canonical_clean_text
    classification: str = "UNKNOWN"  # ARTIFACT_PROFILE, RESEARCH_ARTICLE, GENERAL_HERITAGE
    metadata_fields: Dict[str, Any] = field(default_factory=dict)
    metadata_evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    heading_hierarchy: List[Dict[str, Any]] = field(default_factory=list)
    content_hash: str = ""           # SHA-256 of raw HTML
    retrieved_at: str = ""           # ISO 8601 UTC timestamp of fetch
    parser_version: str = "vnmh_v2"
    schema_version: str = "2.0.0"
    validation_status: str = "VALIDATED"  # VALIDATED, QUARANTINED, PARSE_FAILED
    quarantine_reasons: List[str] = field(default_factory=list)
    copyright_status: str = "RESERVED_CITATION_PERMITTED"
    reuse_terms: str = "Scholarly citation with provenance attribution"
```

### 2.3. `DocumentSection` (RAG Evidence Chunk)
Section-aware chunking with character-exact evidence invariant:
```python
@dataclass
class DocumentSection:
    section_id: str                  # Format: {doc_id}-SEC-{idx:03d} (FK Anchor)
    doc_id: str                      # FK -> ParsedDocument.doc_id
    source_id: str                   # "VNMH"
    heading_path: List[str]          # Hierarchical breadcrumb path [H1, H2, ...]
    heading_level: int               # 1, 2, 3...
    section_text: str                # Exact chunk text
    offset_source: str               # "canonical_clean_text" or "summary_abstract"
    char_start: int                  # 0-indexed start offset
    char_end: int                    # 0-indexed end offset
    language: str                    # "vi" or "en"
    parent_section_id: Optional[str] = None
    token_count: int = 0             # Character-estimated token count (len // 4)
    temporal_context: Optional[str] = None
    source_attribution: str = "Bảo tàng Lịch sử quốc gia"
    corpus_version: str = "2.0.0"
    schema_version: str = "2.0.0"
    index_eligibility: bool = True   # False if quarantined
    ineligibility_reason: Optional[str] = None
```

### 2.4. `EntityMention`
Mention-level annotations for NER and entity discovery:
```python
@dataclass
class EntityMention:
    mention_id: str                  # Format: {doc_id}-MNT-{idx:03d}
    doc_id: str                      # FK -> ParsedDocument.doc_id
    section_id: str                  # FK -> DocumentSection.section_id (MUST exist)
    entity_type: str                 # ARTIFACT, PERSON, EVENT, CULTURE, PERIOD, LOCATION, INSTITUTION
    mention_text: str                # Exact substring from offset_source
    normalized_name: str             # Normalized canonical entity label
    offset_source: str = "canonical_clean_text"
    char_start: int = 0              # Start offset within offset_source
    char_end: int = 0                # End offset within offset_source
    confidence: float = 1.0
    provenance: str = "DOM_LEAF"
```

### 2.5. `KGCandidateEdge`
Candidate Knowledge Graph relations with epistemic and review status:
```python
@dataclass
class KGCandidateEdge:
    edge_id: str                     # Format: {doc_id}-EDG-{idx:03d}
    source_entity: str               # Subject URI or stable name
    source_entity_type: str          # ARTIFACT, DOCUMENT, PERSON, CULTURE...
    target_entity: str               # Object URI or stable name
    target_entity_type: str          # PERSON, PERIOD, CULTURE, INSTITUTION, LOCATION...
    relation_type: str               # AUTHORED_BY, CREATED_BY, CURRENTLY_HELD_BY,
                                     # ASSOCIATED_WITH_CULTURE, BELONGS_TO_PERIOD,
                                     # DISCOVERED_AT, PART_OF_COLLECTION, EXHIBITED_AT, LOCATED_IN
    epistemic_status: str            # ASSERTED, DERIVED, HYPOTHESIZED
    review_status: str = "PENDING_REVIEW"
    provenance_doc_id: str = ""      # FK -> ParsedDocument.doc_id
    provenance_section_id: str = ""  # FK -> DocumentSection.section_id (MUST exist)
    evidence_quote: str = ""         # Literal verbatim excerpt from section_text
    derivation_note: Optional[str] = None  # Synthetic explanation note (isolated from quote)
    confidence: float = 1.0
```

---

## 3. SQLite Database Schema DDL (Schema V2)

```sql
PRAGMA user_version = 2;
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Crawl Queue Table with Worker Leasing and Retry Backoff
CREATE TABLE IF NOT EXISTS crawl_queue (
    url TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    page_type TEXT NOT NULL,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued',       -- 'queued', 'processing', 'completed', 'failed', 'skipped_lang', 'quarantined'
    worker_id TEXT,                     -- Current claiming worker
    claimed_at TIMESTAMP,               -- Timestamp when worker claimed URL
    lease_expires_at TIMESTAMP,         -- Timestamp when worker lease expires
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMP,            -- Earliest time this URL can be retried
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crawled Documents Table
CREATE TABLE IF NOT EXISTS crawled_documents (
    doc_id TEXT PRIMARY KEY,
    canonical_url TEXT UNIQUE NOT NULL,
    source_id TEXT NOT NULL,
    language TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    http_status INTEGER,
    version INTEGER DEFAULT 1,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Multi-URL Alias Tracking Table
CREATE TABLE IF NOT EXISTS url_aliases (
    alias_url TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES crawled_documents(doc_id) ON DELETE CASCADE
);

-- Failure Ledger Table
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

-- Performance and Concurrency Indices
CREATE INDEX IF NOT EXISTS idx_queue_status_retry 
    ON crawl_queue(status, next_retry_at, priority DESC, depth ASC);
CREATE INDEX IF NOT EXISTS idx_docs_source 
    ON crawled_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_docs_canon_url 
    ON crawled_documents(canonical_url);
CREATE INDEX IF NOT EXISTS idx_failures_url 
    ON crawl_failures(url);
CREATE INDEX IF NOT EXISTS idx_aliases_doc 
    ON url_aliases(doc_id);
```
