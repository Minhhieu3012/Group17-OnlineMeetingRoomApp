from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import socket
import struct
import threading
import time
from typing import Generator, Iterable, Optional


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def chunk_bytes(data: bytes, chunk_size: int) -> Generator[bytes, None, None]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def file_sha256(path: str) -> str:
    hash_obj = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            hash_obj.update(block)
    return hash_obj.hexdigest()


class TokenBucket:
    def __init__(self, rate_bytes_per_sec: Optional[int], burst: Optional[int] = None) -> None:
        self.rate = rate_bytes_per_sec
        self.capacity = burst if burst is not None else (rate_bytes_per_sec or 0)
        self.tokens = self.capacity
        self.timestamp = time.monotonic()

    def consume(self, amount: int) -> None:
        if self.rate is None or self.rate <= 0:
            return
        now = time.monotonic()
        elapsed = now - self.timestamp
        self.timestamp = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= amount:
            self.tokens -= amount
            return
        needed = amount - self.tokens
        wait_time = needed / self.rate
        time.sleep(wait_time)
        self.tokens = 0


def recvall(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed during recvall")
        data.extend(packet)
    return bytes(data)


def send_json_length_prefixed(sock: socket.socket, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack("!I", len(data)))
    sock.sendall(data)


def recv_json_length_prefixed(sock: socket.socket) -> dict:
    (length,) = struct.unpack("!I", recvall(sock, 4))
    raw = recvall(sock, length)
    return json.loads(raw.decode("utf-8"))


class StoppableThread(threading.Thread):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def stopped(self) -> bool:
        return self._stop_event.is_set()
