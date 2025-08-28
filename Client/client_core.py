# filename: client_core.py
from __future__ import annotations
import asyncio, json, struct, base64, os, time, uuid
from pathlib import Path
from typing import Callable, Optional, Dict, Any

FRAME_LEN = 4
CHUNK_SIZE = 32 * 1024
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ---------------- Frame helpers ----------------
async def read_exactly(reader: asyncio.StreamReader, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = await reader.read(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        data += chunk
    return data

async def recv_frame(reader: asyncio.StreamReader) -> Dict[str, Any]:
    hdr = await read_exactly(reader, FRAME_LEN)
    (length,) = struct.unpack(">I", hdr)
    payload = await read_exactly(reader, length)
    return json.loads(payload.decode("utf-8"))

async def send_frame(writer: asyncio.StreamWriter, obj: Dict[str, Any]):
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    writer.write(struct.pack(">I", len(data)))
    writer.write(data)
    await writer.drain()

# ---------------- Client ----------------
class ChatClient:
    """Async TCP client implementing the JSON protocol (no DB server).
    Provide on_event(event: dict) to receive pushes and local status events.
    """
    def __init__(self, host: str, port: int, on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
                 aes=None):
        self.host, self.port = host, port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.on_event = on_event or (lambda e: None)
        self.username: Optional[str] = None
        self.room_code: Optional[str] = None
        self.connected = False
        self.aes = aes  # optional crypto helper with encrypt/decrypt

    # ---- lifecycle ----
    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self.connected = True
        self.on_event({"type":"local","event":"connected"})
        asyncio.create_task(self._listen_loop())

    async def close(self):
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.connected = False
        self.on_event({"type":"local","event":"disconnected"})

    async def _listen_loop(self):
        try:
            while True:
                msg = await recv_frame(self.reader)
                if self.aes and isinstance(msg, dict) and msg.get("enc"):
                    msg = self.aes.decrypt_message(msg)
                self.on_event(msg)
        except Exception as e:
            self.on_event({"type":"error","error":str(e)})
            await self.close()

    # ---- commands ----
    async def login(self, username: str, gmail: str):
        self.username = username
        msg = {"type":"auth","action":"login","username":username,"gmail":gmail}
        await self._send(msg)

    async def list_rooms(self):
        await self._send({"type":"room","action":"list"})

    async def create_room(self, room_name: str, password: str = ""):
        await self._send({"type":"room","action":"create","room_name":room_name,"password":password})

    async def join_by_code(self, room_code: str, password: str = ""):
        self.room_code = room_code
        await self._send({"type":"room","action":"join","room_code":room_code,"password":password})

    async def leave_room(self):
        await self._send({"type":"room","action":"leave"})
        self.room_code = None

    async def list_users(self, room_code: Optional[str] = None):
        rc = room_code or self.room_code
        if rc:
            await self._send({"type":"users","action":"list","room_code":rc})

    async def send_chat(self, text: str, room_code: Optional[str] = None):
        rc = room_code or self.room_code
        if not rc:
            raise ValueError("Not in a room")
        await self._send({"type":"chat","action":"send","room_code":rc,"text":text})

    async def send_dm(self, to_user: str, text: str):
        await self._send({"type":"dm","action":"send","to":to_user,"text":text})

    async def send_file(self, filepath: str, room_code: Optional[str] = None):
        rc = room_code or self.room_code
        if not rc:
            raise ValueError("Not in a room")
        p = Path(filepath)
        size = p.stat().st_size
        transfer_id = str(uuid.uuid4())
        await self._send({"type":"file","action":"meta","room_code":rc,
                          "filename":p.name,"size":size,"transfer_id":transfer_id})
        seq = 0
        sent = 0
        with p.open("rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                b64 = base64.b64encode(chunk).decode("ascii")
                await self._send({"type":"file","action":"chunk","transfer_id":transfer_id,
                                  "seq":seq,"data":b64})
                seq += 1
                sent += len(chunk)
                self.on_event({"type":"local","event":"file_progress","sent":sent,"total":size,
                               "filename":p.name})
        await self._send({"type":"file","action":"complete","transfer_id":transfer_id})

    async def _send(self, obj: Dict[str, Any]):
        if self.aes:
            obj = self.aes.encrypt_message(obj)
        await send_frame(self.writer, obj)

# ---------------- File receive helper ----------------
class FileAssembler:
    def __init__(self):
        self.buffers: Dict[str, Dict[str, Any]] = {}

    def handle(self, msg: Dict[str, Any]):
        if msg.get("type") != "file":
            return None
        action = msg.get("action")
        tid = msg.get("transfer_id")
        if action == "meta":
            self.buffers[tid] = {
                "filename": msg["filename"],
                "size": msg["size"],
                "chunks": {},
                "received": 0,
            }
        elif action == "chunk" and tid in self.buffers:
            data = base64.b64decode(msg["data"])  # may raise if corrupted
            self.buffers[tid]["chunks"][msg["seq"]] = data
            self.buffers[tid]["received"] += len(data)
        elif action == "complete" and tid in self.buffers:
            info = self.buffers.pop(tid)
            out = DOWNLOAD_DIR / info["filename"]
            with out.open("wb") as f:
                for i in range(0, len(info["chunks"])):
                    f.write(info["chunks"][i])
            return out
        return None
