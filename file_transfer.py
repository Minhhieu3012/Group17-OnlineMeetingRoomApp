import os
import json
import struct
import asyncio

CHUNK_SIZE = 64 * 1024   # 64KB mỗi chunk

# ===============================
# Helper để gửi/nhận JSON message
# ===============================
async def send_msg(writer: asyncio.StreamWriter, obj: dict):
    data = json.dumps(obj).encode()
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()

async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    data = await reader.readexactly(ln)
    return json.loads(data.decode())

# ===============================
# File Transfer Client
# ===============================
class FileTransferClient:
    def __init__(self, username: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.username = username
        self.reader = reader
        self.writer = writer

    async def send_file(self, path: str, to: str = None):
        """Gửi file tới 1 user hoặc cả room nếu `to=None`."""
        if not os.path.exists(path):
            print(f"[File] Không tìm thấy file: {path}")
            return

        size = os.path.getsize(path)
        if size > 20_000_000:  # 20MB limit
            print(f"[File] File quá lớn ({size} bytes > 20MB)")
            return

        filename = os.path.basename(path)

        # 1. Gửi metadata
        meta = {
            "type": "file_meta",
            "from": self.username,
            "to": to,
            "payload": {"filename": filename, "size": size},
        }
        await send_msg(self.writer, meta)
        print(f"[File] Bắt đầu gửi file {filename} ({size} bytes)")

        # 2. Gửi từng chunk
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                msg = {
                    "type": "file_chunk",
                    "from": self.username,
                    "to": to,
                    "payload": {"filename": filename, "data": chunk.hex()},
                }
                await send_msg(self.writer, msg)

        print(f"[File] Đã gửi xong {filename}")

    async def handle_incoming(self, msg: dict, download_dir="downloads"):
        """Xử lý gói file_meta/file_chunk nhận được từ server."""
        t = msg.get("type")
        p = msg.get("payload", {})
        sender = msg.get("from")

        os.makedirs(download_dir, exist_ok=True)

        if t == "file_meta":
            filename = p["filename"]
            size = p["size"]
            path = os.path.join(download_dir, filename)
            print(f"[File] Nhận metadata từ {sender}: {filename} ({size} bytes)")
            # mở file mới để ghi (overwrite nếu đã tồn tại)
            self._file = open(path, "wb")

        elif t == "file_chunk":
            filename = p["filename"]
            data = bytes.fromhex(p["data"])
            if hasattr(self, "_file") and not self._file.closed:
                self._file.write(data)
            else:
                print(f"[File] Cảnh báo: nhận chunk nhưng chưa mở file {filename}")

        # Đóng file khi đủ size (option: bạn có thể kiểm tra đủ bytes theo metadata)
        # Để đơn giản mình đóng luôn sau mỗi file transfer
        if t == "file_chunk" and len(data) < CHUNK_SIZE:
            if hasattr(self, "_file") and not self._file.closed:
                self._file.close()
                print(f"[File] Đã lưu file {self._file.name}")
