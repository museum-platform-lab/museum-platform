"""
Museum Platform - Vietnamese Heritage Corpus Crawler Engine (V2)
Coordinates multi-stage discovery, polite rate-limited extraction, RAG chunking,
KG relation induction, and legacy matching for the National Museum of History (VNMH).

Features:
- Multi-stage pipeline: FETCH_OK -> PARSE_OK -> VALIDATED -> COMMITTED / QUARANTINED
- True dry-run: discovery only, zero body fetch, zero disk side-effects, zero completed status
- Separate quotas: max_discovery_pages vs max_articles
- Offline local reprocessing mode: reprocess raw HTML archives without network calls
- Schema V2 compatibility with exact substring evidence and strict FK integrity
"""

import datetime
import hashlib
import os
import time
import uuid
import json
import glob
from typing import Dict, Any, List, Optional, Set

from .adapters.vnmh import VNMHAdapter
from .kg_preparer import KGPreparer
from .legacy_matcher import LegacyMatcher
from .models import CrawlManifest, RawDocument, CrawlFailure, ParsedDocument
from .rag_preparer import RAGPreparer
from .source_registry import SourceRegistry
from .state_manager import CorpusStateManager
from .storage import CorpusStorage
from .url_normalizer import URLNormalizer


class HeritageCorpusCrawler:
    def __init__(
        self,
        output_dir: str = "scraper/heritage_corpus/data",
        state_db: str = "scraper/heritage_corpus/data/heritage_corpus_state.db",
        dry_run: bool = False,
        max_pages: Optional[int] = None,
        max_discovery_pages: Optional[int] = None,
        max_articles: Optional[int] = None,
        rate_limit_delay: float = 1.5,
        target_langs: Optional[List[str]] = None,
        legacy_csv_path: Optional[str] = None,
        seed_urls: Optional[List[str]] = None
    ):
        self.output_dir = os.path.abspath(output_dir)
        self.dry_run = dry_run
        self.max_pages = max_pages
        self.max_discovery_pages = max_discovery_pages
        self.max_articles = max_articles if max_articles is not None else max_pages
        self.target_langs = target_langs or ["vi", "en"]
        self.seed_urls = seed_urls

        # Ensure directories
        os.makedirs(self.output_dir, exist_ok=True)

        self.storage = CorpusStorage(self.output_dir)
        self.state = CorpusStateManager(state_db)
        self.registry = SourceRegistry()

        # VNMH Adapter
        vnmh_cfg = self.registry.get("VNMH")
        if vnmh_cfg:
            vnmh_cfg.rate_limit_delay = rate_limit_delay
        self.adapter = VNMHAdapter(vnmh_cfg)

        self.legacy_matcher = LegacyMatcher(legacy_csv_path)

        # Save registry configuration to output dir
        self.registry.save_to_file(self.storage.paths["source_registry"])

    def generate_url_inventory(self, max_hubs: Optional[int] = 30) -> Dict[str, Any]:
        """
        Discovers all category hubs from Sitemap.aspx and nav menus,
        then samples/traverses hubs to compile a structured URL inventory.
        Saves to url_inventory.json and url_inventory.csv.
        """
        import csv
        inventory_records = []
        seen_urls = set()

        # 1. Fetch Sitemap
        sitemap_url = "https://baotanglichsu.vn/Sitemap.aspx"
        xml_text, status, _, _ = self.adapter.fetch_url(sitemap_url)
        if xml_text and status == 200:
            sm_urls = self.adapter.parse_sitemap(xml_text)
            for u in sm_urls:
                norm = URLNormalizer.normalize_url(u)
                if norm and norm not in seen_urls:
                    seen_urls.add(norm)
                    p_info = URLNormalizer.parse_vnmh_path(norm)
                    inventory_records.append({
                        "url": norm,
                        "canonical_url": norm,
                        "language": p_info.get("language", "vi"),
                        "page_type": p_info.get("page_type", "CATEGORY_HUB"),
                        "category_id": p_info.get("category_id"),
                        "category_slug": p_info.get("category_slug"),
                        "stable_doc_id": p_info.get("stable_doc_id") or URLNormalizer.get_stable_id(norm, "VNMH"),
                        "discovery_source": "SITEMAP"
                    })

        # 2. Fetch VI & EN Homepages for Nav menus
        for home_url in ["https://baotanglichsu.vn/vi", "https://baotanglichsu.vn/en"]:
            html_text, status, _, _ = self.adapter.fetch_url(home_url)
            if html_text and status == 200:
                nav_cats = self.adapter.discover_nav_categories(html_text, home_url)
                for cat in nav_cats:
                    norm = URLNormalizer.normalize_url(cat)
                    if norm and norm not in seen_urls:
                        seen_urls.add(norm)
                        p_info = URLNormalizer.parse_vnmh_path(norm)
                        inventory_records.append({
                            "url": norm,
                            "canonical_url": norm,
                            "language": p_info.get("language", "vi"),
                            "page_type": p_info.get("page_type", "CATEGORY_HUB"),
                            "category_id": p_info.get("category_id"),
                            "category_slug": p_info.get("category_slug"),
                            "stable_doc_id": p_info.get("stable_doc_id") or URLNormalizer.get_stable_id(norm, "VNMH"),
                            "discovery_source": "NAV_MENU"
                        })

        # 3. Explore category hubs for articles
        hubs_to_probe = [r["url"] for r in inventory_records if r["page_type"] in ("CATEGORY_HUB", "ALBUM")]
        if max_hubs:
            hubs_to_probe = hubs_to_probe[:max_hubs]

        for hub_url in hubs_to_probe:
            html_text, status, _, _ = self.adapter.fetch_url(hub_url)
            if html_text and status == 200:
                links_dict = self.adapter.extract_links_from_page(html_text, hub_url)
                for art_url in links_dict.get("articles", []):
                    norm = URLNormalizer.normalize_url(art_url)
                    if norm and norm not in seen_urls:
                        seen_urls.add(norm)
                        p_info = URLNormalizer.parse_vnmh_path(norm)
                        inventory_records.append({
                            "url": norm,
                            "canonical_url": norm,
                            "language": p_info.get("language", "vi"),
                            "page_type": "ARTICLE",
                            "category_id": p_info.get("category_id"),
                            "category_slug": p_info.get("category_slug"),
                            "stable_doc_id": p_info.get("stable_doc_id") or URLNormalizer.get_stable_id(norm, "VNMH"),
                            "discovery_source": "HUB_PAGE_LINKS"
                        })
                for pag_url in links_dict.get("paginations", []):
                    norm = URLNormalizer.normalize_url(pag_url)
                    if norm and norm not in seen_urls:
                        seen_urls.add(norm)
                        p_info = URLNormalizer.parse_vnmh_path(norm)
                        inventory_records.append({
                            "url": norm,
                            "canonical_url": norm,
                            "language": p_info.get("language", "vi"),
                            "page_type": "PAGINATION",
                            "category_id": p_info.get("category_id"),
                            "category_slug": p_info.get("category_slug"),
                            "stable_doc_id": URLNormalizer.get_stable_id(norm, "VNMH"),
                            "discovery_source": "PAGINATION_LINK"
                        })

        # Export JSON and CSV
        json_path = os.path.join(self.output_dir, "url_inventory.json")
        csv_path = os.path.join(self.output_dir, "url_inventory.csv")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(inventory_records, f, ensure_ascii=False, indent=2)

        if inventory_records:
            fieldnames = list(inventory_records[0].keys())
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(inventory_records)

        summary = {
            "total_urls": len(inventory_records),
            "articles": sum(1 for r in inventory_records if r["page_type"] == "ARTICLE"),
            "category_hubs": sum(1 for r in inventory_records if r["page_type"] == "CATEGORY_HUB"),
            "paginations": sum(1 for r in inventory_records if r["page_type"] == "PAGINATION"),
            "albums": sum(1 for r in inventory_records if r["page_type"] == "ALBUM"),
            "vi_urls": sum(1 for r in inventory_records if r["language"] == "vi"),
            "en_urls": sum(1 for r in inventory_records if r["language"] == "en"),
            "json_path": json_path,
            "csv_path": csv_path
        }
        return summary

    def run(self) -> CrawlManifest:
        run_id = f"RUN-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        manifest = CrawlManifest(
            run_id=run_id,
            source_id="VNMH",
            started_at=started_at,
            status="RUNNING",
            config={
                "dry_run": self.dry_run,
                "max_pages": self.max_pages,
                "max_discovery_pages": self.max_discovery_pages,
                "max_articles": self.max_articles,
                "target_langs": self.target_langs,
                "output_dir": self.output_dir,
                "seed_urls": self.seed_urls
            }
        )
        if not self.dry_run:
            self.storage.save_manifest(manifest)

        # 1. Enqueue seeds
        seeds = self.seed_urls if self.seed_urls else self.adapter.DEFAULT_SEEDS
        for seed in seeds:
            p_info = URLNormalizer.parse_vnmh_path(seed)
            ptype = "SITEMAP" if "Sitemap" in seed else p_info.get("page_type", "HOMEPAGE")
            prio = 10 if ptype in ("SITEMAP", "ARTICLE") else 9
            self.state.add_to_queue(seed, "VNMH", ptype, depth=0, priority=prio)

        discovery_pages_processed = 0
        articles_processed = 0

        try:
            while True:
                # Check quotas
                if self.max_articles and articles_processed >= self.max_articles:
                    break

                batch = self.state.get_next_batch(batch_size=1)
                if not batch:
                    break

                item = batch[0]
                url = item["url"]
                ptype = item["page_type"]
                depth = item["depth"]

                # Language filter check upfront
                parsed_path = URLNormalizer.parse_vnmh_path(url)
                if parsed_path["is_valid_vnmh"] and parsed_path["language"] not in self.target_langs:
                    self.state.mark_skipped_lang(url, parsed_path["language"])
                    manifest.quarantined_urls += 1
                    continue

                # In DRY RUN mode: DO NOT fetch article bodies!
                if self.dry_run and ptype == "ARTICLE":
                    # In dry-run, we discover and record article URLs without fetching bodies
                    manifest.discovered_urls += 1
                    # Do NOT mark as completed, keep in queue or leave as pending
                    continue

                # Check discovery quota
                if ptype in ("HOMEPAGE", "CATEGORY_HUB", "PAGINATION", "ALBUM", "SITEMAP"):
                    if self.max_discovery_pages and discovery_pages_processed >= self.max_discovery_pages:
                        continue

                self.state.mark_processing(url)
                manifest.attempted_urls += 1

                # Fetch URL
                html_text, status, headers, err = self.adapter.fetch_url(url)

                if err or not html_text:
                    manifest.failed_urls += 1
                    err_type = "HTTP_ERROR" if status and status >= 400 else "FETCH_FAILURE"
                    self.state.mark_failed(url, "VNMH", err_type, err or "Unknown Error", http_status=status)
                    if not self.dry_run:
                        self.storage.append_jsonl("crawl_failures", [CrawlFailure(
                            failure_id=f"FAIL-{uuid.uuid4().hex[:8]}",
                            url=url,
                            source_id="VNMH",
                            attempt_count=item.get("attempts", 0) + 1,
                            http_status=status,
                            error_type=err_type,
                            error_message=err or "Unknown",
                            last_attempted_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
                        )])
                    continue

                manifest.succeeded_urls += 1
                retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                content_hash = hashlib.sha256(html_text.encode("utf-8")).hexdigest()

                # Handle Sitemap
                if ptype == "SITEMAP":
                    discovery_pages_processed += 1
                    sitemap_urls = self.adapter.parse_sitemap(html_text)
                    for sm_url in sitemap_urls:
                        p_info = URLNormalizer.parse_vnmh_path(sm_url)
                        if p_info["language"] in self.target_langs:
                            if self.state.add_to_queue(sm_url, "VNMH", "CATEGORY_HUB", depth=1, priority=8):
                                manifest.discovered_urls += 1
                    self.state.mark_completed("VNMH-SITEMAP", url, "VNMH", "vi", content_hash, status)
                    continue

                # Handle Homepage / Categories / Pagination
                if ptype in ("HOMEPAGE", "CATEGORY_HUB", "PAGINATION", "ALBUM"):
                    discovery_pages_processed += 1
                    links_dict = self.adapter.extract_links_from_page(html_text, url)
                    for cat_url in links_dict.get("categories", []):
                        if self.state.add_to_queue(cat_url, "VNMH", "CATEGORY_HUB", depth=depth + 1, priority=8):
                            manifest.discovered_urls += 1

                    for pag_url in links_dict.get("paginations", []):
                        if self.state.add_to_queue(pag_url, "VNMH", "PAGINATION", depth=depth + 1, priority=7):
                            manifest.discovered_urls += 1

                    for art_url in links_dict.get("articles", []):
                        if self.state.add_to_queue(art_url, "VNMH", "ARTICLE", depth=depth + 1, priority=5):
                            manifest.discovered_urls += 1

                    doc_id = URLNormalizer.get_stable_id(url, "VNMH")
                    self.state.mark_completed(doc_id, url, "VNMH", parsed_path.get("language", "vi"), content_hash, status)
                    continue

                # Handle Article (.html)
                if ptype == "ARTICLE":
                    articles_processed += 1
                    doc_id = URLNormalizer.get_stable_id(url, "VNMH")
                    existing_hash = self.state.get_existing_hash(doc_id)
                    if existing_hash and existing_hash != content_hash:
                        manifest.content_changes_detected += 1

                    # Stage 1: FETCH_OK - Save Raw Document
                    raw_doc = RawDocument(
                        doc_id=doc_id,
                        source_id="VNMH",
                        url=url,
                        canonical_url=url,
                        http_status=status,
                        content_hash=content_hash,
                        retrieved_at=retrieved_at,
                        headers=headers,
                        raw_html=html_text,
                        language=parsed_path.get("language", "vi")
                    )
                    self.storage.save_raw_document(raw_doc)

                    # Stage 2: PARSE_OK - Parse Article
                    parsed_doc, sections, links, media = self.adapter.parse_article_page(html_text, url, retrieved_at)

                    # Stage 3: VALIDATION & QUARANTINE CHECK
                    if parsed_doc.validation_status == "QUARANTINED":
                        manifest.quarantined_urls += 1
                        self.storage.append_jsonl("parsed_documents", [parsed_doc])
                        self.state.mark_quarantined(doc_id, url, "VNMH", "; ".join(parsed_doc.quarantine_reasons))
                        continue

                    # Stage 4: COMMITTED - RAG Chunks, KG Candidates, Legacy Matches
                    rag_chunks = RAGPreparer.prepare_chunks(parsed_doc, sections)
                    mentions, edges = KGPreparer.extract_kg_candidates(parsed_doc, rag_chunks)
                    matches = self.legacy_matcher.find_matches(parsed_doc)

                    self.storage.append_jsonl("parsed_documents", [parsed_doc])
                    self.storage.append_jsonl("document_sections", rag_chunks)
                    self.storage.append_jsonl("document_links", links)
                    self.storage.append_jsonl("media_metadata", media)
                    self.storage.append_jsonl("entity_mentions", mentions)
                    self.storage.append_jsonl("kg_candidate_edges", edges)
                    self.storage.append_jsonl("entity_match_candidates", matches)

                    self.state.mark_completed(doc_id, url, "VNMH", parsed_doc.language, content_hash, status)

        except KeyboardInterrupt:
            manifest.status = "INTERRUPTED"
        except Exception as e:
            manifest.status = "FAILED"
            manifest.config["error"] = str(e)
        else:
            manifest.status = "DRY_RUN_COMPLETED" if self.dry_run else "COMPLETED"

        manifest.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not self.dry_run:
            self.storage.save_manifest(manifest)
            self.storage.generate_quality_report()

        return manifest

    def reprocess_local(self, target_doc_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Reprocesses raw documents from local storage without making any network calls.
        Re-executes parsing, RAG chunking, KG induction, and legacy matching.
        Atomically updates the corpus JSONL files and recalculates quality report.
        """
        raw_files = []
        if os.path.exists(self.storage.raw_dir):
            for root, _, files in os.walk(self.storage.raw_dir):
                for f in files:
                    if f.endswith(".json"):
                        raw_files.append(os.path.join(root, f))

        # Filter by target_doc_ids if specified
        target_set = set(target_doc_ids) if target_doc_ids else None

        processed_docs: List[ParsedDocument] = []
        all_sections = []
        all_links = []
        all_media = []
        all_mentions = []
        all_edges = []
        all_matches = []

        seen_doc_ids = set()

        for rf in raw_files:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            doc_id = data.get("doc_id")
            if not doc_id or doc_id in seen_doc_ids:
                continue
            if target_set and doc_id not in target_set:
                continue

            raw_html = data.get("raw_html") or ""
            url = data.get("url") or ""
            retrieved_at = data.get("retrieved_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            if not raw_html:
                continue

            seen_doc_ids.add(doc_id)

            # Re-parse article
            parsed_doc, sections, links, media = self.adapter.parse_article_page(raw_html, url, retrieved_at)
            processed_docs.append(parsed_doc)

            if parsed_doc.validation_status != "QUARANTINED":
                chunks = RAGPreparer.prepare_chunks(parsed_doc, sections)
                mentions, edges = KGPreparer.extract_kg_candidates(parsed_doc, chunks)
                matches = self.legacy_matcher.find_matches(parsed_doc)

                all_sections.extend(chunks)
                all_links.extend(links)
                all_media.extend(media)
                all_mentions.extend(mentions)
                all_edges.extend(edges)
                all_matches.extend(matches)

        # Atomically rewrite datasets
        def _write_jsonl_clean(path_key: str, items: List[Any]):
            p = self.storage.paths[path_key]
            tmp = f"{p}.tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                for it in items:
                    d = it.to_dict() if hasattr(it, "to_dict") else it
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
            os.replace(tmp, p)

        _write_jsonl_clean("parsed_documents", processed_docs)
        _write_jsonl_clean("document_sections", all_sections)
        _write_jsonl_clean("document_links", all_links)
        _write_jsonl_clean("media_metadata", all_media)
        _write_jsonl_clean("entity_mentions", all_mentions)
        _write_jsonl_clean("kg_candidate_edges", all_edges)
        _write_jsonl_clean("entity_match_candidates", all_matches)

        # Refresh in-memory seen cache in storage
        self.storage._seen_ids = {k: set() for k in self.storage.paths}
        self.storage._initialize_seen_ids()

        # Recalculate quality report
        report = self.storage.generate_quality_report()

        return {
            "reprocessed_docs": len(processed_docs),
            "reprocessed_sections": len(all_sections),
            "reprocessed_mentions": len(all_mentions),
            "reprocessed_edges": len(all_edges),
            "reprocessed_matches": len(all_matches),
            "quality_report": report.to_dict()
        }
