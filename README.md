# HLC Cloud - Live Automation v2 PRO

Hệ thống tự động hóa chuyển cảnh, phát video livestream và quản lý phát sóng đa thương hiệu thông qua **OBS WebSocket v5**, giao diện Web Dashboard Cyberpunk điều khiển thời gian thực và xác thực bản quyền Cloud.

---

## 🌟 4 Nâng Cấp Đột Phá Trên Phiên Bản v2 PRO

1. ⚡ **WebSocket `ExecuteBatch` (< 5ms)**:
   - Gộp toàn bộ lệnh ẩn video cũ, hiện video mới và kích hoạt phát lại vào **1 gói tin WebSocket duy nhất**.
   - Tốc độ chuyển cảnh tăng gấp 60 lần, chuyển video trong chớp mắt không có độ trễ.

2. 🛡️ **Dedicated `Web Worker` Engine (Chống ngủ tab / Chống lag CPU)**:
   - Bộ đếm thời gian được chạy trên luồng ngầm Web Worker độc lập.
   - Không bị Chrome/Edge bóp nghẹt khi thu nhỏ trình duyệt hay khóa màn hình, đảm bảo live 24/7 mượt mà.

3. 🎮 **Stream Deck Ảo & Phím Tắt Nhanh (Keyboard Shortcuts) + Cài Đặt PWA Desktop**:
   - Phím số **`1` &rarr; `28`**: Xếp video vào hàng đợi Queue.
   - **`Shift + Số`**: Fast Switch cắt ngang phát ngay lập tức.
   - **`Space`**: Tạm dừng / Tiếp tục chế độ Chờ (Standby).
   - **`F`**: Bật / Tắt nhanh chế độ ⚡ Fast Track.
   - **`L`**: Phím tắt Bắt đầu / Dừng Live Stream.
   - **`PWA`**: Hỗ trợ cài đặt thành ứng dụng Desktop độc lập trên Windows chỉ bằng 1 cú nhấp chuột.

4. 🤖 **Auto-Pilot AI: Live Chat Trigger & Webhook**:
   - Tự động nhận diện từ khóa bình luận (mẫu, mã, áo, sp, số...) từ khách hàng để tự động đổi video.
   - Có bảng mô phỏng thử nghiệm bình luận và hỗ trợ endpoint Webhook `/api/chat/webhook`.


---

---

## 🚀 Hai Phiên Bản Hoạt Động Song Song

Dự án cung cấp 2 phiên bản độc lập để bạn linh hoạt sử dụng:

### 1. Bản 1-Click Cục Bộ (`CHAY_LIVE.bat`)
- Nhấp đúp vào file **`CHAY_LIVE.bat`**.
- Hệ thống tự kiểm tra thư viện, tự kết nối OBS nội bộ `127.0.0.1:4455`, tự động mở **Cloudflare Tunnel** sinh link online bảo mật HTTPS (`https://xxx.trycloudflare.com`) để điều khiển từ xa qua điện thoại.

### 2. Bản Web Thuần GitHub Pages (`docs/`)
- Chạy 100% bằng JavaScript trực tiếp trên trình duyệt, không cần cài đặt Python.
- Cách kích hoạt trên GitHub:
  1. Vào kho mã nguồn trên GitHub: **Settings** &rarr; **Pages**.
  2. Tại mục **Build and deployment** &rarr; **Source**: Chọn **Deploy from a branch**.
  3. Chọn Branch: **`master`** và Folder: **`/docs`** &rarr; Bấm **Save**.
  4. GitHub sẽ cấp đường link: `https://<username>.github.io/next-live-automation/`.
  5. Bất kỳ ai mở link này trên máy tính có OBS đều có thể điều khiển trực tiếp OBS của máy tính đó!

---

## 📁 Cấu Trúc Dự Án

```text
Next Live Automation/
├── config.py                 # File cấu hình trung tâm (OBS, Supabase, Ports)
├── requirements.txt          # Thư viện phụ thuộc
├── run.py                    # Entry point khởi động ứng dụng
├── core/
│   ├── state.py              # Thread-safe State, Standby & Fast Switch Event
│   ├── profile_manager.py    # Quản lý Profiles JSON, lọc base_ & đo OpenCV
│   ├── obs_engine.py         # Bộ điều khiển OBS WebSocket, RTMP Stream & Scene
│   └── quota_manager.py      # Quản lý xác thực bản quyền & Quota Supabase
├── web/
│   ├── app.py                # Khởi tạo Flask App
│   ├── routes/
│   │   ├── auth_routes.py    # Login & kích hoạt Cloud Key
│   │   ├── live_routes.py    # Order, Fast-Track, State Polling, Terminate
│   │   ├── profile_routes.py # Đổi Scene, lưu Brand, quét Scene OBS
│   │   └── stream_routes.py  # Cấu hình RTMP Server/Key & Điều khiển Live
│   └── templates/
│       └── index.html        # Web Dashboard Cyberpunk
└── profiles/                 # Thư mục lưu cấu hình từng phiên live / brand
    ├── wipro.json
    └── demo_brand.json
```

---

## ⚙️ Thiết Lập Môi Trường (Tùy chọn)

Bạn có thể cấu hình các biến môi trường nếu cần:
- `OBS_HOST`: Địa chỉ IP của máy chạy OBS (mặc định `127.0.0.1`)
- `OBS_PORT`: Cổng OBS WebSocket (mặc định `4455`)
- `OBS_PASSWORD`: Mật khẩu OBS WebSocket (nếu có đặt mật khẩu)

---
&copy; 2026 HLC Cloud Automation Team.
