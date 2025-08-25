# UDP nhanh, không đảm bảo đủ gói → chấp nhận mất vài gói, dùng cho video,voice
import asyncio
import json
import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UDPServer")

@dataclass
class ClientInfo:
    addr: Tuple[str, int]
    room: str
    last_seen: float
    packet_count: int = 0

class UDPServer:
    def __init__(self, host="0.0.0.0", port=5000, rate_limit=100, timeout=120):
        self.host = host
        self.port = port

        self.clients: Dict[str, ClientInfo] = {}
        self.rooms: Dict[str, Set[str]] = defaultdict(set)

        # Rate limiting
        self.rate_limit = rate_limit
        self.client_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=rate_limit))

        # Timeout cleanup
        self.client_timeout = timeout
        self.cleanup_interval = 30

        # Stats
        self.stats = {"rx": 0, "tx": 0, "errors": 0}

    async def start(self):
        logger.info(f"Starting UDP server on {self.host}:{self.port}")
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self), local_addr=(self.host, self.port)
        )
        self.transport = transport

        # background cleanup
        asyncio.create_task(self._cleanup_clients())
        await asyncio.Future()  # run forever

    async def process_packet(self, data: bytes, addr: Tuple[str, int]):
        self.stats["rx"] += 1
        try:
            if b"\n\n" not in data:
                return
            header_bytes, payload = data.split(b"\n\n", 1)
            header = json.loads(header_bytes.decode())
            username, room = header.get("from"), header.get("room", "default")
            if not username:
                return

            # Rate limit
            if not self._check_rate_limit(username):
                return

            # Update client
            self.clients[username] = ClientInfo(addr, room, time.time(), self.stats["rx"])
            self.rooms[room].add(username)

            # Broadcast to room
            await self._broadcast(data, room, username)

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error processing packet: {e}")

    def _check_rate_limit(self, username: str) -> bool:
        now = time.time()
        q = self.client_rates[username]
        q.append(now)
        return sum(1 for t in q if now - t < 1.0) <= self.rate_limit

    async def _broadcast(self, data: bytes, room: str, sender: str):
        for user in self.rooms.get(room, set()):
            if user == sender or user not in self.clients:
                continue
            try:
                self.transport.sendto(data, self.clients[user].addr)
                self.stats["tx"] += 1
            except Exception as e:
                logger.warning(f"Send error: {e}")

    async def _cleanup_clients(self):
        while True:
            await asyncio.sleep(self.cleanup_interval)
            now = time.time()
            inactive = [u for u, c in self.clients.items() if now - c.last_seen > self.client_timeout]
            for u in inactive:
                room = self.clients[u].room
                self.rooms[room].discard(u)
                del self.clients[u]
                logger.info(f"Removed inactive client {u}")

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, server: UDPServer):
        self.server = server

    def datagram_received(self, data, addr):
        asyncio.create_task(self.server.process_packet(data, addr))

# Run server
if __name__ == "__main__":
    try:
        asyncio.run(UDPServer().start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
