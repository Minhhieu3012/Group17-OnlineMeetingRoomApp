"""
Config cho SERVER – chạy trên máy chủ (main.py).
Server sẽ lắng nghe trên tất cả địa chỉ mạng (0.0.0.0).
"""

# Server host: lắng nghe trên mọi IP
SERVER_HOST = "0.0.0.0"
TCP_PORT = 8888

# UDP media ports
UDP_PORT_VOICE = 9999
UDP_PORT_VIDEO = 10000

# Backward compat (nếu code cũ gọi UDP_PORT)
UDP_PORT = UDP_PORT_VOICE

# WebSocket Gateway
GATEWAY_PORT = 8765
WS_PORT = GATEWAY_PORT

APP_NAME = "HPH Meeting – Server"
