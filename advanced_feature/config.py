from __future__ import annotations

# Server connection settings
SERVER_HOST: str = "127.0.0.1"

# Ports for different services
TCP_PORT_CHAT: int = 8401
TCP_PORT_FILE: int = 8501
UDP_PORT_VOICE: int = 8601
UDP_PORT_VIDEO: int = 8701

# File transfer settings
FILE_CHUNK_SIZE_BYTES: int = 64 * 1024  # 64 KiB
FILE_MAX_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MiB safety cap client-side
FILE_RATE_LIMIT_BPS: int | None = 8 * 1024 * 1024  # 8 Mbps; set None to disable

# Voice settings
VOICE_SAMPLE_RATE: int = 16000
VOICE_CHANNELS: int = 1
VOICE_FRAMES_PER_BUFFER: int = 1024
VOICE_SAMPLE_WIDTH_BYTES: int = 2  # 16-bit
VOICE_RATE_LIMIT_BPS: int | None = 256 * 1024  # 256 Kbps; None to disable

# Video settings
VIDEO_WIDTH: int = 640
VIDEO_HEIGHT: int = 480
VIDEO_FPS: int = 15
VIDEO_JPEG_QUALITY: int = 60  # 0-100
VIDEO_RATE_LIMIT_BPS: int | None = 2 * 1024 * 1024  # 2 Mbps; None to disable

# UDP fragmentation
UDP_MAX_PAYLOAD: int = 1200  # conservative for typical MTU

# Simple protocol constants
MAGIC_VIDEO: bytes = b"VD"
MAGIC_VOICE: bytes = b"AU"


