import asyncio # xử lý bất đồng bộ
import base64
import time
from typing import Dict

from routing import relay_message # chuyển tiếp msg đến client khác 
from protocol import send_msg # gửi response về client

# Cấu hình giới hạn
MAX_FILE_SIZE = 20 * 1024 * 1024    # 20MB
MAX_CHUNK_SIZE = 1_500_000          # 1.5MB
RATE_LIMIT = 5                      # 5 files mỗi phút / user

# Bộ nhớ tạm để theo dõi tần suất gửi file
file_rate: Dict[str, list] = {}  # username -> list of timestamps


async def handle_file_meta(username: str, msg: dict, writer):
    """
    Xử lý metadata của file (tên file, kích thước, gửi tới ai/room nào)
    """
    payload = msg.get("payload", {})
    size = payload.get("size", 0)
    fname = payload.get("name", "unknown")

    # Kiểm tra kích thước file (file > 20MB)
    if size > MAX_FILE_SIZE:
        await send_msg(writer, {"ok": False, "error": "File too large (max 20MB)"})
        return False

    # Kiểm tra rate limit (user gửi quá 5 file trên 1 phút)
    if not _check_rate_limit(username):
        await send_msg(writer, {"ok": False, "error": "Too many file transfers, slow down!"})
        return False

    # Nếu hợp lệ → relay metadata tới client khác
    await relay_message(username, msg)
    return True


async def handle_file_chunk(username: str, msg: dict, writer):
    """
    Xử lý từng chunk của file
    """
    payload = msg.get("payload", {})
    data_b64 = payload.get("data", "")

    # Giải mã base64 để biết chunk size thật
    try:
        raw = base64.b64decode(data_b64) # decode base64 -> binary data
    except Exception:
        await send_msg(writer, {"ok": False, "error": "Invalid file chunk encoding"})
        return False

    if len(raw) > MAX_CHUNK_SIZE: # chunk > 1.5MB
        await send_msg(writer, {"ok": False, "error": "File chunk too large (max 1.5MB)"})
        return False

    # Nếu hợp lệ → relay chunk tới client khác
    await relay_message(username, msg)
    return True

# kiểm tra tần suất 
def _check_rate_limit(username: str) -> bool:
    """
    Giới hạn số lần gửi file (metadata) để tránh spam.
    """
    now = time.time()
    history = file_rate.setdefault(username, [])

    # Xóa các lần cũ > 60s (giữ lại lần gửi trong 60s gần nhất - sliding window)
    history[:] = [t for t in history if now - t < 60]

    # Nếu quá số lần cho phép thì từ chối
    if len(history) >= RATE_LIMIT:
        return False

    # Ghi lại lần gửi này nếu Ok
    history.append(now)
    return True
