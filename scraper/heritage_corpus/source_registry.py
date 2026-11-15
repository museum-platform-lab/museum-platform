"""
Museum Platform - Multi-source Registry (Schema V2)
Defines and registers all primary and expanded cultural heritage sources.
Explicitly marks operational status (OPERATIONAL vs STAGED_NOT_IMPLEMENTED)
to prevent unverified claims.
"""

from typing import Dict, Any, List, Optional
import json
import os
from .models import SourceConfig


DEFAULT_SOURCES: Dict[str, SourceConfig] = {
    "VNMH": SourceConfig(
        source_id="VNMH",
        name="Bảo tàng Lịch sử Quốc gia (Vietnam National Museum of History)",
        base_url="https://baotanglichsu.vn",
        allowed_domains=["baotanglichsu.vn", "www.baotanglichsu.vn"],
        robots_url="https://baotanglichsu.vn/robots.txt",
        rate_limit_delay=1.5,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="PROPRIETARY_OR_EDUCATIONAL_CITATION",
        provenance_tier="OFFICIAL_MUSEUM",
        enabled=True,
        operational_status="OPERATIONAL",
        attribution_required=True
    ),
    "DCH": SourceConfig(
        source_id="DCH",
        name="Cục Di sản văn hóa (Department of Cultural Heritage - Vietnam)",
        base_url="http://dsvh.gov.vn",
        allowed_domains=["dsvh.gov.vn"],
        robots_url="http://dsvh.gov.vn/robots.txt",
        rate_limit_delay=2.0,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="GOVERNMENT_OPEN_INFORMATION",
        provenance_tier="STATE_AUTHORITY",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=True
    ),
    "UNESCO_WH": SourceConfig(
        source_id="UNESCO_WH",
        name="UNESCO World Heritage Centre",
        base_url="https://whc.unesco.org",
        allowed_domains=["whc.unesco.org"],
        robots_url="https://whc.unesco.org/robots.txt",
        rate_limit_delay=2.0,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="UNESCO_OPEN_ACCESS",
        provenance_tier="INTERGOVERNMENTAL",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=True
    ),
    "UNESCO_ICH": SourceConfig(
        source_id="UNESCO_ICH",
        name="UNESCO Intangible Cultural Heritage",
        base_url="https://ich.unesco.org",
        allowed_domains=["ich.unesco.org"],
        robots_url="https://ich.unesco.org/robots.txt",
        rate_limit_delay=2.0,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="UNESCO_OPEN_ACCESS",
        provenance_tier="INTERGOVERNMENTAL",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=True
    ),
    "WIKIDATA": SourceConfig(
        source_id="WIKIDATA",
        name="Wikidata SPARQL / Entity API",
        base_url="https://query.wikidata.org",
        allowed_domains=["query.wikidata.org", "www.wikidata.org"],
        robots_url="https://www.wikidata.org/robots.txt",
        rate_limit_delay=1.0,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="CC0_1.0_UNIVERSAL",
        provenance_tier="CROWDSOURCED_LINKED_DATA",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=False
    ),
    "COMMONS": SourceConfig(
        source_id="COMMONS",
        name="Wikimedia Commons Media Metadata",
        base_url="https://commons.wikimedia.org",
        allowed_domains=["commons.wikimedia.org"],
        robots_url="https://commons.wikimedia.org/robots.txt",
        rate_limit_delay=1.0,
        max_concurrency=1,
        auth_type="NONE",
        license_terms="CREATIVE_COMMONS_VARIOUS",
        provenance_tier="MEDIA_REPOSITORY",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=True
    ),
    "SCHOLARLY": SourceConfig(
        source_id="SCHOLARLY",
        name="Scholarly Archaeological Publications & Metadata",
        base_url="https://openalex.org",
        allowed_domains=["openalex.org", "doi.org"],
        robots_url="https://openalex.org/robots.txt",
        rate_limit_delay=1.5,
        max_concurrency=1,
        auth_type="API_KEY_OR_PUBLIC",
        license_terms="OPEN_ACCESS_RESEARCH",
        provenance_tier="PEER_REVIEWED_RESEARCH",
        enabled=False,
        operational_status="STAGED_NOT_IMPLEMENTED",
        attribution_required=True
    )
}


class SourceRegistry:
    def __init__(self, sources: Optional[Dict[str, SourceConfig]] = None):
        self._sources = sources or dict(DEFAULT_SOURCES)

    def get(self, source_id: str) -> Optional[SourceConfig]:
        return self._sources.get(source_id.upper())

    def list_sources(self) -> List[SourceConfig]:
        return list(self._sources.values())

    def list_enabled(self) -> List[SourceConfig]:
        return [s for s in self._sources.values() if s.enabled and s.operational_status == "OPERATIONAL"]

    def to_json(self) -> str:
        data = {k: s.__dict__ for k, s in self._sources.items()}
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save_to_file(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())
