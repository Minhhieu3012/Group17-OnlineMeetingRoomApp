import asyncio
import json 
import struct 

clients={} # dict để lưu trữ thông tin client

async def send_msg(writer, data: dict):
    raw=json.dumps(data).encode('utf-8') 
    writer.write(struct.pack('!I',len(raw))+raw) # gửi tiền tố độ dài và dữ liệu
    await writer.drain() # đảm bảo dữ liệu được gửi

async def read_msg(reader):
    header=await reader.readexactly(4) # đọc tiền tố độ dài
    (ln,)=struct.unpack("!I",header) # giải nén độ dài
    raw=await reader.readexactly(ln) # đọc dữ liệu
    return json.loads(raw.decode('utf-8')) # giải mã JSON và trả về dict