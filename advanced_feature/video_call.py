import socket
import struct
import threading
import time
from typing import Optional, Callable

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

from advanced_feature import config

MAGIC = b"HPH1"
HDR_FMT = "!4sBHHI"  # magic, type, room_len, user_len, seq
HDR_SIZE = struct.calcsize(HDR_FMT)

MSG_VIDEO = 2
MSG_JOIN = 10
MSG_LEAVE = 11
MSG_KEEPALIVE = 12

MAX_DATAGRAM = 60000  # keep under typical UDP MTU limits


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


class VideoCallClient:
    def __init__(self, host: str, port: int, on_frame: Optional[Callable[[bytes], None]] = None) -> None:
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV (opencv-python) is not installed")
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.room = "default"
        self.user = "user"
        self._alive = False
        self._seq = 0
        self._tx: Optional[threading.Thread] = None
        self._rx: Optional[threading.Thread] = None
        self._cap = None
        self._show_window = True
        self._on_frame = on_frame

    def start(self, room: str, user: str, show_window: bool = True) -> None:
        self.room = room
        self.user = user
        self._show_window = show_window
        self._alive = True

        self._cap = cv2.VideoCapture(0)
        if not self._cap or not self._cap.isOpened():
            raise RuntimeError("Cannot open camera")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

        # JOIN
        self.sock.sendto(_pack(MSG_JOIN, self.room, self.user, 0, b""), (self.host, self.port))

        self._tx = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx.start(); self._rx.start()

    def stop(self) -> None:
        self._alive = False
        try:
            self.sock.sendto(_pack(MSG_LEAVE, self.room, self.user, 0, b""), (self.host, self.port))
        except Exception:
            pass
        time.sleep(0.05)
        try:
            if self._cap:
                self._cap.release()
            if self._show_window:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
        except Exception:
            pass

    def _tx_loop(self) -> None:
        next_keep = time.time() + 5
        while self._alive:
            ok, frame = self._cap.read() if self._cap else (False, None)
            if not ok:
                time.sleep(0.02)
                continue
            # Resize + JPEG compress to fit UDP
            frame = cv2.resize(frame, (640, 360))
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
            ok, buf = cv2.imencode('.jpg', frame, encode_param)
            if not ok:
                continue
            data = buf.tobytes()
            # If still too big, downscale quality once more
            if len(data) > MAX_DATAGRAM:
                encode_param[1] = 55
                ok, buf = cv2.imencode('.jpg', frame, encode_param)
                if not ok:
                    continue
                data = buf.tobytes()
            if len(data) > MAX_DATAGRAM:
                # Drop this frame
                continue
            self._seq = (self._seq + 1) & 0xFFFFFFFF
            pkt = _pack(MSG_VIDEO, self.room, self.user, self._seq, data)
            try:
                self.sock.sendto(pkt, (self.host, self.port))
            except Exception:
                pass
            if self._show_window:
                try:
                    cv2.imshow('Local', frame)
                    cv2.waitKey(1)
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
            if mtype != MSG_VIDEO or room != self.room or user == self.user:
                continue
            try:
                if self._on_frame:
                    self._on_frame(payload)
                if self._show_window:
                    arr = np.frombuffer(payload, dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        cv2.imshow('Remote', img)
                        cv2.waitKey(1)
            except Exception:
                pass
