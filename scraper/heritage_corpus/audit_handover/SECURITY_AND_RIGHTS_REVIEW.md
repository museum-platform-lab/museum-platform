# Security, Rights, and Provenance Governance Review

**Document Reference**: `SECURITY_AND_RIGHTS_REVIEW.md`  
**Target Domain**: National Museum of History (`https://baotanglichsu.vn`)  
**Compliance Standard**: Gate G5 (Network Safety, Security & Legal Boundaries)  

---

## 1. Domain Legal & Robots.txt Assessment

### 1.1. Robots.txt Policy
- **Endpoint**: `https://baotanglichsu.vn/robots.txt`
- **Directive Found**:
  ```text
  User-agent: *
  Disallow:
  ```
- **Interpretation**: Crawling of public content on `baotanglichsu.vn` is explicitly permitted under standard web conventions.
- **Fail-Safe Mechanism (Finding P1-10 Fix)**:  
  In the event of network timeouts or server errors when retrieving `robots.txt`, the crawler operates **fail-closed** (`status = "ROBOTS_UNAVAILABLE"`). It blocks further crawling until the policy can be verified, preventing inadvertent policy violations.

### 1.2. Public Content Scope
- Discovered URLs originate exclusively from publicly linked content published on `baotanglichsu.vn/vi` and `baotanglichsu.vn/en`.
- No authentication bypass, CAPTCHA solving, session sniffing, or undocumented admin interfaces were attempted or implemented.

---

## 2. Network Security & SSRF Defense (Finding P1-08 & P1-09 Fix)

To prevent Server-Side Request Forgery (SSRF) and host pollution:

1. **IP Range Blocklist**:
   Before initiating any HTTP request, `BaseSourceAdapter.is_safe_host()` resolves hostnames and blocks the following ranges:
   - Loopback: `127.0.0.0/8`, `::1/128`, `localhost`
   - Private RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
   - Link-local (Cloud Metadata): `169.254.0.0/16`, `fe80::/10`
   - Carrier-grade NAT & Reserved: `100.64.0.0/10`, `fc00::/7`
2. **Hop-by-Hop Redirect Inspection**:
   Redirects are handled manually with `allow_redirects=False`. Every redirect hop destination is validated against `is_safe_host()` and the allowed domain registry. Any hop pointing to an external domain (e.g. phishing or third-party ad networks) is immediately rejected with `OUT_OF_SCOPE_REDIRECT`.

---

## 3. Rate Limiting & Domain Politeness (Finding P0-01 Fix)

- **Serial Rate Limiting**: The crawler operates strictly sequentially with 1 concurrent request per host by default, enforcing `rate_limit_delay = 1.5s` between requests.
- **RFC-Compliant Retry-After Handling**:
  If the target server responds with HTTP 429 (Too Many Requests) or HTTP 503:
  - Integer seconds (e.g. `Retry-After: 120`) are parsed directly.
  - RFC 1123 / RFC 2822 HTTP-date strings (e.g. `Retry-After: Wed, 21 Oct 2026 07:28:00 GMT`) are parsed and converted to exact remaining seconds.
  - The SQLite queue updates `next_retry_at` and freezes attempts on that domain until the backoff window elapses.

---

## 4. Media Asset Rights & Copyright Governance

### 4.1. Metadata-Only Media Ingestion
- Media assets (`<img>`, embedded PDF, audio, video) are ingested as **metadata records only** (`media_metadata.jsonl`).
- Recorded fields: `media_id`, `doc_id`, `media_url`, `media_type`, `caption`, `credit`, `original_width`, `original_height`, `license_status`.
- **Zero Binary Downloads**: No bulk media binaries (JPEG, PNG, MP4, PDF) are downloaded to disk, respecting museum server bandwidth and image copyright terms.

### 4.2. Copyright & Citation Terms
- All parsed documents and RAG chunks carry immutable copyright status:
  - `copyright_status`: `"RESERVED_CITATION_PERMITTED"`
  - `reuse_terms`: `"Scholarly citation with provenance attribution"`
  - `source_attribution`: `"Bảo tàng Lịch sử quốc gia (baotanglichsu.vn)"`
- This complies with Vietnamese Intellectual Property Law regarding fair-use research citation and non-commercial academic attribution.

---

## 5. Production Dataset Isolation

- **File Integrity Guarantee**:  
  `scraper/crawled_artifacts_production.csv` (SHA-256: `44416c559675be23fb0fce91e12f1fff542bccac553dc1a26e5875843e466c90`) remains completely isolated. The crawler has read-only access to this file exclusively via `legacy_matcher.py`.
- **Directory Isolation**:  
  All crawler outputs are written exclusively to `scraper/heritage_corpus/data/` or user-configured output directories. Zero modifications are made to the existing production database or Wikipedia scrapers.
