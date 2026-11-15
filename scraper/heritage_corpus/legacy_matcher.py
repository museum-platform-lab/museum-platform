"""
Museum Platform - Legacy Dataset Entity Matcher
Matches newly discovered museum evidence documents with existing production
artifact dataset (crawled_artifacts_production.csv, 6254 records) without
modifying production files. Preserves N-N relationships.
"""

import os
import csv
import re
import unicodedata
from typing import List, Dict, Any, Optional
from .models import ParsedDocument, EntityMatchCandidate


class LegacyMatcher:
    def __init__(self, production_csv_path: Optional[str] = None):
        if not production_csv_path:
            # Default to existing scraper/crawled_artifacts_production.csv
            production_csv_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "crawled_artifacts_production.csv"
            )
        self.production_csv_path = production_csv_path
        self.legacy_records: List[Dict[str, Any]] = []
        self.status: str = "INITIALIZED"  # LOADED, LEGACY_DATA_UNAVAILABLE, EMPTY
        self._load_legacy_dataset()

    def _load_legacy_dataset(self):
        if not os.path.exists(self.production_csv_path):
            self.status = "LEGACY_DATA_UNAVAILABLE"
            return

        try:
            with open(self.production_csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                raw_headers = next(reader, None)
                if not raw_headers:
                    self.status = "EMPTY"
                    return
                headers = [unicodedata.normalize("NFC", h.strip('" \ufeff')) for h in raw_headers]
                for row_vals in reader:
                    if not row_vals or len(row_vals) < len(headers):
                        continue
                    row = dict(zip(headers, row_vals))
                    try:
                        row_id = int(row.get("ID") or 0)
                    except ValueError:
                        continue
                    name = unicodedata.normalize("NFC", row.get("Name") or "")
                    desc = unicodedata.normalize("NFC", row.get("Description") or "")
                    era = unicodedata.normalize("NFC", row.get("Artifact Era") or "")
                    loc = unicodedata.normalize("NFC", row.get("Location") or "")

                    # Extract registration numbers if present in text
                    reg_nums = re.findall(r"LS[ab]\.?\s*\d+", f"{name} {desc}", re.IGNORECASE)
                    reg_cleaned = [re.sub(r"\s+", "", r.upper()) for r in reg_nums]

                    self.legacy_records.append({
                        "id": row_id,
                        "name": name,
                        "clean_name": self._normalize_text(name),
                        "era": era,
                        "location": loc,
                        "reg_numbers": set(reg_cleaned),
                        "full_text": f"{name} {desc} {era} {loc}".lower()
                    })
            self.status = "LOADED" if self.legacy_records else "EMPTY"
        except Exception:
            self.status = "LEGACY_DATA_UNAVAILABLE"

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    GENERIC_NAMES = {"bao vat quoc gia", "di tich quoc gia", "di tich lich su", "bao tang lich su"}
    STOP_WORDS = {"dong", "go", "da", "gom", "su", "bang", "thoi", "cua", "tai", "o"}

    def find_matches(self, doc: ParsedDocument) -> List[EntityMatchCandidate]:
        if self.status != "LOADED" or not self.legacy_records:
            return []

        candidates: List[EntityMatchCandidate] = []
        meta = doc.metadata_fields
        doc_reg = meta.get("registration_number")
        doc_reg_clean = re.sub(r"\s+", "", doc_reg.upper()) if doc_reg else None

        # Strip generic prefixes like 'Bảo vật quốc gia:'
        clean_title = re.sub(
            r"^(?:bảo\s+vật\s+quốc\s+gia|national\s+treasure|hiện\s+vật|di\s+tích)\s*[:\-\–]?\s*",
            "", doc.title, flags=re.IGNORECASE
        ).strip()
        doc_title_norm = self._normalize_text(clean_title)
        doc_tokens = set(doc_title_norm.split()) - self.STOP_WORDS

        decree = meta.get("recognition_decree") or ""
        era = meta.get("era_culture") or ""

        cand_idx = 0
        for leg in self.legacy_records:
            score = 0.0
            criteria = []
            notes = []

            leg_name_norm = leg["clean_name"]
            # Ignore generic list pages
            if leg_name_norm in self.GENERIC_NAMES:
                continue

            # 1. Registration Number Match (High confidence)
            if doc_reg_clean:
                if doc_reg_clean in leg["reg_numbers"] or doc_reg_clean.lower() in leg["full_text"]:
                    score = 0.98
                    criteria.append("REGISTRATION_NUMBER")
                    notes.append(f"Khớp số đăng ký hiện vật {doc_reg}")

            # 2. National Treasure Recognition Decree Match
            if decree and decree.lower() in leg["full_text"]:
                score = max(score, 0.85)
                criteria.append("RECOGNITION_DECREE")
                notes.append(f"Khớp quyết định công nhận {decree}")

            # 3. Name & Era Multi-Attribute Verification (Never name alone!)
            leg_tokens = set(leg_name_norm.split()) - self.STOP_WORDS
            token_overlap = doc_tokens & leg_tokens
            overlap_ratio = len(token_overlap) / max(len(doc_tokens), 1)

            if overlap_ratio >= 0.66 or leg_name_norm in doc_title_norm or doc_title_norm in leg_name_norm:
                era_overlap = any(w in leg["full_text"] for w in era.lower().split() if len(w) > 3)
                if era_overlap:
                    multi_score = 0.85
                    if multi_score > score:
                        score = multi_score
                    criteria.append("NAME_AND_ERA_CONSISTENCY")
                    notes.append(f"Trùng tên '{leg['name']}' và tương đồng niên đại '{era}'")
                elif doc.classification == "ARTIFACT_PROFILE" and len(token_overlap) >= 2:
                    multi_score = 0.75
                    if multi_score > score:
                        score = multi_score
                    criteria.append("ARTIFACT_NAME_OVERLAP")
                    notes.append(f"Khớp danh xưng hiện vật '{leg['name']}'")

            if score >= 0.70:
                cand_idx += 1
                candidates.append(EntityMatchCandidate(
                    candidate_id=f"{doc.doc_id}-MAT-{cand_idx:02d}",
                    vnmh_doc_id=doc.doc_id,
                    vnmh_title=doc.title,
                    vnmh_registration_num=doc_reg,
                    legacy_artifact_id=leg["id"],
                    legacy_name=leg["name"],
                    match_criteria=" + ".join(criteria),
                    confidence_score=score,
                    review_status="PENDING_REVIEW",
                    evidence_notes="; ".join(notes)
                ))

        return candidates
