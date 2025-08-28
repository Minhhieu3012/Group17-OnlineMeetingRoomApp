# tập hợp các function bảo mật và tiện ích quan trọng 
"""
os.urandom: tạo random bytes an toàn từ OS, 
hashlib.pbkdf2_hmac: password-based key derivation func, 
hmac.compare_digest: so sánh an toàn chống timing hack 
"""
import os, json, base64, secrets, hashlib, hmac
from typing import Tuple


PBKDF2_ITER = 200_000 # số lần lặp đủ chậm để chống brute force
SALT_LEN = 16 # 16 bytes salt
KEY_LEN = 32  # 32 bytes key (256-bit) 

def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Trả về (salt_hex, hash_hex) dùng PBKDF2-HMAC-SHA256.
    """
    if salt is None:
        salt = os.urandom(SALT_LEN) # tạo salt ngẫu nhiên 16 bytes (salt ngăn chặn rainbow table attacks)
    pwd = password.encode("utf-8") # convert string -> bytes (PBKDF2 yêu cầu bytes)
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, PBKDF2_ITER, dklen=KEY_LEN) # (1)algorithm: SHA-256, (5)output length: 32 bytes
    return salt.hex(), dk.hex()

def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex) # convert hex string -> bytes
    pwd = password.encode("utf-8") # password -> bytes
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, PBKDF2_ITER, dklen=KEY_LEN)
    return hmac.compare_digest(dk.hex(), hash_hex) # compare_digest: chống timing attacks, so sánh từng byte một cách constant-time (tgian không đổi)


# AES-GCM (tùy chọn: cần 'cryptography')
# kiểm tra thư viện cryptography có sẵn không 
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except Exception:
    AESGCM = None
    CRYPTO_AVAILABLE = False

# Tạo AES-256 key ngẫu nhiên từ OS entropy
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
    aes = AESGCM(key) # tạo AES-GCM cipher với key
    nonce = os.urandom(12) # tạo nonce 12 bytes (GCM standard)
    ct = aes.encrypt(nonce, plaintext, associated_data=None) # trả về: ciphertext + authentication_tag (16 bytes)  
    return nonce + ct  # ghép nonce + ciphertext + tag

def aes_decrypt(blob: bytes, key: bytes) -> bytes:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("AES unavailable: install 'cryptography'")
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:] # tách nonce và (ciphertext+tag)
    return aes.decrypt(nonce, ct, associated_data=None) # giải mã và verify authentication tag 

# JSON helpers (đọc/ghi file nhỏ)
def read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default

def write_json(path: str, data) -> None:
    tmp = path + ".tmp" # tạo tên file temporary 
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2) # ensure_ascii=False: allow Unicode characters, indent=2: Format đẹp, dễ đọc 
    os.replace(tmp, path)