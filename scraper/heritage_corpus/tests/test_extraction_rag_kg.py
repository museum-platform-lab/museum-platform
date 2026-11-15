"""
Unit and Integration Test Suite: Extraction, RAG, KG, and Legacy Matching (T-015 to T-028)
Acceptance Gates G1, G2, G3, G4, G5, G6
"""

import os
import sys
import pytest
import unicodedata

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from heritage_corpus.models import ParsedDocument, DocumentSection
from heritage_corpus.rag_preparer import RAGPreparer
from heritage_corpus.kg_preparer import KGPreparer
from heritage_corpus.vnmh_parser import VNMHParser
from heritage_corpus.legacy_matcher import LegacyMatcher


@pytest.fixture
def sample_parsed_doc():
    clean_text = (
        "Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.\n"
        "Hiện vật được phát hiện năm 1961 tại thôn Đào Thịnh, huyện Trấn Yên, tỉnh Yên Bái.\n"
        "Niên đại khoảng 2500 - 2000 năm cách ngày nay.\n"
        "Chất liệu: Đồng thau.\n"
        "Kích thước: Chiều cao 98 cm, đường kính miệng 61 cm.\n"
        "Hiện vật được lưu giữ tại Bảo tàng Lịch sử quốc gia.\n"
        "Tác giả bài viết: Nguyễn Văn A."
    )
    return ParsedDocument(
        doc_id="VNMH-VI-1001-73800",
        source_id="VNMH",
        url="https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html",
        canonical_url="https://baotanglichsu.vn/vi/Articles/1001/73800/thap-dao-thinh.html",
        title="Bảo vật Quốc gia: Thạp Đào Thịnh",
        author="Nguyễn Văn A",
        published_at="2020-01-01",
        language="vi",
        classification="ARTIFACT_PROFILE",
        canonical_clean_text=clean_text,
        content_text=clean_text,
        summary_abstract="Tóm tắt về thạp đồng Đào Thịnh.",
        metadata_fields={
            "registration_number": "LSb 13855",
            "material": "Đồng",
            "dimensions": "Cao 98cm; đk miệng 61cm",
            "era_culture": "Văn hóa Đông Sơn",
            "storage_location": "Bảo tàng Lịch sử quốc gia"
        },
        validation_status="VALIDATED"
    )


# --- T-015: Exact substring slicing invariant for RAG sections ---
def test_t015_exact_substring_slicing_invariant(sample_parsed_doc):
    raw_sections = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["Mô tả"],
            heading_level=2,
            section_text="Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.",
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections)
    for chk in chunks:
        ref_text = sample_parsed_doc.canonical_clean_text if chk.offset_source == "canonical_clean_text" else sample_parsed_doc.summary_abstract
        sliced = ref_text[chk.char_start:chk.char_end]
        assert sliced == chk.section_text, f"Mismatch: '{sliced}' != '{chk.section_text}'"


# --- T-016: Sentence/word boundary chunk splitting ---
def test_t016_sentence_word_boundary_splitting(sample_parsed_doc):
    long_p = "Câu thứ nhất rất quan trọng. " * 30  # ~900 chars
    raw_sections = [
        DocumentSection(
            section_id="TEMP-LONG",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["Dài"],
            heading_level=2,
            section_text=long_p.strip(),
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    # Update canonical text to hold this long paragraph
    sample_parsed_doc.canonical_clean_text = long_p.strip()
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections, max_chunk_chars=300)

    assert len(chunks) > 1
    for chk in chunks:
        # Verify no chunk ends in the middle of a word
        assert not chk.section_text.endswith(" quan")
        # Exact slicing must still hold 100%
        assert sample_parsed_doc.canonical_clean_text[chk.char_start:chk.char_end] == chk.section_text


# --- T-017: Token & hard character cap enforcement ---
def test_t017_hard_cap_enforcement(sample_parsed_doc):
    raw_sections = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["Test"],
            heading_level=2,
            section_text=sample_parsed_doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections, max_chunk_chars=200)
    for chk in chunks:
        assert len(chk.section_text) <= RAGPreparer.HARD_CAP_CHARS
        assert chk.token_count <= (RAGPreparer.HARD_CAP_CHARS // 3)


# --- T-018: Stable section ID format ---
def test_t018_stable_section_id_format(sample_parsed_doc):
    raw_sections = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["H1"],
            heading_level=1,
            section_text="Thạp Đào Thịnh là bảo vật quốc gia thuộc văn hóa Đông Sơn.",
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections)
    for idx, chk in enumerate(chunks, 1):
        expected_id = f"{sample_parsed_doc.doc_id}-SEC-{idx:03d}"
        assert chk.section_id == expected_id


# --- T-019: Section FK resolvability in KG candidate edges ---
def test_t019_section_fk_resolvability(sample_parsed_doc):
    raw_sections = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["H1"],
            heading_level=1,
            section_text=sample_parsed_doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections)
    sec_ids = {c.section_id for c in chunks}

    mentions, edges = KGPreparer.extract_kg_candidates(sample_parsed_doc, chunks)
    for edge in edges:
        assert edge.provenance_section_id in sec_ids, f"Edge FK '{edge.provenance_section_id}' not in sections {sec_ids}"
    for m in mentions:
        assert m.section_id in sec_ids, f"Mention FK '{m.section_id}' not in sections {sec_ids}"


# --- T-020: Exact literal quote in KG edges ---
def test_t020_exact_literal_quote_in_kg_edges(sample_parsed_doc):
    raw_sections = [
        DocumentSection(
            section_id="TEMP-01",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["H1"],
            heading_level=1,
            section_text=sample_parsed_doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=0,
            language="vi"
        )
    ]
    chunks = RAGPreparer.prepare_chunks(sample_parsed_doc, raw_sections)
    sec_map = {c.section_id: c.section_text for c in chunks}

    _, edges = KGPreparer.extract_kg_candidates(sample_parsed_doc, chunks)
    for edge in edges:
        sec_text = sec_map[edge.provenance_section_id]
        assert edge.evidence_quote in sec_text, f"Quote '{edge.evidence_quote}' not found in section text '{sec_text}'"


# --- T-021: Ontological separation: article author maps to AUTHORED_BY document, never CREATED_BY artifact ---
def test_t021_author_vs_creator_separation(sample_parsed_doc):
    chunks = [
        DocumentSection(
            section_id=f"{sample_parsed_doc.doc_id}-SEC-001",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["H1"],
            heading_level=1,
            section_text=sample_parsed_doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=len(sample_parsed_doc.canonical_clean_text),
            language="vi"
        )
    ]
    _, edges = KGPreparer.extract_kg_candidates(sample_parsed_doc, chunks)

    # 1. Must NOT have CREATED_BY pointing to 'Nguyễn Văn A'
    for e in edges:
        if e.predicate == "CREATED_BY":
            assert e.object_name != "Nguyễn Văn A"

    # 2. Must have AUTHORED_BY edge with subject_type DOCUMENT and object_name 'Nguyễn Văn A'
    author_edges = [e for e in edges if e.predicate == "AUTHORED_BY" and e.object_name == "Nguyễn Văn A"]
    assert len(author_edges) == 1
    assert author_edges[0].subject_type == "DOCUMENT"


# --- T-022: Zero custody fabrication: CURRENTLY_HELD_BY never produced without explicit evidence ---
def test_t022_zero_custody_fabrication(sample_parsed_doc):
    # Remove storage_location and text mentioning location
    sample_parsed_doc.metadata_fields["storage_location"] = ""
    sample_parsed_doc.canonical_clean_text = "Thạp Đào Thịnh là một bảo vật quốc gia thời cổ đại."

    chunks = [
        DocumentSection(
            section_id=f"{sample_parsed_doc.doc_id}-SEC-001",
            doc_id=sample_parsed_doc.doc_id,
            source_id="VNMH",
            heading_path=["H1"],
            heading_level=1,
            section_text=sample_parsed_doc.canonical_clean_text,
            offset_source="canonical_clean_text",
            char_start=0,
            char_end=len(sample_parsed_doc.canonical_clean_text),
            language="vi"
        )
    ]
    _, edges = KGPreparer.extract_kg_candidates(sample_parsed_doc, chunks)
    custody_edges = [e for e in edges if e.predicate == "CURRENTLY_HELD_BY"]
    assert len(custody_edges) == 0, "Fabricated CURRENTLY_HELD_BY edge without evidence!"


# --- T-023: Leaf-block DOM extraction (no ancestor-descendant text duplication) ---
def test_t023_leaf_block_dom_extraction():
    html = """
    <html><body>
    <div class="content-detail">
        <div class="wrapper">
            <p>Đoạn văn số một.</p>
            <p>Đoạn văn số hai.</p>
        </div>
    </div>
    </body></html>
    """
    clean_text = VNMHParser.extract_clean_text(html)
    # Both lines should appear exactly once
    assert clean_text.count("Đoạn văn số một.") == 1
    assert clean_text.count("Đoạn văn số hai.") == 1


# --- T-024: Anchored metadata label extraction with MetadataEvidence ---
def test_t024_anchored_metadata_label_extraction():
    html = """
    <html><body>
    <div class="content-detail">
        <p><strong>Số đăng ký:</strong> LSb 13855</p>
        <p><strong>Chất liệu:</strong> Đồng thau</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article_page(html, "https://baotanglichsu.vn/vi/Articles/1001/1/test.html", "2026-11-09")
    meta = doc.metadata_fields
    assert meta.get("registration_number") == "LSb 13855"
    assert meta.get("material") == "Đồng thau"

    # Verify MetadataEvidence provenance
    evidence_list = doc.metadata_evidence
    assert any(ev.field_name == "registration_number" and ev.value == "LSb 13855" for ev in evidence_list)
    assert any(ev.field_name == "material" and ev.value == "Đồng thau" for ev in evidence_list)


# --- T-025: Multiline dimensions parsing ---
def test_t025_multiline_dimensions_parsing():
    html = """
    <html><body>
    <div class="content-detail">
        <p><strong>Kích thước:</strong></p>
        <p>- Chiều cao: 98 cm</p>
        <p>- Đường kính miệng: 61 cm</p>
        <p><strong>Niên đại:</strong> Thời Đông Sơn</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article_page(html, "https://baotanglichsu.vn/vi/Articles/1001/1/dims.html", "2026-11-09")
    dims = doc.metadata_fields.get("dimensions", "")
    assert "98" in dims
    assert "61" in dims


# --- T-026: Material & Era false positive rejection ---
def test_t026_material_and_era_validation():
    # If HTML has "Materials:" followed by empty or single letter 's'
    html = """
    <html><body>
    <div class="content-detail">
        <p><strong>Materials:</strong></p>
        <p>s</p>
        <p><strong>Niên đại:</strong> từ</p>
    </div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article_page(html, "https://baotanglichsu.vn/vi/Articles/1001/1/fp.html", "2026-11-09")
    # Must NOT have material='s' or era='từ'
    assert doc.metadata_fields.get("material") != "s"
    assert doc.metadata_fields.get("era_culture") != "từ"


# --- T-027: Parse quarantine for empty or missing body text ---
def test_t027_quarantine_for_empty_body():
    html = """
    <html><body>
    <h1>Empty Article</h1>
    <div class="content-detail"></div>
    </body></html>
    """
    doc, _, _, _ = VNMHParser.parse_article_page(html, "https://baotanglichsu.vn/vi/Articles/1001/1/empty.html", "2026-11-09")
    assert doc.validation_status == "QUARANTINED"
    assert any("empty" in r.lower() or "missing" in r.lower() for r in doc.quarantine_reasons)


# --- T-028: Legacy matcher handling missing CSV and NFC normalization ---
def test_t028_legacy_matcher_resilience(sample_parsed_doc):
    # 1. Missing CSV handling
    matcher_missing = LegacyMatcher("/non/existent/path/to/legacy.csv")
    assert matcher_missing.status == "LEGACY_DATA_UNAVAILABLE"
    assert matcher_missing.find_matches(sample_parsed_doc) == []

    # 2. NFC normalization
    text_nfd = unicodedata.normalize("NFD", "Bảo vật quốc gia")
    text_nfc = unicodedata.normalize("NFC", "Bảo vật quốc gia")
    norm_nfd = LegacyMatcher._normalize_text(text_nfd)
    norm_nfc = LegacyMatcher._normalize_text(text_nfc)
    assert norm_nfd == norm_nfc
