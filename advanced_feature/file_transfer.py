# file_transfer.py
import os
import json
import struct
import asyncio
from typing import Dict

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

        # Hỗ trợ nhiều file nhận cùng lúc: key = filename -> dict(state)
        # state: {"fileobj": file_handle, "expected": int, "received": int, "path": str}
        self._recv_states: Dict[str, dict] = {}

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
                print(f"[File] Đã gửi {len(chunk)} bytes -> {filename}")

        # 3. Gửi thông báo kết thúc file (receiver biết để show "done")
        end_msg = {
            "type": "file_end",
            "from": self.username,
            "to": to,
            "payload": {"filename": filename, "size": size},
        }
        await send_msg(self.writer, end_msg)
        print(f"[File] Đã gửi xong {filename} (đã gửi file_end)")

    async def handle_incoming(self, msg: dict, download_dir="downloads"):
        """Xử lý gói file_meta/file_chunk/file_end nhận được từ server."""
        t = msg.get("type")
        p = msg.get("payload", {}) or {}
        sender = msg.get("from")

        os.makedirs(download_dir, exist_ok=True)

        if t == "file_meta":
            filename = p["filename"]
            size = p.get("size", 0)
            path = os.path.join(download_dir, filename)
            # Nếu đã có trạng thái cùng filename, reset (overwrite)
            if filename in self._recv_states:
                # close previous if still open
                st = self._recv_states[filename]
                fh = st.get("fileobj")
                if fh and not fh.closed:
                    fh.close()

            fh = open(path, "wb")
            self._recv_states[filename] = {
                "fileobj": fh,
                "expected": size,
                "received": 0,
                "path": path,
                "from": sender
            }
            print(f"[File] Nhận metadata từ {sender}: {filename} ({size} bytes) -> lưu tại {path}")

        elif t == "file_chunk":
            filename = p["filename"]
            data_hex = p.get("data")
            if data_hex is None:
                print("[File] Warning: chunk thiếu payload data")
                return
            data = bytes.fromhex(data_hex)

            st = self._recv_states.get(filename)
            if st and st["fileobj"] and not st["fileobj"].closed:
                st["fileobj"].write(data)
                st["received"] += len(data)
                print(f"[File] Đang nhận {filename}: {st['received']}/{st['expected']} bytes")
            else:
                # Khoảng hợp: chưa nhận metadata nhưng vẫn nhận chunk -> tạo file tạm
                path = os.path.join(download_dir, filename)
                fh = open(path, "ab")
                fh.write(data)
                fh.close()
                # tạo state ghi nhận nhưng expected unknown (0)
                self._recv_states[filename] = {
                    "fileobj": None,
                    "expected": 0,
                    "received": len(data),
                    "path": path,
                    "from": sender
                }
                print(f"[File] Nhận chunk cho {filename} nhưng chưa có metadata. Ghi tạm {len(data)} bytes -> {path}")

        elif t == "file_end":
            filename = p["filename"]
            st = self._recv_states.get(filename)
            if st:
                fh = st.get("fileobj")
                if fh and not fh.closed:
                    fh.close()
                received = st.get("received", 0)
                path = st.get("path")
                expected = st.get("expected", 0)
                # nếu expected==0 có thể không có metadata trước đó
                print(f"[File] Đã hoàn tất nhận file {filename}: {received} bytes (expected={expected}) -> {path}")
                # reset state
                del self._recv_states[filename]
            else:
                # không có state, có thể đã ghi tạm khi nhận chunk trước
                path = os.path.join(download_dir, filename)
                print(f"[File] Nhận file_end cho {filename}, lưu ở {path} (không có state trước đó)")

        else:
            # không phải file message — có thể là chat text hoặc loại khác
            # nếu muốn xử lý chat tại đây, có thể thêm logic
            print(f"[Msg] Nhận message type={t} from={sender}")
