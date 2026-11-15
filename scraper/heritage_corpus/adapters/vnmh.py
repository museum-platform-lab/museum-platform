"""
Museum Platform - VNMH Adapter (National Museum of History)
Handles discovery across Vietnamese and English sections, pagination traversal,
XML sitemap ingestion, and article dispatching.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from .base import BaseSourceAdapter
from ..models import SourceConfig, ParsedDocument, DocumentSection, DocumentLink, MediaMetadata
from ..url_normalizer import URLNormalizer
from ..vnmh_parser import VNMHParser


class VNMHAdapter(BaseSourceAdapter):
    DEFAULT_SEEDS = [
        "https://baotanglichsu.vn/vi",
        "https://baotanglichsu.vn/en",
        "https://baotanglichsu.vn/Sitemap.aspx"
    ]

    def __init__(self, config: Optional[SourceConfig] = None):
        if not config:
            from ..source_registry import DEFAULT_SOURCES
            config = DEFAULT_SOURCES["VNMH"]
        super().__init__(config)

    def parse_sitemap(self, xml_content: str) -> List[str]:
        """
        Parses Sitemap.aspx to discover official category hubs.
        """
        discovered_urls: List[str] = []
        try:
            root = ET.fromstring(xml_content.encode("utf-8"))
            for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if elem.text:
                    url = elem.text.strip()
                    norm = URLNormalizer.normalize_url(url)
                    if norm and norm not in discovered_urls:
                        discovered_urls.append(norm)
        except Exception:
            # Fallback to regex if XML parse fails
            import re
            locs = re.findall(r"<loc>(.*?)</loc>", xml_content)
            for loc in locs:
                norm = URLNormalizer.normalize_url(loc.strip())
                if norm and norm not in discovered_urls:
                    discovered_urls.append(norm)
        return discovered_urls

    def discover_nav_categories(self, homepage_html: str, base_url: str) -> List[str]:
        """
        Extracts all category and section URLs from navigation bars and menus.
        """
        soup = BeautifulSoup(homepage_html, "html.parser")
        categories: List[str] = []

        nav = soup.find("nav")
        if nav:
            for a in nav.find_all("a", href=True):
                norm = URLNormalizer.normalize_url(a["href"], base_url=base_url)
                if norm and norm not in categories:
                    parsed = URLNormalizer.parse_vnmh_path(norm)
                    if parsed["page_type"] in ("CATEGORY_HUB", "ALBUM"):
                        categories.append(norm)
        return categories

    def extract_links_from_page(self, raw_html: str, current_url: str) -> Dict[str, List[str]]:
        """
        Extracts all article, pagination, and category links from an arbitrary page.
        """
        return VNMHParser.extract_hub_links(raw_html, current_url)

    def parse_article_page(self, raw_html: str, url: str, retrieved_at: str) -> Tuple[ParsedDocument, List[DocumentSection], List[DocumentLink], List[MediaMetadata]]:
        return VNMHParser.parse_article(raw_html, url, retrieved_at)
