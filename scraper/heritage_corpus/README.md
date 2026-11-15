# Vietnamese Cultural Heritage Evidence Corpus
## Multi-source Heritage Data Collection, Extraction & Knowledge Preparation Engine

---

## 1. Kiến trúc Tổng thể (Architecture Overview)

Hệ thống được thiết kế độc lập hoàn toàn với crawler Wikipedia và database production hiện tại. Toàn bộ quy trình thu thập và chuẩn bị dữ liệu di sản tuân thủ chuẩn nghiên cứu đa nguồn (Multi-source Evidence Corpus), hướng tới phục vụ RAG (Retrieval-Augmented Generation), multilingual retrieval, Knowledge Graph và provenance-aware reasoning.

```
scraper/
├── run_heritage_corpus.py           # CLI điều phối chính (--audit-only, --dry-run, --pilot, --max-pages)
├── heritage_corpus/
│   ├── models.py                    # Schemas chuẩn cho 12 intermediate datasets/artifacts
│   ├── source_registry.py           # Multi-source registry (VNMH, DCH, UNESCO, Wikidata, Commons, Scholarly)
│   ├── url_normalizer.py            # Canonicalization, phân giải relative links, lọc loop, bóc tách ID/Ngôn ngữ
│   ├── state_manager.py             # SQLite State Machine (Queue, Checkpoint/Resume, Failure Ledger, Backoff)
│   ├── vnmh_parser.py               # Parser chính xác: bóc tách số đăng ký (LSb.), niên đại, kích thước, ảnh & chú thích
│   ├── rag_preparer.py              # Section-aware chunking, evidence spans (char offsets), temporal context
│   ├── kg_preparer.py               # Entity mentions & Candidate Edges (ASSERTED/DERIVED/HYPOTHESIZED, PENDING_REVIEW)
│   ├── legacy_matcher.py            # Đối soát đa thuộc tính với crawled_artifacts_production.csv (không dùng tên đơn thuần)
│   ├── storage.py                   # Quản lý lưu trữ raw archive bất biến và các tệp JSONL chuẩn hóa
│   ├── crawler.py                   # Engine crawl tuần tự, rate limit, retry-after, phát hiện hash change
│   └── adapters/                    # Tầng adapter nguồn độc lập
│       ├── base.py                  # BaseSourceAdapter (Robots.txt, polite delay, session transport)
│       ├── vnmh.py                  # Adapter Bảo tàng Lịch sử Quốc gia (VI + EN, Sitemap.aspx, Categories, Pagination)
│       ├── dsvh.py                  # Adapter Cục Di sản văn hóa (Staged)
│       ├── unesco.py                # Adapter UNESCO World Heritage & ICH (Staged)
│       ├── wikidata.py              # Adapter Wikidata SPARQL / Entity API (Staged)
│       └── scholarly.py             # Adapter Scholarly Open Access Research (Staged)
└── tests/
    └── test_heritage_corpus.py      # Bộ kiểm thử tự động toàn diện (9 test cases)
```

---

## 2. Kết quả Tiền kiểm Kiểm toán (Pre-flight Audit Report)

| Mục kiểm toán | URL kiểm tra | Kết quả HTTP | Thời gian phản hồi | Đánh giá Pháp lý & Kỹ thuật |
| :--- | :--- | :---: | :---: | :--- |
| **Robots Policy** | `https://baotanglichsu.vn/robots.txt` | **200 OK** | 506 ms | `User-agent: * Disallow:` (Công khai cho phép thu thập). |
| **Sitemap XML** | `https://baotanglichsu.vn/Sitemap.aspx` | **200 OK** | 680 ms | Chứa danh mục 437 hubs chính thức (400 VI, 7 EN). |
| **Vietnamese Portal** | `https://baotanglichsu.vn/vi` | **200 OK** | 941 ms | Cấu trúc phân trang `Page{n}`, DOM container ASP.NET. |
| **English Portal** | `https://baotanglichsu.vn/en` | **200 OK** | 824 ms | Độc lập hoàn toàn, không gộp dịch tự động với bài tiếng Việt. |
| **Bảo vật Quốc gia Hub** | `.../vi/Articles/1001/bao-vat-quoc-gia` | **200 OK** | 418 ms | 12 hiện vật/trang, phân trang đến `Page7`. |

### Quy tắc an toàn & Trách nhiệm dữ liệu
1. **Mức tải thận trọng (Polite Rate Limiting):** Mặc định 1 request đồng thời, khoảng nghỉ tối thiểu `1.5 giây` giữa các request. Tự động dừng theo dõi và chờ khi gặp mã HTTP `429` kèm header `Retry-After`.
2. **Bảo vệ tài nguyên đa phương tiện:** Với hình ảnh, video, PDF, hệ thống chỉ trích xuất và lưu **metadata** (URL gốc, kích thước, alt text, chú thích caption trong ngữ cảnh). Tuyệt đối **không tự ý tải hàng loạt file media** khi chưa có sự cho phép quyền khai thác.
3. **Bảo vệ Dataset Production:** Tuyệt đối không ghi đè vào `crawled_artifacts_production.csv` (6,254 bản ghi) hoặc cơ sở dữ liệu backend. Toàn bộ dữ liệu mới được cách ly trong thư mục cấu hình (mặc định: `scraper/heritage_corpus/data/`).

---

## 3. Danh mục 12 Bộ Dữ liệu Trung gian (Deliverables Schema)

1. **`crawl_manifest.json`**: Ghi nhận toàn bộ thông số phiên crawl (Run ID, thời gian bắt đầu/kết thúc, số URL tìm thấy, số thành công, số lỗi, số cách ly, mã băm cấu hình).
2. **`raw_documents/`**: Thư mục lưu trữ nguyên văn phản hồi HTML gốc `{doc_id}.json` kèm mã băm SHA-256 bất biến phục vụ đối soát provenance.
3. **`parsed_documents.jsonl`**: Bản ghi tài liệu đã bóc tách sạch, loại bỏ triệt để navigation/footer/chia sẻ/đánh giá, giữ nguyên tiêu đề, tác giả, ngày đăng chính xác từ web (không lấy ngày crawl), tóm tắt, nội dung chính, và metadata chuyên sâu (Số đăng ký `LSb.`, chất liệu, kích thước, niên đại, quyết định công nhận `QĐ-TTg`, địa điểm phát hiện, nơi lưu giữ).
4. **`document_sections.jsonl`**: Phân đoạn nội dung cho RAG theo cấu trúc cây tiêu đề (`heading_path`), xác định rõ `char_start`, `char_end`, ngữ cảnh niên đại (`temporal_context`), và trạng thái đủ điều kiện đánh chỉ mục (`index_eligibility`).
5. **`document_links.jsonl`**: Mọi liên kết ra ngoài và nội bộ được phân loại: `INTERNAL_ARTICLE`, `CATEGORY_HUB`, `PAGINATION`, `EXTERNAL_REFERENCE`.
6. **`media_metadata.jsonl`**: Bảng dữ liệu ảnh và phương tiện nhúng, liên kết chính xác với đoạn văn chú thích và giấy phép bản quyền.
7. **`entity_mentions.jsonl`**: Thực thể được phát hiện trong văn bản (`ARTIFACT`, `HERITAGE_SITE`, `PERSON`, `EVENT`, `PERIOD`, `CULTURE`, `LOCATION`, `INSTITUTION`, `COLLECTION`, `DOCUMENT`, `EXHIBITION`).
8. **`entity_match_candidates.jsonl`**: Danh sách ứng viên đối soát với 6,254 bản ghi production hiện tại dựa trên số đăng ký hiện vật, quyết định công nhận và tương quan niên đại/địa điểm, duy trì quan hệ N-N và luôn ở trạng thái `PENDING_REVIEW`.
9. **`kg_candidate_edges.jsonl`**: Quan hệ đồ thức tri thức (`BELONGS_TO_PERIOD`, `DISCOVERED_AT`, `CREATED_BY`, `CURRENTLY_HELD_BY`, `ASSOCIATED_WITH_CULTURE`, v.v.) được gắn nhãn nhận thức luận minh bạch (`ASSERTED`, `DERIVED`, `HYPOTHESIZED`) và cờ `PENDING_REVIEW`.
10. **`crawl_failures.jsonl`**: Sổ cái lỗi (Failure Ledger) theo dõi từng URL bị gián đoạn, mã lỗi HTTP, số lần thử, lịch retry lùi theo hàm mũ (`exponential backoff`), đảm bảo URL lỗi không bị đánh dấu hoàn tất.
11. **`quality_report.json`**: Báo cáo tổng hợp chất lượng corpus: độ phủ phân loại, tỷ lệ trường metadata quan trọng, phân bổ ngôn ngữ VI/EN, độ hoàn thiện dữ liệu.
12. **`source_registry.json`**: Bản ghi chính thức các nguồn dữ liệu, cấp độ tin cậy (provenance tier), chính sách bản quyền và giới hạn kỹ thuật.

---

## 4. Hướng dẫn Sử dụng CLI Script (`run_heritage_corpus.py`)

### Bước 1: Chạy kiểm toán kết nối và chính sách trước khi thu thập
```bash
python scraper/run_heritage_corpus.py --audit-only
```

### Bước 2: Chạy chế độ Discovery khám phá (Dry-run, không tải bài viết)
```bash
python scraper/run_heritage_corpus.py --dry-run --max-pages 10
```

### Bước 3: Chạy thử nghiệm Pilot có kiểm soát (5 bài viết mẫu để review thủ công)
```bash
python scraper/run_heritage_corpus.py --pilot --delay 2.0
```

### Bước 4: Chạy thu thập theo hạn mức hoặc toàn bộ sau khi đã phê duyệt
```bash
# Thu thập có giới hạn số trang
python scraper/run_heritage_corpus.py --max-pages 50 --delay 1.5

# Chỉ thu thập tiếng Việt hoặc tiếng Anh
python scraper/run_heritage_corpus.py --lang vi --delay 1.5
python scraper/run_heritage_corpus.py --lang en --delay 1.5

# Xem báo cáo chất lượng tổng hợp
python scraper/run_heritage_corpus.py --export-report
```

---

## 5. Kết quả Kiểm thử Tự động (Automated Test Suite)

Chạy bộ kiểm thử tự động:
```bash
python -m unittest scraper/tests/test_heritage_corpus.py
```
Kết quả kiểm thử: **9/9 test cases đạt 100% (OK)** bao gồm:
1. `test_url_normalization_and_deduplication`: Chuẩn hóa URL, loại bỏ tham số theo dõi, phát hiện tiếng Việt/tiếng Anh, sinh stable doc ID.
2. `test_pagination_and_hub_extraction`: Phân trang `/Page2`, `/Page3`, bóc tách liên kết bài viết trong hub.
3. `test_parser_metadata_and_fidelity`: Trích xuất số đăng ký hiện vật `LSb. 32967`, chất liệu `Đồng thau`, niên đại `Đông Sơn`, quyết định công nhận `1426/QĐ-TTg`, tác giả, ngày giờ xuất bản chính xác `2023-03-27T10:46:00`.
4. `test_parser_contamination_resistance`: Loại bỏ 100% rác điều hướng, thanh chia sẻ, star ratings, footer khỏi nội dung.
5. `test_rag_evidence_spans`: Chia chunk theo cấu trúc tiêu đề, tính toán chính xác `char_start` và `char_end`.
6. `test_kg_candidate_edges`: Xác định đúng thực thể và quan hệ với nhãn nhận thức luận `ASSERTED` / `DERIVED` / `HYPOTHESIZED`, cờ `PENDING_REVIEW`.
7. `test_legacy_matching`: Khớp chính xác Thạp Đào Thịnh với ID 3 trong dataset production 6,254 bản ghi bằng tương quan đa thuộc tính, không dựa vào tên đơn thuần.
8. `test_state_manager_resume_and_failure_ledger`: Kiểm thử trạng thái hàng đợi, cơ chế resume và sổ cái thất bại kèm backoff.
9. `test_source_registry_and_multi_source`: Quản lý danh mục nguồn mở rộng (VNMH, DCH, UNESCO, Wikidata, Commons, Scholarly).
