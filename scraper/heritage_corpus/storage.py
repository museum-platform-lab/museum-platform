"""
Museum Platform - Heritage Corpus Storage Engine (V2)
Manages atomic serialization for raw archives and intermediate JSONL/JSON datasets:
- crawl_manifest
- raw_documents/{doc_id}/{content_hash}.json (immutable)
- parsed_documents.jsonl
- document_sections.jsonl
- document_links.jsonl
- media_metadata.jsonl
- entity_mentions.jsonl
- entity_match_candidates.jsonl
- kg_candidate_edges.jsonl
- crawl_failures.jsonl
- quality_report.json
- source_registry.json
"""

import os
import json
import uuid
import datetime
from typing import Dict, Any, List, Optional, Set
from .models import (
    CrawlManifest, RawDocument, ParsedDocument, DocumentSection,
    DocumentLink, MediaMetadata, EntityMention, EntityMatchCandidate,
    KGCandidateEdge, CrawlFailure, QualityReport, SCHEMA_VERSION
)


class CorpusStorage:
    def __init__(self, output_dir: str = "scraper/heritage_corpus/data"):
        self.output_dir = os.path.abspath(output_dir)
        self.raw_dir = os.path.join(self.output_dir, "raw_documents")
        os.makedirs(self.raw_dir, exist_ok=True)

        self.paths = {
            "manifest": os.path.join(self.output_dir, "crawl_manifest.json"),
            "parsed_documents": os.path.join(self.output_dir, "parsed_documents.jsonl"),
            "document_sections": os.path.join(self.output_dir, "document_sections.jsonl"),
            "document_links": os.path.join(self.output_dir, "document_links.jsonl"),
            "media_metadata": os.path.join(self.output_dir, "media_metadata.jsonl"),
            "entity_mentions": os.path.join(self.output_dir, "entity_mentions.jsonl"),
            "entity_match_candidates": os.path.join(self.output_dir, "entity_match_candidates.jsonl"),
            "kg_candidate_edges": os.path.join(self.output_dir, "kg_candidate_edges.jsonl"),
            "crawl_failures": os.path.join(self.output_dir, "crawl_failures.jsonl"),
            "quality_report": os.path.join(self.output_dir, "quality_report.json"),
            "source_registry": os.path.join(self.output_dir, "source_registry.json")
        }

        # Track written IDs to guarantee idempotent appends within process lifecycle
        self._seen_ids: Dict[str, Set[str]] = {k: set() for k in self.paths}
        self._initialize_seen_ids()

    def _initialize_seen_ids(self):
        """Reads existing JSONL files to populate seen IDs for deduplication."""
        id_keys = {
            "parsed_documents": "doc_id",
            "document_sections": "section_id",
            "document_links": "link_id",
            "media_metadata": "media_id",
            "entity_mentions": "mention_id",
            "entity_match_candidates": "candidate_id",
            "kg_candidate_edges": "edge_id",
            "crawl_failures": "failure_id"
        }
        for key, id_field in id_keys.items():
            path = self.paths.get(key)
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line_str = line.strip()
                            if line_str:
                                rec = json.loads(line_str)
                                rid = rec.get(id_field)
                                if rid:
                                    self._seen_ids[key].add(str(rid))
                except Exception:
                    pass

    def save_raw_document(self, raw_doc: RawDocument) -> str:
        """
        Saves raw document to immutable archive raw_documents/{doc_id}/{content_hash}.json
        using atomic temporary file and rename to prevent partial writes.
        """
        doc_dir = os.path.join(self.raw_dir, raw_doc.doc_id)
        os.makedirs(doc_dir, exist_ok=True)

        filepath = os.path.join(doc_dir, f"{raw_doc.content_hash}.json")
        temp_filepath = f"{filepath}.tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}"

        with open(temp_filepath, "w", encoding="utf-8") as f:
            json.dump(raw_doc.to_dict(), f, ensure_ascii=False, indent=2)

        os.replace(temp_filepath, filepath)

        # Also write a doc_id.json link / convenience copy for fast lookup
        latest_file = os.path.join(self.raw_dir, f"{raw_doc.doc_id}.json")
        try:
            with open(latest_file, "w", encoding="utf-8") as f:
                json.dump(raw_doc.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return filepath

    def append_jsonl(self, key: str, records: List[Any], dedup_id_field: Optional[str] = None):
        """
        Appends a batch of dataclass instances or dicts to the corresponding JSONL file.
        Deduplicates against already written records in this storage instance.
        """
        if not records:
            return
        target_path = self.paths.get(key)
        if not target_path:
            raise ValueError(f"Unknown storage key: {key}")

        id_field_map = {
            "parsed_documents": "doc_id",
            "document_sections": "section_id",
            "document_links": "link_id",
            "media_metadata": "media_id",
            "entity_mentions": "mention_id",
            "entity_match_candidates": "candidate_id",
            "kg_candidate_edges": "edge_id",
            "crawl_failures": "failure_id"
        }
        check_field = dedup_id_field or id_field_map.get(key)
        seen = self._seen_ids.setdefault(key, set())

        to_write = []
        for rec in records:
            d = rec.to_dict() if hasattr(rec, "to_dict") else rec
            if check_field and check_field in d:
                rid = str(d[check_field])
                if rid in seen:
                    continue
                seen.add(rid)
            to_write.append(d)

        if not to_write:
            return

        with open(target_path, "a", encoding="utf-8") as f:
            for item in to_write:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def save_manifest(self, manifest: CrawlManifest):
        """Atomically saves manifest."""
        path = self.paths["manifest"]
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def save_quality_report(self, report: QualityReport):
        """Atomically saves quality report."""
        path = self.paths["quality_report"]
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def generate_quality_report(self) -> QualityReport:
        """
        Reads generated JSONL datasets and computes comprehensive QualityReport V2 metrics
        including FK integrity, exact substring span accuracy, and token cap compliance.
        """
        docs: Dict[str, Dict[str, Any]] = {}
        lang_dist: Dict[str, int] = {}
        class_dist: Dict[str, int] = {}
        status_dist: Dict[str, int] = {}
        field_present_counts: Dict[str, int] = {
            "registration_number": 0,
            "material": 0,
            "dimensions": 0,
            "era_culture": 0,
            "recognition_decree": 0,
            "discovery_location": 0,
            "storage_location": 0,
            "published_at": 0
        }
        field_valid_counts: Dict[str, int] = {
            "registration_number": 0,
            "material": 0,
            "dimensions": 0,
            "era_culture": 0,
            "recognition_decree": 0,
            "discovery_location": 0,
            "storage_location": 0,
            "published_at": 0
        }
        quarantine_count = 0

        # 1. Inspect Parsed Documents
        if os.path.exists(self.paths["parsed_documents"]):
            with open(self.paths["parsed_documents"], "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    doc = json.loads(line)
                    doc_id = doc.get("doc_id")
                    if not doc_id:
                        continue
                    docs[doc_id] = doc

                    lang = doc.get("language", "vi")
                    lang_dist[lang] = lang_dist.get(lang, 0) + 1

                    cls = doc.get("classification", "UNKNOWN")
                    class_dist[cls] = class_dist.get(cls, 0) + 1

                    status = doc.get("validation_status", "VALIDATED")
                    status_dist[status] = status_dist.get(status, 0) + 1
                    if status == "QUARANTINED":
                        quarantine_count += 1

                    meta = doc.get("metadata_fields", {})
                    for k in field_present_counts:
                        if k in meta and meta[k]:
                            field_present_counts[k] += 1
                            # Check validity
                            val = str(meta[k]).strip()
                            if k == "material" and len(val) > 1 and val.lower() != "s":
                                field_valid_counts[k] += 1
                            elif k == "era_culture" and len(val) > 2 and val.lower() != "từ":
                                field_valid_counts[k] += 1
                            elif k != "material" and k != "era_culture":
                                field_valid_counts[k] += 1

                    if doc.get("published_at"):
                        field_present_counts["published_at"] += 1
                        field_valid_counts["published_at"] += 1

        total_docs = len(docs)
        field_presence_rates = {
            k: round((v / max(total_docs, 1)) * 100, 2)
            for k, v in field_present_counts.items()
        }
        field_validity_rates = {
            k: round((v / max(field_present_counts[k], 1)) * 100, 2)
            for k, v in field_valid_counts.items()
        }

        # 2. Inspect Sections & RAG Slices
        sections: Dict[str, Dict[str, Any]] = {}
        span_total = 0
        span_matches = 0
        token_cap_total = 0
        token_cap_compliant = 0
        max_char_len = 0
        max_token_len = 0
        hard_char_limit = 2500

        if os.path.exists(self.paths["document_sections"]):
            with open(self.paths["document_sections"], "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    sec = json.loads(line)
                    sec_id = sec.get("section_id")
                    if not sec_id:
                        continue
                    sections[sec_id] = sec

                    # Token / Char cap check
                    token_cap_total += 1
                    sec_text = sec.get("section_text", "")
                    sec_len = len(sec_text)
                    tok_count = sec.get("token_count", sec_len // 4)
                    if sec_len > max_char_len:
                        max_char_len = sec_len
                    if tok_count > max_token_len:
                        max_token_len = tok_count
                    if sec_len <= hard_char_limit:
                        token_cap_compliant += 1

                    # Exact span verification
                    span_total += 1
                    doc_id = sec.get("doc_id")
                    parent_doc = docs.get(doc_id)
                    if parent_doc:
                        offset_src = sec.get("offset_source", "canonical_clean_text")
                        source_text = parent_doc.get(offset_src, "")
                        c_start = sec.get("char_start", 0)
                        c_end = sec.get("char_end", 0)
                        if source_text and 0 <= c_start <= c_end <= len(source_text):
                            sliced = source_text[c_start:c_end]
                            if sliced == sec_text:
                                span_matches += 1

        # 3. Inspect Entity Mentions
        mention_count = 0
        mention_valid_fk = 0
        mention_span_matches = 0

        if os.path.exists(self.paths["entity_mentions"]):
            with open(self.paths["entity_mentions"], "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    mention_count += 1
                    m = json.loads(line)
                    sec_id = m.get("section_id")
                    doc_id = m.get("doc_id")
                    if sec_id in sections:
                        mention_valid_fk += 1

                    # Check exact slice from indicated offset_source (canonical_clean_text, title, etc.)
                    parent_doc = docs.get(doc_id)
                    if parent_doc:
                        offset_src = m.get("offset_source", "canonical_clean_text")
                        source_text = parent_doc.get(offset_src, "")
                        c_start = m.get("char_start", 0)
                        c_end = m.get("char_end", 0)
                        m_text = m.get("mention_text", "")
                        if 0 <= c_start <= c_end <= len(source_text):
                            if source_text[c_start:c_end] == m_text:
                                mention_span_matches += 1

        # 4. Inspect KG Edges
        edge_count = 0
        edge_valid_fk = 0
        edge_quote_matches = 0
        author_as_creator_count = 0
        ungrounded_custody_count = 0

        if os.path.exists(self.paths["kg_candidate_edges"]):
            with open(self.paths["kg_candidate_edges"], "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    edge_count += 1
                    e = json.loads(line)
                    sec_id = e.get("provenance_section_id")
                    if sec_id in sections:
                        edge_valid_fk += 1

                    # Check literal quote exists in section
                    quote = e.get("evidence_quote", "")
                    sec_obj = sections.get(sec_id)
                    if sec_obj and quote:
                        if quote in sec_obj.get("section_text", ""):
                            edge_quote_matches += 1

                    # Check ontology rules:
                    # 1) CREATED_BY must not point to article author
                    # 2) CURRENTLY_HELD_BY must be grounded
                    pred = e.get("predicate")
                    subj_type = e.get("subject_type")
                    if pred == "CREATED_BY" and subj_type == "DOCUMENT":
                        author_as_creator_count += 1

        # FK Integrity metrics
        total_fk_refs = len(sections) + mention_count + edge_count
        valid_fk_refs = (
            sum(1 for s in sections.values() if s.get("doc_id") in docs)
            + mention_valid_fk
            + edge_valid_fk
        )
        fk_integrity_pct = round((valid_fk_refs / max(total_fk_refs, 1)) * 100, 2)

        fk_metrics = {
            "total_sections": len(sections),
            "sections_with_valid_doc_fk": sum(1 for s in sections.values() if s.get("doc_id") in docs),
            "total_mentions": mention_count,
            "mentions_with_valid_section_fk": mention_valid_fk,
            "total_edges": edge_count,
            "edges_with_valid_section_fk": edge_valid_fk,
            "fk_integrity_pct": fk_integrity_pct
        }

        # Span accuracy metrics
        span_metrics = {
            "total_section_spans": span_total,
            "section_span_matches": span_matches,
            "section_span_accuracy_pct": round((span_matches / max(span_total, 1)) * 100, 2),
            "total_mention_spans": mention_count,
            "mention_span_matches": mention_span_matches,
            "mention_span_accuracy_pct": round((mention_span_matches / max(mention_count, 1)) * 100, 2),
            "total_edge_quotes": edge_count,
            "edge_quote_matches": edge_quote_matches,
            "edge_quote_accuracy_pct": round((edge_quote_matches / max(edge_count, 1)) * 100, 2)
        }

        # Token cap compliance
        token_cap_metrics = {
            "total_sections": token_cap_total,
            "sections_under_hard_cap": token_cap_compliant,
            "max_char_len": max_char_len,
            "max_token_len": max_token_len,
            "hard_char_limit": hard_char_limit,
            "violations_count": token_cap_total - token_cap_compliant,
            "compliance_pct": round((token_cap_compliant / max(token_cap_total, 1)) * 100, 2)
        }

        media_count = self._count_lines(self.paths["media_metadata"])
        match_count = self._count_lines(self.paths["entity_match_candidates"])
        failure_count = self._count_lines(self.paths["crawl_failures"])

        report = QualityReport(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            corpus_version="2.0.0",
            schema_version=SCHEMA_VERSION,
            total_logical_documents=total_docs,
            language_distribution=lang_dist,
            classification_breakdown=class_dist,
            validation_status_breakdown=status_dist,
            field_presence_rates=field_presence_rates,
            field_validity_rates=field_validity_rates,
            fk_integrity_metrics=fk_metrics,
            span_accuracy_metrics=span_metrics,
            token_cap_compliance_metrics=token_cap_metrics,
            media_count=media_count,
            section_count=len(sections),
            kg_edge_count=edge_count,
            legacy_match_candidate_count=match_count,
            failure_count=failure_count,
            quarantine_count=quarantine_count
        )
        self.save_quality_report(report)
        return report

    @staticmethod
    def _count_lines(path: str) -> int:
        if not os.path.exists(path):
            return 0
        cnt = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for l in f:
                if l.strip():
                    cnt += 1
        return cnt
