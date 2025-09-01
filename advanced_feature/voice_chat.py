import socket
import struct
import threading
import time
from typing import Optional

try:
    import pyaudio
except Exception as e:
    pyaudio = None

from advanced_feature import config

MAGIC = b"HPH1"
HDR_FMT = "!4sBHHI"  # magic, type, room_len, user_len, seq
HDR_SIZE = struct.calcsize(HDR_FMT)

MSG_VOICE = 1
MSG_JOIN = 10
MSG_LEAVE = 11
MSG_KEEPALIVE = 12

AUDIO_RATE = 16000
AUDIO_CH = 1
SAMPLE_WIDTH = 2  # 16-bit
FRAME_MS = 20
FRAME_SAMPLES = int(AUDIO_RATE * FRAME_MS / 1000)  # 320
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_WIDTH  # 640


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
    def __init__(self, host: str, port: int) -> None:
        if pyaudio is None:
            raise RuntimeError("PyAudio is not installed")
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.room: str = "default"
        self.user: str = "user"
        self._alive = False
        self._seq = 0
        self._tx_thread: Optional[threading.Thread] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._pa = pyaudio.PyAudio()
        self._in = None
        self._out = None

    def start(self, room: str, user: str) -> None:
        self.room = room
        self.user = user
        self._alive = True

        # Audio streams
        self._in = self._pa.open(format=self._pa.get_format_from_width(SAMPLE_WIDTH),
                                  channels=AUDIO_CH, rate=AUDIO_RATE, input=True,
                                  frames_per_buffer=FRAME_SAMPLES)
        self._out = self._pa.open(format=self._pa.get_format_from_width(SAMPLE_WIDTH),
                                   channels=AUDIO_CH, rate=AUDIO_RATE, output=True,
                                   frames_per_buffer=FRAME_SAMPLES)

        # Send JOIN then start threads
        self.sock.sendto(_pack(MSG_JOIN, self.room, self.user, 0, b""), (self.host, self.port))
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
            if self._in:
                self._in.stop_stream(); self._in.close()
            if self._out:
                self._out.stop_stream(); self._out.close()
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass

    def _tx_loop(self) -> None:
        next_keep = time.time() + 5
        while self._alive:
            try:
                frame = self._in.read(FRAME_SAMPLES, exception_on_overflow=False)
            except Exception:
                frame = b"\x00" * FRAME_BYTES
            self._seq = (self._seq + 1) & 0xFFFFFFFF
            pkt = _pack(MSG_VOICE, self.room, self.user, self._seq, frame)
            try:
                self.sock.sendto(pkt, (self.host, self.port))
            except Exception:
                pass
            if time.time() >= next_keep:
                try:
                    self.sock.sendto(_pack(MSG_KEEPALIVE, self.room, self.user, 0, b""), (self.host, self.port))
                except Exception:
                    pass
                next_keep = time.time() + 5

    def _rx_loop(self) -> None:
        self.sock.settimeout(1.0)
        while self._alive:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            parsed = _parse(data)
            if not parsed:
                continue
            mtype, room, user, seq, payload = parsed
            if mtype != MSG_VOICE or room != self.room or user == self.user:
                continue
            try:
                self._out.write(payload)
            except Exception:
                pass
