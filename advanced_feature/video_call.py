import socket
import struct
import threading
import time
import traceback
from typing import Optional, Callable

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

from advanced_feature import config

MAGIC = b"HPH1"
HDR_FMT = "!4sBHHI"
HDR_SIZE = struct.calcsize(HDR_FMT)

MSG_VIDEO = 2
MSG_JOIN = 10
MSG_LEAVE = 11
MSG_KEEPALIVE = 12

MAX_DATAGRAM = 60000


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
    def __init__(self,
                 host: str,
                 port: int,
                 on_remote_frame: Optional[Callable[[bytes], None]] = None,
                 on_local_frame: Optional[Callable[[np.ndarray], None]] = None) -> None:
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
        self._on_remote_frame = on_remote_frame
        self._on_local_frame = on_local_frame
        self.cam_visible = True  # bật/tắt video

    def _open_camera(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap or not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if not cap or not cap.isOpened():
            raise RuntimeError("Cannot open camera")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        return cap

    def start(self, room: str, user: str) -> None:
        self.room = room
        self.user = user
        self._alive = True

        self._cap = self._open_camera()
        self.sock.sendto(_pack(MSG_JOIN, self.room, self.user, 0, b""), (self.host, self.port))

        self._tx = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx.start(); self._rx.start()

    def stop(self) -> None:
        self._alive = False
        try:
            self.sock.sendto(_pack(MSG_LEAVE, self.room, self.user, 0, b""), (self.host, self.port))
        except:
            pass
        time.sleep(0.05)
        if self._cap:
            self._cap.release()

    def _tx_loop(self) -> None:
        fail_count = 0
        next_keep = time.time() + 5
        while self._alive:
            try:
                ok, frame = self._cap.read() if self._cap else (False, None)
                if not ok:
                    fail_count += 1
                    if fail_count > 10:
                        self._cap = self._open_camera()
                        fail_count = 0
                    time.sleep(0.05)
                    continue
                fail_count = 0

                # nếu cam OFF → tạo frame đen
                if not self.cam_visible:
                    frame = np.zeros((360, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Camera OFF", (180, 180),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

                # callback local frame
                if self._on_local_frame:
                    self._on_local_frame(frame)

                # compress JPEG
                frame = cv2.resize(frame, (640, 360))
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
                ok, buf = cv2.imencode('.jpg', frame, encode_param)
                if not ok:
                    continue
                data = buf.tobytes()
                if len(data) > MAX_DATAGRAM:
                    encode_param[1] = 55
                    ok, buf = cv2.imencode('.jpg', frame, encode_param)
                    if not ok:
                        continue
                    data = buf.tobytes()
                if len(data) > MAX_DATAGRAM:
                    continue

                self._seq = (self._seq + 1) & 0xFFFFFFFF
                pkt = _pack(MSG_VIDEO, self.room, self.user, self._seq, data)
                self.sock.sendto(pkt, (self.host, self.port))

                if time.time() >= next_keep:
                    self.sock.sendto(_pack(MSG_KEEPALIVE, self.room, self.user, 0, b""), (self.host, self.port))
                    next_keep = time.time() + 5

            except Exception:
                print("[VideoCall] Error in _tx_loop:\n", traceback.format_exc())
                time.sleep(0.1)

    def _rx_loop(self) -> None:
        self.sock.settimeout(1.0)
        while self._alive:
            try:
                data, _ = self.sock.recvfrom(65535)
                parsed = _parse(data)
                if not parsed:
                    continue
                mtype, room, user, seq, payload = parsed
                if mtype != MSG_VIDEO or room != self.room or user == self.user:
                    continue

                if self._on_remote_frame:
                    self._on_remote_frame(payload)

            except socket.timeout:
                continue
            except Exception:
                print("[VideoCall] Error in _rx_loop:\n", traceback.format_exc())
