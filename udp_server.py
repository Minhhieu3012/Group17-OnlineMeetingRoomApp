# UDP nhanh, không đảm bảo đủ gói → chấp nhận mất vài gói, dùng cho video,voice
import asyncio
import json
import time
import logging
from collections import defaultdict, deque # cấu trúc dữ liệu đặc biệt
from dataclasses import dataclass, field # Tạo class dữ liệu đơn giản
from typing import Dict, Set, Tuple # Tạo hint cho code rõ ràng 

# Setup logging
# DEBUG <- INFO <- WARNING <- ERROR <- CRITICAL
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UDPServer")

# Cấu trúc dữ liệu client
@dataclass # Tự động tạo __init__, __repr__, ...
class ClientInfo:
    addr: Tuple[str, int] # (IP, port) - địa chỉ UDP endpoint 
    room: str # tên phòng chat/voice channel 
    last_seen: float # Thời gian lần cuối nhận gói
    packet_count: int = 0 # Số gói đã nhận (statistics)

# Global state management
class UDPServer:
    def __init__(self, host="0.0.0.0", port=5000, rate_limit=100, timeout=120): # rate_limit: gói/giây, timeout: giây
        # Cấu hình network
        self.host = host # Địa chỉ bind
        self.port = port

        # State storage - lưu trữ trạng thái trong memory
        self.clients: Dict[str, ClientInfo] = {} # username -> ClientInfo
        self.rooms: Dict[str, Set[str]] = defaultdict(set) # room -> set of usernames

        # Rate limiting (chống spam/DDoS)
        self.rate_limit = rate_limit # gói/giây
        self.client_rates: Dict[str, deque] = defaultdict( # username -> timestamps of received packets
            lambda: deque(maxlen=rate_limit) #  # Auto-remove old timestamps
        )

        # Timeout cleanup (xóa client không hoạt động)
        self.client_timeout = timeout
        self.cleanup_interval = 30 # giây giữa các lần dọn dẹp

        # Thống kê hiệu suất
        self.stats = {"rx": 0, "tx": 0, "errors": 0} # gói nhận, gói gửi, lỗi

    # Bắt đầu server    
    async def start(self):
        logger.info(f"Starting UDP server on {self.host}:{self.port}")

        # lấy event loop hiện tại
        loop = asyncio.get_running_loop()

        # Tạo UDP endpoint
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),  # Protocol factory function
            local_addr=(self.host, self.port) # Bind to this address
        )

        # Lưu transport để gửi gói
        self.transport = transport

        # Khởi động task dọn dẹp client không hoạt động
        asyncio.create_task(self._cleanup_clients())

        # Giữ server chạy mãi
        await asyncio.Future()  

    # Xử lý gói nhận được
    async def process_packet(self, data: bytes, addr: Tuple[str, int]):
        self.stats["rx"] += 1 # Tăng bộ đếm gói nhận

        try:
            # step1: Validate packet format
            if b"\n\n" not in data: # Check for header/payload separator
                return # Silent drop - Invalid packet format
            
            # step2: Split header and payload
            header_bytes, payload = data.split(b"\n\n", 1) # Split on first "\n\n"

            # step3: Parse JSON header
            header = json.loads(header_bytes.decode()) # Decode bytes to str and parse JSON

            # step4: Extract required fields
            username, room = header.get("from"), # sender username
            header.get("room", "default") # target room (optional, default="default")

            if not username: # Anonymous packets not allowed
                return # Silent drop 

            # step5: Rate limiting check
            if not self._check_rate_limit(username): # Too many packets per second
                return # Silent drop (no error response)

            # step6: Update client state
            self.clients[username] = ClientInfo(
                addr=addr, # update client udp endpoint
                room=room, # update current room
                last_seen=time.time(), # update activity timestamp
                packet_count=self.stats["rx"] # update packet counter
            )

            # step7: Add client to room
            self.rooms[room].add(username) # Add user to room set

            # step8: Broadcast payload to other clients in the same room
            await self._broadcast(data, room, username) # Forward packet to others
            # Silent drop (no error response to avoid amplification attacks)

        except json.JSONDecodeError: # Malformed JSON in header
            self.stats["errors"] += 1 # Increment error counter
            # Silent drop (no error response to avoid amplification attacks)

        except Exception as e: # Any other unexpected error
            self.stats["errors"] += 1
            logger.error(f"Error processing packet: {e}")

    # Rate limiting - sliding window algorithm
    def _check_rate_limit(self, username: str) -> bool:
        now = time.time() # current timestamp

        q = self.client_rates[username] # get user's timestamp queue
        q.append(now) # add current timestamp

        # Count recent packets within 1 second window
        recent_count=sum(
            1 for t in q # Iterate through timestamps
            if now - t < 1.0 # only count packets within last 1 second
        )

        return recent_count <= self.rate_limit # Allow if under limit

    # Broadcast packet to all clients in the same room except sender
    async def _broadcast(self, data: bytes, room: str, sender: str):

        # get all room members:
        room_members = self.rooms.get(room, set()) # Get room's user set (empty if room doesn't exist)

        for user in room_members: # Iterate over users in the room
            if user == sender or user not in self.clients: # Skip sender and offline clients
                continue # Do not send to self
            try:
                # get client udp endpoint
                client_addr = self.clients[user].addr # Get client's (IP, port)

                # send packet directly via UDP
                self.transport.sendto(data, client_addr) # non-blocking udp send
                self.stats["tx"] += 1 # Increment transmit counter

            except Exception as e: # network error
                logger.warning(f"Send error: {e}") # Log warning but continue
                # Don't remove client here - cleanup task will handle timeouts

    # Cleanup task to remove inactive clients
    async def _cleanup_clients(self):
        while True:
            await asyncio.sleep(self.cleanup_interval) # Wait before next cleanup
            
            now = time.time() # current timestamp

            # find inactive clients using list comprehension
            inactive = [
                username # username of inactive client
                for username, client in self.clients.items() # iterate all clients
                if now - client.last_seen > self.client_timeout # check if timeout exceeded
            ]

            # remove inactive clients
            for username in inactive: # iterate inactive clients
                room = self.clients[username].room # get user's current room
                self.rooms[room].discard(username) # remove user from room
                del self.clients[username] # delete client record
                logger.info(f"Removed inactive client {username}") # Log cleanup action

# UDP Protocol handler
class UDPProtocol(asyncio.DatagramProtocol): # inherits from asyncio's udp protocol
    def __init__(self, server: UDPServer): # constructor takes server reference
        self.server = server # Reference to main server

    def datagram_received(self, data, addr): # callback when packet arrives
        # create async task to process packet
        asyncio.create_task(self.server.process_packet(data, addr))

# Run server
if __name__ == "__main__":
    try:
        asyncio.run(UDPServer().start())
    except KeyboardInterrupt: # Graceful shutdown on Ctrl+C
        logger.info("Server stopped by user")
