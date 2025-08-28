from __future__ import annotations

import socket
import struct
import threading
from typing import Optional

from . import config
from .utils import TokenBucket, StoppableThread, setup_logger


logger = setup_logger("VoiceChatClient")


try:
    import pyaudio  # type: ignore
except Exception as e:  # pragma: no cover - optional dependency at dev time
    pyaudio = None  # type: ignore
    logger.warning("PyAudio chưa sẵn sàng: %s", e)


class VoiceChatClient:
    def __init__(self, server_host: str = config.SERVER_HOST, port: int = config.UDP_PORT_VOICE) -> None:
        self.server_host = server_host
        self.port = port
        self.bucket = TokenBucket(config.VOICE_RATE_LIMIT_BPS, burst=(config.VOICE_RATE_LIMIT_BPS or 0))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._send_thread: Optional[StoppableThread] = None
        self._recv_thread: Optional[StoppableThread] = None
        self._pya: Optional["pyaudio.PyAudio"] = None
        self._stream_in = None
        self._stream_out = None

    def start(self, room_id: str, username: str, input_device_index: Optional[int] = None, output_device_index: Optional[int] = None) -> None:
        if pyaudio is None:
            raise RuntimeError("PyAudio không khả dụng. Vui lòng cài đặt 'pyaudio'.")
        self._pya = pyaudio.PyAudio()
        fmt = pyaudio.paInt16
        self._stream_in = self._pya.open(
            format=fmt,
            channels=config.VOICE_CHANNELS,
            rate=config.VOICE_SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.VOICE_FRAMES_PER_BUFFER,
            input_device_index=input_device_index,
        )
        self._stream_out = self._pya.open(
            format=fmt,
            channels=config.VOICE_CHANNELS,
            rate=config.VOICE_SAMPLE_RATE,
            output=True,
            frames_per_buffer=config.VOICE_FRAMES_PER_BUFFER,
            output_device_index=output_device_index,
        )

        addr = (self.server_host, self.port)

        def send_loop() -> None:
            header = f"{room_id}|{username}".encode("utf-8")
            while not self._send_thread.stopped():  # type: ignore
                data = self._stream_in.read(config.VOICE_FRAMES_PER_BUFFER, exception_on_overflow=False)
                self.bucket.consume(len(data))
                # Simple header: MAGIC + len(header) + header + pcm
                packet = config.MAGIC_VOICE + struct.pack("!H", len(header)) + header + data
                self.sock.sendto(packet, addr)

        def recv_loop() -> None:
            while not self._recv_thread.stopped():  # type: ignore
                pkt, _ = self.sock.recvfrom(2048)
                if not pkt.startswith(config.MAGIC_VOICE):
                    continue
                (_, hdr_len) = (pkt[:2], struct.unpack("!H", pkt[2:4])[0])
                pcm = pkt[4 + hdr_len :]
                self._stream_out.write(pcm)

        self._send_thread = StoppableThread(target=send_loop, daemon=True)
        self._recv_thread = StoppableThread(target=recv_loop, daemon=True)
        self._send_thread.start()
        self._recv_thread.start()
        logger.info("Voice chat started.")

    def stop(self) -> None:
        if self._send_thread:
            self._send_thread.stop()
        if self._recv_thread:
            self._recv_thread.stop()
        if self._send_thread:
            self._send_thread.join(timeout=1)
        if self._recv_thread:
            self._recv_thread.join(timeout=1)
        if self._stream_in:
            self._stream_in.stop_stream(); self._stream_in.close()
        if self._stream_out:
            self._stream_out.stop_stream(); self._stream_out.close()
        if self._pya:
            self._pya.terminate()
        logger.info("Voice chat stopped.")



