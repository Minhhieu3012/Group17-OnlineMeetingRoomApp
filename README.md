# 🧑🏻‍💻 HPH Meeting - Ứng dụng Phòng Họp Trực Tuyến

## 📌 Giới thiệu
HPH Meeting là ứng dụng họp trực tuyến mô phỏng, hỗ trợ **real-time chat, voice chat, video call và multi-room**.  
Được xây dựng theo mô hình **Client–Server với TCP & UDP**, sản phẩm hướng đến sự **trực quan, dễ hiểu và có thể mở rộng**.

---

## 👀 Mục tiêu
- Tạo nền tảng giao tiếp thời gian thực với hiệu suất cao.  
- Đảm bảo an toàn cơ bản khi đăng nhập và truyền dữ liệu.  
- Giao diện trực quan, dễ dùng bằng Tkinter.  

---

## 🔎 Tính năng

### 💬 Chat văn bản (TCP)
- Truyền tin cậy với TCP (length-prefixed JSON).  
- Hỗ trợ **chat nhóm trong phòng** và **chat riêng (DM)**.  
- Server định tuyến tin nhắn đến đúng người.  

### 🎙️ Voice chat (UDP)
- Truyền âm thanh **UDP** để giảm độ trễ.  
- Dùng **PyAudio** (16kHz, mono, PCM).  
- Hỗ trợ bật/tắt micro.  

### 📹 Video call (UDP)
- Thu webcam → nén JPEG → chia gói (MTU 1200B) → gửi UDP.  
- Server relay frame theo phòng.  
- Client ghép gói → giải nén → hiển thị video.  
- Dùng **sequence number** để bỏ qua frame lỗi.  
- Hỗ trợ bật/tắt camera.  

### 🏠 Multi-room
- Tạo/join/thoát phòng.  
- Server duy trì danh sách phòng + thành viên.  
- Giao diện Lobby hiển thị real-time số người.  

### 🔐 Bảo mật
- Đăng nhập với **username + email**.  
- Session key **AES-256-GCM** cho TCP messages.  
- Input validation (regex).  
- Rate limiting cho UDP.  

### 🖥️ Giao diện
- **Tkinter GUI**: Login, Lobby, Room.  
- Điều khiển mic/cam, chat, tham gia phòng.  
- Gateway WebSocket ⇄ UDP/TCP (hướng mở rộng).  

---

## 🏗️ Kiến trúc
- **Server**: quản lý user, phòng, relay dữ liệu.  
- **Client**: gửi/nhận chat, audio, video.  
- **Multi-room**: hỗ trợ nhiều phòng song song.  

---

## 📋 Yêu cầu
- Python 3.8+
- Thư viện (xem requirements.txt):
-	cryptography>=42.0
-	numpy>=1.24
-	pyaudio>=0.2.13
-	opencv-python>=4.9.0
-	(Tùy chọn): Pillow để xử lý hình ảnh mượt hơn trong GUI.

---

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

---

## Cách chạy nhanh (Quick start)

### 1. Khởi động server
```sh
python main.py
```

### 2. Khởi động phần giao diện (GUI)
```sh
python -m Client.meeting_gui_client
```


