#!/usr/bin/env python3
import threading
import sounddevice as sd
import numpy as np

CHUNK = 1024
FS = 16000
CHANNELS = 1

# ====== Gửi voice ======
def send_voice(sock):
    def callback(indata, frames, time, status):
        if status:
            print("⚠️ Lỗi ghi âm:", status)
        try:
            sock.sendall(indata.tobytes())
        except:
            pass

    with sd.InputStream(samplerate=FS, channels=CHANNELS, dtype=np.int16,
                        blocksize=CHUNK, callback=callback):
        threading.Event().wait()  # giữ luồng chạy

# ====== Nhận voice ======
def receive_voice(sock, stop_flag):
    with sd.OutputStream(samplerate=FS, channels=CHANNELS, dtype=np.int16,
                         blocksize=CHUNK) as out_stream:
        while not stop_flag.is_set():
            try:
                data = sock.recv(CHUNK * 2)
                if not data:
                    break
                audio = np.frombuffer(data, dtype=np.int16)
                out_stream.write(audio)
            except:
                break

# ====== Khởi động voice chat ======
def start_voice(sock):
    stop_flag = threading.Event()
    threading.Thread(target=send_voice, args=(sock,), daemon=True).start()
    threading.Thread(target=receive_voice, args=(sock, stop_flag), daemon=True).start()
    return stop_flag  # trả về để GUI có thể dùng stop_flag.set() khi ngắt
