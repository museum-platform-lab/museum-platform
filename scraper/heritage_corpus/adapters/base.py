"""
Museum Platform - Base Source Adapter (Hardened V2)
Standard interface, polite transport, strict domain boundary enforcement,
RFC-compliant Retry-After parsing, and fail-safe robots policy.
"""

import time
import datetime
import email.utils
import ipaddress
import urllib.parse
import urllib.robotparser
from typing import Optional, Dict, Any, Tuple, List
import requests

from ..models import SourceConfig


PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class BaseSourceAdapter:
    def __init__(self, config: SourceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(self.config.default_headers)
        self._robots_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._robots_loaded_at: Optional[float] = None
        self._robots_status: str = "NOT_LOADED"  # ROBOTS_ALLOWED, ROBOTS_DENIED, ROBOTS_UNAVAILABLE, ROBOTS_NOT_PRESENT
        self._robots_ttl: float = 3600.0  # 1 hour cache
        self._last_request_time: float = 0.0

    @classmethod
    def is_safe_host(cls, host: str, allowed_domains: List[str]) -> bool:
        """
        Validates host is in allowed_domains and NOT a loopback/private/internal IP (SSRF protection).
        """
        if not host:
            return False
        host_clean = host.split(":")[0].lower().strip(".")
        if host_clean == "localhost":
            return False

        # Check if host is an IP literal
        try:
            ip = ipaddress.ip_address(host_clean)
            for priv in PRIVATE_NETWORKS:
                if ip in priv:
                    return False
        except ValueError:
            pass  # Normal hostname, not IP literal

        # Check domain allowlist
        for allowed in allowed_domains:
            allowed_clean = allowed.lower().strip(".")
            if host_clean == allowed_clean or host_clean.endswith("." + allowed_clean):
                return True
        return False

    def load_robots(self) -> str:
        if not self.config.robots_url:
            self._robots_status = "ROBOTS_NOT_PRESENT"
            return self._robots_status

        now = time.time()
        if self._robots_loaded_at and (now - self._robots_loaded_at < self._robots_ttl):
            return self._robots_status

        try:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(self.config.robots_url)
            # Use our session headers for robots fetch with strict timeout
            r = self.session.get(self.config.robots_url, timeout=10)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                self._robots_parser = rp
                self._robots_loaded_at = now
                self._robots_status = "ROBOTS_ALLOWED"
            elif r.status_code in (401, 403):
                self._robots_status = "ROBOTS_DENIED"
            elif r.status_code == 404:
                self._robots_status = "ROBOTS_NOT_PRESENT"
            else:
                self._robots_status = "ROBOTS_UNAVAILABLE"
        except Exception:
            # Conservative fail-safe: mark unavailable, do NOT fail-open silently
            self._robots_status = "ROBOTS_UNAVAILABLE"

        return self._robots_status

    def is_allowed_by_robots(self, url: str) -> Tuple[bool, str]:
        status = self.load_robots()
        if status == "ROBOTS_DENIED":
            return False, "ROBOTS_DENIED"
        if status == "ROBOTS_UNAVAILABLE":
            # Conservative fail-safe: defer / block when robots cannot be verified
            return False, "ROBOTS_UNAVAILABLE"
        if status == "ROBOTS_NOT_PRESENT":
            return True, "ROBOTS_NOT_PRESENT"

        if self._robots_parser:
            user_agent = self.config.default_headers.get("User-Agent", "*")
            allowed = self._robots_parser.can_fetch(user_agent, url)
            return allowed, "ROBOTS_ALLOWED" if allowed else "ROBOTS_DENIED"

        return True, "ROBOTS_ALLOWED"

    def _wait_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        required_delay = self.config.rate_limit_delay
        if elapsed < required_delay:
            time.sleep(required_delay - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def parse_retry_after(header_val: Optional[str]) -> Optional[int]:
        """
        Parses HTTP Retry-After header supporting both integer seconds (e.g. '120')
        and HTTP-date (RFC 2822 / RFC 1123, e.g. 'Wed, 21 Oct 2026 07:28:00 GMT').
        Returns delay in integer seconds.
        """
        if not header_val:
            return None
        val_str = header_val.strip()
        # 1. Integer seconds
        try:
            return max(1, int(val_str))
        except ValueError:
            pass

        # 2. HTTP-date
        try:
            dt = email.utils.parsedate_to_datetime(val_str)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = int((dt - now).total_seconds())
            return max(1, delta)
        except Exception:
            return None

    def fetch_url(
        self,
        url: str,
        timeout: int = 15,
        max_redirects: int = 5
    ) -> Tuple[Optional[str], int, Dict[str, str], Optional[str], Optional[int]]:
        """
        Fetches URL with strict domain checking, redirect validation, and rate limiting.
        Returns:
            (html_text, http_status, headers_dict, error_message, retry_after_seconds)
        """
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None, 400, {}, f"INVALID_SCHEME_{parsed.scheme}", None

        if not self.is_safe_host(parsed.netloc, self.config.allowed_domains):
            return None, 403, {}, f"DISALLOWED_HOST_{parsed.netloc}", None

        allowed, robot_reason = self.is_allowed_by_robots(url)
        if not allowed:
            return None, 403, {}, f"BLOCKED_BY_{robot_reason}", None

        self._wait_rate_limit()

        try:
            # We control redirects to verify each hop
            current_url = url
            response = None

            for hop in range(max_redirects + 1):
                # Verify hop destination domain
                hop_parsed = urllib.parse.urlparse(current_url)
                if not self.is_safe_host(hop_parsed.netloc, self.config.allowed_domains):
                    return None, 403, {}, f"OUT_OF_SCOPE_REDIRECT_{hop_parsed.netloc}", None

                response = self.session.get(
                    current_url,
                    timeout=timeout,
                    allow_redirects=False
                )

                if response.status_code in (301, 302, 303, 307, 308):
                    loc = response.headers.get("Location")
                    if not loc:
                        break
                    next_url = urllib.parse.urljoin(current_url, loc)
                    current_url = next_url
                else:
                    break

            if response is None:
                return None, 500, {}, "NO_RESPONSE", None

            http_status = response.status_code
            headers = dict(response.headers)
            retry_after_sec = self.parse_retry_after(headers.get("Retry-After"))

            if http_status in (429, 503):
                msg = f"RATE_LIMITED_OR_UNAVAILABLE (Retry-After: {retry_after_sec})"
                return None, http_status, headers, msg, retry_after_sec

            if http_status >= 400:
                return None, http_status, headers, f"HTTP_ERROR_{http_status}", None

            # Detect encoding safely
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text, http_status, headers, None, None

        except requests.exceptions.Timeout:
            return None, 408, {}, "REQUEST_TIMEOUT", None
        except requests.exceptions.ConnectionError as e:
            return None, 599, {}, f"CONNECTION_ERROR: {str(e)}", None
        except requests.exceptions.RequestException as e:
            return None, 500, {}, f"REQUEST_EXCEPTION: {str(e)}", None
