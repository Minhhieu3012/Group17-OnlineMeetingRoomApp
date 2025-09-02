import asyncio
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple, Set

from advanced_feature import config_client

MAGIC = b"HPH1"  # 4 bytes
# Header: magic(4s) type(B) room_len(H) user_len(H) seq(I)
HDR_FMT = "!4sBHHI"
HDR_SIZE = struct.calcsize(HDR_FMT)

# Message types
MSG_VOICE = 1
MSG_VIDEO = 2
MSG_JOIN = 10
MSG_LEAVE = 11
MSG_KEEPALIVE = 12

Address = Tuple[str, int]


@dataclass
class RoomState:
    users: Dict[Address, str] = field(default_factory=dict)  # addr -> username
    last_seen: Dict[Address, float] = field(default_factory=dict)


class _UDPWorker:
    def __init__(self, host: str, port: int, media_type: int) -> None:
        self.host = host
        self.port = port
        self.media_type = media_type
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.rooms: Dict[str, RoomState] = {}
        self._alive = False
        self._thread: threading.Thread | None = None

    @property
    def media_name(self) -> str:
        return "VOICE" if self.media_type == MSG_VOICE else "VIDEO"

    def start(self) -> None:
        self._alive = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        print(f"[UDP] {self.media_name} server listening on {self.host}:{self.port}")

    def stop(self) -> None:
        self._alive = False
        try:
            self.sock.close()
        except Exception:
            pass

    def _parse_packet(self, data: bytes):
        if len(data) < HDR_SIZE:
            return None
        magic, mtype, room_len, user_len, seq = struct.unpack(HDR_FMT, data[:HDR_SIZE])
        if magic != MAGIC:
            return None
        off = HDR_SIZE
        try:
            room = data[off:off + room_len].decode("utf-8"); off += room_len
            user = data[off:off + user_len].decode("utf-8"); off += user_len
        except Exception:
            return None
        payload = data[off:]
        return mtype, room, user, seq, payload

    def _broadcast(self, room: str, payload: bytes, exclude: Address | None = None) -> None:
        state = self.rooms.get(room)
        if not state:
            return
        for addr in list(state.users.keys()):
            if exclude and addr == exclude:
                continue
            try:
                self.sock.sendto(payload, addr)
            except Exception:
                pass

    def _serve(self) -> None:
        self.sock.settimeout(1.0)
        while self._alive:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                self._gc()
                continue
            except OSError:
                break

            parsed = self._parse_packet(data)
            if not parsed:
                continue
            mtype, room, user, seq, payload = parsed

            rs = self.rooms.setdefault(room, RoomState())
            rs.last_seen[addr] = time.time()

            if mtype in (MSG_JOIN, MSG_KEEPALIVE):
                rs.users[addr] = user
                continue
            if mtype == MSG_LEAVE:
                rs.users.pop(addr, None)
                rs.last_seen.pop(addr, None)
                continue

            if mtype in (MSG_VOICE, MSG_VIDEO):
                # forward to peers in same room (except sender)
                self._broadcast(room, data, exclude=addr)

    def _gc(self) -> None:
        now = time.time()
        for room, rs in list(self.rooms.items()):
            dead: Set[Address] = set()
            for addr, ts in list(rs.last_seen.items()):
                if now - ts > 20:
                    dead.add(addr)
            for addr in dead:
                rs.users.pop(addr, None)
                rs.last_seen.pop(addr, None)
            if not rs.users:
                self.rooms.pop(room, None)


class UDPServer:
    """Run two UDP workers: one for VOICE, one for VIDEO.

    Backwards-compat params:
      - Some code instantiates UDPServer(host=..., port=PORT). We accept `port` and
        map it to voice port if explicit voice_port not given.
    """

    def __init__(self, host: str | None = None,
                 port: int | None = None,
                 voice_port: int | None = None,
                 video_port: int | None = None) -> None:
        host = host or getattr(config_client, "SERVER_HOST", "0.0.0.0")
        # derive ports
        if voice_port is None:
            voice_port = port if port is not None else getattr(config_client, "UDP_PORT_VOICE", 9999)
        if video_port is None:
            video_port = getattr(config_client, "UDP_PORT_VIDEO", 10000)
        self.voice = _UDPWorker(host, int(voice_port), MSG_VOICE)
        self.video = _UDPWorker(host, int(video_port), MSG_VIDEO)

    async def start(self) -> None:
        """Start workers and keep running until cancelled. Compatible with `await udp.start()`.
        """
        self.voice.start()
        self.video.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.stop()

    def stop(self) -> None:
        self.voice.stop()
        self.video.stop()


if __name__ == "__main__":
    # Standalone run for quick test (blocking threads under the hood)
    srv = UDPServer()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(srv.start())
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        loop.stop()
        loop.close()
