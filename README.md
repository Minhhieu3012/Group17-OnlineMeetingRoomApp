# 🧑🏻‍💻 HPH Meeting - Ứng dụng Phòng Họp Trực Tuyến

## 📌 Giới thiệu
- Đề tài mô phỏng một ứng dụng họp trực tuyến cơ bản, hỗ trợ nhiều tính năng **real-time** như chat, voice chat, video call và quản lý nhiều phòng họp.  
- Mục tiêu chính là xây dựng **hệ thống client-server sử dụng socket TCP/UDP** để đảm bảo tính trực quan, dễ hiểu, có thể mở rộng và tích hợp bảo mật cơ bản.

---

## 👀 Mục tiêu 
- Cung cấp nền tảng giao tiếp thời gian thực với hiệu suất cao.
- Đảm bảo tính bảo mật cho đăng nhập và truyền dữ liệu.
- Hỗ trợ giao diện người dùng thân thiện (GUI) bằng Tkinter.

---

## 🔎 Tính năng

### 1. Chat văn bản (TCP)
- Sử dụng **TCP socket** để đảm bảo tin nhắn được truyền đầy đủ, không mất mát.
- Hỗ trợ chat nhóm **broadcast trong phòng** và chat riêng (direct message - DM).
- Server quản lý danh sách người dùng và phòng, định tuyến tin nhắn chính xác.

### 2. Voice chat (UDP)
- Âm thanh được truyền qua **UDP** để giảm độ trễ.  
- Dùng thư viện **PyAudio** để thu và phát âm thanh theo thời gian thực.  
- Server relay dữ liệu âm thanh giữa các client trong cùng phòng.
- Hỗ trợ bật/tắt micro.

### 3. Video call (UDP)
- Client: sử dụng **OpenCV** để đọc webcam → nén frame (JPEG) → chia nhỏ gói (MTU ~1200B) → gửi UDP.  
- Server: relay frame theo phòng/người nhận.  
- Client nhận: ghép gói → giải nén → hiển thị video.  
- Có thể mất một số gói (UDP) → dùng số thứ tự frame để bỏ qua frame lỗi.  
- Hỗ trợ bật/tắt camera 

### 4. Quản lý nhiều phòng họp (Multi-room)
- Server quản lý nhiều nhóm kết nối song song.  
- Server duy trì trạng thái phòng (danh sách người tham gia) và cập nhật real-time.
- Người dùng có thể tạo phòng mới, tham gia phòng có sẵn hoặc rời phòng.
- Giao diện sảnh chờ (Lobby) hiển thị danh sách phòng và số người tham gia.

### 5. Cơ chế bảo mật cơ bản
- Đăng nhập với **username + email**.  
- Có thể tích hợp mã hóa **AES hoặc SSL socket** để bảo mật dữ liệu.  

### 6. Giao diện
- Client Python (CLI hoặc Tkinter).  
  - Đăng nhập  
  - Chat, quản lý phòng  
  - Điều khiển (bật/tắt mic/cam, mời call)  
- Với voice/video: có thể chạy gateway Python để kết nối **WebSocket ⇄ UDP/TCP**.  

---

## 🏗️ Kiến trúc hệ thống
- **Server chính**: quản lý user, phòng họp, định tuyến tin nhắn, relay dữ liệu.  
- **Client**: gửi/nhận dữ liệu (chat, file, audio, video).  
- **Multi-room**: nhiều client có thể tham gia các phòng khác nhau đồng thời.  

---

## 🛡️ Bảo mật
- Passwords được hash với PBKDF2-HMAC-SHA256
- Session keys sử dụng AES-256-GCM encryption
- Rate limiting cho UDP packets
- Input validation cho tất cả user inputs

---

## 📋 Yêu cầu
- Python 3.8+
- Thư viện (xem requirements.txt):
-	cryptography>=42.0
-	numpy>=1.24
-	pyaudio>=0.2.13
-	opencv-python>=4.9.0
-	(Tùy chọn): Pillow để xử lý hình ảnh mượt hơn trong GUI.

## Cài đặt (Implement)
### 1. Cài đặt dependencies
```sh
pip install -r requirements.txt
```

### 2. (Tùy chọn) Cài đặt audio/video dependencies
#### Cho video processing:
```sh
pip install opencv-python
```

#### Cho audio processing (cần build tools):
```sh
pip install pyaudio

```

## Cách chạy nhanh (Quick start)
### 1. Khởi động server
```sh
python main.py
```

### 2. Khởi động phần giao diện (GUI):
```sh
python -m Client.meeting_gui_client
```


