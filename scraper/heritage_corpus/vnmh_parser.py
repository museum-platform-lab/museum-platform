"""
Museum Platform - VNMH Parser (V2 Hardened)
Extracts clean, structured heritage documents, metadata, sections, media,
and links with exact span provenance, leaf-node DOM traversal,
and anchored metadata extraction.
"""

import hashlib
import re
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple, Set
from bs4 import BeautifulSoup, Tag, NavigableString

from .models import (
    ParsedDocument, DocumentSection, DocumentLink, MediaMetadata,
    MetadataEvidence
)
from .url_normalizer import URLNormalizer


BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote"}
STOPWORDS_VI_EN = {"từ", "của", "và", "the", "of", "and", "in", "at", "s", "a", "an"}


class VNMHParser:
    PARSER_VERSION = "vnmh_v2"

    @classmethod
    def extract_clean_text(cls, html_text: str) -> str:
        """Extracts clean leaf-node block text without DOM ancestor duplication."""
        soup = BeautifulSoup(html_text, "html.parser")
        for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        detail = soup.find(class_=re.compile(r"content|detail|article", re.I)) or soup.body or soup
        blocks = cls._extract_leaf_blocks(detail)
        return "\n".join(blocks)

    @classmethod
    def parse_article_page(cls, raw_html: str, url: str, retrieved_at: str):
        return cls.parse_article(raw_html, url, retrieved_at)

    @classmethod
    def parse_article(
        cls,
        raw_html: str,
        url: str,
        retrieved_at: str
    ) -> Tuple[ParsedDocument, List[DocumentSection], List[DocumentLink], List[MediaMetadata]]:
        canonical_url = URLNormalizer.normalize_url(url) or url
        path_info = URLNormalizer.parse_vnmh_path(canonical_url)
        doc_id = URLNormalizer.get_stable_id(canonical_url, source_id="VNMH")
        language = path_info.get("language", "vi")

        content_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Clean out scripts, styles, iframes
        for unwanted in soup.find_all(["script", "style", "noscript", "iframe"]):
            unwanted.decompose()

        # 2. Title extraction
        title = ""
        h2_header = soup.find("h2", class_=lambda c: c and "page-header" in str(c))
        if h2_header:
            title = h2_header.get_text().strip()
        elif soup.find("h2"):
            title = soup.find("h2").get_text().strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # 3. Breadcrumbs
        breadcrumbs = []
        bc_ol = soup.find("ol", class_="breadcrumb")
        if bc_ol:
            for li in bc_ol.find_all("li"):
                text = li.get_text().strip()
                if text:
                    breadcrumbs.append(text)

        category_name = breadcrumbs[-1] if len(breadcrumbs) > 1 else path_info.get("category_slug")
        category_id = path_info.get("category_id")

        # 4. Publication Date, Time, View Count
        published_at = None
        view_count = None
        stat_div = soup.find("div", class_="blogpost-stat")
        if stat_div:
            stat_text = stat_div.get_text()
            date_m = re.search(r"(\d{2}/\d{2}/\d{4})", stat_text)
            time_m = re.search(r"(\d{2}:\d{2})", stat_text)
            if date_m:
                d_str = date_m.group(1)
                day, month, year = d_str.split("/")
                t_str = time_m.group(1) if time_m else "00:00"
                published_at = f"{year}-{month}-{day}T{t_str}:00"

            eye_icon = stat_div.find("i", class_=lambda c: c and "eye" in str(c))
            if eye_icon and eye_icon.next_sibling:
                val = str(eye_icon.next_sibling).strip()
                val_m = re.search(r"\d+", val)
                if val_m:
                    view_count = int(val_m.group(0))

        # 5. Summary / Abstract
        summary_abstract = ""
        abs_div = soup.find("div", class_="article-abstracts")
        if abs_div:
            summary_abstract = abs_div.get_text(separator=" ", strip=True)

        # 6. Source Attribution
        source_attribution = "Bảo tàng Lịch sử quốc gia"
        src_div = soup.find("div", class_="article-source")
        if src_div:
            src_txt = src_div.get_text(separator=" ", strip=True)
            if src_txt:
                source_attribution = src_txt

        # 7. Main Article Detail
        detail_div = soup.find("div", class_=lambda c: c and ("article-detail" in str(c) or "content-detail" in str(c))) or soup.find("div", class_="article-detail")
        quarantine_reasons = []
        validation_status = "VALIDATED"

        if not detail_div:
            validation_status = "PARSE_FAILED"
            quarantine_reasons.append("MISSING_ARTICLE_DETAIL_CONTAINER")

        # Extract Leaf Blocks to eliminate P2-19 ancestor-descendant text duplication
        leaf_blocks: List[str] = []
        if detail_div:
            leaf_blocks = cls._extract_leaf_blocks(detail_div)

        canonical_clean_text = "\n\n".join(leaf_blocks)

        if len(canonical_clean_text.strip()) < 30 and validation_status == "VALIDATED":
            validation_status = "QUARANTINED"
            quarantine_reasons.append("INSUFFICIENT_BODY_LENGTH")

        # Extract Author at the end of detail (right-aligned signature)
        author = None
        if detail_div:
            paras = detail_div.find_all("p")
            if paras:
                for p in reversed(paras[-3:]):
                    align = (p.get("align") or "").lower()
                    style = (p.get("style") or "").lower()
                    p_txt = p.get_text().strip()
                    if ("right" in align or "text-align: right" in style) and 0 < len(p_txt) < 80:
                        if not re.search(r"\d{2}/\d{2}/\d{4}", p_txt) and "nguồn" not in p_txt.lower():
                            author = p_txt
                            break

        # 8. Anchored Metadata Field Extraction (Fixes P1-12)
        metadata_fields, metadata_evidence = cls._extract_metadata_fields(
            detail_div, canonical_clean_text, language
        )

        # 9. Extract Media & Links
        media: List[MediaMetadata] = []
        links: List[DocumentLink] = []

        if detail_div:
            media = cls._extract_media(detail_div, doc_id, canonical_url)
            links = cls._extract_links(detail_div, doc_id, canonical_url)

        # 10. Document Classification
        classification = cls._classify_document(title, category_name or "", canonical_clean_text, metadata_fields)

        # 11. Build Initial Section Hierarchy
        initial_sections = cls._build_initial_sections(
            doc_id, title, summary_abstract, canonical_clean_text,
            language, source_attribution, metadata_fields
        )

        parsed_doc = ParsedDocument(
            doc_id=doc_id,
            source_id="VNMH",
            canonical_url=canonical_url,
            original_url=url,
            language=language,
            title=title,
            canonical_clean_text=canonical_clean_text,
            author=author,
            published_at=published_at,
            updated_at=None,
            view_count=view_count,
            category_id=category_id,
            category_name=category_name,
            breadcrumbs=breadcrumbs,
            summary_abstract=summary_abstract,
            content_text=canonical_clean_text,
            classification=classification,
            metadata_fields=metadata_fields,
            metadata_evidence=metadata_evidence,
            heading_hierarchy=[],
            content_hash=content_hash,
            retrieved_at=retrieved_at,
            parser_version=cls.PARSER_VERSION,
            validation_status=validation_status,
            quarantine_reasons=quarantine_reasons,
            copyright_status="RESERVED_CITATION_PERMITTED",
            reuse_terms="Scholarly citation with provenance attribution"
        )

        return parsed_doc, initial_sections, links, media

    @classmethod
    def _extract_leaf_blocks(cls, container: Tag) -> List[str]:
        """
        P2-19 Fix: Traverses only leaf block elements.
        If a block tag contains child block tags, its own text is NOT extracted directly.
        Only innermost leaf blocks are extracted, preventing duplicate text concatenation.
        """
        leaves: List[str] = []

        def recurse(node: Tag):
            if not isinstance(node, Tag):
                return
            # If node is a block tag and has no child block tags
            has_child_blocks = any(c.name in BLOCK_TAGS for c in node.find_all(BLOCK_TAGS))
            if node.name in BLOCK_TAGS and not has_child_blocks:
                text = node.get_text(separator=" ", strip=True)
                if text and len(text) > 1:
                    leaves.append(text)
            else:
                for child in node.children:
                    if isinstance(child, Tag):
                        recurse(child)

        recurse(container)
        # If no leaf block elements were found (e.g. bare text with <br>), extract stripped paragraphs
        if not leaves:
            for line in container.get_text(separator="\n", strip=True).splitlines():
                line = line.strip()
                if line and len(line) > 1:
                    leaves.append(line)

        return leaves

    @classmethod
    def _extract_metadata_fields(
        cls,
        detail_div: Optional[Tag],
        canonical_text: str,
        language: str
    ) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """
        P1-12 Fix: Anchored metadata extraction with validation and evidence quotes.
        Prevents false positives like English "materials" -> "s" or era_culture -> "từ".
        """
        fields: Dict[str, Any] = {}
        evidence: Dict[str, Dict[str, Any]] = {}

        if not detail_div or not canonical_text:
            return fields, evidence

        # Helper to find exact offsets in canonical_text
        def find_offsets(sub: str) -> Tuple[int, int]:
            idx = canonical_text.find(sub)
            if idx != -1:
                return idx, idx + len(sub)
            return 0, 0

        # 1. Registration Number (LSb. or LSa.)
        reg_match = re.search(
            r"(?:Số\s+đăng\s+ký|SĐK|Registration\s+(?:No|Number))\s*[:：]?\s*(LS[ab]\.?\s*\d+[A-Za-z0-9\-_/]*|[A-Za-z0-9\.\-_/]+)",
            canonical_text, re.IGNORECASE
        )
        if reg_match:
            val = reg_match.group(1).strip()
            # Must look like an accession code, not prose
            if len(val) >= 3 and not any(w in val.lower() for w in ["chất", "kích", "niên", "được"]):
                fields["registration_number"] = val
                start, end = find_offsets(reg_match.group(0))
                evidence["registration_number"] = MetadataEvidence(
                    field_name="registration_number",
                    value=val,
                    raw_evidence_quote=reg_match.group(0),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        # 2. Material (must be anchored to label, not ordinary word 'materials')
        mat_match = re.search(
            r"(?:^|\n|\r)(?:Chất\s+liệu|Material)\s*[:：]\s*([^\n\r\.\;]+)",
            canonical_text, re.IGNORECASE
        )
        if mat_match:
            raw_val = mat_match.group(1).strip()
            # Reject if single character like 's', or stopword
            if len(raw_val) > 1 and raw_val.lower() not in STOPWORDS_VI_EN:
                fields["material"] = raw_val
                start, end = find_offsets(mat_match.group(0))
                evidence["material"] = MetadataEvidence(
                    field_name="material",
                    value=raw_val,
                    raw_evidence_quote=mat_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        # 3. Dimensions (Multiline support: captures mouth, base, height, units)
        dim_match = re.search(
            r"(?:^|\n|\r)(?:Kích\s+thước|Dimensions?|Size)\s*[:：]?\s*([^\n\r]+(?:\n+[ \t]*[-–•*]\s*[^\n\r]+)*)",
            canonical_text, re.IGNORECASE
        )
        if not dim_match:
            # Fallback if dimension bullet lines start immediately on next line
            dim_match = re.search(
                r"(?:^|\n|\r)(?:Kích\s+thước|Dimensions?|Size)\s*[:：]?\s*\n+([ \t]*[-–•*]\s*[^\n\r]+(?:\n+[ \t]*[-–•*]\s*[^\n\r]+)*)",
                canonical_text, re.IGNORECASE
            )
        if dim_match:
            dim_val = dim_match.group(1).strip()
            # Clean up into readable single string
            clean_dim = " ".join([l.strip() for l in dim_val.splitlines() if l.strip()])
            if len(clean_dim) > 2 and any(u in clean_dim.lower() for u in ["cm", "mm", "m", "cao", "đường kính", "dài", "rộng"]):
                fields["dimensions"] = clean_dim
                start, end = find_offsets(dim_match.group(0))
                evidence["dimensions"] = MetadataEvidence(
                    field_name="dimensions",
                    value=clean_dim,
                    raw_evidence_quote=dim_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_MULTILINE"
                ).to_dict()

        # 4. Era / Culture (reject dangling prepositions like 'từ')
        era_match = re.search(
            r"(?:^|\n|\r)(?:Niên\s+đại|Văn\s+hóa|Period|Culture|Era)\s*[:：]\s*([^\n\r\.\;]+)",
            canonical_text, re.IGNORECASE
        )
        if era_match:
            era_val = era_match.group(1).strip()
            if len(era_val) >= 4 and era_val.lower() not in STOPWORDS_VI_EN:
                fields["era_culture"] = era_val
                start, end = find_offsets(era_match.group(0))
                evidence["era_culture"] = MetadataEvidence(
                    field_name="era_culture",
                    value=era_val,
                    raw_evidence_quote=era_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        # 5. Recognition Decree (Quyết định công nhận / QĐ-TTg)
        decree_match = re.search(
            r"(?:Quyết\s+định(?:\s+công\s+nhận)?(?:\s+số)?|Decision)\s*[:：]?\s*(\d+/[A-Za-z0-9\-_]+[^\n\r\.\;]*)",
            canonical_text, re.IGNORECASE
        )
        if decree_match:
            dec_val = decree_match.group(1).strip()
            if len(dec_val) >= 5:
                fields["recognition_decree"] = dec_val
                start, end = find_offsets(decree_match.group(0))
                evidence["recognition_decree"] = MetadataEvidence(
                    field_name="recognition_decree",
                    value=dec_val,
                    raw_evidence_quote=decree_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        # 6. Discovery Location
        disc_match = re.search(
            r"(?:(?:được\s+)?phát\s+hiện\s+tại|(?:được\s+)?tìm\s+thấy\s+tại|Địa\s+điểm\s+phát\s+hiện|Discovered\s+at)\s*[:：]?\s*([^\n\r\.\;]+)",
            canonical_text, re.IGNORECASE
        )
        if disc_match:
            loc_val = disc_match.group(1).strip()
            if len(loc_val) >= 4 and not any(k in loc_val.lower() for k in ["bảo tàng", "museum"]):
                fields["discovery_location"] = loc_val
                start, end = find_offsets(disc_match.group(0))
                evidence["discovery_location"] = MetadataEvidence(
                    field_name="discovery_location",
                    value=loc_val,
                    raw_evidence_quote=disc_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        # 7. Explicit Storage Location (Must be explicitly stated in body)
        store_match = re.search(
            r"(?:hiện\s+lưu\s+giữ\s+tại|đang\s+lưu\s+giữ\s+tại|lưu\s+giữ\s+tại|trưng\s+bày\s+tại|Currently\s+held\s+at)\s*[:：]?\s*([^\n\r\.\;]+)",
            canonical_text, re.IGNORECASE
        )
        if store_match:
            store_val = store_match.group(1).strip()
            if len(store_val) >= 4:
                fields["storage_location"] = store_val
                start, end = find_offsets(store_match.group(0))
                evidence["storage_location"] = MetadataEvidence(
                    field_name="storage_location",
                    value=store_val,
                    raw_evidence_quote=store_match.group(0).strip(),
                    char_start=start,
                    char_end=end,
                    extraction_method="ANCHORED_LABEL_REGEX"
                ).to_dict()

        return fields, evidence

    @classmethod
    def _extract_media(cls, detail_div: Tag, doc_id: str, canonical_url: str) -> List[MediaMetadata]:
        media: List[MediaMetadata] = []
        img_index = 0

        for img in detail_div.find_all("img"):
            img_src = img.get("src")
            if not img_src:
                continue
            img_index += 1
            norm_img_url = urllib.parse.urljoin(canonical_url, img_src)
            alt_text = (img.get("alt") or "").strip()
            caption_text = ""

            # Check direct parent if center-aligned
            parent = img.parent
            if parent and parent.name in ("p", "div"):
                align = (parent.get("align") or "").lower()
                if "center" in align:
                    caption_text = parent.get_text(separator=" ", strip=True)

            # Check immediate next sibling
            if not caption_text and parent:
                next_sib = parent.find_next_sibling()
                if next_sib and next_sib.name in ("p", "div"):
                    sib_align = (next_sib.get("align") or "").lower()
                    if "center" in sib_align or next_sib.find("em"):
                        caption_text = next_sib.get_text(separator=" ", strip=True)

            media.append(MediaMetadata(
                media_id=f"{doc_id}-MED-{img_index:03d}",
                doc_id=doc_id,
                media_type="IMAGE",
                source_url=img_src,
                normalized_url=norm_img_url,
                alt_text=alt_text,
                caption=caption_text,
                placement_section="article-detail",
                copyright_status="UNKNOWN_PENDING_VERIFICATION",
                license_evidence_url=None,
                attribution_required=True,
                rights_holder="Bảo tàng Lịch sử quốc gia",
                download_permitted=False
            ))

        return media

    @classmethod
    def _extract_links(cls, detail_div: Tag, doc_id: str, canonical_url: str) -> List[DocumentLink]:
        links: List[DocumentLink] = []
        link_index = 0

        for a_tag in detail_div.find_all("a", href=True):
            href = a_tag["href"].strip()
            anchor = a_tag.get_text(separator=" ", strip=True)
            if not href:
                continue
            link_index += 1
            norm_href = urllib.parse.urljoin(canonical_url, href)
            link_type = "EXTERNAL_REFERENCE"
            if "baotanglichsu.vn" in norm_href:
                link_type = "INTERNAL_ARTICLE" if norm_href.endswith(".html") else "INTERNAL_LINK"

            links.append(DocumentLink(
                link_id=f"{doc_id}-LNK-{link_index:03d}",
                source_doc_id=doc_id,
                target_url=href,
                target_canonical_url=norm_href,
                anchor_text=anchor,
                link_type=link_type
            ))

        return links

    @classmethod
    def _build_initial_sections(
        cls,
        doc_id: str,
        title: str,
        summary: str,
        canonical_text: str,
        language: str,
        source_attribution: str,
        metadata_fields: Dict[str, Any]
    ) -> List[DocumentSection]:
        """
        Builds initial logical sections with exact slicing against canonical_text.
        """
        sections: List[DocumentSection] = []
        sec_idx = 0

        # Section 1: Abstract / Lead (offset against summary_abstract)
        if summary:
            sec_idx += 1
            sections.append(DocumentSection(
                section_id=f"{doc_id}-SEC-{sec_idx:03d}",
                doc_id=doc_id,
                source_id="VNMH",
                heading_path=[title, "Tóm tắt" if language == "vi" else "Abstract"],
                heading_level=2,
                section_text=summary,
                offset_source="summary_abstract",
                char_start=0,
                char_end=len(summary),
                language=language,
                temporal_context=metadata_fields.get("era_culture"),
                source_attribution=source_attribution,
                index_eligibility=len(summary.strip()) >= 20
            ))

        # Section 2+: Body paragraphs (exact slices of canonical_clean_text)
        if canonical_text:
            cursor = 0
            paragraphs = canonical_text.split("\n\n")
            current_cluster: List[str] = []
            cluster_start = 0

            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    cursor += len(p) + 2
                    continue

                p_start = canonical_text.find(p_clean, cursor)
                if p_start == -1:
                    p_start = cursor
                p_end = p_start + len(p_clean)

                if not current_cluster:
                    cluster_start = p_start
                    current_cluster.append(p_clean)
                else:
                    current_cluster.append(p_clean)

                cluster_text = "\n\n".join(current_cluster)
                # Cluster threshold ~800 chars
                if len(cluster_text) >= 800:
                    sec_idx += 1
                    cluster_end = cluster_start + len(cluster_text)
                    sections.append(DocumentSection(
                        section_id=f"{doc_id}-SEC-{sec_idx:03d}",
                        doc_id=doc_id,
                        source_id="VNMH",
                        heading_path=[title, "Nội dung chính" if language == "vi" else "Main Content"],
                        heading_level=3,
                        section_text=cluster_text,
                        offset_source="canonical_clean_text",
                        char_start=cluster_start,
                        char_end=cluster_end,
                        language=language,
                        temporal_context=metadata_fields.get("era_culture"),
                        source_attribution=source_attribution,
                        index_eligibility=True
                    ))
                    current_cluster = []
                    cluster_start = p_end + 2

                cursor = p_end + 2

            if current_cluster:
                sec_idx += 1
                cluster_text = "\n\n".join(current_cluster)
                cluster_end = cluster_start + len(cluster_text)
                sections.append(DocumentSection(
                    section_id=f"{doc_id}-SEC-{sec_idx:03d}",
                    doc_id=doc_id,
                    source_id="VNMH",
                    heading_path=[title, "Nội dung chính" if language == "vi" else "Main Content"],
                    heading_level=3,
                    section_text=cluster_text,
                    offset_source="canonical_clean_text",
                    char_start=cluster_start,
                    char_end=cluster_end,
                    language=language,
                    temporal_context=metadata_fields.get("era_culture"),
                    source_attribution=source_attribution,
                    index_eligibility=True
                ))

        return sections

    @classmethod
    def _classify_document(cls, title: str, category_name: str, content: str, meta: Dict[str, Any]) -> str:
        combined = f"{title} {category_name}".lower()
        if meta.get("registration_number") or "bảo vật quốc gia" in combined or "national treasure" in combined:
            return "ARTIFACT_PROFILE"
        if any(k in combined for k in ["trưng bày", "exhibition", "chuyên đề"]):
            return "EXHIBITION_NOTICE"
        if any(k in combined for k in ["khảo cổ", "chuyên khảo", "nghiên cứu", "archaeology", "monograph", "research"]):
            return "RESEARCH_ARTICLE"
        if any(k in combined for k in ["tin tức", "hoạt động", "hội thảo", "news", "activity", "conference"]):
            return "NEWS_EVENT"
        if any(k in combined for k in ["ấn phẩm", "tạp chí", "sách", "publication", "book"]):
            return "PUBLICATION_SUMMARY"
        if any(k in combined for k in ["em yêu lịch sử", "clb", "giáo dục", "education"]):
            return "EDUCATIONAL_RESOURCE"
        return "GENERAL_HERITAGE_DOCUMENT"

    @classmethod
    def extract_hub_links(cls, raw_html: str, current_url: str) -> Dict[str, List[str]]:
        soup = BeautifulSoup(raw_html, "html.parser")
        canonical_current = URLNormalizer.normalize_url(current_url) or current_url

        articles: List[str] = []
        paginations: List[str] = []
        categories: List[str] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            norm = URLNormalizer.normalize_url(href, base_url=canonical_current)
            if not norm:
                continue
            parsed = URLNormalizer.parse_vnmh_path(norm)
            ptype = parsed["page_type"]

            if ptype == "ARTICLE":
                if norm not in articles:
                    articles.append(norm)
            elif ptype == "PAGINATION":
                if norm not in paginations:
                    paginations.append(norm)
            elif ptype in ("CATEGORY_HUB", "ALBUM"):
                if norm not in categories:
                    categories.append(norm)

        return {
            "articles": articles,
            "paginations": paginations,
            "categories": categories
        }
