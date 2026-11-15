# PROMPT BỔ SUNG SỬA V2 — MUSEUM PLATFORM HERITAGE CORPUS

Bạn là Senior Python Engineer + Data Engineer + QA Lead + Heritage Knowledge Graph Reviewer. Hãy sửa code trong `scraper/heritage_corpus/` dựa trên báo cáo `KIEM_DINH_CAP_NHAT_HERITAGE_CORPUS_V2_2026-11-09.md`. **Không kết luận chỉ dựa trên 28/28 unit tests**. Mục tiêu là bảo đảm live crawl chạy được, extraction không mất thông tin, resume an toàn và báo cáo chất lượng phát hiện được lỗi cố tình cài vào.

## Quy tắc bắt buộc
- Giữ nguyên toàn bộ snapshot `data_baseline_v1`, raw archive và production CSV/database. Chỉ chỉnh sửa code + test + artifacts V2 sau khi backup, không ghi đè dữ liệu lịch sử.
- Đọc **toàn bộ file hiện có**, `models.py`, `base.py`, `crawler.py`, `state_manager.py`, `storage.py`, `vnmh_parser.py`, `rag_preparer.py`, `kg_preparer.py`, `verify_corpus_integrity.py`, `tests/`, `run_all_tests.py`, `README` và các báo cáo handover. Không tạo logic giả hoặc test khớp implement sai.
- Mỗi lỗi phải có root cause, test FAIL trước khi sửa, patch, test PASS sau khi sửa, log và số liệu before/after. Nếu thiếu quyền/môi trường/fixture, ghi NOT VERIFIED, không báo PASS.
- Không tự chạy crawl hàng loạt hoặc ghi production. Cho phép chạy offline trên 5 fixtures và mock transport; pilot thực phải xin phê duyệt cùng rate limit/robots.

## Blocker A — Khôi phục đường chạy crawler end-to-end
1. `state_manager.py` V2 không có `mark_processing()` còn `crawler.py:260` gọi. Bỏ lời gọi hoặc hợp nhất atomic claim; sửa với API nhất quán.
2. `adapters/base.py.fetch_url()` trả 5 giá trị nhưng `crawler.py:86,107,132,264` giải nén 4. Chuẩn hóa thành `FetchResult(html,status,headers,error,retry_after_seconds,final_url)` hoặc thống nhất 5-tuple; tìm tất cả call sites và update test. Header Retry-After phải được đưa qua `mark_failed` khi 429/503.
3. Viết integration tests không mạng dùng stub HTTP cho `SITEMAP → CATEGORY_HUB → PAGINATION → ARTICLE → PARSE → RAG → KG → SQLite/Storage`; kiểm tra 200/302/429/503/404/timeouts/robots denied/empty HTML, manifest status/counters.
4. Thiếu article-detail phải ra `PARSE_FAILED` và đi quarantine/failed ledger, không được `COMPLETED`. Trạng thái chỉ COMMITTED khi validation & storage thành công.

## Blocker B — Sửa parser mất 95%+ nội dung tiếng Việt
1. `_extract_leaf_blocks` hiện bỏ qua direct text nodes khi parent có descendants block. Thiết kế parser dạng DOM text-stream theo document order, preserve `NavigableString`, `<br>`, tables, inline spans, paragraphs và caption; loại bỏ nav/share/boilerplate bằng selector/context.
2. Gold fixtures là 5 raw HTML: `VNMH-VI-1001-73800`, `VNMH-VI-1001-75069`, `VNMH-VI-1001-76300`, `VNMH-EN-1005-28454`, `VNMH-EN-3181-19143`. Thêm asserts:
   - Thạp Đào Thịnh phải chứa `Chất liệu: Đồng`, `Đường kính miệng: 61cm`, `Đường kính đáy: 60cm`, `Chiều cao: 90cm`, `Văn hóa Đông Sơn`, `1426/QĐ-TTg` và văn bản mô tả thạp.
   - Mộ thuyền Việt Khê phải chứa `LSb. 38456`, `Chất liệu: Gỗ`, `Chiều dài: 476 cm`, `Văn hóa Đông Sơn` và phần mô tả nội dung chính.
   - Sổ vàng phải chứa `Hiện vật có kích thước dài 27 cm`, `BTCM 1768/Gy 532` và đoạn thông tin 72 trang, không chỉ captions; tác giả bài báo không phải người tạo hiện vật.
   - Các trang tiếng Anh phải giữ nguyên nội dung, không nhân đôi hoặc làm mất các đoạn văn.
3. Tách body + caption + summary minh bạch, không duplicate; offset/section span phải luôn trỏ đúng source field; sử dụng tokenizer có version; measure per-document extraction coverage và metadata precision/recall bằng gold annotations.
4. `VALIDATED` yêu cầu passes checks với bài thuộc class cụ thể; nếu parse loss thì QUARANTINED với lý do `EXTRACTION_COVERAGE_LOW` và báo severity; không chỉ `len(text) >= 30`.

## Blocker C — Atomic queue + dry-run + refresh
1. Thay `SELECT → UPDATE unconditional` trong `get_next_batch` bằng `BEGIN IMMEDIATE` trước SELECT hoặc atomic guarded UPDATE/RETURNING, kiểm tra affected rows; không dùng `with conn` như bằng chứng thay thế cho atomic claim.
2. Thêm integration multiprocessing 2/4/8 worker, controlled interleavings, 1000 attempts, khẳng định cùng một URL không bao giờ được trả cho 2 workers đồng thời.
3. Dry-run phải không mutate database/queue và không tạo files trên disk: dùng transient state hoặc non-claim peek; so sánh file hashes + queue snapshots trước/sau, trả danh sách discovery dự kiến; khi kết thúc không còn URL `processing`.
4. Hỗ trợ `force_refresh` trong CLI và scheduler; record `(doc_id, content_hash, version)` immutable, update current logical views atomically. Không skip nội dung VERSION_2 chỉ vì `doc_id` đã xuất hiện VERSION_1; stale sections, edges, mentions phải được thay thế hoặc versioned.
5. Resilience: crash giữa raw/parsed/sections/commit phải có recovery không tạo trùng/đánh dấu complete giả; test retry_after, backoff/dead-letter, lease expired.

## Blocker D — QA verifier phải kiểm tra schema thật
1. `verify_corpus_integrity.py` và `storage.py` đọc sai `predicate`, `subject_type`, `object_name`. Thay bằng `relation_type`, `source_entity_type`, `target_entity`, validate schema tất cả JSONL với `dataclasses`/Pydantic/JSON Schema.
2. Thêm mutation tests: cố tình chèn `ARTIFACT CREATED_BY <article.author>`; custody edge không có nguồn; quote không nằm trong referenced section; section-id thiếu; span lệch; parser body rỗng. Với từng mutation **verifier bắt buộc FAIL** (exit != 0) và báo lỗi đích danh.
3. Chỉ số tự nhất quán 100% phải tách khỏi quality recall, ratio validated/quarantined, missing fields, source coverage và cross-reference.
4. Kiểm tra `run_all_tests.py` chỉ là runner riêng; đồng thời sửa `tests/test_reliability_and_safety.py` import `AdapterConfig`, `tests/test_extraction_rag_kg.py` keyword `url`, `MetadataEvidence` dict vs object, quarantine reasons để `pytest tests` chạy sạch. Không bỏ test sai mà không thay bằng coverage tương đương.

## Blocker E — Handover và nghiệm thu
1. Reprocess offline lại cả 5 raw HTML, tạo `data_v2_verified/` mới, không ghi đè baseline. Đối chiếu từng document `raw → clean_text → metadata → sections → mentions → KG edges → match candidates`.
2. Tạo lại `quality_report.json` với per-doc/per-language quality, metadata quality, missingness, 100% FK/span/quote và benchmark độ phủ đã annotate; sửa manifest V2 và CLI/README cho đúng hiện trạng.
3. Kiểm tra `legacy_matcher` trên fixture production CSV đã làm ẩn thông tin hoặc dataset read-only được cấp quyền. Thạp Đào Thịnh phải sinh match candidate kỳ vọng mà không false positive; nếu không có CSV, ghi NOT TESTED, không khẳng định 6254 records được đối soát.
4. Handover bắt buộc gồm: Git SHA/diff, source code chạy được, requirements lock, entrypoint CLI, migration/rollback, 5 fixtures+gold annotations, pytest + runner + integration logs, mutation test logs, corpus V2 verified, error/quarantine ledger, before-after csv, manifest hashes, runbook, developer sign-off, QA sign-off.
5. Gate `GO` chỉ khi không P0/P1, pytest all pass, end-to-end integration pass, mutation tests fail đúng khi inject lỗi, 5 fixtures có body fidelity tốt, zero data loss, no double claims, no stale JSONL. Nếu không, giữ `NO-GO` trung thực.

## Định dạng trả lời cuối cùng của developer/AI coding agent
1. Bảng Issue ID → Root cause → File:line → Diff → Test FAIL trước → PASS sau → Bằng chứng.
2. Các lệnh thật đã chạy và exit codes, không mô phỏng log.
3. Bảng số liệu theo 5 tài liệu trước/sau (retained chars, status, fields, sections, mentions, edges, matches).
4. Checklist GO/NO-GO kèm người xác nhận và tài liệu chứng cứ.
5. Danh sách điểm chưa giải quyết / hạn chế môi trường, tuyệt đối không dùng '100% fixed' nếu còn lỗi.
