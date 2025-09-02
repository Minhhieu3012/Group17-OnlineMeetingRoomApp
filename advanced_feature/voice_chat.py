import socket
import struct
import threading
import time
from typing import Optional, Callable

try:
    import pyaudio
except Exception:
    pyaudio = None

MAGIC = b"HPH1"
HDR_FMT = "!4sBHHI"  # magic, type, room_len, user_len, seq
HDR_SIZE = struct.calcsize(HDR_FMT)

MSG_VOICE = 1
MSG_JOIN = 10
MSG_LEAVE = 11
MSG_KEEPALIVE = 12

# PCM 16kHz mono 16-bit, frame 20ms (320 mẫu = 640 bytes)
AUDIO_RATE = 16000
AUDIO_CH = 1
SAMPLE_WIDTH = 2
FRAME_MS = 20
FRAME_SAMPLES = int(AUDIO_RATE * FRAME_MS / 1000)  # 320
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_WIDTH         # 640

# ============== helpers ==============
def _pack(mtype: int, room: str, user: str, seq: int, payload: bytes) -> bytes:
    room_b = room.encode(); user_b = user.encode()
    header = struct.pack(HDR_FMT, MAGIC, mtype, len(room_b), len(user_b), seq)
    return header + room_b + user_b + payload

def _parse(data: bytes):
    if len(data) < HDR_SIZE:
        return None
    magic, mtype, rlen, ulen, seq = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    if magic != MAGIC:
        return None
    off = HDR_SIZE
    try:
        room = data[off:off + rlen].decode(); off += rlen
        user = data[off:off + ulen].decode(); off += ulen
    except Exception:
        return None
    payload = data[off:]
    return mtype, room, user, seq, payload


class VoiceChatClient:
    """
    UDP voice client: gửi/nhận PCM 16kHz mono 16-bit.
    - start(room, user): mở mic/speaker và JOIN.
    - stop(): đóng luồng, LEAVE.
    - mute: set self.mic_enabled = False để gửi khung im lặng.
    - volume_playback: 0.0..2.0 (nhân biên độ khi phát).
    """
    def __init__(self,
                 host: str,
                 port: int,
                 on_error: Optional[Callable[[str], None]] = None) -> None:
        if pyaudio is None:
            raise RuntimeError("PyAudio is not installed")
        self.host = host
        self.port = int(port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.0)

        self.room = "default"
        self.user = "user"
        self._alive = False
        self._seq = 0

        self._tx_thread: Optional[threading.Thread] = None
        self._rx_thread: Optional[threading.Thread] = None

        self._pa = pyaudio.PyAudio()
        self._mic = None   # input stream
        self._spk = None   # output stream

        self.mic_enabled = True         # tắt/bật mic (nhưng vẫn giữ kết nối)
        self.volume_playback = 1.0       # nhân biên độ khi phát
        self.on_error = on_error

    # ---------- lifecycle ----------
    def start(self, room: str, user: str) -> None:
        self.room = room
        self.user = user
        self._alive = True

        # open streams
        fmt = self._pa.get_format_from_width(SAMPLE_WIDTH)
        try:
            self._mic = self._pa.open(format=fmt, channels=AUDIO_CH, rate=AUDIO_RATE,
                                      input=True, frames_per_buffer=FRAME_SAMPLES)
        except Exception:
            # Không có mic? vẫn chạy nhưng gửi im lặng
            self._mic = None

        self._spk = self._pa.open(format=fmt, channels=AUDIO_CH, rate=AUDIO_RATE,
                                  output=True, frames_per_buffer=FRAME_SAMPLES)

        # JOIN
        self.sock.sendto(_pack(MSG_JOIN, self.room, self.user, 0, b""), (self.host, self.port))

        # threads
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx_thread.start(); self._rx_thread.start()

    def stop(self) -> None:
        self._alive = False
        try:
            self.sock.sendto(_pack(MSG_LEAVE, self.room, self.user, 0, b""), (self.host, self.port))
        except Exception:
            pass
        time.sleep(0.05)
        try:
            if self._mic:
                self._mic.stop_stream(); self._mic.close()
        except Exception:
            pass
        try:
            if self._spk:
                self._spk.stop_stream(); self._spk.close()
        except Exception:
            pass
        try:
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    # ---------- loops ----------
    def _tx_loop(self) -> None:
        next_keep = time.time() + 5
        while self._alive:
            try:
                if self.mic_enabled and self._mic:
                    try:
                        frame = self._mic.read(FRAME_SAMPLES, exception_on_overflow=False)
                    except Exception:
                        # đọc lỗi → gửi im lặng
                        frame = b"\x00" * FRAME_BYTES
                else:
                    # mic off → gửi im lặng để giữ đồng bộ
                    frame = b"\x00" * FRAME_BYTES

                self._seq = (self._seq + 1) & 0xFFFFFFFF
                pkt = _pack(MSG_VOICE, self.room, self.user, self._seq, frame)
                self.sock.sendto(pkt, (self.host, self.port))

                # keepalive định kỳ
                if time.time() >= next_keep:
                    self.sock.sendto(_pack(MSG_KEEPALIVE, self.room, self.user, 0, b""), (self.host, self.port))
                    next_keep = time.time() + 5

            except Exception as e:
                if self.on_error:
                    self.on_error(f"TX error: {e}")
                time.sleep(0.05)

    def _rx_loop(self) -> None:
        import numpy as np
        while self._alive:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception as e:
                if self.on_error:
                    self.on_error(f"RX socket error: {e}")
                break

            parsed = _parse(data)
            if not parsed:
                continue
            mtype, room, user, seq, payload = parsed
            if mtype != MSG_VOICE or room != self.room or user == self.user:
                continue

            # scale volume nếu cần
            if self._spk and payload:
                if self.volume_playback != 1.0:
                    # int16 scale
                    arr = np.frombuffer(payload, dtype=np.int16).astype(np.float32)
                    arr = np.clip(arr * float(self.volume_playback), -32768, 32767).astype(np.int16)
                    payload = arr.tobytes()
                try:
                    self._spk.write(payload)
                except Exception as e:
                    if self.on_error:
                        self.on_error(f"Playback error: {e}")
