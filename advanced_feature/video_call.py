from __future__ import annotations

import socket
import struct
import threading
from typing import Optional

from . import config
from .utils import TokenBucket, StoppableThread, setup_logger


logger = setup_logger("VideoCallClient")


try:
    import cv2  # type: ignore
except Exception as e:  # pragma: no cover
    cv2 = None  # type: ignore
    logger.warning("OpenCV chưa sẵn sàng: %s", e)


class VideoCallClient:
    def __init__(self, server_host: str = config.SERVER_HOST, port: int = config.UDP_PORT_VIDEO) -> None:
        self.server_host = server_host
        self.port = port
        self.bucket = TokenBucket(config.VIDEO_RATE_LIMIT_BPS, burst=(config.VIDEO_RATE_LIMIT_BPS or 0))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._send_thread: Optional[StoppableThread] = None
        self._recv_thread: Optional[StoppableThread] = None
        self._cap: Optional["cv2.VideoCapture"] = None

    def start(self, room_id: str, username: str, camera_index: int = 0, show_window: bool = True) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV không khả dụng. Vui lòng cài đặt 'opencv-python'.")
        self._cap = cv2.VideoCapture(camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.VIDEO_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.VIDEO_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.VIDEO_FPS)
        addr = (self.server_host, self.port)

        def send_loop() -> None:
            header = f"{room_id}|{username}".encode("utf-8")
            while not self._send_thread.stopped():  # type: ignore
                ret, frame = self._cap.read()  # type: ignore
                if not ret:
                    continue
                ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), config.VIDEO_JPEG_QUALITY])
                if not ok:
                    continue
                data = buf.tobytes()
                self.bucket.consume(len(data))
                # Fragment if needed
                max_payload = config.UDP_MAX_PAYLOAD
                total = len(data)
                total_frags = (total + max_payload - 1) // max_payload
                # Frame id can be a simple increasing counter per sender (wrap)
                # For simplicity we use Python id() over buffer slice, not perfect but okay for demo
                frame_id = (id(buf) & 0xFFFFFFFF)
                for frag_idx in range(total_frags):
                    start = frag_idx * max_payload
                    end = min(start + max_payload, total)
                    frag = data[start:end]
                    # MAGIC + header_len + header + frame_id(uint32) + total_frags(uint16) + frag_idx(uint16) + payload
                    packet = (
                        config.MAGIC_VIDEO
                        + struct.pack("!H", len(header))
                        + header
                        + struct.pack("!IHH", frame_id, total_frags, frag_idx)
                        + frag
                    )
                    self.sock.sendto(packet, addr)

        def recv_loop() -> None:
            # Naive: directly display incoming frames; no reassembly buffer for simplicity
            # If server relays single-fragment frames only, this will show them; for fragmented, a server-side aggregator can re-pack.
            if not show_window:
                return
            while not self._recv_thread.stopped():  # type: ignore
                pkt, _ = self.sock.recvfrom(65536)
                if not pkt.startswith(config.MAGIC_VIDEO):
                    continue
                hdr_len = struct.unpack("!H", pkt[2:4])[0]
                payload = pkt[4 + hdr_len + 8 :]  # skip frame_id(4)+total_frags(2)+frag_idx(2)
                img = cv2.imdecode(
                    __import__("numpy").frombuffer(payload, dtype=__import__("numpy").uint8),
                    cv2.IMREAD_COLOR,
                )
                if img is None:
                    continue
                cv2.imshow("Remote Video", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        self._send_thread = StoppableThread(target=send_loop, daemon=True)
        self._recv_thread = StoppableThread(target=recv_loop, daemon=True)
        self._send_thread.start()
        self._recv_thread.start()
        logger.info("Video call started.")

    def stop(self) -> None:
        if self._send_thread:
            self._send_thread.stop()
        if self._recv_thread:
            self._recv_thread.stop()
        if self._send_thread:
            self._send_thread.join(timeout=1)
        if self._recv_thread:
            self._recv_thread.join(timeout=1)
        if self._cap:
            self._cap.release()
        try:
            import cv2 as _cv2
            _cv2.destroyAllWindows()
        except Exception:
            pass
        logger.info("Video call stopped.")



