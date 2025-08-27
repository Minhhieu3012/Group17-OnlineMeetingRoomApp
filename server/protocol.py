# protocol.py
import json, struct, asyncio
from typing import Optional
from utils import aes_encrypt, aes_decrypt, CRYPTO_AVAILABLE

# ----- Thuần văn bản (JSON + length prefix) -----
async def send_msg(writer: asyncio.StreamWriter, obj: dict):
    data = json.dumps(obj).encode()
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()

async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    data = await reader.readexactly(ln)
    return json.loads(data.decode())

# ----- Mã hóa AES-GCM ở tầng message (sau login) -----
async def send_msg_secure(writer: asyncio.StreamWriter, obj: dict, key: bytes):
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("send_msg_secure: 'cryptography' chưa được cài")
    plaintext = json.dumps(obj).encode()
    blob = aes_encrypt(plaintext, key)  # bytes
    writer.write(struct.pack("!I", len(blob)) + blob)
    await writer.drain()

async def read_msg_secure(reader: asyncio.StreamReader, key: bytes):
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("read_msg_secure: 'cryptography' chưa được cài")
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    blob = await reader.readexactly(ln)
    plaintext = aes_decrypt(blob, key)
    return json.loads(plaintext.decode())

# Helper: đọc theo trạng thái (có key => secure)
async def read_any(reader, key: Optional[bytes]):
    if key:
        return await read_msg_secure(reader, key)
    return await read_msg(reader)

async def send_any(writer, obj: dict, key: Optional[bytes]):
    if key:
        return await send_msg_secure(writer, obj, key)
    return await send_msg(writer, obj)
