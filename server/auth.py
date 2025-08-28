"""time: làm việc với timestamp, uuid: tạo id duy nhất cho session token, base64: mã hóa/giải mã dữ liệu"""
import time, uuid, base64 
from typing import Dict, Optional, Tuple
from pathlib import Path # xử lý đường dẫn file hiện tại 

from utils import ( # các hàm tiện ích tự viết 
    hash_password, verify_password, read_json, write_json,
    generate_session_key
)

USERS_DB = Path(__file__).with_name("users_db.json") # tạo đường dẫn đến file users_db.json cùng thư mục 

# Quản lý người dùng 
class UserStore:
    def __init__(self, path: Path = USERS_DB):
        self.path = path    
        self.data = {"users": {}}
        self.load() # đọc dữ liệu từ file 

    def load(self):
        self.data = read_json(str(self.path), {"users": {}}) # file kh tồn tại thì dùng default {"users": {}}

    # lưu dữ liệu hiện tại xuống file Json
    def save(self):
        write_json(str(self.path), self.data)

    # kiểm tra username đã tồn tại chưa 
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


# Khởi tạo store và user mặc định nếu chưa có
_store = UserStore()
if not _store.exists("test"):
    _store.add_user("test", "123456")  # tài khoản mẫu để chạy thử

# Quản lý phiên (in-memory)
# sessions: username -> {"token": str, "key": bytes, "created_at": ts, "last_seen": ts}
_sessions: Dict[str, Dict] = {}

# Wrapped function để xác thực user
def authenticate_user(username: str, password: str) -> bool:
    """Xác thực username/password từ file JSON."""
    return _store.verify(username, password)

def register_user(username: str, password: str) -> bool:
    """Đăng ký tài khoản mới (nếu muốn)."""
    return _store.add_user(username, password)

def create_session(username: str) -> Tuple[str, bytes]:
    """
    Tạo session mới: sinh token và khóa AES.
    Trả về (token, aes_key_bytes).
    """
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
