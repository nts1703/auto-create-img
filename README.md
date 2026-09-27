# AI Automation Workflow Tool

Công cụ tự động hóa quy trình: Upload ảnh lên Gemini -> Tải kết quả -> Upload lên Meta AI -> Tạo video.

## 1. Cấu trúc dự án
- `app.py`: Chạy server Flask và điều khiển Playwright.
- `templates/index.html`: Giao diện web đơn giản.
- `state.json`: Lưu phiên đăng nhập (phải tạo thủ công sau lần đăng nhập đầu tiên).
- `uploads/` & `downloads/`: Thư mục lưu trữ tệp tin tạm thời.

## 2. Bảng Selector (Địa chỉ các nút bấm)

Dưới đây là các tọa độ "vàng" để bot tương tác với giao diện web:

| Trang | Chức năng | Selector (Bộ chọn) |
| :--- | :--- | :--- |
| **Gemini** | Ô nhập liệu | `div[aria-label="Nhập câu lệnh cho Gemini"]` |
| **Gemini** | Nút Gửi | `button[aria-label="Gửi tin nhắn"]` |
| **Meta AI** | Ô nhập liệu | `div[data-testid="composer-input"]` |
| **Meta AI** | Nút Gửi | `button[data-testid="composer-send-button"]` |
| **Meta AI** | Nút "Tạo video" | `button[data-slot="capability-pill"]:has-text("Tạo video")` |
| **Meta AI** | Tải ảnh (Input ẩn) | `input[type="file"].hidden` |

data-test-id="local-images-files-uploader-button"

Các thuộc tính có chữ data-test-id là do chính các kỹ sư của Google tạo ra để phục vụ việc viết code tự động hóa (test tự động). Nó cực kỳ ổn định, không bao giờ lo bị đổi kể cả khi Google thay đổi giao diện hay ngôn ngữ từ tiếng Anh sang tiếng Việt.

## 3. Cách cài đặt & Chạy
1. **Cài đặt thư viện:**
   ```bash
   pip install flask playwright
   playwright install