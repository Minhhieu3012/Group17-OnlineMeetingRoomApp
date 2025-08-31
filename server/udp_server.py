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

# Global state management
class UDPServer:
    def __init__(self, host="0.0.0.0", port=6000, rate_limit=100, timeout=120):
        self.host = host
        self.port = port

        # State storage
        self.clients: Dict[str, ClientInfo] = {}
        self.rooms: Dict[str, Set[str]] = defaultdict(set)

        # Rate limiting
        self.rate_limit = rate_limit
        self.client_rates: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=rate_limit)
        )

        # Timeout cleanup
        self.client_timeout = timeout
        self.cleanup_interval = 30

        # Statistics
        self.stats = {"rx": 0, "tx": 0, "errors": 0}

    async def start(self):
        logger.info(f"Starting UDP server on {self.host}:{self.port}")

        loop = asyncio.get_running_loop()

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=(self.host, self.port)
        )

        self.transport = transport

        # Khởi động task dọn dẹp
        asyncio.create_task(self._cleanup_clients())

        # Giữ server chạy
        await asyncio.Future()

    async def process_packet(self, data: bytes, addr: Tuple[str, int]):
        self.stats["rx"] += 1

        try:
            if b"\n\n" not in data:
                return

            header_bytes, payload = data.split(b"\n\n", 1)
            header = json.loads(header_bytes.decode())

            username = header.get("from")
            room = header.get("room", "default")

            if not username:
                return

            if not self._check_rate_limit(username):
                return

            self.clients[username] = ClientInfo(
                addr=addr,
                room=room,
                last_seen=time.time(),
                packet_count=self.clients.get(username, ClientInfo(addr, room, time.time())).packet_count + 1
            )

            self.rooms[room].add(username)

            await self._broadcast(data, room, username)

        except json.JSONDecodeError:
            self.stats["errors"] += 1

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error processing packet: {e}")

    def _check_rate_limit(self, username: str) -> bool:
        now = time.time()
        q = self.client_rates[username]
        q.append(now)

        recent_count = sum(
            1 for t in q
            if now - t < 1.0
        )

        return recent_count <= self.rate_limit

    async def _broadcast(self, data: bytes, room: str, sender: str):
        room_members = self.rooms.get(room, set())

        for user in room_members:
            if user == sender or user not in self.clients:
                continue
            try:
                client_addr = self.clients[user].addr
                self.transport.sendto(data, client_addr)
                self.stats["tx"] += 1

            except Exception as e:
                logger.warning(f"Send error: {e}")

    async def _cleanup_clients(self):
        while True:
            await asyncio.sleep(self.cleanup_interval)
            
            now = time.time()

            inactive = [
                username
                for username, client in self.clients.items()
                if now - client.last_seen > self.client_timeout
            ]

            for username in inactive:
                room = self.clients[username].room
                self.rooms[room].discard(username)
                del self.clients[username]
                logger.info(f"Removed inactive client {username}")

# UDP Protocol handler
class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, server: UDPServer):
        self.server = server

    def datagram_received(self, data, addr):
        asyncio.create_task(self.server.process_packet(data, addr))
