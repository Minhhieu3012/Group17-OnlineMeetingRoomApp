# Hệ thống giao tiếp mạng với mã hóa AES - GCM
"""json: serialize/deserialize dữ liệu, struct: đóng gói binary data (length prefix)"""
import json, struct, asyncio
from typing import Optional
from utils import aes_encrypt, aes_decrypt, CRYPTO_AVAILABLE # CRYPTO_AVAILABLE: Flag kiểm tra thư viện crypto có sẵn không 


# Thuần văn bản (JSON + length prefix) không mã hóa 
async def send_msg(writer: asyncio.StreamWriter, obj: dict):
    data = json.dumps(obj).encode() # convert dict -> json string -> bytes (b'')
    writer.write(struct.pack("!I", len(data)) + data) # đóng gói length thành 4 bytes big-endian
    await writer.drain() # đảm bảo dữ liệu đc gửi đi 

async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header) # giải mã 4 bytes -> số nguyên length
    data = await reader.readexactly(ln) # json data
    return json.loads(data.decode()) # bytes -> string -> dict object

# Mã hóa AES-GCM ở tầng message (sau login) 
# Gửi msg có mã hóa 
async def send_msg_secure(writer: asyncio.StreamWriter, obj: dict, key: bytes):
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("send_msg_secure: 'cryptography' chưa được cài")
    plaintext = json.dumps(obj).encode() # dict -> json bytes (plaintext)
    blob = aes_encrypt(plaintext, key) # trả về encrypted blob (chứa nonce + ciphertext + tag)
    writer.write(struct.pack("!I", len(blob)) + blob) # gửi [4 bytes length][encrypted blob]
    await writer.drain()

# Đọc msg có mã hóa 
async def read_msg_secure(reader: asyncio.StreamReader, key: bytes):
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("read_msg_secure: 'cryptography' chưa được cài")
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    blob = await reader.readexactly(ln)
    plaintext = aes_decrypt(blob, key) # giải mã AES-CGM -> plaintext 
    return json.loads(plaintext.decode()) # plaintext -> json object 

# Helper function: đọc theo trạng thái (có key => secure)
# Đọc linh hoạt 
async def read_any(reader, key: Optional[bytes]):
    if key:
        return await read_msg_secure(reader, key) # có key dùng chế độ mã hóa
    return await read_msg(reader) # không có key dùng chế độ plaintext

# Gửi linh hoạt 
async def send_any(writer, obj: dict, key: Optional[bytes]):
    if key:
        return await send_msg_secure(writer, obj, key)
    return await send_msg(writer, obj)
