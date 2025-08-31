from __future__ import annotations

# Server connection settings
SERVER_HOST: str = "127.0.0.1"

# Ports for different services - updated to match new system
TCP_PORT: int = 8888  # Main TCP server port
UDP_PORT: int = 6000  # UDP server port for voice/video
GATEWAY_PORT: int = 8080  # WebSocket gateway port

# Legacy ports for compatibility
TCP_PORT_CHAT: int = 8401
TCP_PORT_FILE: int = 8501
UDP_PORT_VOICE: int = 8601
UDP_PORT_VIDEO: int = 8701

# File transfer settings
FILE_CHUNK_SIZE_BYTES: int = 64 * 1024  # 64 KiB
FILE_MAX_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB (updated to match new system)
FILE_RATE_LIMIT_BPS: int | None = 8 * 1024 * 1024  # 8 Mbps

# Voice settings
VOICE_SAMPLE_RATE: int = 16000
VOICE_CHANNELS: int = 1
VOICE_FRAMES_PER_BUFFER: int = 1024
VOICE_SAMPLE_WIDTH_BYTES: int = 2  # 16-bit
VOICE_RATE_LIMIT_BPS: int | None = 256 * 1024  # 256 Kbps

# Video settings
VIDEO_WIDTH: int = 640
VIDEO_HEIGHT: int = 480
VIDEO_FPS: int = 15
VIDEO_JPEG_QUALITY: int = 60  # 0-100
VIDEO_RATE_LIMIT_BPS: int | None = 2 * 1024 * 1024  # 2 Mbps

# UDP fragmentation
UDP_MAX_PAYLOAD: int = 1200  # conservative for typical MTU

# Protocol constants
MAGIC_VIDEO: bytes = b"VD"
MAGIC_VOICE: bytes = b"AU"

MAX_CHUNK_SIZE = 1_500_000  # 1.5MB for file chunks
RATE_LIMIT = 5  # files per minute per user
CLIENT_TIMEOUT = 120  # seconds
CLEANUP_INTERVAL = 30  # seconds
