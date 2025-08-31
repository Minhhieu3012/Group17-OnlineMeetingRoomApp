import os, json, base64, secrets, hashlib, hmac
import logging
import queue
import socket
import struct
import threading
import time
from typing import Tuple, Generator, Optional
from pathlib import Path

# Password hashing constants
PBKDF2_ITER = 200_000
SALT_LEN = 16
KEY_LEN = 32

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

def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Trả về (salt_hex, hash_hex) dùng PBKDF2-HMAC-SHA256.
    """
    if salt is None:
        salt = os.urandom(SALT_LEN)
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, PBKDF2_ITER, dklen=KEY_LEN)
    return salt.hex(), dk.hex()

def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, PBKDF2_ITER, dklen=KEY_LEN)
    return hmac.compare_digest(dk.hex(), hash_hex)

# AES-GCM encryption
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except Exception:
    AESGCM = None
    CRYPTO_AVAILABLE = False

def generate_session_key() -> bytes:
    """Sinh khóa phiên 32 byte (256-bit)."""
    return os.urandom(32)

def aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    Mã hóa AES-GCM. Gói dữ liệu = nonce(12B) | ciphertext | tag(16B).
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("AES unavailable: install 'cryptography'")
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ct

def aes_decrypt(blob: bytes, key: bytes) -> bytes:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("AES unavailable: install 'cryptography'")
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, associated_data=None)

# JSON helpers
def read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default

def write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
