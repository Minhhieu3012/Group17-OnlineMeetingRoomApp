"""time: làm việc với timestamp, uuid: tạo id duy nhất cho session token, base64: mã hóa/giải mã dữ liệu"""
import time, uuid, base64
from typing import Dict, Optional, Tuple
from pathlib import Path

from .utils import (
    hash_password, verify_password, read_json, write_json,
    generate_session_key
)

USERS_DB = Path(__file__).with_name("users_db.json")

# ===============================
# Quản lý người dùng
# ===============================
class UserStore:
    def __init__(self, path: Path = USERS_DB):
        self.path = path
        self.data = {"users": {}}
        self.load()

    def load(self):
        self.data = read_json(str(self.path), {"users": {}})

    def save(self):
        write_json(str(self.path), self.data)

    def exists(self, username: str) -> bool:
        return username in self.data["users"]

    def add_user(self, username: str, password: str) -> bool:
        if self.exists(username):
            return False
        salt_hex, hash_hex = hash_password(password)
        self.data["users"][username] = {
            "salt": salt_hex,
            "hash": hash_hex,
            "created_at": int(time.time())
        }
        self.save()
        return True

    def verify(self, username: str, password: str) -> bool:
        user = self.data["users"].get(username)
        if not user:
            return False
        return verify_password(password, user["salt"], user["hash"])


# ===============================
# Khởi tạo store & user mặc định
# ===============================
_store = UserStore()
if not _store.exists("test"):
    _store.add_user("test", "123456")  # tài khoản mẫu để test nhanh


# ===============================
# Quản lý phiên (in-memory)
# sessions: username -> {"token": str, "key": bytes, ...}
# ===============================
_sessions: Dict[str, Dict] = {}


# ===============================
# API chính cho TCP server gọi
# ===============================
def login_or_register(username: str, password: str) -> Tuple[bool, str]:
    """
    Nếu user tồn tại -> xác thực.
    Nếu chưa tồn tại -> tự động đăng ký.
    Trả về (ok, message).
    """
    if _store.exists(username):
        if _store.verify(username, password):
            return True, "Login successful"
        else:
            return False, "Invalid credentials"
    else:
        _store.add_user(username, password)
        return True, "User registered automatically"


def create_session(username: str) -> Tuple[str, bytes]:
    """Tạo session mới: sinh token và khóa AES."""
    token = uuid.uuid4().hex
    key = generate_session_key()
    now = time.time()
    _sessions[username] = {
        "token": token,
        "key": key,
        "created_at": now,
        "last_seen": now
    }
    return token, key


def end_session(username: str) -> None:
    _sessions.pop(username, None)


def touch_session(username: str) -> None:
    if username in _sessions:
        _sessions[username]["last_seen"] = time.time()


def get_session_key(username: str) -> Optional[bytes]:
    sess = _sessions.get(username)
    return sess["key"] if sess else None


def verify_token(username: str, token: str) -> bool:
    sess = _sessions.get(username)
    return bool(sess and sess["token"] == token)
