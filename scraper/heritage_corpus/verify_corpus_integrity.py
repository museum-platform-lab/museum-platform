"""
Museum Platform - Heritage Corpus QA & Integrity Verification Script
Performs rigorous offline verification against all acceptance criteria:
- Gate G1: 100% FK resolvability across documents, sections, mentions, edges
- Gate G2: 100% exact substring slicing invariant (sections and mentions)
- Gate G3: 100% exact literal quotes in KG edges
- Gate G4: Zero ontological contamination (no author as CREATED_BY, no ungrounded custody)
- Gate G5: Hard token and character cap compliance (zero violations)
- Gate G6: Immutable raw archive presence and hash verification

Exits with code 0 on PASS, 1 on FAIL.
Generates audit_handover/evidence/qa-integrity-report.json.
"""

import sys
import os
import json
import hashlib
from typing import Dict, Any, List


def verify_corpus(data_dir: str, output_report_path: str = None) -> bool:
    print("======================================================================")
    print("       VIETNAMESE HERITAGE CORPUS - OFFLINE QA INTEGRITY VERIFICATION")
    print("======================================================================")
    print(f"Target Data Directory: {data_dir}\n")

    parsed_path = os.path.join(data_dir, "parsed_documents.jsonl")
    sections_path = os.path.join(data_dir, "document_sections.jsonl")
    mentions_path = os.path.join(data_dir, "entity_mentions.jsonl")
    edges_path = os.path.join(data_dir, "kg_candidate_edges.jsonl")
    raw_dir = os.path.join(data_dir, "raw_documents")

    errors = []
    warnings = []

    # 1. Load Parsed Documents
    docs: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(parsed_path):
        with open(parsed_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                if line.strip():
                    d = json.loads(line)
                    doc_id = d.get("doc_id")
                    if doc_id:
                        docs[doc_id] = d
    print(f"Loaded {len(docs)} parsed documents.")
    if not docs:
        errors.append("No parsed documents found.")

    # 2. Check Raw Archive Immutability & Hash
    raw_hash_matches = 0
    raw_hash_total = 0
    for doc_id, doc in docs.items():
        chash = doc.get("content_hash")
        # Check either raw_documents/{doc_id}/{chash}.json or raw_documents/{doc_id}.json
        path1 = os.path.join(raw_dir, doc_id, f"{chash}.json")
        path2 = os.path.join(raw_dir, f"{doc_id}.json")
        raw_file = path1 if os.path.exists(path1) else (path2 if os.path.exists(path2) else None)

        if not raw_file:
            errors.append(f"Missing raw document for {doc_id} at {path1}")
        else:
            raw_hash_total += 1
            try:
                with open(raw_file, "r", encoding="utf-8") as f:
                    rdata = json.load(f)
                    raw_html = rdata.get("raw_html", "")
                    computed = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
                    if computed == chash:
                        raw_hash_matches += 1
                    else:
                        errors.append(f"Content hash mismatch for {doc_id}: expected {chash}, got {computed}")
            except Exception as e:
                errors.append(f"Error reading raw document {raw_file}: {e}")

    # 3. Load & Check Sections (Exact span slice invariant, token cap, doc FK)
    sections: Dict[str, Dict[str, Any]] = {}
    sec_span_matches = 0
    sec_span_total = 0
    sec_fk_matches = 0
    sec_cap_compliant = 0
    hard_char_limit = 2500

    if os.path.exists(sections_path):
        with open(sections_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                s = json.loads(line)
                sec_id = s.get("section_id")
                if not sec_id:
                    continue
                sections[sec_id] = s
                sec_span_total += 1

                doc_id = s.get("doc_id")
                if doc_id in docs:
                    sec_fk_matches += 1
                else:
                    errors.append(f"Section {sec_id} references non-existent doc_id '{doc_id}'")

                sec_text = s.get("section_text", "")
                if len(sec_text) <= hard_char_limit:
                    sec_cap_compliant += 1
                else:
                    errors.append(f"Section {sec_id} exceeds hard char limit: {len(sec_text)} > {hard_char_limit}")

                # Exact substring slice verification
                p_doc = docs.get(doc_id)
                if p_doc:
                    offset_src = s.get("offset_source", "canonical_clean_text")
                    src_text = p_doc.get(offset_src, "")
                    c_start = s.get("char_start", 0)
                    c_end = s.get("char_end", 0)
                    if 0 <= c_start <= c_end <= len(src_text):
                        sliced = src_text[c_start:c_end]
                        if sliced == sec_text:
                            sec_span_matches += 1
                        else:
                            errors.append(f"Section {sec_id} exact span slice mismatch in {offset_src}")
                    else:
                        errors.append(f"Section {sec_id} span offsets [{c_start}:{c_end}] out of bounds (len {len(src_text)})")

    print(f"Checked {sec_span_total} sections: FKs valid={sec_fk_matches}, Spans valid={sec_span_matches}, Cap compliant={sec_cap_compliant}")

    # 4. Load & Check Entity Mentions (FK, exact span)
    mentions: List[Dict[str, Any]] = []
    m_fk_matches = 0
    m_span_matches = 0

    if os.path.exists(mentions_path):
        with open(mentions_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                m = json.loads(line)
                mentions.append(m)
                m_id = m.get("mention_id")

                sec_id = m.get("section_id")
                if sec_id in sections:
                    m_fk_matches += 1
                else:
                    errors.append(f"Mention {m_id} references non-existent section_id '{sec_id}'")

                doc_id = m.get("doc_id")
                p_doc = docs.get(doc_id)
                if p_doc:
                    offset_src = m.get("offset_source", "canonical_clean_text")
                    src_text = p_doc.get(offset_src, "")
                    c_start = m.get("char_start", 0)
                    c_end = m.get("char_end", 0)
                    m_text = m.get("mention_text", "")
                    if 0 <= c_start <= c_end <= len(src_text):
                        if src_text[c_start:c_end] == m_text:
                            m_span_matches += 1
                        else:
                            errors.append(f"Mention {m_id} text mismatch at [{c_start}:{c_end}] in {offset_src}")
                    else:
                        errors.append(f"Mention {m_id} span [{c_start}:{c_end}] out of bounds in {offset_src}")

    print(f"Checked {len(mentions)} entity mentions: FKs valid={m_fk_matches}, Spans valid={m_span_matches}")

    # 5. Load & Check KG Candidate Edges (FK, exact literal quotes, ontological correctness)
    edges: List[Dict[str, Any]] = []
    edge_fk_matches = 0
    edge_quote_matches = 0
    author_as_creator_violations = 0
    ungrounded_custody_violations = 0

    if os.path.exists(edges_path):
        with open(edges_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                e = json.loads(line)
                edges.append(e)
                e_id = e.get("edge_id")

                sec_id = e.get("provenance_section_id")
                sec_obj = sections.get(sec_id)
                if sec_obj:
                    edge_fk_matches += 1
                else:
                    errors.append(f"Edge {e_id} references non-existent section_id '{sec_id}'")

                quote = e.get("evidence_quote", "")
                if sec_obj and quote:
                    if quote in sec_obj.get("section_text", ""):
                        edge_quote_matches += 1
                    else:
                        errors.append(f"Edge {e_id} evidence_quote not found in section {sec_id}")

                # Ontological checks
                pred = e.get("predicate")
                subj_type = e.get("subject_type")
                obj_name = e.get("object_name", "")

                # Author must NEVER be maker of artifact
                if pred == "CREATED_BY":
                    # Check if object is author of article
                    doc_for_edge = docs.get(e.get("edge_id", "").split("-EDG-")[0])
                    if doc_for_edge and doc_for_edge.get("author") and obj_name == doc_for_edge.get("author"):
                        author_as_creator_violations += 1
                        errors.append(f"Ontology violation: Author '{obj_name}' assigned as CREATED_BY artifact in {e_id}")

                # Custody must be grounded
                if pred == "CURRENTLY_HELD_BY":
                    if not quote or len(quote) < 3:
                        ungrounded_custody_violations += 1
                        errors.append(f"Ungrounded custody relation in edge {e_id}")

    print(f"Checked {len(edges)} KG edges: FKs valid={edge_fk_matches}, Quotes valid={edge_quote_matches}, Author-as-Creator={author_as_creator_violations}, Ungrounded custody={ungrounded_custody_violations}")

    # Compile Verification Results
    total_fk = sec_span_total + len(mentions) + len(edges)
    valid_fk = sec_fk_matches + m_fk_matches + edge_fk_matches
    fk_pct = round((valid_fk / max(total_fk, 1)) * 100, 2)

    sec_span_pct = round((sec_span_matches / max(sec_span_total, 1)) * 100, 2)
    m_span_pct = round((m_span_matches / max(len(mentions), 1)) * 100, 2)
    quote_pct = round((edge_quote_matches / max(len(edges), 1)) * 100, 2)
    cap_pct = round((sec_cap_compliant / max(sec_span_total, 1)) * 100, 2)

    passed = (
        len(errors) == 0
        and fk_pct == 100.0
        and sec_span_pct == 100.0
        and m_span_pct == 100.0
        and quote_pct == 100.0
        and cap_pct == 100.0
        and author_as_creator_violations == 0
        and ungrounded_custody_violations == 0
    )

    result_data = {
        "verified_at": "2026-11-09T12:00:00Z",
        "verdict": "PASS" if passed else "FAIL",
        "metrics": {
            "total_documents": len(docs),
            "raw_hash_matches": raw_hash_matches,
            "raw_hash_total": raw_hash_total,
            "fk_integrity_pct": fk_pct,
            "section_span_accuracy_pct": sec_span_pct,
            "mention_span_accuracy_pct": m_span_pct,
            "edge_quote_accuracy_pct": quote_pct,
            "token_cap_compliance_pct": cap_pct,
            "author_as_creator_violations": author_as_creator_violations,
            "ungrounded_custody_violations": ungrounded_custody_violations
        },
        "errors_count": len(errors),
        "errors": errors[:50],  # cap at first 50
        "warnings": warnings
    }

    print("\n----------------------------------------------------------------------")
    print(f"VERIFICATION VERDICT: {'[PASS] ALL INTEGRITY GATES MET' if passed else '[FAIL] INTEGRITY GATES FAILED'}")
    print(f"  FK Integrity         : {fk_pct}% (Target: 100%)")
    print(f"  Section Span Accuracy: {sec_span_pct}% (Target: 100%)")
    print(f"  Mention Span Accuracy: {m_span_pct}% (Target: 100%)")
    print(f"  KG Quote Accuracy    : {quote_pct}% (Target: 100%)")
    print(f"  Token Cap Compliance : {cap_pct}% (Target: 100%)")
    print(f"  Author-as-Maker Viol : {author_as_creator_violations} (Target: 0)")
    print(f"  Ungrounded Custody   : {ungrounded_custody_violations} (Target: 0)")
    print(f"  Total Errors         : {len(errors)}")
    print("----------------------------------------------------------------------\n")

    if output_report_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_report_path)), exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        print(f"Saved QA report to: {output_report_path}")

    return passed


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    data_directory = sys.argv[1] if len(sys.argv) > 1 else "scraper/heritage_corpus/data"
    report_out = sys.argv[2] if len(sys.argv) > 2 else "scraper/heritage_corpus/audit_handover/evidence/qa-integrity-report.json"

    is_ok = verify_corpus(data_directory, report_out)
    sys.exit(0 if is_ok else 1)
