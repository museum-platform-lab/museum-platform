# Bộ công cụ Cào Dữ Liệu Vét Cạn & Tải Hình Ảnh (Museum Platform)

Bộ công cụ thu thập dữ liệu hiện vật, di tích lịch sử và di sản văn hóa Việt Nam theo cơ chế **vét cạn đệ quy (BFS Spider)**, tự động bám theo tất cả các liên kết nội bộ, trích xuất dữ liệu chuẩn hóa, **tải hình ảnh về máy** và đồng bộ trực tiếp vào cơ sở dữ liệu của dự án `museum-platform`.

---

## 📁 Cấu trúc thư mục

```
D:\project\museum-platform\scraper\
├── crawler.py                  # Script cào vét cạn chính (BFS Spider + Tự tải ảnh)
├── download_existing_images.py # Script tải ảnh hàng loạt cho file CSV có sẵn
├── merge_to_backend.py         # Script hợp nhất & chống trùng lặp vào artifacts.csv
├── requirements.txt            # Danh sách thư viện phụ thuộc
├── images/                     # Thư mục chứa ảnh đã tải về máy
└── README.md                   # Hướng dẫn sử dụng
```

---

## 📸 1. Tính năng Tải hình ảnh về máy (`Local Image Path`)

File CSV kết quả được bổ sung cột mới:
- **`Local Image Path`**: Lưu đường dẫn cục bộ của file ảnh đã tải về (ví dụ: `images/1125_Ngoc_Lu_I.jpg` hoặc `/artifacts/1125_Ngoc_Lu_I.jpg`).
- **`Main Image URL`**: Vẫn giữ nguyên link gốc (Wikimedia Commons / Online CDN) để dự phòng.

---

## 🚀 2. Hướng dẫn chạy cào dữ liệu & tải hình

### Cách 1: Cào vét cạn liên tục & tự động tải toàn bộ ảnh về máy
```bash
cd D:\project\museum-platform\scraper
python crawler.py
```
*Ảnh sẽ được lưu tự động vào thư mục `images/` và ghi đường dẫn vào cột `Local Image Path`.*

### Cách 2: Tải ảnh thẳng vào thư mục public của Next.js Frontend
Để website Next.js có thể load ảnh nội bộ ngay lập tức qua `/artifacts/...`:
```bash
python crawler.py --max-items 50 --frontend-public
```
*Ảnh sẽ được lưu vào `frontend/public/artifacts/` và cột `Local Image Path` ghi dạng `/artifacts/{id}_{name}.jpg`.*

### Cách 3: Cào dữ liệu nhưng KHÔNG tải file ảnh (chỉ lưu URL)
```bash
python crawler.py --no-download-images
```

---

## 📥 3. Tải hình ảnh cho file CSV đã có từ trước

Nếu bạn đã có file CSV (như `artifacts.csv` của backend hoặc file đã cào trước đó) và muốn tải toàn bộ hình ảnh về máy rồi cập nhật thêm cột `Local Image Path`:

```bash
# Tải ảnh cho file artifacts.csv của Backend (lưu vào thư mục images)
python download_existing_images.py ../backend/src/main/resources/artifacts.csv

# Hoặc tải ảnh thẳng vào thư mục public của Frontend
python download_existing_images.py ../backend/src/main/resources/artifacts.csv --frontend-public
```

---

## 🔄 4. Hợp nhất dữ liệu vào Backend

Hợp nhất các hiện vật mới vào file backend một cách an toàn (tự động bỏ qua các hiện vật đã tồn tại và tự tăng ID):

```bash
python merge_to_backend.py crawled_artifacts.csv ..\backend\src\main\resources\artifacts.csv
```
