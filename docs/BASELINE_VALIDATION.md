# Kiểm tra bản nền — 15/11/2026

- npm ci: thành công theo package-lock.json, có --ignore-scripts, không nâng dependency. Lần chạy offline trước đó thiếu cache.
- npm run build: PASS, Next.js 16.1.6 biên dịch/TypeScript/prerender thành công. Lần chạy sandbox trước đó lỗi tải Google Fonts; chạy ngoài sandbox đã thành công. Không kiểm chứng API/database thực tế hoặc đầy đủ giao diện do ảnh chưa rõ quyền được giữ ngoài Git.
- npm run lint: FAIL, 38 errors và 21 warnings trong mã sẵn có (any, setState trong effect, prefer-const, hooks và img). Không sửa ngoài phạm vi. Các file frontend nguồn giữ nguyên byte, trừ .gitignore được cho phép lưu .env.example.
- Backend: Maven wrapper không khởi động, báo The system cannot find the path specified / Cannot start maven from wrapper. Đã thử với JAVA_HOME trỏ JDK 26 cục bộ; pom.xml yêu cầu Java 21. Chưa có kết quả compile/test backend, chưa kiểm chứng thay đổi cấu hình JWT bằng build.
- Python: không tìm được interpreter chạy được trong các vị trí thông dụng; WindowsApps chỉ có alias và C:/Python314 chỉ còn Lib. Tests crawler chưa được chạy. Số liệu pass trong README/audit cũ là dữ liệu lịch sử, không phải kết quả đợt này.
- Database: không tìm thấy migration SQL schema nghiệp vụ; ddl-auto=validate. Chưa xác minh dựng mới từ DB trống, restore dữ liệu, kết nối pgvector hay Gemini.
- Bảo mật: scan mẫu key/token/private key/JWT và đối chiếu credential viết trực tiếp trong cấu hình nguồn trên tập file đã chọn không còn phát hiện. Các phép gán biến password và tên cột @Column đã rà soát là kết quả khớp giả, không phải giá trị credential. Scan không đảm bảo phát hiện mọi bí mật.
- Lịch sử frontend: quét 208 blob qua 51 commit thuộc các ref hợp lệ, không phát hiện mẫu bí mật hoặc blob trên 5 MB. Ref desktop.ini hỏng được bỏ qua khi đọc, không sửa repo nguồn. Không đưa lịch sử này vào monorepo mới vì có tài nguyên ảnh chưa xác minh quyền sử dụng. Repo backend nguồn và cultural-museum chưa có commit trên HEAD; index và thay đổi gốc không bị sửa.
- Manifest có checksum SHA-256 cho file dữ liệu được liệt kê; checksum thư mục chưa tính. Chưa upload hoặc xác minh bản sao Google Drive. Drive IDs/link chưa biết để null.

Đây là baseline hiện trạng với giới hạn được ghi nhận, không phải xác nhận production-ready.
