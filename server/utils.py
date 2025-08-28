import os, json, base64, secrets, hashlib, hmac
from typing import Tuple

# -----------------------------
# Password hashing (PBKDF2-HMAC)
# -----------------------------
PBKDF2_ITER = 200_000
SALT_LEN = 16
KEY_LEN = 32  # 256-bit

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
    # so khớp an toàn thời gian
    return hmac.compare_digest(dk.hex(), hash_hex)

# -----------------------------
# AES-GCM (tùy chọn: cần 'cryptography')
# -----------------------------
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
    Trả về bytes, phù hợp để gửi qua TCP (đã có length-prefix).
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("AES unavailable: install 'cryptography'")
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ct  # bạn có thể base64 nếu muốn nhúng vào JSON

def aes_decrypt(blob: bytes, key: bytes) -> bytes:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("AES unavailable: install 'cryptography'")
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, associated_data=None)

# -----------------------------
# JSON helpers (đọc/ghi file nhỏ)
# -----------------------------
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
