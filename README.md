# 🧑🏻‍💻 Ứng dụng Phòng Họp Trực Tuyến

## 📌 Giới thiệu
- Đề tài mô phỏng một ứng dụng họp trực tuyến cơ bản, hỗ trợ nhiều tính năng **real-time** như chat, gửi file, voice chat, video call và quản lý nhiều phòng họp.  
- Mục tiêu chính là xây dựng **hệ thống client-server sử dụng socket TCP/UDP** để đảm bảo tính trực quan, dễ hiểu, và có thể mở rộng về sau.

---

## 🔎 Ý tưởng & Tính năng

### 1. Chat văn bản (TCP)
- Sử dụng **TCP socket** để đảm bảo tin nhắn đến đầy đủ, không mất mát.  
- Server quản lý danh sách user, phân phối tin nhắn, **broadcast theo từng phòng**.

### 2. Gửi file (TCP/UDP + kiểm tra lỗi)
- Hỗ trợ gửi file nhỏ (PDF, Word, ảnh).  
- Có cơ chế đóng gói dữ liệu và kiểm tra kích thước để truyền file chính xác.  

### 3. Voice chat (UDP)
- Âm thanh được truyền qua **UDP** để giảm độ trễ.  
- Dùng thư viện **PyAudio** để thu và phát âm thanh theo thời gian thực.  

### 4. Video call (UDP)
- Client: sử dụng **OpenCV** để đọc webcam → nén frame (JPEG) → chia nhỏ gói (MTU ~1200B) → gửi UDP.  
- Server: relay frame theo phòng/người nhận.  
- Client nhận: ghép gói → giải nén → hiển thị video.  
- Có thể mất một số gói (UDP) → dùng số thứ tự frame để bỏ qua frame lỗi.  

### 5. Quản lý nhiều phòng họp (Multi-room)
- Người dùng có thể **tạo phòng mới**, tham gia phòng có sẵn.  
- Server quản lý nhiều nhóm kết nối song song.  

### 6. Chat riêng (Direct Message)
- Hỗ trợ gửi tin nhắn riêng giữa 2 user (server định tuyến chính xác đến người nhận).  

### 7. Cơ chế bảo mật cơ bản
- Đăng nhập với **username + email**.  
- Có thể tích hợp mã hóa **AES hoặc SSL socket** để bảo mật dữ liệu.  

### 8. Giao diện
- Client Python (CLI hoặc Tkinter).  
- Web client (HTML/CSS/JS) kết nối qua **WebSocket** tới server để:  
  - Đăng nhập  
  - Chat, quản lý phòng  
  - Điều khiển (bật/tắt mic/cam, mời call)  
- Với voice/video: có thể chạy gateway Python để kết nối **WebSocket ⇄ UDP/TCP**.  

---

## 🏗️ Kiến trúc hệ thống
- **Server chính**: quản lý user, phòng họp, định tuyến tin nhắn, relay dữ liệu.  
- **Client**: gửi/nhận dữ liệu (chat, file, audio, video).  
- **Multi-room**: nhiều client có thể tham gia các phòng khác nhau đồng thời.  
- **Web + Gateway (optional)**: web interface cho chat/điều khiển, relay sang server socket thật.   

---

## Security
- Passwords được hash với PBKDF2-HMAC-SHA256
- Session keys sử dụng AES-256-GCM encryption
- Rate limiting cho file transfer và UDP packets
- Input validation cho tất cả user inputs

---

## Cài đặt
### 1. Cài đặt dependencies
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 2. (Tùy chọn) Cài đặt audio/video dependencies
\`\`\`bash
# Cho video processing
pip install opencv-python

# Cho audio processing (cần build tools)
pip install pyaudio
\`\`\`

## Sử dụng

### Khởi động toàn bộ hệ thống
\`\`\`bash
python main.py
\`\`\`

### Khởi động từng component riêng lẻ
\`\`\`bash
# Chỉ TCP server
python main.py --component tcp

# Chỉ UDP server  
python main.py --component udp

# Chỉ WebSocket gateway
python main.py --component gateway
\`\`\`

### Truy cập web interface
Mở trình duyệt và truy cập: `http://localhost:8080`

## Tài khoản mặc định

Hệ thống tạo sẵn các tài khoản test:
- Username: `test`, Password: `123456`
- Username: `admin`, Password: `admin123`

### Lỗi audio/video
\`\`\`bash
# Cài đặt system dependencies cho audio
sudo apt-get install portaudio19-dev python3-pyaudio

# Cho video
sudo apt-get install python3-opencv
\`\`\`

