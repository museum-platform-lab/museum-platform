# Museum Platform — baseline hiện trạng

Snapshot chuẩn bị ngày 15/11/2026. Bản nền chưa phải một hệ thống đã nghiệm thu hoặc đã xác minh chạy từ database trống.

## Thành phần

- frontend/: Next.js 16.1.6, React 19.2.3, TypeScript, Tailwind 4; package-lock.json được giữ nguyên. Route /api/artifacts chuyển tiếp tới backend qua BACKEND_URL. README cũ trong frontend mô tả tích hợp Sheets trước đây và có thể đã lỗi thời.
- backend/: Java 21 theo pom.xml, Spring Boot 3.4.3, Spring AI 1.0.0, PostgreSQL/pgvector, Maven wrapper và tests có sẵn.
- scraper/: crawler, xử lý/merge snapshot, heritage_corpus, kiểm thử, script di chuyển trạng thái SQLite và tài liệu bàn giao có sẵn. requirements.txt chưa khóa toàn bộ phiên bản Python.
- Hồ sơ nghiên cứu được lưu riêng trong museum-research. Không có mã nguồn sản phẩm được sao chép vào repo nghiên cứu.

## Cấu hình và chạy

1. Backend cần JDK 21, Maven wrapper và Docker Compose nếu chạy PostgreSQL cục bộ. Copy backend/.env.example thành backend/.env, đặt giá trị riêng; không commit .env. Compose đọc backend/.env khi chạy từ backend/: docker compose up -d.
2. Export các biến SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME, SPRING_DATASOURCE_PASSWORD, SPRING_AI_OPENAI_API_KEY, MUSEUM_JWT_SECRET vào tiến trình Java/Maven. Spring Boot không tự đọc file .env. Cấu hình datasource phải khớp POSTGRES_* của Compose. Khóa JWT cần giá trị ngẫu nhiên mới tối thiểu 32 byte UTF-8. Không dùng placeholder để triển khai.
3. Từ backend/: Windows dùng .\mvnw.cmd spring-boot:run; hệ Unix dùng sh mvnw spring-boot:run. Cổng mặc định 8080.
4. Frontend: copy frontend/.env.example thành frontend/.env.local, đặt BACKEND_URL=http://localhost:8080; chạy npm ci rồi npm run dev trong frontend/. Các script kiểm tra có sẵn: npm run lint, npm run build. Node cần phù hợp Next.js 16.
5. Scraper: tạo virtualenv, pip install -r scraper/requirements.txt. Chạy kiểm thử unittest từ gốc: python -m unittest discover -s scraper/tests. Kiểm tra chuyên sâu: python scraper/heritage_corpus/run_all_tests.py. Đọc scraper/README.md và scraper/heritage_corpus/README.md trước khi chạy thu thập; các lệnh crawl/merge tạo dữ liệu hoặc có thể sửa file đích. Chưa chạy crawl hoặc kết nối production trong đợt chuẩn bị Git.

## Database và dữ liệu ngoài Git

Không tìm thấy SQL migration dựng schema nghiệp vụ. Entity Java được giữ nguyên; spring.jpa.hibernate.ddl-auto=validate, vì vậy database trống chưa đủ để chạy hệ thống. Compose chỉ dựng dịch vụ PostgreSQL, không tái lập schema/dữ liệu ứng dụng. Cần cung cấp quy trình tạo schema đã rà soát trước khi xác nhận khả năng dựng mới; đợt này không tự tạo migration hoặc đưa database dump lên Git.

CSV artifacts.csv, corpus, SQLite state, ảnh tải về, raw HTML/JSON, backup và ảnh UI chưa rõ license được giữ ngoài Git. Xem [manifest](docs/external-data-manifest.json) để khôi phục đúng đường dẫn. Thiếu ảnh public ảnh hưởng giao diện; thiếu corpus có thể làm các bước replay/đối soát không tái lập được. CsvDataSeeder hiện được comment, nên CSV không tự nạp database khi khởi động. Không có upload Drive hoặc xác minh backup cloud trong đợt này. Drive ID/link chưa biết được để null, không tạo link giả.

## Truy vết và giới hạn

Nguồn chính: D:/project/museum-platform; bản gốc không bị sửa. Repo backend nguồn chưa có commit. Repo frontend nguồn có remote https://github.com/helitoo/bao-tang-van-hoa.git, HEAD 9267289336fbe0cb3be62532e33efc0ef1a1942a, 51 commit qua các ref hợp lệ. Có thay đổi chưa commit được đưa vào snapshot. Repo cũ D:/project/cultural-museum được giữ nguyên; chỉ hồ sơ project-blueprint được lưu trong repo nghiên cứu.

Monorepo mới ghi nhận snapshot đã loại bí mật và tài nguyên chưa rõ quyền; không viết lại hoặc push lịch sử frontend sang đích mới vì lịch sử đó có các ảnh chưa xác minh quyền sử dụng. Lịch sử gốc vẫn ở repo/thư mục nguồn. Không reset, clean, force-push hoặc sửa remote cũ.

Thay đổi phục vụ đưa lên Git: loại bí mật trong cấu hình; chuyển khóa JWT sang museum.jwt.secret/MUSEUM_JWT_SECRET trong bản sao. Không nâng dependency, đổi logic nghiệp vụ hoặc tái cấu trúc hệ thống. Cần thay khóa API/JWT và mật khẩu đã từng lưu trực tiếp trong bản nguồn trước khi triển khai. Không bổ sung license cho mã nguồn/tài nguyên khi chưa xác minh quyền.

Tài liệu audit và số liệu nghiên cứu có sẵn được lưu để truy vết; các tuyên bố test pass, bản quyền, kiểm chứng học thuật trong tài liệu cũ chưa được đợt chuẩn bị này xác nhận lại. Kết quả kiểm tra đợt này ở [BASELINE_VALIDATION.md](docs/BASELINE_VALIDATION.md).
