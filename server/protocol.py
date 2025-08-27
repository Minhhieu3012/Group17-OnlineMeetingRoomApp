import json, struct
import asyncio

# Gửi dict dưới dạng JSON + length prefix
async def send_msg(writer: asyncio.StreamWriter, obj: dict):
    data = json.dumps(obj).encode()
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()

# Đọc dict từ stream
async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    data = await reader.readexactly(ln)
    return json.loads(data.decode())
