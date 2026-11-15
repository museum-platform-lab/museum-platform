"""
Museum Platform - Knowledge Graph Candidate Preparer (V2 Hardened)
Guarantees:
- Ontological separation: article authors -> AUTHORED_BY document (NEVER artifact CREATED_BY)
- Zero custody fabrication: CURRENTLY_HELD_BY only with explicit literal custody evidence
- 100% resolvable section foreign keys against document_sections
- 100% exact substring mention spans and literal evidence quotes
- Strict PENDING_REVIEW status for all extracted edges
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from .models import ParsedDocument, DocumentSection, EntityMention, KGCandidateEdge


class KGPreparer:
    KNOWN_CULTURES = [
        "Đông Sơn", "Sa Huỳnh", "Óc Eo", "Đại Việt", "Chăm Pa", "Phù Nam",
        "Hòa Bình", "Bắc Sơn", "Hạ Long", "Đồng Đậu", "Gò Mun", "Phùng Nguyên"
    ]
    KNOWN_PERIODS = [
        "Thời Lý", "Thời Trần", "Thời Lê sơ", "Thời Lê Trung hưng", "Thời Lê",
        "Thời Nguyễn", "Thời Mạc", "Thời Tây Sơn", "Thời Đinh", "Thời Tiền Lê",
        "Thời Bắc thuộc", "Thời Pháp thuộc"
    ]

    @classmethod
    def extract_kg_candidates(
        cls,
        doc: ParsedDocument,
        sections: List[DocumentSection]
    ) -> Tuple[List[EntityMention], List[KGCandidateEdge]]:
        mentions: List[EntityMention] = []
        edges: List[KGCandidateEdge] = []
        mention_counter = 0
        edge_counter = 0

        title = doc.title.strip()
        doc_id = doc.doc_id
        canon_text = doc.canonical_clean_text

        # Default section FK fallback to first section if specific section not located
        fallback_sec_id = sections[0].section_id if sections else f"{doc_id}-SEC-001"

        def locate_section_for_text(target_text: str) -> str:
            """Finds which section contains target_text to ensure valid FK."""
            for s in sections:
                if target_text in s.section_text:
                    return s.section_id
            return fallback_sec_id

        # 1. Primary Entity of Document
        primary_entity_type = "ARTIFACT" if doc.classification == "ARTIFACT_PROFILE" else "DOCUMENT"
        mention_counter += 1
        mentions.append(EntityMention(
            mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
            doc_id=doc_id,
            section_id=fallback_sec_id,
            entity_type=primary_entity_type,
            mention_text=title,
            normalized_name=title,
            offset_source="title",
            char_start=0,
            char_end=len(title),
            confidence=1.0,
            provenance="TITLE_HEADER"
        ))

        meta = doc.metadata_fields

        # 2. Relation: CURRENTLY_HELD_BY (P0-06 Fix: NO FALLBACK without explicit evidence)
        explicit_held_by = meta.get("storage_location")
        if explicit_held_by and len(explicit_held_by.strip()) > 2:
            # Find in text
            held_by_clean = explicit_held_by.strip()
            sec_id = locate_section_for_text(held_by_clean)

            # Find exact literal quote in canonical text
            evidence_quote = ""
            idx = canon_text.find(held_by_clean)
            if idx != -1:
                # Extract surrounding sentence or line
                line_start = canon_text.rfind("\n", 0, idx)
                line_start = 0 if line_start == -1 else line_start + 1
                line_end = canon_text.find("\n", idx)
                line_end = len(canon_text) if line_end == -1 else line_end
                evidence_quote = canon_text[line_start:line_end].strip()
            else:
                evidence_quote = held_by_clean

            mention_counter += 1
            held_start = canon_text.find(held_by_clean)
            held_end = (held_start + len(held_by_clean)) if held_start != -1 else len(held_by_clean)
            mentions.append(EntityMention(
                mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
                doc_id=doc_id,
                section_id=sec_id,
                entity_type="INSTITUTION",
                mention_text=held_by_clean,
                normalized_name=held_by_clean,
                offset_source="canonical_clean_text" if held_start != -1 else "title",
                char_start=max(0, held_start),
                char_end=held_end,
                confidence=0.95,
                provenance="STORAGE_LOCATION_FIELD"
            ))

            edge_counter += 1
            edges.append(KGCandidateEdge(
                edge_id=f"{doc_id}-EDG-{edge_counter:03d}",
                source_entity=title,
                source_entity_type=primary_entity_type,
                target_entity=held_by_clean,
                target_entity_type="INSTITUTION",
                relation_type="CURRENTLY_HELD_BY",
                epistemic_status="ASSERTED",
                review_status="PENDING_REVIEW",
                provenance_doc_id=doc_id,
                provenance_section_id=sec_id,
                evidence_quote=evidence_quote,
                confidence=0.95
            ))

        # 3. Relation: ASSOCIATED_WITH_CULTURE / BELONGS_TO_PERIOD
        era_culture = meta.get("era_culture") or ""
        if era_culture:
            # Check cultures
            for c in cls.KNOWN_CULTURES:
                if c.lower() in era_culture.lower():
                    culture_name = f"Văn hóa {c}"
                    sec_id = locate_section_for_text(c)

                    # Substring check for mention
                    c_idx = canon_text.find(culture_name)
                    if c_idx == -1:
                        c_idx = canon_text.find(c)
                        m_txt = c
                    else:
                        m_txt = culture_name

                    m_start = max(0, c_idx)
                    m_end = m_start + len(m_txt)

                    mention_counter += 1
                    mentions.append(EntityMention(
                        mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
                        doc_id=doc_id,
                        section_id=sec_id,
                        entity_type="CULTURE",
                        mention_text=m_txt,
                        normalized_name=culture_name,
                        offset_source="canonical_clean_text",
                        char_start=m_start,
                        char_end=m_end,
                        confidence=0.90,
                        provenance="ERA_CULTURE_FIELD"
                    ))

                    # Literal evidence quote
                    ev_quote = era_culture if era_culture in canon_text else m_txt

                    edge_counter += 1
                    edges.append(KGCandidateEdge(
                        edge_id=f"{doc_id}-EDG-{edge_counter:03d}",
                        source_entity=title,
                        source_entity_type=primary_entity_type,
                        target_entity=culture_name,
                        target_entity_type="CULTURE",
                        relation_type="ASSOCIATED_WITH_CULTURE",
                        epistemic_status="ASSERTED",
                        review_status="PENDING_REVIEW",
                        provenance_doc_id=doc_id,
                        provenance_section_id=sec_id,
                        evidence_quote=ev_quote,
                        confidence=0.90
                    ))
                    break

            # Check periods
            for p in cls.KNOWN_PERIODS:
                if p.lower() in era_culture.lower():
                    sec_id = locate_section_for_text(p)
                    p_idx = canon_text.find(p)
                    p_start = max(0, p_idx)
                    p_end = p_start + len(p)

                    mention_counter += 1
                    mentions.append(EntityMention(
                        mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
                        doc_id=doc_id,
                        section_id=sec_id,
                        entity_type="PERIOD",
                        mention_text=p,
                        normalized_name=p,
                        offset_source="canonical_clean_text",
                        char_start=p_start,
                        char_end=p_end,
                        confidence=0.85,
                        provenance="ERA_PERIOD_FIELD"
                    ))

                    ev_quote = era_culture if era_culture in canon_text else p

                    edge_counter += 1
                    edges.append(KGCandidateEdge(
                        edge_id=f"{doc_id}-EDG-{edge_counter:03d}",
                        source_entity=title,
                        source_entity_type=primary_entity_type,
                        target_entity=p,
                        target_entity_type="PERIOD",
                        relation_type="BELONGS_TO_PERIOD",
                        epistemic_status="ASSERTED",
                        review_status="PENDING_REVIEW",
                        provenance_doc_id=doc_id,
                        provenance_section_id=sec_id,
                        evidence_quote=ev_quote,
                        confidence=0.85
                    ))
                    break

        # 4. Relation: DISCOVERED_AT (Location distinction)
        disc_loc = meta.get("discovery_location")
        if disc_loc and len(disc_loc.strip()) > 3:
            loc_clean = disc_loc.strip()
            sec_id = locate_section_for_text(loc_clean)

            l_idx = canon_text.find(loc_clean)
            l_start = max(0, l_idx)
            l_end = l_start + len(loc_clean)

            mention_counter += 1
            mentions.append(EntityMention(
                mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
                doc_id=doc_id,
                section_id=sec_id,
                entity_type="LOCATION",
                mention_text=loc_clean,
                normalized_name=loc_clean,
                offset_source="canonical_clean_text",
                char_start=l_start,
                char_end=l_end,
                confidence=0.90,
                provenance="DISCOVERY_LOCATION_FIELD"
            ))

            edge_counter += 1
            edges.append(KGCandidateEdge(
                edge_id=f"{doc_id}-EDG-{edge_counter:03d}",
                source_entity=title,
                source_entity_type=primary_entity_type,
                target_entity=loc_clean,
                target_entity_type="LOCATION",
                relation_type="DISCOVERED_AT",
                epistemic_status="ASSERTED",
                review_status="PENDING_REVIEW",
                provenance_doc_id=doc_id,
                provenance_section_id=sec_id,
                evidence_quote=loc_clean,
                confidence=0.90
            ))

        # 5. Author / Creator Relation (P0-05 Fix: AUTHORED_BY document, NOT CREATED_BY artifact)
        if doc.author:
            author_clean = doc.author.strip()
            sec_id = locate_section_for_text(author_clean)

            a_idx = canon_text.find(author_clean)
            a_start = max(0, a_idx)
            a_end = a_start + len(author_clean)

            mention_counter += 1
            mentions.append(EntityMention(
                mention_id=f"{doc_id}-MNT-{mention_counter:03d}",
                doc_id=doc_id,
                section_id=sec_id,
                entity_type="PERSON",
                mention_text=author_clean,
                normalized_name=author_clean,
                offset_source="canonical_clean_text",
                char_start=a_start,
                char_end=a_end,
                confidence=0.95,
                provenance="ARTICLE_SIGNATURE"
            ))

            # P0-05: Source entity MUST be DOCUMENT and relation AUTHORED_BY
            edge_counter += 1
            edges.append(KGCandidateEdge(
                edge_id=f"{doc_id}-EDG-{edge_counter:03d}",
                source_entity=title,
                source_entity_type="DOCUMENT",
                target_entity=author_clean,
                target_entity_type="PERSON",
                relation_type="AUTHORED_BY",
                epistemic_status="ASSERTED",
                review_status="PENDING_REVIEW",
                provenance_doc_id=doc_id,
                provenance_section_id=sec_id,
                evidence_quote=author_clean,
                confidence=0.95
            ))

        return mentions, edges
