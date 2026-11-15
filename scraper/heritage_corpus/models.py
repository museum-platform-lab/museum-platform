"""
Museum Platform - Heritage Evidence Corpus Data Models (Schema V2)
Standardized schemas for all intermediate datasets, RAG chunks, KG candidates,
and provenance-aware quality reporting.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import datetime
import json


SCHEMA_VERSION = "2.0.0"


@dataclass
class SourceConfig:
    source_id: str
    name: str
    base_url: str
    allowed_domains: List[str]
    robots_url: Optional[str]
    rate_limit_delay: float = 1.5
    max_concurrency: int = 1
    auth_type: str = "NONE"
    license_terms: str = "PROPRIETARY_OR_EDUCATIONAL_CITATION"
    provenance_tier: str = "OFFICIAL_MUSEUM"
    enabled: bool = True
    operational_status: str = "OPERATIONAL"  # OPERATIONAL, STAGED_NOT_IMPLEMENTED
    attribution_required: bool = True
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "MuseumPlatformResearchBot/1.0 (+https://github.com/museum-platform; Research & Cultural Preservation)"
    })


@dataclass
class CrawlManifest:
    run_id: str
    source_id: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "RUNNING"  # RUNNING, COMPLETED, INTERRUPTED, FAILED
    discovered_urls: int = 0
    attempted_urls: int = 0
    succeeded_urls: int = 0
    failed_urls: int = 0
    quarantined_urls: int = 0
    content_changes_detected: int = 0
    fetched_hubs: int = 0
    fetched_articles: int = 0
    corpus_version: str = "2.0.0"
    schema_version: str = SCHEMA_VERSION
    parser_version: str = "vnmh_v2"
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RawDocument:
    doc_id: str
    source_id: str
    url: str
    canonical_url: str
    http_status: int
    content_hash: str  # SHA-256 of raw response body
    retrieved_at: str
    headers: Dict[str, str]
    raw_html: str
    language: str = "vi"
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetadataEvidence:
    field_name: str
    value: Any
    raw_evidence_quote: str
    char_start: int
    char_end: int
    offset_source: str = "canonical_clean_text"
    extraction_method: str = "ANCHORED_LABEL_DOM"  # ANCHORED_LABEL_DOM, REGEX_BOUNDED, HEURISTIC
    confidence: float = 1.0
    validation_status: str = "VALIDATED"  # VALIDATED, UNCERTAIN, INVALID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedDocument:
    doc_id: str
    source_id: str
    canonical_url: str
    original_url: str
    language: str  # 'vi' or 'en'
    title: str
    canonical_clean_text: str  # Official text representation for RAG/KG character offsets
    author: Optional[str] = None
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    view_count: Optional[int] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    breadcrumbs: List[str] = field(default_factory=list)
    summary_abstract: str = ""
    content_text: str = ""  # Backward compatible alias for canonical_clean_text
    classification: str = "UNKNOWN"
    metadata_fields: Dict[str, Any] = field(default_factory=dict)
    metadata_evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    heading_hierarchy: List[Dict[str, Any]] = field(default_factory=list)
    content_hash: str = ""
    retrieved_at: str = ""
    parser_version: str = "vnmh_v2"
    schema_version: str = SCHEMA_VERSION
    validation_status: str = "VALIDATED"  # VALIDATED, QUARANTINED, PARSE_FAILED
    quarantine_reasons: List[str] = field(default_factory=list)
    copyright_status: str = "RESERVED_CITATION_PERMITTED"
    reuse_terms: str = "Scholarly citation with provenance attribution"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentSection:
    section_id: str  # Format: {doc_id}-SEC-{idx:03d}
    doc_id: str
    source_id: str
    heading_path: List[str]
    heading_level: int
    section_text: str
    offset_source: str  # "canonical_clean_text" or "summary_abstract"
    char_start: int
    char_end: int
    language: str
    parent_section_id: Optional[str] = None
    token_count: int = 0
    temporal_context: Optional[str] = None
    source_attribution: str = ""
    corpus_version: str = "2.0.0"
    schema_version: str = SCHEMA_VERSION
    index_eligibility: bool = True
    ineligibility_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentLink:
    link_id: str
    source_doc_id: str
    target_url: str
    target_canonical_url: str
    anchor_text: str
    link_type: str  # INTERNAL_ARTICLE, CATEGORY_HUB, PAGINATION, EXTERNAL_REFERENCE, MEDIA_ASSET

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MediaMetadata:
    media_id: str
    doc_id: str
    media_type: str  # IMAGE, VIDEO, PDF, EMBED
    source_url: str
    normalized_url: str
    alt_text: str = ""
    caption: str = ""
    placement_section: Optional[str] = None
    copyright_status: str = "UNKNOWN_PENDING_VERIFICATION"  # UNKNOWN_PENDING_VERIFICATION, VNMH_RESERVED, PUBLIC_DOMAIN
    license_evidence_url: Optional[str] = None
    attribution_required: bool = True
    rights_holder: Optional[str] = None
    download_permitted: bool = False
    local_path: Optional[str] = None
    file_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityMention:
    mention_id: str
    doc_id: str
    section_id: str  # FK -> DocumentSection.section_id (MUST exist)
    entity_type: str  # ARTIFACT, HERITAGE_SITE, PERSON, EVENT, PERIOD, CULTURE, LOCATION, INSTITUTION, COLLECTION, DOCUMENT, EXHIBITION
    mention_text: str
    normalized_name: str
    offset_source: str  # "canonical_clean_text" or "title" or "summary_abstract"
    char_start: int
    char_end: int
    confidence: float = 1.0
    provenance: str = "BODY_CANONICAL_TEXT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityMatchCandidate:
    candidate_id: str
    vnmh_doc_id: str
    vnmh_title: str
    vnmh_registration_num: Optional[str]
    legacy_artifact_id: int
    legacy_name: str
    match_criteria: str  # REGISTRATION_NUMBER, EXACT_ALIAS, NAME_AND_ERA_CONSISTENCY, MANUAL_VERIFIED
    confidence_score: float
    review_status: str = "PENDING_REVIEW"
    evidence_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KGCandidateEdge:
    edge_id: str
    source_entity: str
    source_entity_type: str
    target_entity: str
    target_entity_type: str
    relation_type: str  # AUTHORED_BY, CREATED_BY, CURRENTLY_HELD_BY, ASSOCIATED_WITH_CULTURE, BELONGS_TO_PERIOD, DISCOVERED_AT, PART_OF_COLLECTION, EXHIBITED_AT, LOCATED_IN
    epistemic_status: str  # ASSERTED, DERIVED, HYPOTHESIZED
    review_status: str = "PENDING_REVIEW"
    provenance_doc_id: str = ""
    provenance_section_id: str = ""  # FK -> DocumentSection.section_id (MUST exist)
    evidence_quote: str = ""  # LITERAL substring from canonical source text
    derivation_note: Optional[str] = None  # Synthetic explanation (kept separate from literal quote)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlFailure:
    failure_id: str
    url: str
    source_id: str
    attempt_count: int
    http_status: Optional[int]
    error_type: str  # HTTP_ERROR, TIMEOUT, CONNECTION_ERROR, PARSE_ERROR, RATE_LIMITED, ROBOTS_BLOCKED
    error_message: str
    retryable: bool = True
    last_attempted_at: str = ""
    next_retry_at: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityReport:
    generated_at: str
    corpus_version: str
    schema_version: str
    total_logical_documents: int
    language_distribution: Dict[str, int]
    classification_breakdown: Dict[str, int]
    validation_status_breakdown: Dict[str, int]
    field_presence_rates: Dict[str, float]
    field_validity_rates: Dict[str, float]
    fk_integrity_metrics: Dict[str, Any]
    span_accuracy_metrics: Dict[str, Any]
    token_cap_compliance_metrics: Dict[str, Any]
    media_count: int
    section_count: int
    kg_edge_count: int
    legacy_match_candidate_count: int
    failure_count: int
    quarantine_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
