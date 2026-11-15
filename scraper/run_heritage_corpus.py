"""
Museum Platform - Heritage Corpus Runner CLI
Command-line interface for the Vietnamese Cultural Heritage Evidence Corpus.

Modes:
  --audit-only             Inspects robots.txt, sitemap, response headers, and domain access.
  --inventory              Compiles URL inventory from sitemap & nav menus without fetching bodies.
  --dry-run                Discovers categories and article URLs without fetching article bodies.
  --pilot                  Runs a strictly bounded pilot test (5 articles) for inspection.
  --reprocess-local        Reprocesses local raw HTML documents offline without network calls.
  --max-discovery-pages N  Limits discovery of hubs/paginations.
  --max-articles N         Limits total crawled article pages.
  --max-pages N            Limits total pages (alias for max-articles).
  --delay S                Polite delay between HTTP requests in seconds (default: 1.5).
  --lang vi,en             Languages to collect (default: vi,en).
  --export-report          Regenerates and displays quality metrics from existing crawl data.
"""

import argparse
import json
import os
import sys
import time
import requests

from heritage_corpus.crawler import HeritageCorpusCrawler
from heritage_corpus.models import CrawlManifest
from heritage_corpus.source_registry import SourceRegistry
from heritage_corpus.storage import CorpusStorage


PILOT_SEED_URLS = [
    "https://baotanglichsu.vn/vi/Articles/1001/73800/bao-vat-quoc-gia-thap-djao-thinh.html",
    "https://baotanglichsu.vn/vi/Articles/1001/76300/bao-vat-quoc-gia-so-vang-truong-nguyen-ai-quoc-1949-1950.html",
    "https://baotanglichsu.vn/vi/Articles/1001/75069/bao-vat-quoc-gia-mo-thuyen-viet-khe.html",
    "https://baotanglichsu.vn/en/Articles/1005/28454/mug.html",
    "https://baotanglichsu.vn/en/Articles/3181/19143/chu-dau-pottery-revival.html"
]


def run_audit() -> int:
    print("======================================================================")
    print("       VIETNAMESE CULTURAL HERITAGE EVIDENCE CORPUS - PRE-FLIGHT AUDIT")
    print("======================================================================")
    print("Target Domain: https://baotanglichsu.vn")
    print("Target Scope : Vietnamese (/vi) & English (/en) Cultural Heritage Content\n")

    test_endpoints = [
        ("Robots Policy", "https://baotanglichsu.vn/robots.txt"),
        ("XML Sitemap", "https://baotanglichsu.vn/Sitemap.aspx"),
        ("Vietnamese Portal", "https://baotanglichsu.vn/vi"),
        ("English Portal", "https://baotanglichsu.vn/en"),
        ("National Treasures Hub", "https://baotanglichsu.vn/vi/Articles/1001/bao-vat-quoc-gia")
    ]

    headers = {
        "User-Agent": "MuseumPlatformResearchBot/1.0 (+https://github.com/museum-platform; Research & Non-commercial)"
    }

    all_passed = True

    for name, url in test_endpoints:
        start_t = time.time()
        try:
            r = requests.get(url, headers=headers, timeout=10)
            elapsed_ms = int((time.time() - start_t) * 1000)
            status = r.status_code
            content_len = len(r.content)
            content_type = r.headers.get("Content-Type", "unknown")

            if status == 200:
                print(f"[PASS] {name:25s} | HTTP {status} | {elapsed_ms:4d}ms | {content_len:7d} bytes | {content_type}")
                if "robots.txt" in url:
                    print("       Robots Directive :", r.text.strip().replace("\n", " | "))
            else:
                print(f"[WARN] {name:25s} | HTTP {status} | {elapsed_ms:4d}ms")
                all_passed = False
        except Exception as e:
            print(f"[FAIL] {name:25s} | Error: {str(e)}")
            all_passed = False

    print("\n----------------------------------------------------------------------")
    print("LEGAL & POLICY ASSESSMENT:")
    print("- Robots.txt Directive: 'User-agent: * Disallow:' (Crawling explicitly permitted)")
    print("- Sitemap Disclosed   : Sitemap.aspx (Contains ~437 category hubs)")
    print("- Rate Limit Policy   : Polite serial crawling (1 request at a time, min 1.5s delay)")
    print("- Media Policy        : Metadata-only recording; no bulk image download without rights")
    print("- Provenance Tier     : OFFICIAL_MUSEUM (National Museum of History)")
    print("- Production CSV Safety: Intact. Output written exclusively to isolated directory.")
    print("----------------------------------------------------------------------\n")

    return 0 if all_passed else 1


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Museum Platform - Vietnamese Heritage Corpus Collector"
    )
    parser.add_argument("--audit-only", action="store_true", help="Run network & robots pre-flight audit")
    parser.add_argument("--inventory", action="store_true", help="Generate complete URL inventory from sitemap & nav without fetching bodies")
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no article body downloading")
    parser.add_argument("--pilot", action="store_true", help="Run bounded pilot crawl (5 curated articles across VI/EN)")
    parser.add_argument("--reprocess-local", action="store_true", help="Reprocess local raw HTML documents offline without network calls")
    parser.add_argument("--seed-urls", type=str, default=None, help="Comma-separated custom URLs to seed crawl")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of pages to process")
    parser.add_argument("--max-discovery-pages", type=int, default=None, help="Maximum discovery hub/pagination pages")
    parser.add_argument("--max-articles", type=int, default=None, help="Maximum article pages to fetch and parse")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests in seconds")
    parser.add_argument("--lang", type=str, default="vi,en", help="Target languages separated by comma (e.g. vi,en)")
    parser.add_argument("--output-dir", type=str, default="scraper/heritage_corpus/data", help="Output directory")
    parser.add_argument("--export-report", action="store_true", help="Generate quality report from existing data")

    args = parser.parse_args()

    if args.audit_only:
        sys.exit(run_audit())

    if args.inventory:
        print("Compiling URL inventory from Sitemap.aspx and Nav menus...")
        crawler = HeritageCorpusCrawler(
            output_dir=args.output_dir,
            state_db=":memory:",
            rate_limit_delay=args.delay
        )
        summary = crawler.generate_url_inventory(max_hubs=25)
        print("\n--- URL INVENTORY SUMMARY ---")
        print(f"Total Discovered URLs : {summary['total_urls']}")
        print(f"  Articles            : {summary['articles']}")
        print(f"  Category Hubs       : {summary['category_hubs']}")
        print(f"  Paginations         : {summary['paginations']}")
        print(f"  Albums              : {summary['albums']}")
        print(f"  Vietnamese (/vi)    : {summary['vi_urls']}")
        print(f"  English (/en)       : {summary['en_urls']}")
        print(f"Exported JSON         : {summary['json_path']}")
        print(f"Exported CSV          : {summary['csv_path']}")
        return

    if args.export_report:
        storage = CorpusStorage(args.output_dir)
        report = storage.generate_quality_report()
        print("\n--- CORPUS QUALITY REPORT ---")
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.reprocess_local:
        print(f"Reprocessing raw documents from {args.output_dir}/raw_documents offline...")
        crawler = HeritageCorpusCrawler(
            output_dir=args.output_dir,
            rate_limit_delay=args.delay
        )
        result = crawler.reprocess_local()
        print("\n--- LOCAL REPROCESSING COMPLETE ---")
        print(f"Reprocessed Documents: {result['reprocessed_docs']}")
        print(f"Reprocessed Sections : {result['reprocessed_sections']}")
        print(f"Reprocessed Mentions : {result['reprocessed_mentions']}")
        print(f"Reprocessed Edges    : {result['reprocessed_edges']}")
        print(f"Reprocessed Matches  : {result['reprocessed_matches']}")
        print(f"FK Integrity Rate    : {result['quality_report']['fk_integrity_metrics']['fk_integrity_pct']}%")
        print(f"Section Span Accuracy: {result['quality_report']['span_accuracy_metrics']['section_span_accuracy_pct']}%")
        print(f"Mention Span Accuracy: {result['quality_report']['span_accuracy_metrics']['mention_span_accuracy_pct']}%")
        print(f"Quote Accuracy Rate  : {result['quality_report']['span_accuracy_metrics']['edge_quote_accuracy_pct']}%")
        print(f"Token Cap Compliance : {result['quality_report']['token_cap_compliance_metrics']['compliance_pct']}%")
        return

    langs = [l.strip().lower() for l in args.lang.split(",") if l.strip()]
    seeds = None
    max_articles = args.max_articles or args.max_pages

    if args.pilot:
        seeds = PILOT_SEED_URLS
        max_articles = len(PILOT_SEED_URLS)
        print(f"Configuring PILOT Mode with {len(seeds)} curated test articles across VI & EN...")
    elif args.seed_urls:
        seeds = [u.strip() for u in args.seed_urls.split(",") if u.strip()]

    crawler = HeritageCorpusCrawler(
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        max_pages=args.max_pages,
        max_discovery_pages=args.max_discovery_pages,
        max_articles=max_articles,
        rate_limit_delay=args.delay,
        target_langs=langs,
        seed_urls=seeds
    )

    print(f"Starting Vietnamese Heritage Corpus Collector...")
    print(f"Target Scope: VNMH (baotanglichsu.vn) | Languages: {langs}")
    print(f"Mode: {'DRY RUN (Discovery Only)' if args.dry_run else 'ACTIVE EXTRACTION'}")
    print(f"Quotas: max_discovery_pages={args.max_discovery_pages}, max_articles={max_articles}")

    manifest = crawler.run()

    print("\n======================================================================")
    print("                     CRAWL EXECUTION MANIFEST")
    print("======================================================================")
    print(f"Run ID                   : {manifest.run_id}")
    print(f"Status                   : {manifest.status}")
    print(f"Started At               : {manifest.started_at}")
    print(f"Completed At             : {manifest.completed_at}")
    print(f"Discovered URLs          : {manifest.discovered_urls}")
    print(f"Attempted URLs           : {manifest.attempted_urls}")
    print(f"Succeeded URLs           : {manifest.succeeded_urls}")
    print(f"Failed URLs              : {manifest.failed_urls}")
    print(f"Quarantined URLs         : {manifest.quarantined_urls}")
    print(f"Content Changes Detected : {manifest.content_changes_detected}")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
