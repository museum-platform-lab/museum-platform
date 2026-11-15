"""
Museum Platform - URL Normalizer for National Museum of History (VNMH) (Hardened V2)
Handles canonicalization, deduplication, path parsing, language detection,
scope filtering, and alias resolution.
"""

import ipaddress
import re
import urllib.parse
from typing import Optional, Tuple, Dict, Any, List

ALLOWED_HOSTS = {"baotanglichsu.vn", "www.baotanglichsu.vn"}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


class URLNormalizer:
    @classmethod
    def is_safe_host(cls, url_or_host: str, allowed_domains: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Checks if host is safe from SSRF and within allowed domains if specified."""
        if not url_or_host:
            return False, "Empty host"
        parsed = urllib.parse.urlparse(url_or_host)
        host = (parsed.netloc or parsed.path).split(":")[0].lower().strip(".")
        if host in ("localhost", "127.0.0.1", "::1"):
            return False, "Loopback host blocked"
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"Private/reserved IP blocked: {ip}"
        except ValueError:
            pass
        if allowed_domains:
            if not any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed_domains):
                return False, f"Host {host} not in allowed domains"
        return True, "Safe"

    @staticmethod
    def is_safe_url(url: str) -> bool:
        """Checks for loopback, private IPs, credentials, or dangerous schemes."""
        if not url:
            return False
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.netloc.split(":")[0].lower().strip(".")
        if host in ("localhost", "127.0.0.1", "::1"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass
        return True

    @classmethod
    def normalize_url(cls, url: str, base_url: str = "https://baotanglichsu.vn") -> Optional[str]:
        """
        Normalizes a URL to its canonical form:
        - Resolves relative links against base_url
        - Normalizes scheme to https and host to canonical host
        - Strips fragments (#...)
        - Strips tracking parameters
        - Strips trailing slash unless root path
        - Rejects credentials, private IPs, and external links
        """
        if not url:
            return None

        url = url.strip()
        if url.startswith("javascript:") or url.startswith("mailto:") or url.startswith("tel:"):
            return None

        full_url = urllib.parse.urljoin(base_url, url)
        if not cls.is_safe_url(full_url):
            return None

        parsed = urllib.parse.urlparse(full_url)
        host = (parsed.hostname or parsed.netloc.split(":")[0]).lower()
        if host not in ALLOWED_HOSTS:
            return None

        canonical_host = "baotanglichsu.vn"
        canonical_scheme = "https"

        # Clean query parameters
        clean_query = ""
        if parsed.query:
            query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
            filtered_pairs = [(k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS]
            if filtered_pairs:
                clean_query = urllib.parse.urlencode(filtered_pairs)

        # Normalize path
        path = parsed.path
        if not path:
            path = "/"
        elif len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # Filter out infinite loops, calendars, search, action=edit
        path_lower = path.lower()
        if "/search" in path_lower or "/calendar" in path_lower or "action=edit" in clean_query:
            return None

        reconstructed = f"{canonical_scheme}://{canonical_host}{path}"
        if clean_query:
            reconstructed += f"?{clean_query}"

        return reconstructed

    @staticmethod
    def parse_vnmh_path(url: str) -> Dict[str, Any]:
        """
        Parses VNMH specific path structures:
        - /{lang}/Articles/{cat_id}/{cat_slug}
        - /{lang}/Articles/{cat_id}/{cat_slug}/Page{n}
        - /{lang}/Articles/{cat_id}/{art_id}/{art_slug}.html
        - /{lang}/Album/{album_id}/{album_slug}
        """
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        info: Dict[str, Any] = {
            "is_valid_vnmh": False,
            "language": "vi",
            "page_type": "UNKNOWN",  # HOMEPAGE, CATEGORY_HUB, PAGINATION, ARTICLE, ALBUM
            "category_id": None,
            "category_slug": None,
            "page_number": 1,
            "article_id": None,
            "article_slug": None,
            "stable_doc_id": None
        }

        # Detect language
        if path.startswith("/en") or "/en/" in path:
            info["language"] = "en"
        elif path.startswith("/vi") or "/vi/" in path:
            info["language"] = "vi"
        else:
            return info

        info["is_valid_vnmh"] = True

        # Check for Homepage
        if path.rstrip("/") in ("/vi", "/en"):
            info["page_type"] = "HOMEPAGE"
            return info

        # Regex for Article: /{lang}/Articles/{cat_id}/{art_id}/{slug}.html
        article_match = re.match(r"^/(vi|en)/Articles/(\d+)/(\d+)/([^/]+)\.html$", path, re.IGNORECASE)
        if article_match:
            info["language"] = article_match.group(1).lower()
            info["category_id"] = article_match.group(2)
            info["article_id"] = article_match.group(3)
            info["article_slug"] = article_match.group(4)
            info["page_type"] = "ARTICLE"
            # Stable identity is keyed on source + lang + cat_id + art_id, immune to slug changes
            info["stable_doc_id"] = f"VNMH-{info['language'].upper()}-{info['category_id']}-{info['article_id']}"
            return info

        # Regex for Pagination: /{lang}/Articles/{cat_id}/{cat_slug}/Page(\d+)
        pagination_match = re.match(r"^/(vi|en)/Articles/(\d+)/([^/]+)/Page(\d+)$", path, re.IGNORECASE)
        if pagination_match:
            info["language"] = pagination_match.group(1).lower()
            info["category_id"] = pagination_match.group(2)
            info["category_slug"] = pagination_match.group(3)
            info["page_number"] = int(pagination_match.group(4))
            info["page_type"] = "PAGINATION"
            return info

        # Regex for Category Hub: /{lang}/Articles/{cat_id}/{cat_slug}
        category_match = re.match(r"^/(vi|en)/Articles/(\d+)/([^/]+)$", path, re.IGNORECASE)
        if category_match:
            info["language"] = category_match.group(1).lower()
            info["category_id"] = category_match.group(2)
            info["category_slug"] = category_match.group(3)
            info["page_number"] = 1
            info["page_type"] = "CATEGORY_HUB"
            return info

        # Regex for Album: /{lang}/Album/{album_id}/{album_slug}
        album_match = re.match(r"^/(vi|en)/Album/(\d+)/([^/]+)$", path, re.IGNORECASE)
        if album_match:
            info["language"] = album_match.group(1).lower()
            info["category_id"] = album_match.group(2)
            info["category_slug"] = album_match.group(3)
            info["page_type"] = "ALBUM"
            return info

        info["page_type"] = "OTHER_INTERNAL"
        return info

    @classmethod
    def get_stable_id(cls, url: str, source_id: str = "VNMH") -> str:
        parsed_info = cls.parse_vnmh_path(url)
        if parsed_info["stable_doc_id"]:
            return parsed_info["stable_doc_id"]
        import hashlib
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        lang = parsed_info["language"].upper()
        return f"{source_id}-{lang}-GEN-{h}"
